"""Bounded final export preservation; missing evidence never means zero loss."""

import asyncio
import json
import time
from pathlib import Path

from prepare import sha, write

COUNTERS = (
    "buffered",
    "dropped",
    "invalid",
    "failures",
    "token_evictions",
    "token_unavailable",
)


def validate_stats(stats):
    if not isinstance(stats, dict) or stats.get("runtime_boundary_drained") is not True:
        raise ValueError("backend drain unavailable")
    if any(type(stats.get(k)) is not int or stats[k] < 0 for k in COUNTERS):
        raise ValueError("backend accounting unavailable")
    if any(stats[k] for k in COUNTERS):
        raise ValueError("backend drain/loss gate")


async def preserve_backend(command, commands, root: Path, until):
    result = {
        "complete": False,
        "zero_loss": False,
        "stats": None,
        "steps": [],
        "errors": [],
        "artifacts": {},
    }
    for phase in ("stop-backend", "copy-final-backend"):
        step = next(s for s in commands if s["phase"] == phase)
        remaining = until - time.monotonic()
        record = {
            "phase": phase,
            "cap_seconds": max(0, min(step["seconds"], remaining)),
        }
        result["steps"].append(record)
        try:
            if remaining <= 0:
                raise TimeoutError("backend preservation deadline")
            await command(step["argv"], record["cap_seconds"])
            record["outcome"] = "ok"
        except (
            Exception,  # noqa: BLE001 - preservation must continue
            asyncio.CancelledError,
        ) as error:
            record["outcome"] = "unavailable"
            record["reason"] = type(error).__name__ + ": " + str(error)[:256]
            result["errors"].append(record["reason"])
    try:
        for name, cap in (("backend-stats.json", 65536), ("backend.jsonl", 33554432)):
            path = root / "backend" / name
            if path.is_symlink() or not path.is_file() or path.stat().st_size > cap:
                raise ValueError("backend artifact unavailable: " + name)
            result["artifacts"][name] = {
                "sha256": sha(path),
                "bytes": path.stat().st_size,
            }
        result["stats"] = json.loads((root / "backend/backend-stats.json").read_bytes())
        validate_stats(result["stats"])
        result["zero_loss"] = not result["errors"]
        result["complete"] = result["zero_loss"]
    except (OSError, ValueError, TypeError) as error:
        result["errors"].append(type(error).__name__ + ": " + str(error)[:256])
    write(root / "backend-preservation.json", result)
    return result
