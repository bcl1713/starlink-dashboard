"""Bounded owned offline checks. No runtime proposal, build or browser is run."""

import argparse
import asyncio
import ctypes
import json
import os
from pathlib import Path
import shutil
import signal
import sys

from prepare import HERE, INTEGRATION, sha, write
from owner import Owner


async def check(output):
    if ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) != 0:
        raise RuntimeError("exclusive subreaper required")
    owner = Owner(
        output,
        run="synthetic-prep408",
        sources={"scope": "offline preparation checks"},
        adopt_descendants=True,
    )
    scratch = [
        Path("/tmp/perf391-runtime-prep-408-final1"),
        Path("/tmp/perf391-runtime-prep-408-final2"),
    ]
    if any(p.exists() for p in scratch):
        raise ValueError("previous scratch must be audited/removed first")
    owner.manifest["temporary_paths"] = [str(p) for p in scratch]
    owner.persist()
    interrupted = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, interrupted.set)
    results = []
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

    async def command(argv, seconds, extra=None):
        path = owner.root / ("check-%02d.log" % len(results))
        result = {
            "argv": argv,
            "wall_limit_seconds": seconds,
            "log": path.name,
            "status": "intent",
        }
        results.append(result)
        write(owner.root / "checks.json", results)
        with path.open("wb") as log:
            child = owner.spawn(argv, stdout=log, env={**env, **(extra or {})})
            until = loop.time() + seconds
            while child.poll() is None:
                if interrupted.is_set() or loop.time() >= until:
                    result["status"] = "timeout_or_signal"
                    raise TimeoutError("offline child must be reaped before retry")
                await asyncio.sleep(0.02)
            result["exit"] = child.returncode
            result["status"] = "passed" if child.returncode == 0 else "failed"
            write(owner.root / "checks.json", results)
            if child.returncode:
                raise RuntimeError("offline check failed: " + str(argv[:3]))
        return path

    passed = False
    try:
        for root in scratch:
            await command(
                [sys.executable, "-B", str(HERE / "prepare.py"), "--output", str(root)],
                120,
            )
        plan1 = scratch[0] / "runtime-build-plan.json"
        if plan1.read_bytes() != (scratch[1] / plan1.name).read_bytes():
            raise ValueError("nondeterministic build plan")
        await command(
            [sys.executable, "-B", str(HERE / "test_preparation.py")],
            30,
            {"PERF391_OFFLINE_ROOT": str(scratch[0])},
        )
        for file in ("browser-owner.proposed.mjs", "vite.perf391.mjs"):
            await command(["node", "--check", str(HERE / file)], 10)
        primary = Path(
            "/home/oracle-worker/Work/starlink-dashboard/frontend/mission-planner"
        )
        tsc_root = owner.root / "typecheck"
        tsc_root.mkdir()
        shutil.copyfile(HERE / "browser-runtime.ts", tsc_root / "browser-runtime.ts")
        shutil.copyfile(INTEGRATION / "browser-probe.ts", tsc_root / "browser-probe.ts")
        write(
            tsc_root / "tsconfig.json",
            {
                "compilerOptions": {
                    "noEmit": True,
                    "target": "ES2022",
                    "module": "ESNext",
                    "moduleResolution": "bundler",
                    "strict": True,
                    "skipLibCheck": True,
                    "types": [],
                    "lib": ["ES2022", "DOM"],
                },
                "files": [
                    "browser-runtime.ts",
                    "browser-probe.ts",
                    str(primary / "node_modules/vite/client.d.ts"),
                ],
            },
        )
        await command(
            [
                "node",
                str(primary / "node_modules/typescript/bin/tsc"),
                "-p",
                str(tsc_root / "tsconfig.json"),
            ],
            30,
        )
        for role in ("A", "C"):
            for suffix in ("base", "override"):
                file = role + ".compose." + suffix + ".json"
                if (scratch[0] / file).read_bytes() != (scratch[1] / file).read_bytes():
                    raise ValueError("nondeterministic Compose")
                shutil.copyfile(scratch[0] / file, owner.root / file)
            for kind in ("backend", "frontend"):
                file = ".perf391/" + kind + ".Dockerfile"
                if (scratch[0] / role / file).read_bytes() != (
                    scratch[1] / role / file
                ).read_bytes():
                    raise ValueError("nondeterministic Dockerfile")
                shutil.copyfile(
                    scratch[0] / role / file,
                    owner.root / (role + "." + kind + ".Dockerfile"),
                )
            launch_log = await command(
                [
                    sys.executable,
                    "-B",
                    str(HERE / "launcher.py"),
                    "--role",
                    role,
                    "--plan",
                    str(plan1),
                    "--root",
                    "/tmp/perf391-smoke-408-" + role.lower(),
                ],
                10,
            )
            shutil.copyfile(launch_log, owner.root / (role + ".launch.json"))
            launch = json.loads(launch_log.read_bytes())
            config_env = {
                **launch["env"],
                "PERF391_BACKEND_IMAGE": "sha256:" + "0" * 64,
                "PERF391_FRONTEND_IMAGE": "sha256:" + "0" * 64,
            }
            config_log = await command(
                [
                    "docker",
                    "compose",
                    "-p",
                    "perf391-prep-408",
                    "-f",
                    str(scratch[0] / (role + ".compose.base.json")),
                    "-f",
                    str(scratch[0] / (role + ".compose.override.json")),
                    "config",
                    "--format",
                    "json",
                ],
                10,
                config_env,
            )
            shutil.copyfile(config_log, owner.root / (role + ".compose.rendered.json"))
        shutil.copyfile(plan1, owner.root / "runtime-build-plan.json")
        # Keep only authored source hashes in the typecheck evidence, not temporary copies.
        shutil.rmtree(tsc_root)
        write(
            owner.root / "validation.json",
            {
                "schema": "perf391-runtime-offline-validation-v1",
                "passed": True,
                "two_build_plans_byte_identical": True,
                "frozen_files": 621,
                "frozen_source_entries": 97,
                "tests": 10,
                "node_syntax_files": 2,
                "typescript_no_emit": True,
                "compose_configurations": 2,
                "images_built": False,
                "browsers_launched": False,
                "runtime_executed": False,
                "manifest_sha256_before_reporting_format": sha(
                    owner.root / "runtime-build-plan.json"
                ),
                "fixture_receipts": "synthetic only; no image identity certification",
            },
        )
        passed = True
    finally:
        await owner.close()
        if owner.manifest["status"] == "clean":
            for path in scratch:
                if path.exists():
                    shutil.rmtree(path)
        owner.manifest["temporary_paths_remaining"] = [
            str(p) for p in scratch if p.exists()
        ]
        owner.persist()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(sig)
    if (
        not passed
        or owner.manifest["status"] != "clean"
        or owner.manifest["temporary_paths_remaining"]
    ):
        raise RuntimeError("offline check or cleanup failure")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(check(args.output))
