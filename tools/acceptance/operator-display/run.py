"""Issue 376 display proof using existing source fixtures and the real worker.

This writes only a display proof, never the pinned-source GFS foundation PASS.
"""

import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def synthetic_sources(destination):
    """Existing actual-GRIB fixture; only upstream source bytes are synthetic."""
    sys.path.insert(0, str(ROOT / "backend/starlink-location"))
    from tests.fixtures.gfs_fields import grib_bundle

    bundle = grib_bundle(destination)
    offset, lines = 0, []
    tokens = {
        "u": "UGRD:500 mb",
        "v": "VGRD:500 mb",
        "t": "TMP:500 mb",
        "sp": "PRES:surface",
    }
    for index, path in enumerate(bundle.paths, 1):
        lines.append(f"{index}:{offset}:d=2026100600:{tokens[path.stem]}:6 hour fcst:")
        offset += path.stat().st_size
    lines.append(f"5:{offset}:d=2026100600:HGT:surface:6 hour fcst:")
    (destination / "source.idx").write_text("\n".join(lines) + "\n")
    (destination / "oracles.json").write_text("[]")
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [*bundle.paths, destination / "source.idx"]
    }


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    if len(sys.argv) != 3:
        raise SystemExit("run.py exact-SHA existing-browser")
    foundation = module(
        "operator_display_weather_owner",
        ROOT / "tools/acceptance/gfs-weather/runner.py",
    )
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT))
    foundation.preflight(sys.argv[1], Path(sys.argv[2]), head, dirty)
    foundation.PROJECT = "starlink-operator-display-376"
    foundation.PORTS = (56540, 56541)
    runner = foundation.Runner(ROOT, head, Path(sys.argv[2]))
    runner.mode = "operator-display-synthetic-sources"
    sys.path.insert(0, str(ROOT / "tools/acceptance/operator-journal"))
    from ownership import Owner, group_alive

    relay = Owner(runner.project, runner.output / "relay-owner")
    relay.ownership.update(
        volumes=[], images=[], fixture="issue376 display proof loopback relay"
    )
    relay.persist()
    report = {
        "candidateSha": head,
        "scope": "Issue376 display visibility only; synthetic upstream sources; real GRIB decoder, worker, APIs and rendering; software SwiftShader",
        "checksPassed": False,
    }
    print(f"Display evidence: {runner.output}", flush=True)

    def interrupted(signum, _frame):
        raise InterruptedError(f"signal {signum}")

    handlers = {
        number: signal.signal(number, interrupted)
        for number in (signal.SIGTERM, signal.SIGINT)
    }
    try:
        source = runner.output / "synthetic-source-inputs"
        foundation.SOURCE_HASHES = synthetic_sources(source)
        runner.env["GFS_ACCEPTANCE_SOURCE_DIR"] = str(source)
        os.environ["GFS_ACCEPTANCE_SOURCE_DIR"] = str(source)
        runner.prepare()
        epoch = 1791266400000
        runner.command(
            [
                "python3",
                "-c",
                "import sys; from pathlib import Path; from runpy import run_path; run_path(sys.argv[1])['generate'](Path(sys.argv[2]),int(sys.argv[3]))",
                str(
                    runner.source
                    / "tools/acceptance/aviation-weather/generate_fixtures.py"
                ),
                str(runner.output / "capture"),
                str(epoch),
            ]
        )
        control = runner.output / "control/control.json"
        control.write_text(
            json.dumps(
                {
                    "replay_utc_ms": epoch,
                    "replay_monotonic": time.monotonic(),
                    "frame": epoch // 1000 - 120,
                }
            )
        )
        control.chmod(0o666)
        runner.record(
            "source-label.json",
            {
                "synthetic": True,
                "generator": "existing tests.fixtures.gfs_fields.grib_bundle",
                "hashes": foundation.SOURCE_HASHES,
                "epoch_ms": epoch,
            },
        )
        runner.record(
            "compose.json",
            json.loads(
                runner.command([*runner.compose, "config", "--format", "json"]).stdout
            ),
        )
        runner.command([*runner.compose, "build"], seconds=1200, name="build.log")
        images = []
        for kind in ("backend", "frontend", "worker"):
            inspected = json.loads(
                runner.command(
                    ["docker", "image", "inspect", f"{runner.project}-{kind}:{head}"]
                ).stdout
            )[0]
            assert (
                inspected["Config"]["Labels"]["org.opencontainers.image.revision"]
                == head
            )
            images.append({"kind": kind, "id": inspected["Id"], "revision": head})
        runner.record("images.json", images)
        runner.allocated = True
        runner.command(
            [
                *runner.compose,
                "up",
                "-d",
                "--no-build",
                "--wait",
                "--wait-timeout",
                "180",
                "mission-planner",
                "prometheus",
                "gfs-worker",
            ],
            seconds=300,
            name="start.log",
        )
        runner.bind_browser()
        container = runner.command(
            [*runner.compose, "ps", "-q", "mission-planner"]
        ).stdout.strip()
        relay.env.update(
            runner.env,
            OPERATOR_SOURCE_ROOT=str(runner.source),
            OPERATOR_ACCEPTANCE_PORT=str(runner.ports[0]),
        )
        relay.start_relay(container)
        runner.command(
            [
                "timeout",
                "--kill-after=10s",
                "17m",
                "npx",
                "--no-install",
                "playwright",
                "test",
                "--config",
                "playwright.operator-display.config.ts",
            ],
            seconds=1040,
            cwd=runner.source / "frontend/mission-planner",
            name="browser.log",
        )
        report["checksPassed"] = True
    except BaseException as error:
        report["error"] = str(error)
        raise
    finally:
        try:
            if relay.relay is not None:
                relay.child = relay.relay
                relay.stop_child()
                relay.ownership["relay"].update(
                    reaped=True,
                    returncode=relay.relay.returncode,
                    groupRemaining=group_alive(relay.relay.pid),
                )
                relay.persist()
                report["relayRemaining"] = group_alive(relay.relay.pid)
        finally:
            try:
                runner.cleanup()
                report["cleanup"] = runner.proofs["cleanup"]
                cleanup = report["cleanup"]
                if (
                    report.get("relayRemaining")
                    or not cleanup["ports_free"]
                    or any(
                        cleanup[key]
                        for key in (
                            "containers",
                            "networks",
                            "volumes",
                            "processes",
                            "errors",
                        )
                    )
                ):
                    report["checksPassed"] = False
                    raise RuntimeError(
                        "Owned display resources remain; inspect cleanup evidence"
                    )
            finally:
                runner.record("operator-display-summary.json", report)
                for number, handler in handlers.items():
                    signal.signal(number, handler)
                print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
