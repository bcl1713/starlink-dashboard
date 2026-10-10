"""Bounded exact-HEAD production journey with durable, private resource ownership."""

from __future__ import annotations

import argparse
import ctypes
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
PROJECT = "starlink-itinerary-planning"
PORT = 15322


class Owner:
    """Record intent before launch; reap entire owned groups on every outcome."""

    def __init__(self, output: Path, sha: str):
        self.output = output.resolve()
        self.output.mkdir(parents=True, exist_ok=True, mode=0o700)
        if (self.output / "ownership.json").exists():
            raise RuntimeError("Evidence directory already has an ownership record")
        self.env = dict(os.environ)
        self.children: list[subprocess.Popen[str]] = []
        self.record: dict = {
            "candidate_sha": sha,
            "pid": os.getpid(),
            "pgid": os.getpgrp(),
            "compose_project": PROJECT,
            "session_id": os.getsid(0),
            "port": PORT,
            "volumes": [f"{PROJECT}_{n}" for n in ("app-data", "poi-data", "metrics")],
            "temporary_paths": [],
            "commands": [],
            "cleanup": {},
        }
        # Orphaned browser grandchildren become ours to reap on Linux.
        if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0):
            raise OSError(ctypes.get_errno(), "Could not become child subreaper")
        self.persist()

    def persist(self) -> None:
        pending = self.output / "ownership.pending"
        pending.write_text(json.dumps(self.record, indent=2))
        pending.replace(self.output / "ownership.json")

    def signal(self, signum: int, _frame: object) -> None:
        raise InterruptedError(f"Interrupted by signal {signum}")

    def stop(self, child: subprocess.Popen[str]) -> None:
        def signal_group(number: int) -> bool:
            try:
                os.killpg(child.pid, number)
                return True
            except ProcessLookupError:
                return False

        signal_group(signal.SIGTERM)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            child.poll()
            try:
                while os.waitpid(-child.pid, os.WNOHANG)[0]:
                    pass
            except ChildProcessError:
                pass
            if not signal_group(0):
                break
            time.sleep(0.02)
        if signal_group(0):
            signal_group(signal.SIGKILL)
        child.wait(timeout=5)
        deadline = time.monotonic() + 3
        while signal_group(0) and time.monotonic() < deadline:
            try:
                while os.waitpid(-child.pid, os.WNOHANG)[0]:
                    pass
            except ChildProcessError:
                pass
            time.sleep(0.02)
        if signal_group(0):
            raise RuntimeError(f"Owned process group survives: {child.pid}")

    def execute(
        self, command: list[str], timeout: float = 120, cwd: Path = ROOT
    ) -> str:
        entry = {
            "command": command,
            "cwd": str(cwd),
            "pid": None,
            "pgid": None,
            "reaped": False,
        }
        self.record["commands"].append(entry)
        self.persist()
        log = self.output / f'command-{len(self.record["commands"]):03d}.log'
        with log.open("w") as stream:
            child = subprocess.Popen(
                command,
                cwd=cwd,
                env=self.env,
                stdout=stream,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
            self.children.append(child)
            entry.update(pid=child.pid, pgid=child.pid, log=str(log))
            self.persist()
            try:
                result = child.wait(timeout=timeout)
                if result:
                    raise RuntimeError(
                        f"Command failed ({result}): {command}; see {log}"
                    )
            finally:
                self.stop(child)
                self.children.remove(child)
                entry.update(returncode=child.returncode, reaped=True)
                self.persist()
        return log.read_text()

    def close_processes(self) -> None:
        for child in list(self.children):
            self.stop(child)
            self.children.remove(child)
        self.record["cleanup"]["processes_gone"] = True
        self.persist()

    def compose(self, *arguments: str, timeout: float = 120) -> str:
        return self.execute(
            [
                "docker",
                "compose",
                "-p",
                PROJECT,
                "-f",
                str(
                    Path(self.env["ITINERARY_SOURCE_ROOT"])
                    / "tools/acceptance/itinerary-planning/compose.yml"
                ),
                *arguments,
            ],
            timeout=timeout,
        )


def resources(owner: Owner) -> dict[str, str]:
    return {
        key: owner.execute(
            [*command, "--filter", f"label=com.docker.compose.project={PROJECT}"]
        ).strip()
        for key, command in {
            "containers": ["docker", "ps", "-aq"],
            "networks": ["docker", "network", "ls", "-q"],
            "volumes": ["docker", "volume", "ls", "-q"],
        }.items()
    }


def check_port() -> None:
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", PORT))


def preflight(owner: Owner) -> None:
    if any(resources(owner).values()):
        raise RuntimeError("Existing project resources found; ownership not assumed")
    check_port()
    owner.execute(["docker", "info", "--format", "{{.ServerVersion}} {{.Driver}}"])
    context = owner.execute(["docker", "context", "show"]).strip()
    owner.record["docker"] = {
        "context": context,
        "endpoint": os.environ.get("DOCKER_HOST", "<context>"),
    }
    owner.persist()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT
    ):
        raise RuntimeError(
            "Acceptance requires a clean tracked worktree; commit candidate first"
        )
    output = Path(
        os.environ.get(
            "ITINERARY_EVIDENCE_DIR",
            str(
                ROOT
                / ".superpowers/sdd/2026-10-09-itinerary-xband-planning/evidence/task10"
                / f"production-{sha}-{time.time_ns()}"
            ),
        )
    )
    owner = Owner(output, sha)
    previous = {
        n: signal.signal(n, owner.signal)
        for n in (signal.SIGINT, signal.SIGTERM, signal.SIGALRM)
    }
    signal.alarm(28 * 60)  # Reserve two minutes for teardown before the outer deadline.
    owned = False
    summary: dict = {"candidate_sha": sha, "passed": False}
    try:
        preflight(owner)
        if args.check:
            summary["passed"] = True
            return
        source = owner.output / "candidate-source"
        archive = owner.output / "candidate-source.tar"
        owner.record["temporary_paths"] = [str(source), str(archive)]
        owner.persist()
        owner.execute(["git", "archive", "--format=tar", f"--output={archive}", sha])
        source.mkdir()
        with tarfile.open(archive) as bundle:
            bundle.extractall(source, filter="data")
        owner.env.update(
            ITINERARY_SOURCE_ROOT=str(source), ACCEPTANCE_CANDIDATE_SHA=sha
        )
        owner.env["ITINERARY_BACKEND_IMAGE"] = f"{PROJECT}-backend:{sha}"
        owner.env["ITINERARY_FRONTEND_IMAGE"] = f"{PROJECT}-frontend:{sha}"
        owner.record["source_path"] = str(source)
        owner.persist()
        sys.path.insert(0, str(source))
        from tools.acceptance.compose import parse_buildkit_log

        for name, context in [
            ("backend", source),
            ("frontend", source / "frontend/mission-planner"),
        ]:
            dockerfile = source / (
                "backend/starlink-location/Dockerfile"
                if name == "backend"
                else "frontend/mission-planner/Dockerfile"
            )
            tag = owner.env[f"ITINERARY_{name.upper()}_IMAGE"]
            command = [
                "docker",
                "build",
                "--progress=plain",
                "-f",
                str(dockerfile),
                "--build-arg",
                f"ACCEPTANCE_CANDIDATE_SHA={sha}",
                "-t",
                tag,
            ]
            if ca := os.environ.get("CODEX_PROXY_CERT"):
                command += ["--secret", f"id=proxy_ca,src={ca}"]
            log = owner.execute([*command, str(context)], timeout=1100)
            if not all(r.complete for r in parse_buildkit_log(log, [tag])):
                raise RuntimeError("Missing BuildKit exact image completion evidence")
            identity = json.loads(
                owner.execute(
                    ["docker", "image", "inspect", tag, "--format", "{{json .}}"]
                )
            )
            if identity["Config"]["Labels"]["org.opencontainers.image.revision"] != sha:
                raise RuntimeError("Built image candidate SHA mismatch")
            summary[name] = {"image": identity["Id"], "revision": sha}
        owner.compose("config", "--quiet")
        owned = True  # Record responsibility before any partial Compose launch.
        owner.record["compose_started"] = True
        owner.persist()
        owner.compose(
            "up", "--no-build", "-d", "--wait", "--wait-timeout", "180", timeout=210
        )
        origin = f"http://127.0.0.1:{PORT}"
        summary["api_status"] = json.loads(
            owner.execute(["curl", "--fail", "--silent", f"{origin}/api/status"])
        )
        summary["node"] = owner.execute(["node", "--version"]).strip()
        for service, name in [
            ("starlink-location", "backend"),
            ("mission-planner", "frontend"),
        ]:
            container = owner.compose("ps", "-q", service).strip()
            running_image = owner.execute(
                ["docker", "inspect", container, "--format", "{{.Image}}"]
            ).strip()
            if running_image != summary[name]["image"]:
                raise RuntimeError(
                    "Running container differs from exact candidate image"
                )
            summary[name]["container"] = container
        owner.execute(
            [
                "python3",
                str(source / "tools/acceptance/itinerary-planning/seed.py"),
                "--origin",
                origin,
                "--output",
                str(owner.output / "seed"),
            ]
        )
        frontend = source / "frontend/mission-planner"
        browser_root = owner.output / "browsers"
        owner.record["temporary_paths"].append(str(browser_root))
        owner.persist()
        provenance = owner.output / "browser-provenance.json"
        owner.execute(
            [
                "node",
                str(
                    source
                    / "tools/acceptance/browser/provision-v2-mission-retirement-chromium.mjs"
                ),
                "--mode",
                "provision",
                "--project-dir",
                str(frontend),
                "--browser-root",
                str(browser_root),
                "--task-root",
                str(owner.output),
                "--provenance-file",
                str(provenance),
                "--npm-executable",
                str(Path(shutil.which("npm") or "").resolve()),
            ],
            timeout=300,
        )
        owner.env.update(
            ITINERARY_ORIGIN=origin,
            ITINERARY_EVIDENCE_DIR=str(owner.output),
            ITINERARY_SEED_DIR=str(owner.output / "seed"),
            ITINERARY_CHROME=json.loads(provenance.read_text())["executable"]["path"],
        )
        owner.execute(
            ["node", str(source / "tools/acceptance/browser/itinerary-planning.mjs")],
            timeout=600,
        )
        summary["passed"] = True
    except BaseException as error:
        summary["error"] = str(error)
        raise
    finally:
        signal.alarm(0)
        for number in previous:
            signal.signal(number, signal.SIG_IGN)
        try:
            owner.close_processes()
            if owned:
                try:
                    owner.compose("logs", "--no-color", timeout=30)
                finally:
                    owner.compose("down", "--volumes", "--remove-orphans", timeout=90)
                remaining = resources(owner)
                owner.record["cleanup"]["resources"] = remaining
                owner.persist()
                if any(remaining.values()):
                    raise RuntimeError(f"Owned resources remain: {remaining}")
                check_port()
                owner.record["cleanup"]["port_free"] = True
            for temporary in owner.record["temporary_paths"]:
                path = Path(temporary)
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink(missing_ok=True)
            owner.record["cleanup"]["temporary_paths_removed"] = True
            owner.close_processes()
        except BaseException as error:
            summary.update(passed=False, cleanup_error=str(error))
            raise
        finally:
            summary["cleanup"] = owner.record["cleanup"]
            (owner.output / "summary.json").write_text(json.dumps(summary, indent=2))
            for number, handler in previous.items():
                signal.signal(number, handler)


if __name__ == "__main__":
    main()
