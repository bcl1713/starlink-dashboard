"""Record and bound one build/inspection command; never start an application."""

import argparse
import asyncio
import ctypes
import json
import resource
import signal
import sys
import time
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.with_name("perf391-diagnostic-integration-v1")),
)
from owner import Owner


async def main(args):
    if ctypes.CDLL(None).prctl(36, 1, 0, 0, 0):
        raise RuntimeError("subreaper unavailable")
    owner = Owner(
        args.output,
        run="synthetic-build408",
        sources={"scope": "build and stopped-image inspection"},
        adopt_descendants=True,
    )
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    started = time.monotonic()
    result = {
        "argv": args.command,
        "seconds_limit": args.seconds,
        "utc": time.strftime("%FT%TZ", time.gmtime()),
    }
    status = 1
    try:
        with (owner.root / "command.log").open("wb") as log:
            child = owner.spawn(
                ["timeout", "--kill-after=10s", str(args.seconds) + "s", *args.command],
                stdout=log,
            )
            while child.poll() is None:
                if stop.is_set() or time.monotonic() - started > args.seconds + 11:
                    raise TimeoutError("owned command interrupted or expired")
                await asyncio.sleep(0.1)
            status = child.wait()
            result["exit"] = status
    finally:
        await owner.close()
        result["wall_seconds"] = time.monotonic() - started
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        result["client_child_usage"] = {
            "user_seconds": usage.ru_utime,
            "system_seconds": usage.ru_stime,
            "max_rss_kib": usage.ru_maxrss,
        }
        result["accounting_limit"] = (
            "Client child usage excludes Docker daemon/BuildKit work; not a performance measurement."
        )
        (owner.root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return status


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--seconds", type=int, required=True)
    p.add_argument("command", nargs=argparse.REMAINDER)
    args = p.parse_args()
    sys.exit(asyncio.run(main(args)))
