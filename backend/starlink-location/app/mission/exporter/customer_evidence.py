"""Exact machine-readable evidence, gated on actual PDF and cleanup proof."""

import json
import re
from dataclasses import asdict
from pathlib import PurePosixPath

from .customer_document import build_customer_document, stamp
from .snapshot_inputs import canonical_json
from .trial_clocks import format_clocks


def build_customer_evidence(snapshot, trial, view, report: dict) -> bytes:
    build_customer_document(snapshot, view, trial)
    expected = [r.id for r in view.rows]
    fit = report.get("fit") or {}
    pdf = report.get("pdfValidation") or {}
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
    origin = trial.utc_bounds[0]

    def clocks(value):
        labels = format_clocks(value, origin)
        return {"et": labels.et, "zulu": labels.zulu, "t_plus": labels.relative}

    return canonical_json(
        {
            "schemaVersion": 1,
            "snapshotFingerprint": snapshot.fingerprint,
            "legId": trial.leg_id,
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
                "capturedSourceRecords": [
                    json.loads(s) for s in snapshot.legs[0].source_records
                ],
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
            "pages": [
                {
                    "page": 1,
                    "startUtc": stamp(origin),
                    "endUtc": stamp(trial.utc_bounds[1]),
                    "rowIds": expected,
                }
            ],
            "render": report,
        }
    )
