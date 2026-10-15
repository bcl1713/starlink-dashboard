"""Bounded exact-HEAD production journey with durable, private resource ownership."""

from __future__ import annotations

import argparse
import base64
import ctypes
import errno
import gzip
import hashlib
import json
import logging
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import time
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
PROJECT = "starlink-itinerary-planning"
PORT = 15322
# Kernel-owned, process-lifetime coordination across worktrees; no stale lockfile.
CLAIM_NAME = f"{PROJECT}-{os.getuid()}-{PORT}"
RESOURCE_COMMANDS = {
    "containers": ["docker", "ps", "-aq"],
    "networks": ["docker", "network", "ls", "-q"],
    "volumes": ["docker", "volume", "ls", "-q"],
}


class Owner:
    """Record intent before launch; reap entire owned groups on every outcome."""

    def __init__(
        self, output: Path, sha: str, *, project: str = PROJECT, port: int = PORT
    ):
        if (
            not re.fullmatch(r"[a-z0-9][a-z0-9-]{3,90}", project)
            or project in {"dev", "main", "starlink-dashboard"}
            or not 1024 <= port <= 65533
        ):
            raise ValueError("Choose an isolated project and an unprivileged port")
        self.project, self.port = project, port
        self.claim_name = (
            CLAIM_NAME
            if (project, port) == (PROJECT, PORT)
            else f"{project}-{os.getuid()}-{port}"
        )
        self.output = output.resolve()
        self.output.mkdir(parents=True, exist_ok=True, mode=0o700)
        if (self.output / "ownership.json").exists():
            raise RuntimeError("Evidence directory already has an ownership record")
        self.env = dict(os.environ)
        self.children: list[subprocess.Popen[str]] = []
        self.claim: socket.socket | None = None
        self.scope_claims: list[socket.socket] = []
        self.record: dict = {
            "candidate_sha": sha,
            "pid": os.getpid(),
            "pgid": os.getpgrp(),
            "compose_project": self.project,
            "session_id": os.getsid(0),
            "port": self.port,
            "health_port": self.port + 2,
            "volumes": [
                f"{self.project}_{n}" for n in ("app-data", "poi-data", "metrics")
            ],
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

    def acquire_claim(self) -> None:
        self.record["claim"] = {
            "kind": "linux-abstract-unix-socket",
            "name": self.claim_name,
            "state": "requested",
        }
        self.persist()  # Record intent before the atomic, nonblocking acquisition.
        claim = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            claim.bind("\0" + self.claim_name)
        except OSError as error:
            claim.close()
            self.record["claim"]["state"] = (
                "contended" if error.errno == errno.EADDRINUSE else "failed"
            )
            self.persist()
            raise RuntimeError(
                f"Cannot acquire exclusive run claim {self.claim_name}: {error}"
            ) from error
        self.claim = claim
        names = [
            f"itinerary-project-{os.getuid()}-{self.project}",
            *[
                f"itinerary-listener-{os.getuid()}-{p}"
                for p in (self.port, self.port + 2)
            ],
        ]
        self.record["claim"]["scopes"] = names
        self.persist()
        try:
            for name in names:
                scope = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.scope_claims.append(scope)
                scope.bind("\0" + name)
        except OSError as error:
            self.release_claim()
            self.record["claim"]["state"] = "contended"
            self.persist()
            raise RuntimeError(
                f"Cannot acquire exclusive resource scope: {error}"
            ) from error
        self.record["claim"]["state"] = "acquired"
        self.persist()

    def release_claim(self) -> None:
        for scope in self.scope_claims:
            scope.close()
        self.scope_claims.clear()
        if self.claim is not None:
            self.claim.close()
            self.claim = None
            self.record["claim"]["state"] = "released"
            self.persist()

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
        failures = []
        self.record["cleanup"]["processes_gone"] = False
        for child in list(self.children):
            try:
                self.stop(child)
            except BaseException as error:
                logger.exception("Failed to stop owned group %s", child.pid)
                failures.append(f"Owned group {child.pid}: {error}")
                continue
            self.children.remove(child)
            for command in self.record["commands"]:
                if command["pid"] == child.pid:
                    command.update(reaped=True, returncode=child.returncode)
        self.record["cleanup"].update(
            processes_gone=not self.children,
            unreaped_groups=[child.pid for child in self.children],
        )
        self.persist()
        if failures:
            raise RuntimeError("; ".join(failures))

    def compose(self, *arguments: str, timeout: float = 120) -> str:
        return self.execute(
            [
                "docker",
                "compose",
                "-p",
                self.project,
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
            [*command, "--filter", f"label=com.docker.compose.project={owner.project}"]
        ).strip()
        for key, command in RESOURCE_COMMANDS.items()
    }


def check_port(port: int = PORT) -> None:
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", port))


def preflight(owner: Owner) -> None:
    if any(resources(owner).values()):
        raise RuntimeError("Existing project resources found; ownership not assumed")
    check_port() if owner.port == PORT else check_port(owner.port)
    check_port(owner.port + 2)
    owner.execute(["docker", "info", "--format", "{{.ServerVersion}} {{.Driver}}"])
    context = owner.execute(["docker", "context", "show"]).strip()
    machine = owner.execute(
        ["docker", "info", "--format", "{{json .Name}} {{.NCPU}} {{.MemTotal}}"]
    ).strip()
    owner.record["docker"] = {
        "machine": machine,
        "context": context,
        "endpoint": os.environ.get("DOCKER_HOST", "<context>"),
    }
    owner.persist()


def cleanup(owner: Owner, owned: bool) -> list[dict[str, str]]:
    """Attempt independent teardown stages and preserve every unresolved identifier."""
    failures: list[dict[str, str]] = []

    def attempt(stage, operation):
        try:
            return operation()
        except BaseException as error:
            logger.exception("Cleanup stage failed: %s", stage)
            failures.append({"stage": stage, "error": str(error)})
            return None

    attempt("processes_initial", owner.close_processes)
    if owned:
        attempt("compose_logs", lambda: owner.compose("logs", "--no-color", timeout=30))
        attempt(
            "compose_down",
            lambda: owner.compose("down", "--volumes", "--remove-orphans", timeout=90),
        )
        remaining = {}
        for kind, command in RESOURCE_COMMANDS.items():
            result = attempt(
                f"audit_{kind}",
                lambda command=command: owner.execute(
                    [
                        *command,
                        "--filter",
                        f"label=com.docker.compose.project={owner.project}",
                    ]
                ).strip(),
            )
            remaining[kind] = result  # None means unknown, never falsely empty.
            if result:
                failures.append(
                    {
                        "stage": f"audit_{kind}",
                        "error": f"Owned {kind} remain: {result}",
                    }
                )
        owner.record["cleanup"]["resources"] = remaining
        owner.record["cleanup"]["port_free"] = False

        def audit_port():
            check_port() if owner.port == PORT else check_port(owner.port)
            check_port(owner.port + 2)
            owner.record["cleanup"]["port_free"] = True

        attempt("audit_port", audit_port)
    attempt("processes_final", owner.close_processes)
    survivors = []
    for temporary in owner.record["temporary_paths"]:
        path = Path(temporary)

        def remove(path=path):
            if owner.children:
                raise RuntimeError(
                    f"Cannot remove {path}; owned groups still live: {[child.pid for child in owner.children]}"
                )
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)

        attempt(f"remove:{temporary}", remove)
        exists = attempt(f"audit_path:{temporary}", path.exists)
        if exists is not False:
            survivors.append(temporary)
    owner.record["cleanup"].update(
        temporary_paths_removed=not survivors,
        temporary_survivors=survivors,
    )
    attempt("persist_cleanup", owner.persist)
    return failures


def verify_clone_snapshot(owner, source):
    views = json.loads((owner.output / "collision-views.json").read_text())
    # The journey intentionally revises the original later. Use its actual
    # clone-time package and reconstruct against the retained immutable sources.
    with zipfile.ZipFile(owner.output / "synthetic-package.zip") as package:
        original = base64.b64encode(
            gzip.compress(package.read("mission.json"))
        ).decode()
    result = owner.compose(
        "exec",
        "-T",
        "starlink-location",
        "runuser",
        "-u",
        "appuser",
        "--",
        "python",
        "-c",
        (source / "tools/acceptance/itinerary-planning/verify-clone.py").read_text(),
        views["cloneView"]["mission"]["id"],
        original,
        timeout=120,
    )
    line = next(
        line for line in result.splitlines() if line.startswith("CANONICAL_RECEIPT=")
    )
    receipt = json.loads(line.removeprefix("CANONICAL_RECEIPT="))
    (owner.output / "clone-export-rebuild.json").write_text(
        json.dumps(receipt, indent=2)
    )
    assert receipt["original_mission_id"] == views["beforeClone"]["mission"]["id"]
    assert receipt["mission_id"] == views["cloneView"]["mission"]["id"]
    assert receipt["stored_files_unchanged"]
    expected = views["cloneView"]["mission"]["legs"]
    assert len(receipt["legs"]) == len(expected)
    for actual, baseline in zip(receipt["legs"], expected):
        assert actual["leg_id"] == baseline["id"]
        assert actual["preparation_origins"] == ["rebuilt", "rebuilt"]
        assert actual["context"] == baseline["transports"]["evaluation_context"]
        assert actual["canonical_evaluations_equal"]
        assert actual["export_intervals_equal"]


PRIVATE_NAMES = [
    "Itinerary Rev 5.pdf",
    "Leg 1 Rev 5.kml",
    "Leg 2 Rev 5.kml",
    "Leg 3 Rev 5.kml",
    "package.zip",
]


def validate_evidence_scope(output: Path, inputs: Path | None) -> None:
    if inputs is None:
        return
    output, inputs = output.resolve(), inputs.resolve()
    if output == inputs or inputs in output.parents or output in inputs.parents:
        raise ValueError("Evidence and immutable input paths must not overlap")


def private_inputs(root: Path) -> dict:
    root = root.resolve(strict=True)
    return {
        "root": str(root),
        "hashes": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in PRIVATE_NAMES
        },
    }


def verify_private_inputs(root: Path, before: dict) -> None:
    if private_inputs(root) != before:
        raise RuntimeError("Private input files changed during acceptance")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--workflow", choices=["ordinary", "legacy"], default="ordinary"
    )
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--input-root", type=Path)
    parser.add_argument(
        "--network-mode", choices=["offline", "online"], default="offline"
    )
    parser.add_argument("--evidence", type=Path)
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
    output = args.evidence or output
    validate_evidence_scope(output, args.input_root)
    owner = Owner(output, sha, project=args.project, port=args.port)
    previous = {
        n: signal.signal(n, owner.signal)
        for n in (signal.SIGINT, signal.SIGTERM, signal.SIGALRM)
    }
    signal.alarm(28 * 60)  # Reserve two minutes for teardown before the outer deadline.
    owned = False
    summary: dict = {
        "candidate_sha": sha,
        "passed": False,
        "network_mode": args.network_mode,
        "project": owner.project,
        "port": owner.port,
    }
    original_inputs = None
    primary_error: BaseException | None = None
    try:
        owner.acquire_claim()
        original_inputs = private_inputs(args.input_root) if args.input_root else None
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
            ITINERARY_SOURCE_ROOT=str(source),
            ACCEPTANCE_CANDIDATE_SHA=sha,
            ITINERARY_PORT=str(owner.port),
            ITINERARY_HEALTH_PORT=str(owner.port + 2),
            ITINERARY_NETWORK_MODE=args.network_mode,
        )
        owner.env["ITINERARY_BACKEND_IMAGE"] = (
            f"starlink-itinerary-planning-backend:{sha}"
        )
        owner.env["ITINERARY_FRONTEND_IMAGE"] = (
            f"starlink-itinerary-planning-frontend:{sha}"
        )
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
        # A non-cooperating process may have created foreign resources during builds.
        if any(resources(owner).values()):
            raise RuntimeError(
                "Project resources appeared during build; ownership not assumed"
            )
        check_port() if owner.port == PORT else check_port(owner.port)
        check_port(owner.port + 2)
        owned = True  # Record responsibility before any partial Compose launch.
        owner.record["compose_started"] = True
        owner.persist()
        owner.compose(
            "up", "--no-build", "-d", "--wait", "--wait-timeout", "180", timeout=210
        )
        origin = f"http://127.0.0.1:{owner.port}"
        summary["configuration"] = {
            "docker": owner.record["docker"],
            "telemetry": "simulation",
            "monitoring": "Prometheus, default scrape configuration plus 3 socket probes every 150ms",
            "browser_network": args.network_mode,
            "pdf_network": "local assets, external requests blocked",
        }
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
                *(["--skip-satellites"] if original_inputs else []),
            ]
        )
        if getattr(args, "workflow", "legacy") == "ordinary":
            if original_inputs:
                raise ValueError(
                    "Ordinary qualification currently uses invented fixtures only"
                )
            owner.env["ITINERARY_WORKFLOW"] = "ordinary"
            container = summary["backend"]["container"]
            owner.execute(
                [
                    "docker",
                    "cp",
                    str(owner.output / "seed"),
                    f"{container}:/tmp/ordinary-import-seed",
                ]
            )
            owner.execute(
                [
                    "docker",
                    "cp",
                    str(source / "tools/acceptance/itinerary-planning/seed_legacy.py"),
                    f"{container}:/tmp/seed_legacy.py",
                ]
            )
            seeded = owner.compose(
                "exec",
                "-T",
                "starlink-location",
                "runuser",
                "-u",
                "appuser",
                "--",
                "python",
                "/tmp/seed_legacy.py",
                "/tmp/ordinary-import-seed",
            )
            record = json.loads(
                next(
                    line.removeprefix("MIGRATION_SEED=")
                    for line in seeded.splitlines()
                    if line.startswith("MIGRATION_SEED=")
                )
            )
            (owner.output / "seed" / "migration.json").write_text(json.dumps(record))
            owner.compose("restart", "starlink-location", timeout=180)
            owner.compose(
                "up", "--no-build", "-d", "--wait", "--wait-timeout", "180", timeout=210
            )
        if original_inputs:
            owner.env["ITINERARY_INPUT_ROOT"] = original_inputs["root"]
            (owner.output / "input-hashes.json").write_text(
                json.dumps(original_inputs, indent=2)
            )
            owner.execute(
                [
                    "python3",
                    str(source / "tools/acceptance/itinerary-planning/real_seed.py"),
                    "--origin",
                    origin,
                    "--input-root",
                    original_inputs["root"],
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
            ITINERARY_HEALTH_ORIGIN=f"http://127.0.0.1:{owner.port + 2}",
            ITINERARY_EVIDENCE_DIR=str(owner.output),
            ITINERARY_SEED_DIR=str(owner.output / "seed"),
            ITINERARY_CHROME=json.loads(provenance.read_text())["executable"]["path"],
        )
        owner.execute(
            ["node", str(source / "tools/acceptance/browser/itinerary-planning.mjs")],
            timeout=1100,
        )
        if not original_inputs:
            verify_clone_snapshot(owner, source)
        else:
            container = summary["backend"]["container"]
            owner.execute(
                [
                    "docker",
                    "cp",
                    str(source / "tools/acceptance/itinerary-planning"),
                    f"{container}:/tmp/itinerary-acceptance",
                ]
            )
            owner.execute(
                [
                    "docker",
                    "cp",
                    str(owner.output / "input-hashes.json"),
                    f"{container}:/tmp/input-hashes.json",
                ]
            )
            for temperature in ("cold", "warm"):
                owner.execute(
                    [
                        "docker",
                        "cp",
                        str(owner.output / f"{temperature}.zip"),
                        f"{container}:/tmp/{temperature}.zip",
                    ]
                )
                owner.compose(
                    "exec",
                    "-T",
                    "starlink-location",
                    "runuser",
                    "-u",
                    "appuser",
                    "--",
                    "python",
                    "/tmp/itinerary-acceptance/qualify.py",
                    f"/tmp/{temperature}.zip",
                    f"/tmp/{temperature}-proof",
                    "/tmp/input-hashes.json",
                    timeout=180,
                )
                owner.execute(
                    [
                        "docker",
                        "cp",
                        f"{container}:/tmp/{temperature}-proof",
                        str(owner.output / f"{temperature}-proof"),
                    ]
                )
            probes = json.loads((owner.output / "api-probes.json").read_text())
            if probes["failures"]:
                raise RuntimeError(
                    "A real acceptance API probe missed its two-second deadline"
                )
            summary["maps_qualified"] = 6
            verify_private_inputs(args.input_root, original_inputs)
            summary["inputs_unchanged"] = True
        if getattr(args, "workflow", "legacy") == "ordinary":
            from ordinary_proof import validate

            validate(
                json.loads((owner.output / "ordinary-proof.json").read_text()), sha
            )
        summary["passed"] = True
    except BaseException as error:
        primary_error = error
        summary["error"] = str(error)
        raise
    finally:
        if original_inputs:
            try:
                verify_private_inputs(args.input_root, original_inputs)
                summary["inputs_unchanged"] = True
            except (
                BaseException
            ) as error:  # noqa: BLE001 - cleanup must survive signals
                summary.update(passed=False, input_error=str(error))
                primary_error = primary_error or error
        signal.alarm(0)
        for number in previous:
            signal.signal(number, signal.SIG_IGN)
        failures = []
        try:
            failures.extend(cleanup(owner, owned))
        except BaseException as error:
            logger.exception("Cleanup orchestration failed")
            failures.append({"stage": "cleanup_orchestration", "error": str(error)})
        finally:
            try:
                owner.release_claim()
            except BaseException as error:
                logger.exception("Failed to release exclusive run claim")
                failures.append({"stage": "release_claim", "error": str(error)})
            if failures:
                summary.update(passed=False, cleanup_errors=failures)
            summary["cleanup"] = owner.record["cleanup"]
            summary["claim"] = owner.record.get("claim")
            try:
                (owner.output / "summary.json").write_text(
                    json.dumps(summary, indent=2)
                )
            finally:
                for number, handler in previous.items():
                    signal.signal(number, handler)
        if failures:
            message = f"Acceptance cleanup failed: {failures}"
            if primary_error is not None:
                primary_error.add_note(message)
            else:
                raise RuntimeError(message)


if __name__ == "__main__":
    main()
