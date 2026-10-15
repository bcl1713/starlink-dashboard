"""One archived candidate, isolated runtime, and evidence only after teardown."""

import ctypes
import hashlib
import json
import math
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

VOLUMES = [
    "missions",
    "settings",
    "satellites",
    "coverage",
    "routes",
    "simulation-routes",
    "pois",
    "metrics",
]
REAL_SHA = "8c4c65bb33a7ffb842538f4374029cf6df03a977443aa0fd8e7bd0073a22fc37"


def bind_browser_source(candidate, installed, *, link=True):
    lock = (candidate / "package-lock.json").read_bytes()
    if lock != (installed / "package-lock.json").read_bytes():
        raise ValueError("Provisioned dependencies differ from candidate lock")
    if not (installed / "node_modules").is_dir():
        raise ValueError("Provisioned dependencies missing")
    if link:
        (candidate / "node_modules").symlink_to(
            installed / "node_modules", target_is_directory=True
        )
    files = [
        *candidate.glob("tests/e2e/**/*.ts"),
        *candidate.glob("playwright.aviation-acceptance.config.ts"),
    ]
    return {
        "source": str(candidate),
        "package_lock_sha256": hashlib.sha256(lock).hexdigest(),
        "files": {
            str(p.relative_to(candidate)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files
        },
    }


def require_pass(proofs):
    encounter = proofs.get("encounter", {})
    if not all(
        encounter.get(key) is True
        for key in (
            "altitude_free",
            "time_boundaries",
            "plan_edit_ack_preserved",
            "selected_only_unknown",
            "partial_evidence",
            "two_screen_sync",
            "responsive_details",
            "no_altitude_filter",
        )
    ):
        raise ValueError("Incomplete SIGMET encounter evidence")
    browser, route, cleanup = (
        proofs.get(key, {}) for key in ("browser", "route", "cleanup")
    )
    elapsed = route.get("elapsed_save_to_display_ms", [])
    attention = proofs.get("attention", {})
    if not all(
        attention.get(key) is True
        for key in (
            "quiet_overview",
            "manual_selection",
            "shared_acknowledgement",
            "configuration_relevance",
            "screenshots_complete",
        )
    ):
        raise ValueError("Incomplete SIGMET attention evidence")
    if (
        browser.get("passed", 0) < 2
        or browser.get("failed") != 0
        or browser.get("skipped") != 0
        or not route.get("assertions_complete")
        or not elapsed
        or any(
            not isinstance(v, (int, float))
            or not math.isfinite(v)
            or not 0 <= v <= 8000
            for v in elapsed
        )
        or not proofs.get("real_source", {}).get("replayed")
    ):
        raise ValueError("Incomplete browser/source/propagation evidence")
    if (
        cleanup.get("errors")
        or not cleanup.get("ports_free")
        or cleanup.get("source_absent") is not True
        or any(
            cleanup.get(key) != []
            for key in ("containers", "networks", "volumes", "processes")
        )
    ):
        raise ValueError("Incomplete verified cleanup")


def process_table():
    result = {}
    for path in Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = path.read_text().rsplit(")", 1)[1].split()
            result[int(path.parent.name)] = (int(fields[1]), int(fields[2]), fields[19])
        except (OSError, ValueError, IndexError):
            continue
    return result


class Runner:
    def __init__(self, root, sha, browser, *, output=None):
        # Subreap grandchildren when a timed-out browser/CLI exits before them.
        if ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) != 0:
            raise RuntimeError("Linux child reaping unavailable")
        self.root, self.sha, self.browser = root, sha, browser
        suffix = uuid.uuid4().hex[:12]
        self.project = os.environ.get(
            "WEATHER_ACCEPTANCE_PROJECT", f"starlink-route-sigmets-{suffix}"
        )
        if not re.fullmatch(r"starlink-route-sigmets-[a-z0-9-]+", self.project):
            raise ValueError("A task-specific route SIGMET project is required")
        self.output = output or root / "test-results" / f"route-sigmets-{suffix}" / sha
        self.output.mkdir(parents=True)
        self.source = Path("/tmp") / f"{self.project}-source"
        self.reservations, self.ports, self.processes = [], [], {}
        self.allocated = False
        self.proofs = {}
        self.env = dict(os.environ)
        # Intent is durable before ports, temporary directories, or processes.
        self.record(
            "runtime-owner.json",
            {
                "sha": sha,
                "pid": os.getpid(),
                "pgid": os.getpgrp(),
                "command": sys.argv,
                "project": self.project,
                "source_root": str(self.source),
                "private_volumes": VOLUMES,
                "docker_host": os.environ.get("DOCKER_HOST"),
                "docker_context": os.environ.get("DOCKER_CONTEXT"),
                "ports": [],
            },
        )
        try:
            for variable in (
                "WEATHER_ACCEPTANCE_FRONTEND_PORT",
                "WEATHER_ACCEPTANCE_BACKEND_PORT",
            ):
                sock = socket.socket()
                self.reservations.append(sock)
                sock.bind(("127.0.0.1", int(os.environ.get(variable, "0"))))
                self.ports.append(sock.getsockname()[1])
            owner = json.loads((self.output / "runtime-owner.json").read_bytes())
            owner["ports"] = self.ports
            self.record("runtime-owner.json", owner)
            self.source.mkdir(mode=0o755)
        except BaseException:
            self.release_ports()
            raise
        self.env.update(
            ACCEPTANCE_CANDIDATE_SHA=sha,
            AVIATION_ACCEPTANCE_BROWSER=str(browser),
            WEATHER_ACCEPTANCE_PROJECT=self.project,
            WEATHER_ACCEPTANCE_SOURCE_ROOT=str(self.source),
            WEATHER_ACCEPTANCE_OUTPUT_DIR=str(self.output),
            WEATHER_ACCEPTANCE_CONTROL_DIR=str(self.output / "control"),
            WEATHER_ACCEPTANCE_CONTROL_PATH=str(self.output / "control/control.json"),
            WEATHER_ACCEPTANCE_CAPTURE_DIR=str(self.output / "capture"),
            WEATHER_ACCEPTANCE_FRONTEND_PORT=str(self.ports[0]),
            WEATHER_ACCEPTANCE_BACKEND_PORT=str(self.ports[1]),
            WEATHER_ACCEPTANCE_BASE_URL=f"http://127.0.0.1:{self.ports[0]}",
            WEATHER_ACCEPTANCE_MODE="aviation",
        )
        self.compose = ["docker", "compose", "-p", self.project]
        for name in ("overview-weather", "aviation-weather"):
            self.compose += [
                "-f",
                str(self.source / f"tools/acceptance/{name}/compose.yml"),
            ]

    def record(self, name, value):
        (self.output / name).write_text(json.dumps(value, indent=2))

    def release_ports(self):
        for sock in self.reservations:
            sock.close()
        self.reservations.clear()

    def command(self, argv, *, seconds=60, name=None, cwd=None):
        log = self.output / f"{name or time.time_ns()}.log"
        with (self.output / "commands.jsonl").open("a") as ledger:
            ledger.write(
                json.dumps(
                    {
                        "command": argv,
                        "cwd": str(cwd or self.root),
                        "log": str(log),
                        "limit_s": seconds,
                        "state": "starting",
                    }
                )
                + "\n"
            )
        with log.open("w") as stream:
            child = subprocess.Popen(
                argv,
                cwd=cwd or self.root,
                env=self.env,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            self.processes[child.pid] = process_table().get(
                child.pid, (0, child.pid, None)
            )[2]
            self.record("process-ownership.json", self.processes)
            try:
                child.wait(timeout=seconds)
            except subprocess.TimeoutExpired as error:
                raise TimeoutError(f"Command exceeded {seconds}s") from error
            finally:
                # All descendants inherit this owned process group, including
                # children whose leader already exited after a failed command.
                members = {
                    pid: start
                    for pid, (_, group, start) in process_table().items()
                    if group == child.pid
                }
                self.processes.update(members)
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    self.reap()
                    if not self.survivors(members):
                        break
                    time.sleep(0.05)
                if self.survivors(members):
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                child.wait()
                self.reap()
                self.record("process-ownership.json", self.processes)
        if child.returncode:
            raise RuntimeError(
                f"Command failed ({child.returncode}): {argv[:4]}\n{log.read_text()[-2500:]}"
            )
        return log.read_text()

    @staticmethod
    def reap():
        while True:
            try:
                if os.waitpid(-1, os.WNOHANG)[0] == 0:
                    break
            except ChildProcessError:
                break

    @staticmethod
    def survivors(owned):
        table = process_table()
        return [
            pid
            for pid, start in owned.items()
            if pid in table and table[pid][2] == start
        ]

    def inventory(self):
        return {
            kind: self.command(
                [*argv, "--filter", f"label=com.docker.compose.project={self.project}"]
            ).split()
            for kind, argv in {
                "containers": ["docker", "ps", "-aq"],
                "networks": ["docker", "network", "ls", "-q"],
                "volumes": ["docker", "volume", "ls", "-q"],
            }.items()
        }

    def execute(self):
        if any(self.inventory().values()):
            raise ValueError("Existing labeled resources; refusing ownership")
        self.command(
            [
                "git",
                "archive",
                "--format=tar",
                "-o",
                str(self.source / "candidate.tar"),
                self.sha,
            ]
        )
        self.command(
            ["tar", "-xf", str(self.source / "candidate.tar"), "-C", str(self.source)]
        )
        archive_sha = hashlib.sha256(
            (self.source / "candidate.tar").read_bytes()
        ).hexdigest()
        (self.source / "candidate.tar").unlink()
        candidate = self.source / "frontend/mission-planner"
        provenance = bind_browser_source(
            candidate, self.root / "frontend/mission-planner", link=False
        )
        self.record(
            "candidate.json",
            {
                "sha": self.sha,
                "archive_sha256": archive_sha,
                "browser_sources": provenance,
                "browser": str(self.browser),
                "browser_sha256": hashlib.sha256(self.browser.read_bytes()).hexdigest(),
                "node": self.command(["node", "--version"]).strip(),
                "docker": self.command(
                    ["docker", "info", "--format", "{{.ServerVersion}} {{.Driver}}"]
                ).strip(),
                "context": self.command(["docker", "context", "show"]).strip(),
            },
        )
        capture, control = self.output / "capture", self.output / "control"
        capture.mkdir()
        control.mkdir(mode=0o777)
        control.chmod(0o777)
        (control / "control.json").write_text("{}")
        (control / "control.json").chmod(0o666)
        self.command(
            [
                "python3",
                str(
                    self.source
                    / "tools/acceptance/aviation-weather/generate_fixtures.py"
                ),
                str(capture),
            ]
        )
        real = Path(os.environ["ROUTE_SIGMET_REAL_CAPTURE"])
        if (
            hashlib.sha256((real / "isigmet.geojson").read_bytes()).hexdigest()
            != REAL_SHA
        ):
            raise ValueError("Pinned real source changed")
        shutil.copytree(real, self.output / "real-source")
        shutil.copyfile(real / "isigmet.geojson", capture / "real-sigmets.json")
        shutil.copyfile(real / "capture.json", capture / "real-manifest.json")
        self.command([*self.compose, "config"], name="compose")
        self.allocated = True
        self.command([*self.compose, "build", "--no-cache"], seconds=1200, name="build")
        bind_browser_source(candidate, self.root / "frontend/mission-planner")
        self.release_ports()
        self.command(
            [
                *self.compose,
                "up",
                "-d",
                "--no-build",
                "--wait",
                "--wait-timeout",
                "180",
            ],
            seconds=300,
            name="start",
        )
        self.command(
            [
                "docker",
                "image",
                "inspect",
                f"{self.project}-backend:{self.sha}",
                f"{self.project}-frontend:{self.sha}",
                "--format",
                "{{.RepoTags}} {{.Id}}",
            ],
            name="images",
        )
        self.env["PLAYWRIGHT_JSON_OUTPUT_FILE"] = str(
            self.output / "browser-results.json"
        )
        self.command(
            [
                "node",
                str(candidate / "node_modules/@playwright/test/cli.js"),
                "test",
                "--config",
                str(candidate / "playwright.aviation-acceptance.config.ts"),
                "aviation-weather-production.spec.ts",
                "route-sigmets-production.spec.ts",
            ],
            seconds=600,
            cwd=candidate,
            name="browser",
        )
        results = json.loads((self.output / "browser-results.json").read_bytes())[
            "stats"
        ]
        self.proofs["browser"] = {
            "passed": results["expected"],
            "failed": results["unexpected"],
            "skipped": results["skipped"],
        }
        self.proofs["route"] = json.loads(
            (self.output / "route-sigmet-evidence.json").read_bytes()
        )
        self.proofs["real_source"] = json.loads(
            (self.output / "real-source-evidence.json").read_bytes()
        )
        self.proofs["encounter"] = json.loads(
            (self.output / "sigmet-encounter-evidence.json").read_bytes()
        )
        self.proofs["attention"] = json.loads(
            (self.output / "sigmet-attention-evidence.json").read_bytes()
        )

    def cleanup(self):
        self.release_ports()
        errors = []
        inventory = {key: [] for key in ("containers", "networks", "volumes")}
        if self.allocated:
            try:
                self.command([*self.compose, "logs", "--no-color"], name="containers")
            except (OSError, RuntimeError, TimeoutError) as error:
                errors.append(str(error))
            try:
                self.command(
                    [*self.compose, "down", "--volumes", "--remove-orphans"],
                    seconds=120,
                    name="cleanup",
                )
            except (OSError, RuntimeError, TimeoutError) as error:
                errors.append(str(error))
            try:
                inventory = self.inventory()
            except (OSError, RuntimeError, TimeoutError) as error:
                errors.append(str(error))
        self.reap()
        remaining = self.survivors(self.processes)
        ports_free = True
        for port in self.ports:
            try:
                with socket.socket() as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(("127.0.0.1", port))
            except OSError:
                ports_free = False
        if not any(inventory.values()):
            try:
                if self.source.exists():
                    shutil.rmtree(self.source)
            except OSError as error:
                errors.append(f"Source cleanup failed: {error}")
        source_absent = not self.source.exists() and not self.source.is_symlink()
        if not source_absent:
            errors.append(f"Owned source tree remains: {self.source}")
        self.proofs["cleanup"] = {
            **inventory,
            "processes": remaining,
            "ports_free": ports_free,
            "source_absent": source_absent,
            "errors": errors,
        }
        self.record("cleanup.json", self.proofs["cleanup"])


def main():
    root = Path(__file__).resolve().parents[3]
    if (
        len(sys.argv) != 3
        or not re.fullmatch("[a-f0-9]{40}", sys.argv[1])
        or not os.access(sys.argv[2], os.X_OK)
    ):
        raise SystemExit("usage: run.sh exact-SHA provisioned-browser-executable")
    sha, browser = sys.argv[1], Path(sys.argv[2])
    if subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip() != sha or subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=root
    ):
        raise SystemExit("Acceptance requires clean committed HEAD")
    owner = Runner(root, sha, browser)
    print(f"Route SIGMET acceptance evidence: {owner.output}", flush=True)

    def interrupted(signum, frame):
        raise KeyboardInterrupt(f"signal {signum}")

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, interrupted)
    failed = False
    try:
        owner.execute()
    except BaseException as error:  # noqa: BLE001 - always tear down owned runtime
        failed = True
        owner.record(
            "failure.json", {"type": type(error).__name__, "message": str(error)}
        )
        print(str(error), file=sys.stderr)
    finally:
        owner.cleanup()
        owner.record("proofs.json", owner.proofs)
    if failed:
        return 1
    require_pass(owner.proofs)
    owner.record(
        "PASS.json",
        {
            "sha": sha,
            "scope": "synthetic production controls and dated AWC replay; software WebGL; GFS source/hardware remain unverified",
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
