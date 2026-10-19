"""Read-only facts for the marked private archive exercise, never journal commands."""

from urllib.parse import quote, urlencode


def _ordered(rows):
    return sorted(rows, key=lambda row: (row["record_id"], row["version"]))


def _catalog_revision(missions):
    # The list API constructs ID-only leg stubs with default_factory timestamps
    # on each read (storage.load_mission_metadata_v2). They are not saved edits.
    return sorted(
        [
            dict(
                mission,
                legs=[
                    {
                        key: value
                        for key, value in leg.items()
                        if key not in {"created_at", "updated_at"}
                    }
                    for leg in mission.get("legs", [])
                ],
            )
            for mission in missions
        ],
        key=lambda mission: mission["id"],
    )


def read_snapshot(get, mission_id=None):
    """Read complete ordinary pages at one H and reject identity rotation."""
    health = get("/api/v2/operator/health")
    if (
        not health.get("ready")
        or health.get("source_mode") != "simulation"
        or health.get("clock_regression")
    ):
        raise ValueError("Ready private simulation store required")
    missions = get("/api/v2/missions")
    if not isinstance(missions, list):
        raise TypeError("Complete private mission list required")
    # This course owns one source mission and at most two import copies. The
    # ordinary list defaults to ten: never call a possibly full page complete.
    if len(missions) >= 10:
        raise ValueError("Private mission catalog exceeds the complete course boundary")
    boundary = None

    def pages(path):
        nonlocal boundary
        rows, cursors, cursor = [], set(), None
        while True:
            url = path + (
                ("&" if "?" in path else "?") + urlencode({"cursor": cursor})
                if cursor
                else ""
            )
            page = get(url)
            H = page.get("H")
            if type(H) is not int or H < 0 or (boundary is not None and H != boundary):
                raise ValueError(
                    "Journal boundary changed during private evidence read"
                )
            boundary = H
            rows.extend(item["record"] for item in page["items"])
            cursor = page["cursor"]
            if not cursor:
                return rows
            if not isinstance(cursor, str) or cursor in cursors or len(cursors) >= 100:
                raise ValueError("Private evidence pagination did not finish")
            cursors.add(cursor)

    # The ordinary API requires a mission filter. Read every catalog mission at
    # one global H, including removed rows. An empty private store still needs
    # a valid filtered read to observe H=0 rather than inventing that boundary.
    mission_ids = [mission_id] if mission_id else [item["id"] for item in missions]
    records = []
    for selected in mission_ids or ["operator-training-empty-destination"]:
        query = {"include_removed": "true", "mission_id": selected}
        records.extend(pages("/api/v2/operator/records?" + urlencode(query)))
    history = []
    for row in records:
        history.extend(
            pages(
                "/api/v2/operator/records/"
                + quote(row["record_id"], safe="")
                + "/history"
            )
        )
    if _catalog_revision(get("/api/v2/missions")) != _catalog_revision(missions):
        raise ValueError("Private mission list changed during evidence read")
    if get("/api/v2/operator/health") != health:
        raise ValueError("Private store identity changed during evidence read")
    return {
        "health": health,
        "H": boundary,
        "records": _ordered(records),
        "history": _ordered(history),
        "missions": missions,
    }


def archive_boundary(source, journal):
    """Reconstruct the archive boundary from actual backend history, not ZIP claims."""
    health = source["health"]
    H = journal.get("high_water")
    if (
        type(H) is not int
        or H < 0
        or H > source["H"]
        or any(
            journal.get(key) != health.get(key)
            for key in ("store_id", "source_mode", "simulation_run_id")
        )
    ):
        raise ValueError("Archive does not match the private journal boundary")
    history = [
        row
        for row in source["history"]
        if row["mission_id"] == journal["mission_id"] and row["journal_seq"] <= H
    ]
    versions = {}
    for row in history:
        key = (row["record_id"], row["version"])
        if key in versions and versions[key] != row:
            raise ValueError("Contradictory backend history")
        versions[key] = row
    latest = {}
    for row in versions.values():
        if (
            row["record_id"] not in latest
            or latest[row["record_id"]]["version"] < row["version"]
        ):
            latest[row["record_id"]] = row
    records = _ordered(latest.values())
    if records != _ordered(journal["current_records"]):
        raise ValueError("Archived current records differ from actual backend history")
    return {
        "health": health,
        "H": H,
        "records": records,
        "history": _ordered(versions.values()),
    }


def unchanged_destination(before, after):
    """Keep distinct raw reads; a post-import success flag cannot establish this."""
    if (
        before["health"] != after["health"]
        or before["H"] != after["H"]
        or _ordered(before["records"]) != _ordered(after["records"])
        or _ordered(before["history"]) != _ordered(after["history"])
    ):
        raise ValueError("Destination Operator identity or immutable journal changed")
    return {"before": before, "after": after}


def installed_generation(before, after, mission_id):
    prior = next(
        (row for row in before["planFiles"] if row["mission_id"] == mission_id), None
    )
    current = next(
        (row for row in after["planFiles"] if row["mission_id"] == mission_id), None
    )
    if current is None:
        return False
    if prior is None:
        return True
    return (
        prior["device"] == current["device"]
        and prior["sha256"] == current["sha256"]
        and prior["size"] == current["size"]
        and (
            prior["inode"] != current["inode"]
            or prior["modifiedNs"] != current["modifiedNs"]
        )
    )


def loopback_reader(port, *, deadline=None):
    import http.client
    import json
    import time

    deadline = deadline or time.monotonic() + 240
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("Recorded private loopback port required")

    def get(path, *, binary=False):
        if binary:
            import re

            if not re.fullmatch(
                r"/api/v2/missions/[^/?]+/export-preparations/[0-9a-f]{32}/download",
                path,
            ):
                raise ValueError("Existing ready artifact download path required")
        if not path.startswith("/api/v2/") or "\r" in path or "\n" in path:
            raise ValueError("Normal private API path required")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Private evidence read exceeded its four-minute bound")
        connection = http.client.HTTPConnection(
            "127.0.0.1", port, timeout=min(15, remaining)
        )
        try:
            connection.request("GET", path)
            response = connection.getresponse()
            if response.status != 200:
                raise ValueError(f"Private API read unavailable ({response.status})")
            limit = (64 if binary else 16) * 1024 * 1024
            body = response.read(limit + 1)
            if len(body) > limit:
                raise ValueError("Private evidence response exceeds its read bound")
            return body if binary else json.loads(body)
        finally:
            connection.close()

    return get


def browser_origin(value):
    from urllib.parse import urlsplit

    parts = urlsplit(value)
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
    ):
        raise ValueError("Use the private browser origin without path or credentials")
    return f"{parts.scheme}://{parts.netloc}"


# This opens the existing preparation database read-only and hashes its existing
# ready artifact. It starts no service, creates no schema and generates no ZIP.
PLAN_FILES_READ = """
import hashlib, importlib.util, json, sys
from pathlib import Path
from app.mission import storage
spec = importlib.util.spec_from_file_location("training_plan_guard", "/source/tools/training/operator-mission/scenario.py")
scenario = importlib.util.module_from_spec(spec); spec.loader.exec_module(scenario)
if scenario.training_namespace(Path("/app/data"), mode="simulation") != sys.argv[1]:
    raise ValueError("Private destination namespace changed")
ids = json.loads(sys.argv[2])
if len(ids) >= 10 or len(set(ids)) != len(ids):
    raise ValueError("Complete bounded private catalog required")
facts = []
for mission_id in ids:
    path = storage.get_mission_file_path(mission_id)
    if path.is_symlink() or not path.resolve().is_relative_to(storage.MISSIONS_DIR.resolve()):
        raise ValueError("Owned private plan file required")
    before = path.stat()
    if before.st_size > 16 * 1024 * 1024:
        raise ValueError("Private plan file exceeds read boundary")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size) != (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size):
        raise ValueError("Installed plan changed during generation read")
    facts.append({"mission_id": mission_id, "device": str(after.st_dev), "inode": str(after.st_ino),
                  "modifiedNs": str(after.st_mtime_ns), "sha256": digest, "size": after.st_size})
print(json.dumps(facts))
"""


PREPARATION_READ = """
import hashlib, importlib.util, json, re, sqlite3, sys
from pathlib import Path
from app.mission import storage
from app.mission.package.preparation_store import ExportPreparation
spec = importlib.util.spec_from_file_location("training_read_guard", "/source/tools/training/operator-mission/scenario.py")
scenario = importlib.util.module_from_spec(spec); spec.loader.exec_module(scenario)
if scenario.training_namespace(Path("/app/data"), mode="simulation") != sys.argv[1]:
    raise ValueError("Private source namespace changed")
cache = storage.MISSIONS_DIR / ".slide-cache" / "slides.sqlite3"
results = []
with sqlite3.connect(cache.resolve().as_uri() + "?mode=ro", uri=True) as db:
    rows = list(db.execute("SELECT payload FROM export_jobs WHERE mission=?", (sys.argv[2],)))
for row in rows:
    job = ExportPreparation.model_validate_json(row[0])
    fact = {"job": job.model_dump(mode="json")}
    if job.state == "ready":
        if not re.fullmatch("[0-9a-f]{32}", job.id):
            raise ValueError("Unexpected private preparation ID")
        artifact = cache.parent / "exports" / (job.id + ".zip")
        if artifact.is_symlink() or artifact.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("Ready training artifact exceeds its private read boundary")
        digest = hashlib.sha256()
        with artifact.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        fact["artifact"] = {"sha256": digest.hexdigest(), "size": artifact.stat().st_size, "path": str(artifact)}
    results.append(fact)
print(json.dumps(results))
"""


def main():
    import argparse
    import hashlib
    import importlib.util
    import io
    import json
    import signal
    import time
    import zipfile
    from pathlib import Path
    from uuid import uuid4

    import launcher

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("baseline", "check"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--label", required=True, choices=("empty", "nonempty"))
    parser.add_argument("--zip", type=Path)
    parser.add_argument("--browser-origin")
    args = parser.parse_args()
    source_owner = launcher.open_owner(args.root)
    target_owner = launcher.open_owner(
        source_owner.root / "import-destination", destination=True
    )
    # Record the artifact-read command separately from checkpoint commands.
    reader = launcher.Owner(
        source_owner.project,
        source_owner.root
        / "archive-reader"
        / f"{args.label}-{args.command}-{uuid4().hex[:8]}",
    )
    reader.deadline = time.monotonic() + 240
    reader.env.update(source_owner.env)
    reader.compose_file = source_owner.compose_file
    reader.ownership.update(
        volumes=[], images=[], purpose="read-only private archive evidence"
    )
    reader.persist()
    handlers = {
        number: signal.signal(number, reader.signal)
        for number in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        launcher.validate(source_owner)
        launcher.validate(target_owner)
        source_get = loopback_reader(
            source_owner.ownership["port"], deadline=reader.deadline
        )
        target_get = loopback_reader(
            target_owner.ownership["port"], deadline=reader.deadline
        )
        source = read_snapshot(source_get)
        if source["health"]["simulation_run_id"] != source_owner.ownership["fixture"]:
            raise ValueError("Owned private source identity changed")
        origin = browser_origin(
            args.browser_origin or f'http://127.0.0.1:{source_owner.ownership["port"]}'
        )
        identity = {
            "origin": origin,
            "fixtureVersion": 1,
            "storeId": source["health"]["store_id"],
            "epoch": source["health"]["api_epoch"],
        }
        missions = source["missions"]
        if len(missions) != 1:
            raise ValueError("The marked course must have exactly one mission")
        mission = source_get("/api/v2/missions/" + quote(missions[0]["id"], safe=""))
        if (
            mission.get("metadata", {})
            .get("operator_training_fixture", {})
            .get("namespace")
            != source_owner.ownership["fixture"]
        ):
            raise ValueError("Marked private course mission required")
        if mission["metadata"]["operator_training_fixture"].get("version") != 1:
            raise ValueError("Supported private course version required")
        identity["missionId"] = mission["id"]
        target = read_snapshot(target_get)
        target["planFiles"] = json.loads(
            reader.execute(
                [
                    "docker",
                    "compose",
                    "-p",
                    target_owner.project,
                    "-f",
                    str(target_owner.compose_file),
                    "exec",
                    "-T",
                    "--user",
                    "appuser",
                    "starlink-location",
                    "python",
                    "-c",
                    PLAN_FILES_READ,
                    target_owner.ownership["fixture"],
                    json.dumps([item["id"] for item in target["missions"]]),
                ],
                timeout=90,
                env=target_owner.env,
            )
        )
        if target["health"]["store_id"] == identity["storeId"]:
            raise ValueError("Use the separately owned import destination")
        baseline_path = source_owner.root / f"archive-baseline-{args.label}.json"

        def write(path, value):
            pending = path.with_suffix(path.suffix + ".pending")
            try:
                pending.write_text(json.dumps(value, indent=2) + "\n")
                pending.chmod(0o600)
                pending.replace(path)
            finally:
                pending.unlink(missing_ok=True)

        if args.command == "baseline":
            if (args.label == "empty") != (not target["records"]):
                raise ValueError(
                    "Empty/nonempty label must match the actual destination journal"
                )
            if args.label == "empty" and (target["missions"] or target["H"] != 0):
                raise ValueError(
                    "Empty import exercise starts with no destination missions"
                )
            write(baseline_path, {"identity": identity, "destination": target})
            print(
                json.dumps(
                    {
                        "baseline": str(baseline_path),
                        "next": "Import the unchanged original ZIP through the destination Missions UI, then run check with the same label.",
                    }
                )
            )
            return
        baseline = json.loads(baseline_path.read_text())
        if baseline["identity"] != identity:
            raise ValueError("The baseline belongs to another source identity")
        transfer = unchanged_destination(baseline["destination"], target)
        preparations = json.loads(
            reader.compose(
                "exec",
                "-T",
                "--user",
                "appuser",
                "starlink-location",
                "python",
                "-c",
                PREPARATION_READ,
                source_owner.ownership["fixture"],
                mission["id"],
                timeout=90,
            )
        )
        if args.zip is None:
            ready = [
                item
                for item in preparations
                if item["job"]["state"] == "ready" and item.get("artifact")
            ]
            if not ready:
                raise ValueError(
                    "Complete the normal Missions export before checking its original artifact"
                )
            selected = max(ready, key=lambda item: item["job"]["queued_at"])
            cache = source_owner.root / "archive-artifacts"
            cache.mkdir(mode=0o700, exist_ok=True)
            args.zip = cache / (selected["artifact"]["sha256"] + ".zip")
            reader.ownership["temporaryPaths"] = [str(args.zip)]
            reader.persist()
            # The ordinary download endpoint only opens this already-ready file.
            # Avoid Docker cp's rootless read-only mount remapping; do not prepare
            # another export. Hash/size equality below pins these original bytes.
            payload = source_get(
                "/api/v2/missions/"
                + quote(mission["id"], safe="")
                + "/export-preparations/"
                + selected["job"]["id"]
                + "/download",
                binary=True,
            )
            args.zip.write_bytes(payload)
            args.zip.chmod(0o600)
        if args.zip.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("Private training ZIP read is limited to 64 MiB")
        payload = args.zip.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if not any(
            item.get("artifact", {}).get("sha256") == digest
            and item.get("artifact", {}).get("size") == len(payload)
            for item in preparations
        ):
            raise ValueError(
                "Selected ZIP does not match an existing ready server artifact"
            )
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            journal = json.loads(archive.read("operations/journal.json"))
        if journal["mission_id"] != mission["id"]:
            raise ValueError("ZIP belongs to another mission")
        boundary = archive_boundary(source, journal)
        boundary["mission"] = mission
        stage = source_owner.root / "archive-inspection" / digest
        reader.ownership.setdefault("temporaryPaths", []).append(str(stage))
        reader.persist()
        stage.mkdir(parents=True, exist_ok=True, mode=0o700)
        write(stage / "archive-source-snapshot.json", boundary)
        (stage / "original-mission.zip").write_bytes(payload)
        try:
            spec = importlib.util.spec_from_file_location(
                "training_original_zip_inspector",
                Path(__file__).with_name("inspect_archive.py"),
            )
            inspector = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(inspector)
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "Run archive check in the existing backend requirements environment (including pypdf)"
            ) from error
        inspection = inspector.inspect(stage)
        write(stage / "archive-inspection.json", inspection)
        imported = None
        expected_legs = [(leg["name"], leg["transports"]) for leg in mission["legs"]]
        for item in target["missions"]:
            if not installed_generation(baseline["destination"], target, item["id"]):
                continue
            candidate = target_get("/api/v2/missions/" + quote(item["id"], safe=""))
            if [
                (leg["name"], leg["transports"]) for leg in candidate["legs"]
            ] == expected_legs:
                imported = candidate
                break
        if imported is None:
            raise ValueError(
                "No newly imported mission matches the original course legs/transports"
            )
        fact = {
            "schemaVersion": 1,
            "kind": "operator-training-archive-evidence",
            "identity": identity,
            "namespace": source_owner.ownership["fixture"],
            "label": args.label,
            "source": boundary,
            "inspection": inspection,
            "preparations": preparations,
            "transfer": transfer,
            "importedMission": imported,
        }
        report_path = source_owner.root / f"archive-evidence-{args.label}.json"
        write(report_path, fact)
        print(
            json.dumps(
                {
                    "evidence": str(report_path),
                    "originalZipSha256": digest,
                    "originalPdf": str(stage / "original-customer-brief.pdf"),
                    "humanPdfReview": "pending",
                }
            )
        )
    finally:
        reader.stop_child()
        for number, handler in handlers.items():
            signal.signal(number, handler)


if __name__ == "__main__":
    main()
