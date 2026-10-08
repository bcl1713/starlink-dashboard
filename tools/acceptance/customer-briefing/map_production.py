"""Task 3B: three cold integrated whole-mission runs in the final backend image."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import time
import uuid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument(
        "--development",
        action="store_true",
        help="Diagnostic only; cannot qualify the final image",
    )
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[3]
    owner = "mission-map-3b-" + uuid.uuid4().hex[:12]
    owned = {
        "owner": owner,
        "pid": os.getpid(),
        "image": args.image,
        "containers": [],
        "commands": [],
        "volumes": [],
        "networks": [],
        "listeners": [],
        "temporaryPaths": [str(evidence)],
    }

    def save():
        (evidence / "ownership.json").write_text(json.dumps(owned, indent=2))

    save()

    def command(argv, seconds=30):
        argv = ["timeout", "--kill-after=2s", f"{max(.1, seconds)}s", *argv]
        entry = {"command": argv, "pid": None, "pgid": None}
        owned["commands"].append(entry)
        save()
        with subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True
        ) as child:
            entry.update(pid=child.pid, pgid=child.pid)
            save()
            try:
                stdout, stderr = child.communicate(timeout=seconds + 3)
            finally:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait()
            entry.update(exitCode=child.returncode)
            save()
        return child.returncode, stdout.decode(), stderr.decode()

    def required(argv, seconds=30):
        code, out, err = command(argv, seconds)
        if code:
            raise RuntimeError(f"Command failed ({code}): {argv[0:3]}: {err}")
        return out

    def remove(name):
        command(["docker", "stop", "--time", "1", name], 5)
        command(["docker", "rm", "-f", name], 5)
        return not required(
            ["docker", "ps", "-aq", "--filter", f"name=^/{name}$"]
        ).strip()

    def interrupted(*_):
        raise KeyboardInterrupt("Production proof interrupted")

    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    runs, faults = [], []
    report = {
        "schema": "ProductionMapIntegrationReport/v1",
        "status": "no-go",
        "reasons": [],
        "runs": runs,
        "faults": faults,
    }
    try:
        revision = required(["git", "rev-parse", "HEAD"]).strip()
        image = json.loads(required(["docker", "image", "inspect", args.image]))[0]
        if not args.development:
            assert (
                image["Config"]["Labels"]["org.opencontainers.image.revision"]
                == revision
            ), "Image/source revision mismatch"
            assert not required(
                ["git", "status", "--porcelain"]
            ).strip(), "Final proof requires a clean committed source candidate"
        report.update(
            sourceRevision=revision,
            development=args.development,
            image={
                "id": image["Id"],
                "sizeBytes": image["Size"],
                "revision": image["Config"]["Labels"][
                    "org.opencontainers.image.revision"
                ],
            },
            hardware={
                "host": platform.node(),
                "kernel": platform.release(),
                "architecture": platform.machine(),
                "cpu": next(
                    (
                        line.split(":", 1)[1].strip()
                        for line in Path("/proc/cpuinfo").read_text().splitlines()
                        if line.startswith("model name")
                    ),
                    platform.processor(),
                ),
                "docker": required(
                    [
                        "docker",
                        "info",
                        "--format",
                        "{{.NCPU}} CPUs; {{.MemTotal}} bytes; {{.ServerVersion}}; {{.Driver}}",
                    ]
                ),
                "containerCpus": 4,
                "containerMemoryBytes": 4294967296,
                "rendering": "CPU ANGLE SwiftShader",
            },
            limits={
                "sharedStageSeconds": 60,
                "screeningSeconds": 50,
                "coldRuns": 3,
                "requestCacheHits": 0,
                "includes": [
                    "container/Python/Node/browser startup",
                    "final interval projection/markers",
                    "all primary views",
                    "PNG collection",
                    "browser/listener/request-temp/container cleanup",
                ],
            },
        )
        report["runtimeInputs"] = {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in (
                "backend/starlink-location/Dockerfile",
                "backend/starlink-location/app/mission/exporter/trial_maps.py",
                "backend/starlink-location/app/mission/exporter/trial_projection.py",
                "backend/starlink-location/tests/fixtures/customer_briefing/f08.json",
                "frontend/mission-planner/package-lock.json",
                "frontend/mission-planner/src/mission-export/render.mjs",
                "frontend/mission-planner/src/mission-export/protocol.ts",
                "frontend/mission-planner/src/mission-export/framing.ts",
                "frontend/mission-planner/src/mission-export/scene.tsx",
                "frontend/mission-planner/src/mission-export/main.tsx",
            )
        }
        for name, fault in [
            ("fault-" + fault, fault)
            for fault in ("parent-death", "startup", "texture", "context-loss", "slow")
        ] + [(f"cold-{i}", None) for i in range(1, 4)]:
            container = {"name": owner + "-" + name, "removed": False}
            owned["containers"].append(container)
            save()
            output = evidence / name
            output.mkdir()
            started = time.monotonic()
            deadline = started + (60 if fault is None else 35)
            remaining = lambda: max(0.1, deadline - time.monotonic())
            try:
                required(
                    [
                        "docker",
                        "create",
                        "--name",
                        container["name"],
                        "--label",
                        f"mission-map-owner={owner}",
                        "--init",
                        "--network",
                        "none",
                        "--cpus",
                        "4",
                        "--memory",
                        "4g",
                        "--user",
                        "1000:1000",
                        "--entrypoint",
                        "python",
                        "-e",
                        "PYTHONPATH=/app",
                        args.image,
                        "/tmp/probe.py",
                        *([fault] if fault else []),
                    ],
                    remaining(),
                )
                required(
                    [
                        "docker",
                        "cp",
                        str(Path(__file__).with_name("production_map_probe.py")),
                        container["name"] + ":/tmp/probe.py",
                    ],
                    remaining(),
                )
                exit_code, stdout, stderr = command(
                    ["docker", "start", "-a", container["name"]], remaining()
                )
                (output / "stdout.log").write_text(stdout + stderr)
                required(
                    [
                        "docker",
                        "cp",
                        container["name"] + ":/tmp/evidence/.",
                        str(output),
                    ],
                    remaining(),
                )
                run = json.loads((output / "result.json").read_text())
                run["exitCode"] = exit_code
                run["name"] = name
            finally:
                container["removed"] = remove(container["name"])
                save()
            run["elapsedSeconds"] = time.monotonic() - started
            run["marginSeconds"] = 60 - run["elapsedSeconds"]
            run["cleanupVerified"] = run["cleanupVerified"] and container["removed"]
            for view in run["views"]:
                view["pngHash"] = hashlib.sha256(
                    (output / view["filename"]).read_bytes()
                ).hexdigest()
            (output / "stage.json").write_text(json.dumps(run, indent=2))
            (faults if fault else runs).append(run)
            print(
                f'{name}: {run["status"]}, {run["elapsedSeconds"]:.3f}s, {len(run["views"])} views, cleanup {run["cleanupVerified"]}',
                flush=True,
            )
            assert (
                run["exitCode"] == 0 and run["cleanupVerified"]
            ), f"{name}: integration/cleanup failed; inspect stdout.log"
            if fault == "parent-death":
                assert run[
                    "parentDeathVerified"
                ], "Renderer owner death leaked resources"
            elif fault:
                assert all(
                    result["status"] == "static" for result in run["results"]
                ), f"{name}: labeled static fallback missing"
            else:
                assert (
                    run["status"] == "primary" and run["elapsedSeconds"] <= 50
                ), f"{name}: 50-second primary map screen failed"
                assert run["uid"] == 1000, "Production renderer must run as appuser"
                assert (
                    run["backendSourceDigest"]
                    == report["runtimeInputs"][
                        "backend/starlink-location/app/mission/exporter/trial_maps.py"
                    ]
                ), "Production backend/source mismatch"
                for source, digest in run["renderer"]["runtime"][
                    "sourceDigests"
                ].items():
                    assert (
                        report["runtimeInputs"][source] == digest
                    ), f"Production renderer/source mismatch: {source}"
                for view, rendered in zip(run["views"], run["renderer"]["views"]):
                    assert (
                        view["pngHash"] == rendered["pngHash"]
                    ), "Collected PNG mismatch"
        assert len(runs) == 3
        report["status"] = "development-pass" if args.development else "pass"
    except (Exception, KeyboardInterrupt) as err:
        report["reasons"].append(str(err))
    finally:
        for container in owned["containers"]:
            if not container["removed"]:
                container["removed"] = remove(container["name"])
        report["cleanup"] = {
            "containersGone": not required(
                ["docker", "ps", "-aq", "--filter", f"label=mission-map-owner={owner}"]
            ).strip(),
            "volumes": [],
            "networks": [],
            "hostListeners": [],
        }
        if not report["cleanup"]["containersGone"]:
            report["status"] = "no-go"
            report["reasons"].append("Owned containers remain")
        save()
        (evidence / "ProductionMapIntegrationReport.json").write_text(
            json.dumps(report, indent=2)
        )
    print("Task 3B: " + report["status"], flush=True)
    return 0 if report["status"] in {"pass", "development-pass"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
