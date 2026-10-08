"""Isolated, exact-SHA developer checkpoint. No production export integration."""

import argparse
import atexit
import json
import os
import shutil
import signal
import subprocess
import time
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / "tools/acceptance/customer-briefing/compose.html-pdf.yml"


def publish_checkpoint(staging: Path, destination: Path, evidence: bytes) -> None:
    raw = json.loads(evidence)
    report = raw["render"]
    if (
        report["status"] != "success"
        or not report["cleanup"]["success"]
        or not report["pdfValidation"]["verified"]
        or report["pdfValidation"]["pageCount"] != 1
    ):
        raise ValueError("Unqualified publication")
    artifacts = report["artifacts"]
    if set(artifacts) != {"htmlPath", "pngPath", "pdfPath"}:
        raise ValueError("Incomplete artifact pair")
    for key, name in artifacts.items():
        if (
            Path(name).name != name
            or Path(name).is_absolute()
            or (staging / name).is_symlink()
        ):
            raise ValueError("Artifact escapes request directory")
        if (
            sha256((staging / name).read_bytes()).hexdigest()
            != report["artifactHashes"][key]
        ):
            raise ValueError("Artifact hash mismatch")
    if (
        destination.exists()
        or staging.stat().st_dev != destination.parent.stat().st_dev
    ):
        raise ValueError("Publication destination/filesystem mismatch")
    # Retain only the validated four-file set in each delivered directory.
    for file in staging.iterdir():
        if file.name not in artifacts.values():
            if file.is_dir():
                shutil.rmtree(file)
            else:
                file.unlink()
    (staging / "mission-customer-briefing-evidence.json").write_bytes(evidence)
    staging.rename(destination)


def publish_after_cleanup(owner, staging: Path, destination: Path) -> dict:
    cleanup = owner.close()
    if (
        not cleanup.get("children_reaped")
        or not cleanup.get("compose_removed")
        or any(cleanup.get("remaining", {}).values())
    ):
        raise RuntimeError("Owned runtime cleanup did not qualify publication")
    staging.rename(destination)
    return cleanup


class CheckpointOwner:
    def __init__(self, project, evidence_root, command=None):
        self.project = project
        self.root = Path(evidence_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.cancelled = False
        self.child = None
        self.closed = False
        self.compose_env = None
        self.ownership = {
            "pid": os.getpid(),
            "pgid": os.getpgrp(),
            "compose": project,
            "composeFile": str(COMPOSE),
            "volumes": [project + "_evidence"],
            "temporaryPaths": [],
            "commands": [],
            "cleanup": {},
        }
        self.command = command or self.execute
        self.persist()

    def persist(self):
        (self.root / "ownership.json").write_text(json.dumps(self.ownership, indent=2))

    def execute(self, args, timeout=600, env=None):
        self.ownership["commands"].append({"command": args, "startedAt": time.time()})
        self.persist()
        log = self.root / f"command-{len(self.ownership['commands']):02d}.log"
        with log.open("w") as output:
            self.child = subprocess.Popen(
                args,
                cwd=ROOT,
                env=env,
                start_new_session=True,
                stdout=output,
                stderr=subprocess.STDOUT,
            )
            self.ownership["commands"][-1].update(
                pid=self.child.pid, pgid=self.child.pid
            )
            self.persist()
            try:
                code = self.child.wait(timeout=timeout)
                if code:
                    raise RuntimeError(f"Command failed ({code}); see {log}")
            except BaseException:
                self.stop_child()
                raise
            finally:
                self.ownership["commands"][-1]["returncode"] = self.child.returncode
                self.child = None
                self.persist()
        return log.read_text()

    def stop_child(self):
        if self.child is not None and self.child.poll() is None:
            os.killpg(self.child.pid, signal.SIGTERM)
            try:
                self.child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(self.child.pid, signal.SIGKILL)
                self.child.wait(timeout=10)

    def signal(self, signum, frame):
        self.cancelled = True
        self.stop_child()

    def close(self):
        if self.closed:
            return self.ownership["cleanup"]
        self.stop_child()
        self.command(
            [
                "docker",
                "compose",
                "-p",
                self.project,
                "-f",
                str(COMPOSE),
                "down",
                "--volumes",
                "--remove-orphans",
            ],
            timeout=60,
            env=self.compose_env,
        )
        remaining = {}
        for resource, args in {
            "containers": ["docker", "ps", "-aq"],
            "networks": ["docker", "network", "ls", "-q"],
            "volumes": ["docker", "volume", "ls", "-q"],
        }.items():
            remaining[resource] = self.command(
                [*args, "--filter", f"label=com.docker.compose.project={self.project}"],
                timeout=30,
            ).strip()
        cleanup = {
            "children_reaped": self.child is None,
            "compose_removed": not any(remaining.values()),
            "remaining": remaining,
        }
        self.ownership["cleanup"] = cleanup
        self.closed = True
        self.persist()
        if not cleanup["compose_removed"]:
            raise RuntimeError("Owned Docker resources remain")
        return cleanup


def run_checkpoint(
    candidate_sha: str,
    evidence_root: Path,
    runtime_tests: bool = False,
    image_tag=None,
    build_only=False,
):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

    if candidate_sha != git("rev-parse", "HEAD") or git("status", "--porcelain"):
        raise ValueError("Checkpoint requires clean committed HEAD")
    run_id = str(time.time_ns())
    project = f"briefing-html-pdf-{candidate_sha[:12]}-{run_id}"
    root = Path(evidence_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    image = (
        image_tag
        or f"starlink-dashboard-briefing-html-pdf:{candidate_sha[:12]}-{run_id}"
    )
    owner = CheckpointOwner(project, root)
    env = {
        **os.environ,
        "CHECKPOINT_IMAGE": image,
        "CHECKPOINT_RUNTIME_TESTS": "1" if runtime_tests else "0",
    }
    owner.compose_env = env
    started_container = False
    previous = {
        s: signal.signal(s, owner.signal) for s in (signal.SIGTERM, signal.SIGINT)
    }
    atexit.register(owner.close)
    summary = {
        "candidateSha": candidate_sha,
        "project": project,
        "imageTag": image,
        "checksPassed": False,
        "visualAcceptance": "pending",
        "scanTest": "pending",
        "publication": None,
    }
    try:
        if image_tag is None:
            build = [
                "timeout",
                "--kill-after=10s",
                "45m",
                "docker",
                "build",
                "-f",
                "tools/acceptance/customer-briefing/Dockerfile.html-pdf-checkpoint",
                "--build-arg",
                f"ACCEPTANCE_CANDIDATE_SHA={candidate_sha}",
                "-t",
                image,
            ]
            ca = os.environ.get("CODEX_PROXY_CERT")
            if ca:
                build += ["--secret", f"id=proxy_ca,src={ca}"]
            owner.command([*build, "."], timeout=2715)
        identity = json.loads(
            owner.command(
                ["docker", "image", "inspect", image, "--format", "{{json .}}"],
                timeout=30,
            )
        )
        if (
            identity["Config"]["Labels"]["org.opencontainers.image.revision"]
            != candidate_sha
        ):
            raise ValueError("Image revision mismatch")
        summary["imageId"] = identity["Id"]
        env["CHECKPOINT_IMAGE_ID"] = identity["Id"]
        env["CHECKPOINT_CANDIDATE_SHA"] = candidate_sha
        # Persist the small non-secret Compose environment for teardown.
        started_container = not build_only
        (
            owner.command(
                [
                    "docker",
                    "compose",
                    "-p",
                    project,
                    "-f",
                    str(COMPOSE),
                    "up",
                    "--abort-on-container-exit",
                    "--exit-code-from",
                    "checkpoint",
                ],
                timeout=610,
                env=env,
            )
            if not build_only
            else None
        )
        if build_only:
            summary["buildOnly"] = True
            return summary
        raw = root / "raw"
        raw.mkdir()
        owner.command(
            [
                "docker",
                "compose",
                "-p",
                project,
                "-f",
                str(COMPOSE),
                "cp",
                "checkpoint:/evidence/.",
                str(raw),
            ],
            timeout=60,
            env=env,
        )
        generated = json.loads((raw / "generation-report.json").read_text())
        if not generated["checksPassed"]:
            raise ValueError("Generated checkpoint failed")
        pending = root / "deliverables-staging"
        pending.mkdir()
        for name in ("fully-assessed", "incomplete-x"):
            source = raw / "delivered" / name
            evidence = (source / "mission-customer-briefing-evidence.json").read_bytes()
            staged = pending / (name + "-staging")
            shutil.copytree(source, staged)
            publish_checkpoint(staged, pending / name, evidence)
        summary["cleanup"] = publish_after_cleanup(
            owner, pending, root / "deliverables"
        )
        summary.update(
            checksPassed=True, publication="deliverables", generation=generated
        )
        return summary
    finally:
        # Docker Compose interpolation must have the same image identity at teardown.
        if started_container and not (root / "raw").exists():
            try:
                failed = root / "failed-raw"
                failed.mkdir(exist_ok=True)
                owner.command(
                    [
                        "docker",
                        "compose",
                        "-p",
                        project,
                        "-f",
                        str(COMPOSE),
                        "cp",
                        "checkpoint:/evidence/.",
                        str(failed),
                    ],
                    timeout=60,
                    env=env,
                )
            except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
                summary["failedEvidenceCopyError"] = str(exc)
        try:
            summary["cleanup"] = owner.close()
        finally:
            atexit.unregister(owner.close)
            for sig, handler in previous.items():
                signal.signal(sig, handler)
            (root / "summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--runtime-tests", action="store_true")
    parser.add_argument("--image-tag")
    parser.add_argument("--build-only", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            run_checkpoint(
                args.candidate_sha,
                args.evidence_root,
                args.runtime_tests,
                args.image_tag,
                args.build_only,
            ),
            indent=2,
        )
    )
