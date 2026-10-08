"""Read-only request cleanup and persisted-source audit in the owned backend."""

import json
import time
import socket
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
identity_checks = []
listener_checks = []
for directory in Path("/tmp/briefing-production-observations").glob(
    "customer-briefing-*"
):
    for name in ("ownership.json", "python-owner.json"):
        file = directory / name
        if not file.exists():
            continue
        owner = json.loads(file.read_text())
        records = [owner, *owner.get("workers", [])]
        if owner.get("browserPid"):
            records.append({"pid": owner["browserPid"], "start": owner["browserStart"]})
        for record in records:
            if not isinstance(record.get("pid"), int) or not record.get("start"):
                continue
            stat = Path(f"/proc/{record['pid']}/stat")
            try:
                fields = stat.read_text().split(") ")[1].split()
                alive = fields[19] == record["start"] and fields[0] != "Z"
            except OSError:
                alive = False
            identity_checks.append(
                {
                    "request": directory.name,
                    "pid": record["pid"],
                    "start": record["start"],
                    "alive": alive,
                }
            )
        listener = owner.get("listener")
        if listener:
            with socket.socket() as connection:
                connection.settimeout(0.05)
                listening = (
                    connection.connect_ex((listener["address"], listener["port"])) == 0
                )
            listener_checks.append(
                {"request": directory.name, **listener, "listening": listening}
            )
report = {
    "processes": survivors,
    "privateStaging": [str(p) for p in staging],
    "sourceHashes": sources,
    "ownedIdentityChecks": identity_checks,
    "ownedListenerChecks": listener_checks,
}
print(json.dumps(report))
if (
    survivors
    or staging
    or any(record["alive"] for record in identity_checks)
    or any(record["listening"] for record in listener_checks)
):
    raise SystemExit(1)
