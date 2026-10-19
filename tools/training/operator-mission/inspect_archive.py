"""Inspect the original browser download; never rebuild or amend the mission ZIP."""

import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

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

        def checksums(items, prefix=""):
            assert items, "Missing archive checksums"
            for name, expected in items.items():
                path = prefix + name
                assert digest(archive.read(path)) == expected, path
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
        (root / "original-customer-brief.pdf").write_bytes(pdf)
        telemetry = json.loads(archive.read("telemetry/manifest.json"))
        assert len(telemetry["legs"]) == 2
        telemetry_states = []
        for leg in telemetry["legs"]:
            prefix = "telemetry/" + leg["path"] + "/"
            details = json.loads(archive.read(prefix + "manifest.json"))
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
            "records": len(records),
            "revisions": len(revisions),
            "checkedMembers": sorted(checked),
            "telemetry": telemetry_states,
            "originalZipUnchanged": digest((root / "original-mission.zip").read_bytes())
            == digest(payload),
            "humanPdfReview": "pending",
        }


if __name__ == "__main__":
    root = Path(sys.argv[1])
    result = inspect(root)
    (root / "archive-inspection.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
