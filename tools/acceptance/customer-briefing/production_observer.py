"""Private acceptance-only observer; never modifies renderer inputs or outputs."""

import json
import os
import signal
import time
from pathlib import Path

destination = Path("/tmp/briefing-production-observations")
destination.mkdir(exist_ok=True)
running = True


def stop(*args):
    global running
    running = False


for number in (signal.SIGINT, signal.SIGTERM):
    signal.signal(number, stop)
start = Path(f"/proc/{os.getpid()}/stat").read_text().split(") ")[1].split()[19]
(destination / "observer-owner.json").write_text(
    json.dumps({"pid": os.getpid(), "pgid": os.getpgrp(), "start": start})
)
seen = {}
while running:
    for root in Path("/tmp").glob("customer-briefing-*"):
        for name in (
            "ownership.json",
            "python-owner.json",
            "stage-progress.json",
            "render-report.json",
        ):
            source = root / name
            try:
                content = source.read_bytes()
                if seen.get(str(source)) == content:
                    continue
                data = json.loads(content)
                if name == "render-report.json":
                    for result in data.get("maps", {}).values():
                        result.pop("pngs", None)
                target = destination / root.name
                target.mkdir(exist_ok=True)
                (target / name).write_text(json.dumps(data, indent=2))
                seen[str(source)] = content
            except (OSError, ValueError):
                continue
    time.sleep(0.002)
(destination / "observer-stopped.json").write_text(json.dumps({"stopped": True}))
