"""Verify the real prepared mission ZIP and clean, separate-instance plan import."""

import hashlib
import io
import json
import time
import zipfile
from pathlib import Path
from uuid import uuid4

import httpx
from pypdf import PdfReader

MISSION = "synthetic-mission-a"
ROOT = Path("/app/data/operator/archive-acceptance")


def prepared(client):
    response = client.post(f"/api/v2/missions/{MISSION}/export")
    response.raise_for_status()
    if response.status_code == 200:
        return response.content, None
    job = response.json()
    path = f'/api/v2/missions/{MISSION}/export-preparations/{job["id"]}'
    deadline = time.monotonic() + 620
    while job["state"] in ("queued", "preparing"):
        assert time.monotonic() < deadline, job
        time.sleep(0.2)
        result = client.get(path)
        result.raise_for_status()
        job = result.json()
    assert job["state"] == "ready", job
    response = client.get(path + "/download")
    response.raise_for_status()
    return response.content, job


def counts(client):
    response = client.get("/api/v2/operator/records", params={"mission_id": MISSION})
    response.raise_for_status()
    return response.json()


def run():
    with httpx.Client(
        base_url="http://127.0.0.1:8000", timeout=30
    ) as source, httpx.Client(
        base_url="http://import-destination:8000", timeout=60
    ) as destination:
        # Feed only synthetic raw model inputs; persist #348's real advisory.
        control = "/api/_synthetic/operator-model-inputs"
        response = source.post(
            control,
            json={"now": "2026-10-17T16:10:00+00:00", "longitude": -9.5, "speed": 600},
        )
        response.raise_for_status()
        for stamp in ("2026-10-17T16:10:00+00:00", "2026-10-17T16:10:16+00:00"):
            source.post(control, json={"now": stamp}).raise_for_status()
            source.get(
                "/api/v2/operator/events", params={"mission_id": MISSION}
            ).raise_for_status()
        before = counts(destination)
        assert not before["items"] and before["H"] == 0
        payload, job = prepared(source)
        (ROOT / "synthetic-complete-mission.zip").write_bytes(payload)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            assert not archive.testzip()
            names = archive.namelist()
            assert len(names) == len(set(names))
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["version"] == "2.0"
            assert manifest["statistics"]["total_files"] == len(names)
            for name, digest in manifest["archive_components"]["checksums"].items():
                assert hashlib.sha256(archive.read(name)).hexdigest() == digest
            journal_manifest = json.loads(archive.read("operations/manifest.json"))
            for name, digest in journal_manifest["checksums"].items():
                assert hashlib.sha256(archive.read(name)).hexdigest() == digest
            journal = json.loads(archive.read("operations/journal.json"))
            current = journal["current_records"]
            revisions = [
                json.loads(line)
                for line in archive.read("operations/audit.jsonl").splitlines()
            ]
            assert len(revisions) > len(current)
            assert {"preflight", "leg", "between_legs", "postflight"} <= {
                r["scope"] for r in revisions
            }
            assert any(r["record_type"] == "transport_decision" for r in current)
            assert any(r["version"] > 1 for r in revisions)
            conferences = {
                r["payload"]["conference_id"]
                for r in current
                if r["record_type"] == "call" and r["payload"].get("conference_id")
            }
            assert len(conferences) == 1
            assert sum(r["record_type"] == "call" for r in current) >= 2
            events = json.loads(archive.read("operations/events.json"))
            pops = [
                r["event"]
                for r in events["occurrences"]
                if r["event"]["kind"] == "pop_advisory"
            ]
            assert pops and all(r["provenance"] == "modeled" for r in pops)
            pdfs = [
                n
                for n in names
                if n.startswith("exports/mission/") and n.endswith("-brief.pdf")
            ]
            assert len(pdfs) == 1, names
            pdf = archive.read(pdfs[0])
            assert (
                pdf.startswith(b"%PDF-") and len(PdfReader(io.BytesIO(pdf)).pages) >= 2
            )
            (ROOT / "synthetic-customer-brief.pdf").write_bytes(pdf)
            telemetry = json.loads(archive.read("telemetry/manifest.json"))
            assert len(telemetry["legs"]) == 2
            for leg in telemetry["legs"]:
                details = json.loads(
                    archive.read("telemetry/" + leg["path"] + "/manifest.json")
                )
                assert details["state"] == "sealed"
                kinds = {r["kind"] for r in details["events"]}
                assert {"takeoff", "landed", "on_blocks"} <= kinds, kinds
                for name, digest in leg["checksum"].items():
                    assert (
                        hashlib.sha256(
                            archive.read("telemetry/" + leg["path"] + "/" + name)
                        ).hexdigest()
                        == digest
                    )
            mission = json.loads(archive.read("mission.json"))
            assert len(mission["legs"]) == 2
            assert any(n.startswith("routes/") and n.endswith(".kml") for n in names)
            assert "exports/mission/mission-timeline.csv" in names
            legacy = io.BytesIO()
            with zipfile.ZipFile(legacy, "w", zipfile.ZIP_DEFLATED) as output:
                for name in names:
                    if not name.startswith(("operations/", "telemetry/")):
                        output.writestr(name, archive.read(name))
        response = destination.post(
            "/api/v2/missions/import",
            files={"file": ("synthetic-mission.zip", payload, "application/zip")},
        )
        response.raise_for_status()
        imported = response.json()
        assert (
            imported["success"]
            and imported["leg_count"] == 2
            and imported["routes_imported"] >= 1
        ), imported
        result = destination.get("/api/v2/missions/" + imported["mission_id"])
        result.raise_for_status()
        imported_mission = result.json()
        assert len(imported_mission["legs"]) == len(mission["legs"])
        assert [r["name"] for r in imported_mission["legs"]] == [
            r["name"] for r in mission["legs"]
        ]
        assert [r["transports"] for r in imported_mission["legs"]] == [
            r["transports"] for r in mission["legs"]
        ]
        assert counts(destination) == before
        legacy_result = destination.post(
            "/api/v2/missions/import",
            files={"file": ("legacy.zip", legacy.getvalue(), "application/zip")},
        )
        legacy_result.raise_for_status()
        assert legacy_result.json()["success"] and counts(destination) == before
        repeat, _ = prepared(source)
        assert repeat == payload
        # A retrospective correction creates a new snapshot; the old URL is immutable.
        record = next(
            r
            for r in current
            if r["record_type"] == "journal_entry" and r["scope"] == "preflight"
        )
        health = source.get("/api/v2/operator/health").json()
        fields = {
            k: record[k]
            for k in ("record_type", "mission_id", "leg_id", "scope", "time", "payload")
        }
        fields["payload"] = fields["payload"] | {
            "note": "Synthetic export retrospective correction"
        }
        headers = {
            "Idempotency-Key": str(uuid4()),
            "X-Operator-Store-Epoch": health["api_epoch"],
        }
        response = source.put(
            "/api/v2/operator/records/" + record["record_id"],
            headers=headers,
            json=fields
            | {
                "schema_version": 1,
                "expected_version": record["version"],
                "reason": "Synthetic retrospective correction",
            },
        )
        response.raise_for_status()
        changed, changed_job = prepared(source)
        assert changed != payload
        if job:
            assert source.get(job["download_url"]).content == payload
        (ROOT / "synthetic-latest-mission.zip").write_bytes(changed)
        (ROOT / "synthetic-ready-job.json").write_text(json.dumps(changed_job))
        return {
            "synthetic": True,
            "customerPdf": pdfs[0],
            "customerPdfPages": len(PdfReader(io.BytesIO(pdf)).pages),
            "archivedLegs": 2,
            "records": len(current),
            "revisions": len(revisions),
            "modeledPopOccurrences": len(pops),
            "sourceMode": journal["source_mode"],
            "telemetrySourceMode": telemetry["source_mode"],
            "syntheticOperationalFormatTelemetry": True,
            "independentChecksums": True,
            "cleanSeparateInstanceImport": imported,
            "destinationJournalUnmodified": True,
            "legacyImport": True,
            "repeatBytesIdentical": True,
            "retrospectiveNewSnapshot": True,
            "originalDownloadImmutable": bool(job),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "latestSha256": hashlib.sha256(changed).hexdigest(),
        }


if __name__ == "__main__":
    print(json.dumps(run()))
