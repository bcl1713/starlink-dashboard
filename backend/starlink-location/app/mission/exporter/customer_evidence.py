"""Exact machine-readable evidence, gated on actual PDF and cleanup proof."""

import json
import re
from copy import deepcopy
from dataclasses import asdict
from pathlib import PurePosixPath

from .customer_document import (
    build_customer_document,
    build_customer_mission_document,
    stamp,
)
from .customer_view import project_customer_leg
from .snapshot_inputs import canonical_json
from .trial_clocks import format_clocks
from .trial_projection import project_trial_leg


def _validate_page_plan(payload, plan):
    if (
        plan.get("schemaVersion") != 2
        or plan.get("missionId") != payload["missionId"]
        or plan.get("snapshotFingerprint") != payload["snapshotFingerprint"]
    ):
        raise ValueError("Page plan identity mismatch")
    pages = plan.get("pages") or []
    if [p.get("page") for p in pages] != list(range(1, len(pages) + 1)):
        raise ValueError("Unordered mission pages")
    cursor, proof = 0, []
    for leg in payload["legs"]:
        assigned = [p for p in pages if p.get("legId") == leg["legId"]]
        if (
            not 1 <= len(assigned) <= 3
            or pages[cursor : cursor + len(assigned)] != assigned
        ):
            raise ValueError("Unordered or over-budget leg pages")
        cursor += len(assigned)
        by_id = {r["id"]: r for r in leg["rows"]}
        if [i for p in assigned for i in p.get("rowIds", [])] != list(by_id):
            raise ValueError("Missing, duplicate or unordered page rows")
        for number, page in enumerate(assigned, 1):
            rows = [by_id[i] for i in page["rowIds"]]
            if (
                page.get("legPage") != number
                or page.get("legPageCount") != len(assigned)
                or page.get("kind") != ("primary" if number == 1 else "continuation")
                or page.get("flightStartUtc") != leg["flight"]["startUtc"]
                or page.get("flightEndUtc") != leg["flight"]["endUtc"]
                or page.get("rowStartUtc") != (rows[0]["startUtc"] if rows else None)
                or page.get("rowEndUtc") != (rows[-1]["endUtc"] if rows else None)
            ):
                raise ValueError("Page flight/row bounds or numbering mismatch")
            proof.extend(
                {
                    "legId": leg["legId"],
                    "rowId": r["id"],
                    "page": page["page"],
                    "displayCells": r["displayCells"],
                    "cellsMatched": True,
                    "inBounds": True,
                }
                for r in rows
            )
    if cursor != len(pages):
        raise ValueError("Unknown page leg")
    return proof


def build_customer_mission_evidence(snapshot, payload, page_plan, report) -> bytes:
    """Qualify immutable mission records against final layout and actual PDF proof."""
    if payload != build_customer_mission_document(snapshot):
        raise ValueError("Mission payload differs from captured projection")
    proof = _validate_page_plan(payload, page_plan)
    count = len(page_plan["pages"])
    pdf, fit = report.get("pdfValidation") or {}, report.get("fit") or {}
    if (
        report.get("schemaVersion") != 2
        or report.get("status") != "success"
        or report.get("missionId") != snapshot.mission_id
        or report.get("snapshotFingerprint") != snapshot.fingerprint
        or report.get("pagePlan") != page_plan
        or report.get("launchCount") != 1
        or report.get("sharedBrowser") is not True
        or report.get("cleanup", {}).get("success") is not True
        or not isinstance(report.get("totalMs"), (int, float))
        or not 0 <= report["totalMs"] <= 60000
        or fit.get("pageCount") != count
        or len(fit.get("pages", [])) != count
        or pdf.get("verified") is not True
        or pdf.get("pageCount") != count
        or pdf.get("pageSizePt") != [960, 540]
        or pdf.get("rows") != proof
        or pdf.get("fonts") != ["DejaVuSans", "DejaVuSans-Bold"]
    ):
        raise ValueError("Unqualified mission render proof")
    for page, measured in zip(page_plan["pages"], fit["pages"]):
        if (
            measured.get("page") != page["page"]
            or measured.get("legId") != page["legId"]
            or measured.get("visibleRowIds") != page["rowIds"]
            or measured.get("overflow") != []
            or measured.get("labelOverlaps") != []
            or measured.get("width") != 1280
            or measured.get("height") != 720
        ):
            raise ValueError("Unqualified final page fit")
    maps = report.get("maps") or {}
    if set(maps) != {l["legId"] for l in payload["legs"]} or any(
        maps[l["legId"]].get("inputDiagnostics") != l["mapInputDiagnostics"]
        for l in payload["legs"]
    ):
        raise ValueError("Missing map input reasons")
    artifacts, hashes = (
        report.get("artifacts") or {},
        report.get("artifactHashes") or {},
    )
    if (
        artifacts.get("pdfPath") != "mission-customer-briefing-trial.pdf"
        or any(
            not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{64}", v)
            for v in hashes.values()
        )
        or "pdfPath" not in hashes
    ):
        raise ValueError("Missing public PDF artifact/hash")
    public = deepcopy(report)
    public["artifacts"] = {"pdfPath": artifacts["pdfPath"]}
    public["artifactHashes"] = {"pdfPath": hashes["pdfPath"]}
    public["diagnosticHashes"] = {k: v for k, v in hashes.items() if k != "pdfPath"}
    for result in public["maps"].values():
        result.pop("pngs", None)
    legs = []
    for number, captured in enumerate(snapshot.legs, 1 + snapshot.leg_number_offset):
        trial = project_trial_leg(captured)
        view = project_customer_leg(
            captured,
            trial,
            leg_number=number,
            leg_count=snapshot.leg_count or len(snapshot.legs),
        )
        legs.append(
            {
                "legId": captured.leg_id,
                "mapInputDiagnostics": payload["legs"][
                    number - 1 - snapshot.leg_number_offset
                ]["mapInputDiagnostics"],
                **_leg_records(captured, trial, view),
            }
        )
    return canonical_json(
        {
            "schemaVersion": 2,
            "missionId": snapshot.mission_id,
            "snapshotFingerprint": snapshot.fingerprint,
            "legs": legs,
            "pages": page_plan["pages"],
            "render": public,
        }
    )


def build_customer_evidence(snapshot, trial, view, report: dict) -> bytes:
    payload = build_customer_document(snapshot, view, trial)
    expected = [r.id for r in view.rows]
    fit = report.get("fit") or {}
    pdf = report.get("pdfValidation") or {}
    verified_rows = pdf.get("rows") or []
    expected_rows = [
        {
            "legId": trial.leg_id,
            "rowId": row["id"],
            "page": 1,
            "displayCells": row["displayCells"],
            "cellsMatched": True,
            "inBounds": True,
        }
        for row in payload["rows"]
    ]
    if (
        report.get("schemaVersion") != 1
        or report.get("status") != "success"
        or report.get("snapshotFingerprint") != snapshot.fingerprint
        or report.get("legId") != trial.leg_id
        or fit.get("pageCount") != 1
        or fit.get("visibleRowIds") != expected
        or fit.get("overflow") != []
        or report.get("cleanup", {}).get("success") is not True
        or not isinstance(report.get("totalMs"), (int, float))
        or not 0 <= report["totalMs"] <= 60000
        or pdf.get("verified") is not True
        or pdf.get("pageCount") != 1
        or verified_rows != expected_rows
        or len(pdf.get("pageSizePt", [])) != 2
        or any(abs(a - b) > 0.01 for a, b in zip(pdf["pageSizePt"], (960, 540)))
    ):
        raise ValueError("Unqualified/mismatched render evidence")
    artifacts = report.get("artifacts") or {}
    hashes = report.get("artifactHashes") or {}
    if set(artifacts) != {"htmlPath", "pngPath", "pdfPath"} or set(hashes) != set(
        artifacts
    ):
        raise ValueError("Incomplete paired artifacts")
    for key, value in artifacts.items():
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or len(path.parts) != 1
            or not re.fullmatch(r"[0-9a-f]{64}", hashes[key])
        ):
            raise ValueError("Invalid artifact reference/hash")
    return canonical_json(
        {
            "schemaVersion": 1,
            "snapshotFingerprint": snapshot.fingerprint,
            "legId": trial.leg_id,
            "mapInputDiagnostics": payload["mapInputDiagnostics"],
            **_leg_records(snapshot.legs[0], trial, view),
            "pages": [
                {
                    "page": 1,
                    "startUtc": stamp(trial.utc_bounds[0]),
                    "endUtc": stamp(trial.utc_bounds[1]),
                    "rowIds": expected,
                }
            ],
            "render": report,
        }
    )


def _leg_records(captured, trial, view):
    origin = trial.utc_bounds[0]

    def clocks(value):
        labels = format_clocks(value, origin)
        return {"et": labels.et, "zulu": labels.zulu, "t_plus": labels.relative}

    return {
        "canonical": {
            "utcBounds": [stamp(v) for v in trial.utc_bounds],
            "intervals": [
                {
                    "id": i.id,
                    "startUtc": stamp(i.start_time),
                    "endUtc": stamp(i.end_time),
                    "clocks": {
                        "start": clocks(i.start_time),
                        "end": clocks(i.end_time),
                    },
                    "posture": i.posture,
                    "decisions": [asdict(d) for d in i.decisions],
                    "restrictions": [asdict(r) for r in i.restrictions],
                    "sourceIds": i.active_source_ids,
                    "causes": i.causes,
                    "limitations": i.limitations,
                    "remainingTransports": i.remaining_transports,
                }
                for i in trial.intervals
            ],
            "sources": [
                {
                    "sourceId": s.source_id,
                    "sourceType": s.source_type,
                    "reason": s.reason,
                    "sourceRevision": s.source_revision,
                    "sourceDigest": s.source_digest,
                    "original": json.loads(s.original_json),
                }
                for s in trial.sources
            ],
            "capturedSourceRecords": [json.loads(s) for s in captured.source_records],
            "notes": trial.notes,
        },
        "customerRows": [
            {
                "id": r.id,
                "startUtc": stamp(r.start_time),
                "endUtc": stamp(r.end_time),
                "clock": asdict(r.clock),
                "impact": r.impact,
                "remaining": r.remaining,
                "posture": r.posture,
                "intervalIds": r.interval_ids,
                "sourceIds": r.source_ids,
            }
            for r in view.rows
        ],
    }
