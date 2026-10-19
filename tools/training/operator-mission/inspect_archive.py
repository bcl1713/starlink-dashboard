"""Inspect the original browser download; never rebuild or amend the mission ZIP."""

import hashlib
import io
import json
import re
import sys
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from pypdf import PdfReader


def inspect(root):
    snapshot = json.loads((root / "archive-source-snapshot.json").read_text())
    payload = (root / "original-mission.zip").read_bytes()
    digest = lambda body: hashlib.sha256(body).hexdigest()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert len(names) == len(set(names)), "Duplicate ZIP members"
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["version"] == "2.0"
        assert manifest["statistics"]["total_files"] == len(names)
        checked = set()
        checksum_reads = []

        def checksums(items, prefix=""):
            assert items, "Missing archive checksums"
            for name, expected in items.items():
                path = prefix + name
                actual = digest(archive.read(path))
                assert actual == expected, path
                checksum_reads.append(
                    {"path": path, "expected": expected, "actual": actual}
                )
                checked.add(path)

        checksums(manifest["archive_components"]["checksums"])
        checksums(json.loads(archive.read("operations/manifest.json"))["checksums"])
        journal = json.loads(archive.read("operations/journal.json"))
        assert journal["mission_id"] == snapshot["mission"]["id"]
        assert journal["store_id"] == snapshot["health"]["store_id"]
        assert journal["high_water"] == snapshot["H"]
        assert journal["source_mode"] == "simulation"
        assert journal["simulation_run_id"] == snapshot["health"]["simulation_run_id"]
        records = sorted(snapshot["records"], key=lambda row: row["record_id"])
        assert (
            sorted(journal["current_records"], key=lambda row: row["record_id"])
            == records
        )
        revisions = [
            json.loads(line)
            for line in archive.read("operations/audit.jsonl").splitlines()
        ]
        key = lambda row: (row["record_id"], row["version"])
        assert sorted(revisions, key=key) == sorted(snapshot["history"], key=key)
        assert len(revisions) > len(records), "No immutable revision exercise"
        assert {"preflight", "leg", "between_legs"} <= {
            row["scope"] for row in revisions
        }
        mission = json.loads(archive.read("mission.json"))
        provenance = mission["metadata"]["operator_training_archive_inputs"]
        assert provenance["synthetic"] is True
        assert provenance["source_format"] == "synthetic-operational-format"
        assert len(mission["legs"]) == 2
        assert [leg["id"] for leg in mission["legs"]] == [
            leg["id"] for leg in snapshot["mission"]["legs"]
        ]
        assert "exports/mission/mission-timeline.csv" in names
        assert any(
            name.startswith("routes/") and name.endswith(".kml") for name in names
        )
        pdfs = [
            name
            for name in names
            if name.startswith("exports/mission/") and name.endswith("-brief.pdf")
        ]
        assert len(pdfs) == 1, pdfs
        pdf = archive.read(pdfs[0])
        assert pdf.startswith(b"%PDF-")
        reader = PdfReader(io.BytesIO(pdf))
        assert len(reader.pages) >= 2
        assert any(
            (page.extract_text() or "").strip() for page in reader.pages
        ), "Empty customer PDF"
        text = unicodedata.normalize(
            "NFKC", "\n".join(page.extract_text() or "" for page in reader.pages)
        )
        printed_clocks = []
        ns = {"k": "http://www.opengis.net/kml/2.2"}
        for leg in mission["legs"]:
            assert unicodedata.normalize("NFKC", leg["name"]) in text
            route = ElementTree.fromstring(
                archive.read(f'routes/{leg["route_id"]}.kml')
            )
            stamps = []
            for point in route.findall(".//k:Placemark", ns):
                if point.find("k:Point", ns) is None:
                    continue
                description = point.findtext("k:description", "", ns)
                match = re.search(
                    r"Time Over Waypoint: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}Z)",
                    description,
                )
                if match:
                    stamps.append(
                        datetime.strptime(match[1], "%Y-%m-%d %H:%M:%SZ").replace(
                            tzinfo=timezone.utc
                        )
                    )
            assert len(stamps) >= 2, "Missing declared route clocks"
            departure = (
                datetime.fromisoformat(leg["adjusted_departure_time"])
                if leg.get("adjusted_departure_time")
                else min(stamps)
            )
            arrival = departure + (max(stamps) - min(stamps))
            eastern = ZoneInfo("America/New_York")
            expected = f"DEP {departure.astimezone(eastern):%H:%M} ET | ARR {arrival.astimezone(eastern):%H:%M} ET"
            assert expected in text, expected
            printed_clocks.append(
                {
                    "legId": leg["id"],
                    "departureUtc": departure.isoformat(),
                    "arrivalUtc": arrival.isoformat(),
                    "pdfEasternHeader": expected,
                }
            )
        (root / "original-customer-brief.pdf").write_bytes(pdf)
        telemetry = json.loads(archive.read("telemetry/manifest.json"))
        assert len(telemetry["legs"]) == 2
        telemetry_states = []
        for leg in telemetry["legs"]:
            prefix = "telemetry/" + leg["path"] + "/"
            details = json.loads(archive.read(prefix + "manifest.json"))
            assert details["state"] == "sealed"
            assert {"takeoff", "landed", "on_blocks"} <= {
                event["kind"] for event in details["events"]
            }
            checksums(leg["checksum"], prefix)
            telemetry_states.append(
                {
                    "path": leg["path"],
                    "state": details["state"],
                    "events": [event["kind"] for event in details["events"]],
                }
            )
        return {
            "synthetic": True,
            "zipSha256": digest(payload),
            "pdfPath": pdfs[0],
            "pdfSha256": digest(pdf),
            "pdfPages": len(reader.pages),
            "pdfClocksFromOriginalRouteInputs": printed_clocks,
            "records": len(records),
            "revisions": len(revisions),
            "checkedMembers": sorted(checked),
            "checksumReads": checksum_reads,
            "telemetry": telemetry_states,
            "telemetryInputProvenance": provenance,
            "originalZipUnchanged": digest((root / "original-mission.zip").read_bytes())
            == digest(payload),
            "humanPdfReview": "pending",
        }


if __name__ == "__main__":
    root = Path(sys.argv[1])
    result = inspect(root)
    (root / "archive-inspection.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
