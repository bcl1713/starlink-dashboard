"""Exact-candidate production-image qualification with isolated resource ownership."""

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / "tools/acceptance/customer-briefing/compose.production.yml"


class ProductionOwner:
    def __init__(self, project, evidence_root):
        if not project.startswith("briefing-"):
            raise ValueError("A private briefing project is required")
        self.project = project
        self.root = Path(evidence_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.child = None
        self.cancelled = False
        self.closed = False
        self.cleaning = False
        self.env = dict(os.environ)
        self.compose_file = COMPOSE
        self.ownership = {
            "pid": os.getpid(),
            "pgid": os.getpgrp(),
            "composeProject": project,
            "composeFile": str(COMPOSE),
            "volumes": [
                f"{project}_{name}"
                for name in ("app-data", "poi-data", "prometheus-data")
            ],
            "images": [],
            "temporaryPaths": [],
            "commands": [],
            "cancelled": False,
            "cleanup": {},
        }
        self.persist()

    def persist(self):
        target = self.root / "ownership.json"
        pending = target.with_suffix(".pending")
        pending.write_text(json.dumps(self.ownership, indent=2))
        pending.replace(target)

    def execute(self, command, timeout=600, env=None):
        if self.cancelled and not self.cleaning:
            raise InterruptedError("Production qualification cancelled")
        entry = {
            "command": command,
            "startedAt": time.time(),
            "pid": None,
            "pgid": None,
        }
        self.ownership["commands"].append(entry)
        self.persist()
        log = self.root / f"command-{len(self.ownership['commands']):03d}.log"
        with log.open("w") as output:
            self.child = subprocess.Popen(
                command,
                cwd=ROOT,
                env=env or self.env,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            entry.update(pid=self.child.pid, pgid=self.child.pid, log=str(log))
            self.persist()
            try:
                code = self.child.wait(timeout=timeout)
                if code:
                    raise RuntimeError(f"Command failed ({code}); see {log}")
            except subprocess.TimeoutExpired as exc:
                self.stop_child()
                raise TimeoutError(f"Command timed out; see {log}") from exc
            except BaseException:
                self.stop_child()
                raise
            finally:
                entry.update(
                    returncode=self.child.returncode,
                    reaped=True,
                    finishedAt=time.time(),
                )
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
        self.ownership["cancelled"] = True
        self.persist()
        self.stop_child()
        raise InterruptedError(
            f"Production qualification interrupted by signal {signum}"
        )

    def compose(self, *arguments, timeout=120):
        return self.execute(
            [
                "docker",
                "compose",
                "-p",
                self.project,
                "-f",
                str(self.compose_file),
                *arguments,
            ],
            timeout=timeout,
        )

    def close(self):
        if self.closed:
            return self.ownership["cleanup"]
        self.cleaning = True
        self.stop_child()
        self.compose("down", "--volumes", "--remove-orphans", timeout=90)
        remaining = {}
        for name, command in {
            "containers": ["docker", "ps", "-aq"],
            "networks": ["docker", "network", "ls", "-q"],
            "volumes": ["docker", "volume", "ls", "-q"],
        }.items():
            remaining[name] = self.execute(
                [
                    *command,
                    "--filter",
                    f"label=com.docker.compose.project={self.project}",
                ],
                timeout=30,
            ).strip()
        result = {
            "childrenReaped": self.child is None,
            "composeRemoved": not any(remaining.values()),
            "remaining": remaining,
        }
        self.ownership["cleanup"] = result
        self.persist()
        if not result["composeRemoved"]:
            raise RuntimeError(
                "Owned production resources remain; ownership and context retained"
            )
        for image in self.ownership["images"]:
            # A failed build may have recorded intent without creating its tag.
            images = self.execute(
                ["docker", "image", "ls", "-q", image], timeout=30
            ).strip()
            if images:
                self.execute(["docker", "image", "rm", image], timeout=60)
        for name in self.ownership["temporaryPaths"]:
            path = Path(name)
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
        if "BRIEFING_PORT" in self.env:
            with socket.socket() as listener:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                listener.bind(("127.0.0.1", int(self.env["BRIEFING_PORT"])))
            result["listenerRemoved"] = True
        result["imagesRemoved"] = True
        result["temporaryPathsRemoved"] = True
        self.closed = True
        self.persist()
        return result


def free_loopback_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def run_production(candidate_sha, evidence_root, images_only=False):
    def git(*arguments):
        return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True).strip()

    if (
        len(candidate_sha) != 40
        or candidate_sha != git("rev-parse", "HEAD")
        or git("status", "--porcelain")
    ):
        raise ValueError("Production qualification requires clean committed full HEAD")
    run_id = time.time_ns()
    owner = ProductionOwner(
        f"briefing-production-{candidate_sha[:12]}-{run_id}", evidence_root
    )
    owner.env.update(
        BRIEFING_BACKEND_IMAGE=f"briefing-production-backend:{candidate_sha[:12]}-{run_id}",
        BRIEFING_FRONTEND_IMAGE=f"briefing-production-frontend:{candidate_sha[:12]}-{run_id}",
        BRIEFING_PORT=str(free_loopback_port()),
        BRIEFING_ENABLED="false",
        BRIEFING_SOURCE_ROOT=str(owner.root / "candidate-source"),
    )
    summary = {
        "candidateSha": candidate_sha,
        "checksPassed": False,
        "imagesOnly": images_only,
        "project": owner.project,
        "images": {},
        "customerAcceptance": "pending",
    }
    previous = {
        number: signal.signal(number, owner.signal)
        for number in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        context = owner.root / "candidate-source"
        archive = owner.root / "candidate-source.tar"
        owner.ownership["temporaryPaths"] += [str(context), str(archive)]
        owner.persist()
        owner.execute(
            ["git", "archive", "--format=tar", f"--output={archive}", candidate_sha],
            timeout=60,
        )
        context.mkdir()
        with tarfile.open(archive) as source:
            source.extractall(context, filter="data")
        self_compose = (
            context / "tools/acceptance/customer-briefing/compose.production.yml"
        )
        owner.compose_file = self_compose
        owner.ownership["composeFile"] = str(self_compose)
        owner.persist()
        for name, dockerfile, build_context in (
            ("backend", "backend/starlink-location/Dockerfile", context),
            (
                "frontend",
                "frontend/mission-planner/Dockerfile",
                context / "frontend/mission-planner",
            ),
        ):
            tag = owner.env[f"BRIEFING_{name.upper()}_IMAGE"]
            owner.ownership["images"].append(tag)
            owner.persist()
            command = [
                "timeout",
                "--kill-after=10s",
                "45m",
                "docker",
                "build",
                "--no-cache",
                "-f",
                str(context / dockerfile),
                "--build-arg",
                f"ACCEPTANCE_CANDIDATE_SHA={candidate_sha}",
                "-t",
                tag,
            ]
            if ca := os.environ.get("CODEX_PROXY_CERT"):
                command += ["--secret", f"id=proxy_ca,src={ca}"]
            owner.execute([*command, str(build_context)], timeout=2720)
            identity = json.loads(
                owner.execute(
                    ["docker", "image", "inspect", tag, "--format", "{{json .}}"],
                    timeout=30,
                )
            )
            if (
                identity["Config"]["Labels"]["org.opencontainers.image.revision"]
                != candidate_sha
            ):
                raise ValueError("Production image revision mismatch")
            summary["images"][name] = {
                "tag": tag,
                "id": identity["Id"],
                "revision": candidate_sha,
            }
        probe = (
            context / "tools/acceptance/customer-briefing/production_image_probe.py"
        ).read_text()
        summary["runtime"] = json.loads(
            owner.compose(
                "run",
                "--rm",
                "--no-deps",
                "starlink-location",
                "python",
                "-c",
                probe,
                timeout=60,
            ).splitlines()[-1]
        )
        if not images_only:
            sys.path.insert(0, str(context / "tools/acceptance/customer-briefing"))
            from production_controls import qualify

            summary["production"] = qualify(owner)
        summary["checksPassed"] = True
        return summary
    finally:
        try:
            # Logs remain private evidence even when a production control fails.
            owner.cleaning = True
            try:
                owner.compose("logs", "--no-color", timeout=30)
            except (RuntimeError, OSError, TimeoutError):
                pass
            if observer := owner.ownership.get("observer"):
                try:
                    owner.compose(
                        "exec",
                        "-T",
                        "--user",
                        "appuser",
                        "starlink-location",
                        "python",
                        "-c",
                        """import json,os,signal,time
from pathlib import Path
p=Path('/tmp/briefing-production-observations/observer-owner.json')
r=json.loads(p.read_text()); stat=Path(f'/proc/{r["pid"]}/stat')
def alive():
 try:
  fields=stat.read_text().split(') ')[1].split()
  return fields[19]==r['start'] and fields[0]!='Z'
 except OSError:return False
if alive():os.kill(r['pid'],signal.SIGTERM)
deadline=time.monotonic()+2
while alive() and time.monotonic()<deadline:time.sleep(.01)
if alive():os.kill(r['pid'],signal.SIGKILL)
print(json.dumps({'observerStopped':not alive()}))
""",
                        timeout=10,
                    )
                    observations = owner.root / "runtime-observations"
                    observations.mkdir()
                    owner.compose(
                        "cp",
                        f"starlink-location:{observer['output']}/.",
                        str(observations),
                        timeout=30,
                    )
                except (RuntimeError, OSError, ValueError, TimeoutError) as error:
                    summary["observerError"] = str(error)
                    summary["checksPassed"] = False
            summary["cleanup"] = owner.close()
        finally:
            for number, handler in previous.items():
                signal.signal(number, handler)
            (owner.root / "summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--images-only", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            run_production(args.candidate_sha, args.evidence_root, args.images_only),
            indent=2,
        )
    )
