"""Read-only request cleanup and persisted-source audit in the owned backend."""

import json
import time
from hashlib import sha256
from pathlib import Path

import psutil


def request_processes():
    found = []
    for process in psutil.process_iter(["pid", "cmdline", "status"]):
        try:
            command = process.info["cmdline"] or []
            if command and (
                Path(command[0]).name == "chrome-headless-shell"
                or any(
                    value.endswith("/briefing-render.mjs")
                    or value == "app.mission.exporter.customer_pdf"
                    for value in command
                )
            ):
                found.append(process.info)
        except psutil.Error:
            continue
    return found


deadline = time.monotonic() + 3
while time.monotonic() < deadline:
    survivors = request_processes()
    staging = list(Path("/tmp").glob("customer-briefing-*"))
    if not survivors and not staging:
        break
    time.sleep(0.025)
sources = {}
for root in (
    Path("data/missions"),
    Path("data/satellites"),
    Path("data/sat_coverage"),
    Path("/data/routes"),
    Path("/data/pois.json"),
):
    for file in ([root] if root.is_file() else root.rglob("*")):
        if file.is_file() and file.suffix in {".json", ".kml", ".yaml", ".geojson"}:
            sources[str(file)] = sha256(file.read_bytes()).hexdigest()
report = {
    "processes": survivors,
    "privateStaging": [str(p) for p in staging],
    "sourceHashes": sources,
}
print(json.dumps(report))
if survivors or staging:
    raise SystemExit(1)
