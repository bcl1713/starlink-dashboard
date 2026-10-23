"""Persist Stage 5 offline entrypoint evidence under an exclusive process owner."""

import argparse
import asyncio
import ctypes
import json
import signal
import sys
from pathlib import Path

from test_stage5_qualification import FIXTURES, RUN, replay

from evidence import canonical
from owner import Owner
from run import source_identity
from verify_evidence import verify_analysis, verify_artifacts


async def qualify(output):
    if ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) != 0:
        raise RuntimeError("subreaper unavailable")
    package = Path(__file__).resolve().parents[1]
    owner = Owner(
        output,
        run=RUN,
        sources=source_identity(package.parents[2]),
        adopt_descendants=True,
    )
    results = {}
    try:
        for role in ("A", "C"):
            summary, report, _ = await asyncio.to_thread(
                replay, owner.root / (role + "-api"), role
            )
            assert summary["complete"] and report["integrity"]["complete"]
            results[role] = {
                "api_complete": True,
                "boundaries": report["boundaries"],
                "unavailable": report["unavailable"],
            }
            commands = [
                [
                    "run.py",
                    "integrate",
                    "--role",
                    role,
                    "--backend",
                    str(FIXTURES / "stage5" / (role + "-backend.jsonl")),
                    "--stats",
                    str(FIXTURES / "stage5/backend-stats.json"),
                    "--node-root",
                    str(FIXTURES / "stage5-node"),
                    "--output",
                    str(owner.root / (role + "-cli")),
                ],
                [
                    "run.py",
                    "analyze",
                    "--events",
                    str(owner.root / (role + "-cli/evidence/integration.jsonl")),
                    "--summary",
                    str(owner.root / (role + "-cli/evidence/summary.json")),
                    "--output",
                    str(owner.root / (role + "-cli-analysis.json")),
                ],
            ]
            for index, command in enumerate(commands):
                with (owner.root / (role + f"-command-{index}.log")).open("wb") as log:
                    child = owner.spawn([sys.executable, "-B", *command], stdout=log)
                    status = await asyncio.to_thread(child.wait, timeout=30)
                    if status:
                        raise RuntimeError(f"{role} command {index}: {status}")
            result = json.loads(
                (owner.root / (role + "-cli-analysis.json")).read_bytes()
            )
            cli_evidence = owner.root / (role + "-cli/evidence")
            verify_artifacts(cli_evidence)
            verify_analysis(
                result,
                [
                    json.loads(line)
                    for line in (cli_evidence / "integration.jsonl")
                    .read_text()
                    .splitlines()
                ],
            )
            assert result["integrity"]["complete"]
            results[role]["cli_complete"] = True
        (owner.root / "results.json").write_bytes(canonical(results) + b"\n")
    finally:
        await owner.close()
    if owner.manifest["status"] != "clean":
        raise RuntimeError("qualification cleanup failed")


async def main(output):
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    interrupted = [0]

    def stop(sig):
        if not interrupted[0]:
            interrupted[0] = sig
            task.cancel()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop, sig)
    try:
        await qualify(output)
    except asyncio.CancelledError:
        if not interrupted[0]:
            raise
        return 128 + interrupted[0]
    finally:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(sig)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(asyncio.run(main(parser.parse_args().output)))
