"""Exact-head isolated foundation acceptance; PASS is written after cleanup."""

import hashlib
import importlib.util
import json
import math
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from acceptance.platform.evidence import prepare_evidence_parent, write_artifacts
from acceptance.platform.model import validate_candidate_inputs

PROJECT = "starlink-290-gfs-foundation"
PORTS = (15292, 18292)
VOLUMES = [
    "missions",
    "settings",
    "satellites",
    "coverage",
    "routes",
    "simulation-routes",
    "pois",
    "metrics",
    "gfs_products",
    "gfs_mailbox",
]
REQUIRED_PROOFS = (
    "browser_regression",
    "successful_decode",
    "nginx_buffers",
    "source_oracles",
    "disable_ack",
    "cancelled_decoder",
    "killed_decoder_denial",
    "version_mismatch",
    "core_health",
    "disabled_denial",
    "metrics",
    "cleanup",
)
SOURCE_HASHES = {
    "source.idx": "3e2b4b7b102978fe691f7099b66300aa923956c0b0e64582faa6f60ee9e2efbc",
    "t.grib2": "215804bc167ffca0ac7b3eaf4c1d0ddcd458f3f83990da9b0f49a25335a527a8",
    "u.grib2": "f806169b770684ca6282f099822d9defce58e9172d417481be770b75ff47ab47",
    "v.grib2": "17e7c01cdc7fc06d6be2398b0626b2cae0d444320a2856c1f36cc24c4d52c3c5",
    "sp.grib2": "d7efce7d707f7ba942667e500fc42bd36c69c0e9d44a3e3a5d9921d89a42713e",
}


def preflight(sha, browser, head, dirty):
    validate_candidate_inputs(sha, "foundation")
    if sha != head or dirty:
        raise ValueError("Acceptance requires clean committed HEAD")
    if not browser.is_file() or not os.access(browser, os.X_OK):
        raise ValueError("An existing provisioned browser executable is required")


def require_pass(proofs):
    if any(not proofs.get(key) for key in REQUIRED_PROOFS):
        raise ValueError("incomplete foundation evidence")
    metrics = proofs["metrics"]
    if any(
        not isinstance(metrics.get(key), (int, float))
        or not math.isfinite(metrics[key])
        or metrics[key] <= 0
        for key in ("cpu_usec", "memory_peak", "disk_bytes", "network_bytes")
    ):
        raise ValueError("incomplete foundation measurements")
    cleanup = proofs["cleanup"]
    if (
        cleanup.get("errors")
        or not cleanup.get("ports_free")
        or any(
            cleanup.get(kind) != []
            for kind in ("containers", "networks", "volumes", "processes")
        )
    ):
        raise ValueError("incomplete foundation cleanup")


def process_table():
    result = {}
    for directory in Path("/proc").iterdir():
        if not directory.name.isdecimal():
            continue
        try:
            fields = (directory / "stat").read_text().split(")", 1)[1].split()
            result[int(directory.name)] = (int(fields[1]), fields[19])
        except (OSError, ValueError, IndexError):
            continue
    return result


def ports_available(ports=PORTS):
    try:
        for port in ports:
            with socket.socket() as sock:
                # Closed TCP TIME_WAIT connections are not live listeners.
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False


class Runner:
    def __init__(self, root, sha, browser):
        self.root, self.sha, self.browser = root, sha, browser
        parent = root / "test-results/gfs-foundation" / str(time.time_ns())
        prepare_evidence_parent(parent)
        self.output = parent / sha
        self.output.mkdir()
        self.source = Path(tempfile.mkdtemp(prefix="starlink-290-gfs-source."))
        self.proofs, self.owned_processes = {}, {}
        self.allocated = False
        self.env = {
            **os.environ,
            "ACCEPTANCE_CANDIDATE_SHA": sha,
            "AVIATION_ACCEPTANCE_BROWSER": str(browser),
            "WEATHER_ACCEPTANCE_PROJECT": PROJECT,
            "WEATHER_ACCEPTANCE_SOURCE_ROOT": str(self.source),
            "WEATHER_ACCEPTANCE_OUTPUT_DIR": str(self.output),
            "WEATHER_ACCEPTANCE_CONTROL_DIR": str(self.output / "control"),
            "WEATHER_ACCEPTANCE_CONTROL_PATH": str(
                self.output / "control/control.json"
            ),
            "WEATHER_ACCEPTANCE_CAPTURE_DIR": str(self.output / "capture"),
            "WEATHER_ACCEPTANCE_FRONTEND_PORT": str(PORTS[0]),
            "WEATHER_ACCEPTANCE_BACKEND_PORT": str(PORTS[1]),
            "WEATHER_ACCEPTANCE_BASE_URL": f"http://127.0.0.1:{PORTS[0]}",
            "WEATHER_ACCEPTANCE_MODE": "aviation",
        }
        self.compose = ["docker", "compose", "-p", PROJECT]
        for name in ("overview-weather", "aviation-weather", "gfs-weather"):
            self.compose.extend(
                ["-f", str(root / f"tools/acceptance/{name}/compose.yml")]
            )
        self.record(
            "runtime-owner.json",
            {
                "command": sys.argv,
                "pid": os.getpid(),
                "pgid": os.getpgrp(),
                "project": PROJECT,
                "ports": PORTS,
                "private_volumes": VOLUMES,
                "source_root": str(self.source),
                "output_root": str(self.output),
            },
        )

    def record(self, name, value):
        (self.output / name).write_text(json.dumps(value, indent=2))

    def command(self, argv, *, seconds=60, name=None, cwd=None, allow_failure=False):
        # Save intent before allocation; retain verified PID/start-time identity.
        log = self.output / (name or f"command-{time.time_ns()}.log")
        self.record(
            "active-command.json",
            {"command": argv, "log": str(log), "state": "starting"},
        )
        with log.open("wb") as stream:
            process = subprocess.Popen(
                argv,
                cwd=cwd or self.root,
                env=self.env,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            self.record(
                "active-command.json",
                {
                    "command": argv,
                    "pid": process.pid,
                    "pgid": process.pid,
                    "log": str(log),
                },
            )
            started = time.monotonic()
            try:
                while process.poll() is None:
                    table = process_table()
                    selected = {process.pid}
                    while True:
                        children = {
                            pid
                            for pid, (parent, _) in table.items()
                            if parent in selected
                        }
                        if children <= selected:
                            break
                        selected |= children
                    self.owned_processes.update(
                        {pid: table[pid][1] for pid in selected if pid in table}
                    )
                    if time.monotonic() - started > seconds:
                        raise TimeoutError(f"Command exceeded {seconds}s: {argv[:4]}")
                    time.sleep(0.1)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                self.record("process-ownership.json", self.owned_processes)
        result = subprocess.CompletedProcess(
            argv, process.returncode, log.read_text(errors="replace")
        )
        if result.returncode and not allow_failure:
            raise RuntimeError(f"Failed {argv[:5]}: {result.stdout[-2000:]}")
        return result

    def worker_command(self, argv, **kwargs):
        return self.command(
            [*self.compose, "exec", "-T", "gfs-worker", *argv], **kwargs
        )

    def worker_json(self, path, missing=None):
        result = self.worker_command(["cat", path], allow_failure=missing is not None)
        return missing if result.returncode else json.loads(result.stdout)

    def inventory(self):
        commands = {
            "containers": ["docker", "ps", "-aq"],
            "networks": ["docker", "network", "ls", "-q"],
            "volumes": ["docker", "volume", "ls", "-q"],
        }
        return {
            kind: self.command(
                [*argv, "--filter", f"label=com.docker.compose.project={PROJECT}"]
            ).stdout.split()
            for kind, argv in commands.items()
        }

    def prepare(self):
        if any(self.inventory().values()):
            raise ValueError("Existing acceptance project; ownership refused")
        if not ports_available():
            raise ValueError("Acceptance ports already have listeners")
        archive = self.command(
            [
                "git",
                "archive",
                "--format=tar",
                "-o",
                str(self.source / "source.tar"),
                self.sha,
            ]
        )
        assert archive.returncode == 0
        self.command(
            ["tar", "-xf", str(self.source / "source.tar"), "-C", str(self.source)]
        )
        (self.source / "source.tar").unlink()
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
        destination = capture / "gfs"
        destination.mkdir()
        source = Path(os.environ["GFS_ACCEPTANCE_SOURCE_DIR"])
        objects = []
        index = (source / "source.idx").read_text().splitlines()
        names = {
            "u": ":UGRD:500 mb:",
            "v": ":VGRD:500 mb:",
            "t": ":TMP:500 mb:",
            "sp": ":PRES:surface:",
        }
        for name, digest in SOURCE_HASHES.items():
            body = (source / name).read_bytes()
            if hashlib.sha256(body).hexdigest() != digest:
                raise ValueError(f"Pinned source changed: {name}")
            (destination / name).write_bytes(body)
            quantity = name.split(".")[0]
            ranges = None
            if name != "source.idx":
                matching = [
                    i for i, line in enumerate(index) if names[quantity] in line
                ]
                assert len(matching) == 1
                entry = matching[0]
                ranges = [
                    int(index[entry].split(":")[1]),
                    int(index[entry + 1].split(":")[1]) - 1,
                ]
                assert ranges[1] - ranges[0] + 1 == len(body)
            objects.append({"filename": name, "sha256": digest, "range": ranges})
        (destination / "manifest.json").write_text(json.dumps({"objects": objects}))
        shutil.copyfile(source / "oracles.json", destination / "oracles.json")
        self.record(
            "candidate.json",
            {
                "sha": self.sha,
                "source_hashes": SOURCE_HASHES,
                "browser": str(self.browser),
                "browser_sha256": hashlib.sha256(self.browser.read_bytes()).hexdigest(),
                "browser_version": self.command(
                    [str(self.browser), "--version"]
                ).stdout.strip(),
                "rendering": "software SwiftShader; fixture-source historical replay",
                "acceptance_scope": "GFS foundation; presentation not accepted",
                "docker_host": os.environ.get("DOCKER_HOST", "active-context"),
            },
        )

    def execute(self):
        self.prepare()
        config = self.command(
            [*self.compose, "config", "--format", "json"], name="compose.log"
        )
        self.record("compose.json", json.loads(config.stdout))
        self.command([*self.compose, "build"], seconds=1200, name="build.log")
        images = []
        for kind in ("backend", "frontend", "worker"):
            inspected = json.loads(
                self.command(
                    ["docker", "image", "inspect", f"{PROJECT}-{kind}:{self.sha}"]
                ).stdout
            )[0]
            assert (
                inspected["Config"]["Labels"]["org.opencontainers.image.revision"]
                == self.sha
            )
            images.append({"kind": kind, "id": inspected["Id"], "revision": self.sha})
        self.record("images.json", images)
        self.allocated = True
        self.command(
            [
                *self.compose,
                "up",
                "-d",
                "--no-build",
                "--wait",
                "--wait-timeout",
                "180",
                "mission-planner",
                "prometheus",
            ],
            seconds=300,
            name="start.log",
        )
        self.command(
            [
                "npx",
                "playwright",
                "test",
                "--config",
                "playwright.aviation-acceptance.config.ts",
            ],
            cwd=self.root / "frontend/mission-planner",
            seconds=600,
            name="browser.log",
        )
        self.proofs["browser_regression"] = True
        # Historical replay starts on fresh private volumes. Production rollback
        # protection correctly remembers the native browser phase's later UTC.
        self.command(
            [*self.compose, "down", "--volumes", "--remove-orphans"],
            seconds=90,
            name="browser-phase-cleanup.log",
        )
        assert not any(self.inventory().values())
        (self.output / "control/control.json").write_text(
            json.dumps(
                {
                    "replay_utc_ms": 1791288447620,
                    "frame": 1791288327,
                    "replay_monotonic": time.monotonic(),
                }
            )
        )
        (self.output / "control/control.json").chmod(0o666)
        # New clock authorities; production rollback guards remain active.
        self.command(
            [
                *self.compose,
                "up",
                "-d",
                "--no-build",
                "--wait",
                "--wait-timeout",
                "180",
                "mission-planner",
                "prometheus",
            ],
            seconds=300,
            name="replay-start.log",
        )
        self.command(
            [*self.compose, "up", "-d", "--no-build", "gfs-worker"],
            seconds=60,
            name="worker-start.log",
        )
        spec = importlib.util.spec_from_file_location(
            "foundation_controls",
            self.root / "tools/acceptance/gfs-weather/check_foundation.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.run(self)
        container = self.command(
            [*self.compose, "ps", "-q", "gfs-worker"]
        ).stdout.strip()
        inspected = json.loads(self.command(["docker", "inspect", container]).stdout)[0]
        assert inspected["HostConfig"]["Memory"] == 1024**3
        assert inspected["HostConfig"]["NanoCpus"] == 10**9
        metrics = self.worker_command(
            [
                "python",
                "-c",
                "import json,pathlib; p=pathlib.Path('/sys/fs/cgroup'); print(json.dumps({n:(p/n).read_text() for n in ['cpu.stat','cpu.max','memory.peak','memory.max','memory.events']}))",
            ]
        )
        raw = json.loads(metrics.stdout)
        self.record("worker-cgroup.json", raw)
        cpu = int(
            dict(line.split() for line in raw["cpu.stat"].splitlines())["usage_usec"]
        )
        disk = int(
            self.worker_command(["du", "-sb", "/app/data/gfs"]).stdout.split()[0]
        )
        events = [
            json.loads(line)
            for line in (self.output / "control/gfs-events.jsonl")
            .read_text()
            .splitlines()
        ]
        peak = int(raw["memory.peak"])
        assert 0 < peak < 1024**3 and "oom_kill 0" in raw["memory.events"]
        self.proofs["metrics"] = {
            "cpu_usec": cpu,
            "memory_peak": peak,
            "disk_bytes": disk,
            "network_bytes": sum(event["bytes"] for event in events),
        }

    def cleanup(self):
        errors = []
        if self.allocated:
            for args, kwargs in (
                (
                    ["logs", "--no-color"],
                    {"name": "containers.log", "allow_failure": True},
                ),
                (
                    ["down", "--volumes", "--remove-orphans"],
                    {"seconds": 90, "name": "cleanup.log"},
                ),
            ):
                try:
                    self.command([*self.compose, *args], **kwargs)
                except (OSError, RuntimeError, TimeoutError) as error:
                    errors.append(str(error))
        table = process_table()
        survivors = [
            pid
            for pid, identity in self.owned_processes.items()
            if pid in table and table[pid][1] == identity
        ]
        for pid in survivors:
            os.kill(pid, signal.SIGTERM)
        if survivors:
            time.sleep(2)
            table = process_table()
            for pid in survivors:
                if pid in table and table[pid][1] == self.owned_processes[pid]:
                    os.kill(pid, signal.SIGKILL)
            time.sleep(0.2)
        table = process_table()
        remaining = [
            pid
            for pid, identity in self.owned_processes.items()
            if pid in table and table[pid][1] == identity
        ]
        ports_free = False
        for _ in range(30):
            if ports_available():
                ports_free = True
                break
            time.sleep(1)
        inventory = self.inventory()
        if not any(inventory.values()):
            shutil.rmtree(self.source)
        self.proofs["cleanup"] = {
            **inventory,
            "processes": remaining,
            "ports_free": ports_free,
            "errors": errors,
        }
        self.record("cleanup.json", self.proofs["cleanup"])
        if errors:
            raise RuntimeError("Foundation cleanup failed: " + "; ".join(errors))


def main():
    if len(sys.argv) != 4 or sys.argv[3] != "foundation":
        raise SystemExit("usage: run.sh exact-SHA provisioned-browser foundation")
    root = Path(__file__).resolve().parents[3]
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    dirty = bool(
        subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"], cwd=root
        )
    )
    preflight(sys.argv[1], Path(sys.argv[2]), head, dirty)
    runner = Runner(root, sys.argv[1], Path(sys.argv[2]))
    print(f"Foundation evidence: {runner.output}", flush=True)

    def interrupted(signum, frame):
        raise KeyboardInterrupt(f"signal {signum}")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    error = None
    try:
        runner.execute()
    except BaseException as caught:  # noqa: BLE001 - cleanup before propagating
        error = caught
        runner.record(
            "failure.json", {"type": type(caught).__name__, "message": str(caught)}
        )
    finally:
        runner.cleanup()
        runner.record("proofs.json", runner.proofs)
    if error:
        raise error
    require_pass(runner.proofs)
    # Use the shared no-follow inventory authority only after resource cleanup.
    write_artifacts(
        runner.output,
        {
            "PASS.json": json.dumps(
                {
                    "sha": runner.sha,
                    "scope": "foundation",
                    "labels": "historical source replay; software rendering",
                }
            ).encode()
        },
    )
    print(f"Foundation PASS: {runner.output}", flush=True)


if __name__ == "__main__":
    main()
