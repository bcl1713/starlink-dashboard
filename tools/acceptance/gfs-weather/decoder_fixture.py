"""Measure the real disposable child; allow a labelled cancellation injection."""

import json
import os
import resource
import sys
import time
from pathlib import Path

from app.services.aviation_weather.gfs.decoder_runner import main, parent_death_guard

if __name__ == "__main__":
    start, cpu = time.monotonic(), time.process_time()
    parent_death_guard(int(sys.argv[3]))
    control = json.loads(Path("/control/control.json").read_bytes())
    if control.get("gfs_block_decode"):
        Path("/control/blocked-decoder.json").write_text(
            json.dumps({"pid": os.getpid(), "pgid": os.getpgrp()})
        )
        while True:
            time.sleep(0.05)
    main()
    with Path("/control/decoder-metrics.jsonl").open("a") as stream:
        stream.write(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "wall_seconds": time.monotonic() - start,
                    "cpu_seconds": time.process_time() - cpu,
                    "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                    "successful_decode": True,
                }
            )
            + "\n"
        )
