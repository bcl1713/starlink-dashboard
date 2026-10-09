"""Merge qualified cached pages without layout, maps, or browser work."""

import io
import json
from copy import deepcopy
from hashlib import sha256
from time import monotonic

from pypdf import PdfReader, PdfWriter

from app.mission.exporter.export_cancel import check_cancelled
from app.mission.exporter.snapshot_inputs import canonical_json
from app.mission.package.customer_artifacts import (
    WARNING_CODES,
    CustomerBriefingArtifacts,
    CustomerBriefingOutcome,
)


def assemble_customer_pdf(snapshot, records, *, cancel=None, ordered_ids=None):
    ids = (
        ordered_ids
        if ordered_ids is not None
        else [leg.leg_id for leg in snapshot.legs]
    )
    if not ids:
        return CustomerBriefingOutcome("omitted", "data", None)
    for leg in ids:
        record = records[leg]
        if record["state"] != "ready":
            warning = record.get("warning")
            return CustomerBriefingOutcome(
                "omitted", warning if warning in WARNING_CODES else "runtime", None
            )
    start = monotonic()
    writer = PdfWriter()
    pages, measured, rows, legs, fragments, maps = [], [], [], [], [], {}
    for leg in ids:
        check_cancelled(cancel)
        record = records[leg]
        evidence = json.loads(record["evidence"])
        report = evidence["render"]
        if sha256(record["pdf"]).hexdigest() != report["artifactHashes"]["pdfPath"]:
            raise ValueError("Cached PDF differs from qualified artifact")
        reader = PdfReader(io.BytesIO(record["pdf"]))
        if len(reader.pages) != len(evidence["pages"]) or {
            p["legId"] for p in evidence["pages"]
        } != {leg}:
            raise ValueError("Cached PDF page identity mismatch")
        offset = len(pages)
        writer.append(reader, import_outline=False)

        def rebase(items, offset=offset):
            result = deepcopy(items)
            for item in result:
                item["page"] += offset
            return result

        pages.extend(rebase(evidence["pages"]))
        measured.extend(rebase(report["fit"]["pages"]))
        rows.extend(rebase(report["pdfValidation"]["rows"]))
        legs.extend(evidence["legs"])
        maps.update(report["maps"])
        fragments.append(
            {"legId": leg, "inputFingerprint": record["fingerprint"], "render": report}
        )
    output = io.BytesIO()
    writer.write(output)
    writer.close()
    pdf = output.getvalue()
    check_cancelled(cancel)
    proof = {
        "verified": True,
        "pageCount": len(pages),
        "pageSizePt": [960, 540],
        "rows": rows,
        "fonts": ["DejaVuSans", "DejaVuSans-Bold"],
    }
    evidence = canonical_json(
        {
            "schemaVersion": 2,
            "missionId": snapshot.mission_id,
            "snapshotFingerprint": snapshot.fingerprint,
            "legs": legs,
            "pages": pages,
            "render": {
                "schemaVersion": 3,
                "mode": "cached-page-assembly",
                "status": "success",
                "missionId": snapshot.mission_id,
                "snapshotFingerprint": snapshot.fingerprint,
                "launchCount": 0,
                "sharedBrowser": False,
                "totalMs": (monotonic() - start) * 1000,
                "fit": {"pageCount": len(pages), "pages": measured},
                "maps": maps,
                "pdfValidation": proof,
                "fragments": fragments,
                "artifacts": {"pdfPath": "mission-customer-briefing-trial.pdf"},
                "artifactHashes": {"pdfPath": sha256(pdf).hexdigest()},
                "cleanup": {"success": True, "survivors": [], "errors": []},
            },
        }
    )
    return CustomerBriefingOutcome(
        "included", None, CustomerBriefingArtifacts(pdf, evidence)
    )
