"""Detached planning and already prepared customer pages for one export request."""

import base64
import json
from dataclasses import dataclass, replace

from app.mission.exporter.snapshot import ExportSnapshot
from app.mission.slide_cache.capture import normalize_capture
from app.mission.slide_cache.identity import decode_snapshot, encode_snapshot
from app.mission.slide_cache.prepared_export import captured_snapshot

from .customer_artifacts import (
    EXPORT_ERRORS,
    CustomerBriefingArtifacts,
    CustomerBriefingOutcome,
)


@dataclass(frozen=True)
class FrozenPlanning:
    snapshot: ExportSnapshot
    briefing: CustomerBriefingOutcome | None

    def encode(self):
        outcome = self.briefing
        briefing = None
        if outcome is not None:
            briefing = {"status": outcome.status, "warning": outcome.warning_code}
            if outcome.artifacts is not None:
                briefing.update(
                    pdf=base64.b64encode(outcome.artifacts.pdf).decode("ascii"),
                    evidence=base64.b64encode(outcome.artifacts.evidence).decode(
                        "ascii"
                    ),
                )
        return json.dumps(
            {
                "snapshot": json.loads(encode_snapshot(self.snapshot)),
                "briefing": briefing,
            },
            separators=(",", ":"),
        ).encode("ascii")

    @classmethod
    def decode(cls, payload):
        data = json.loads(payload)
        briefing = data["briefing"]
        outcome = None
        if briefing is not None:
            artifacts = (
                CustomerBriefingArtifacts(
                    base64.b64decode(briefing["pdf"], validate=True),
                    base64.b64decode(briefing["evidence"], validate=True),
                )
                if "pdf" in briefing
                else None
            )
            outcome = CustomerBriefingOutcome(
                briefing["status"], briefing["warning"], artifacts
            )
        return cls(decode_snapshot(json.dumps(data["snapshot"]).encode()), outcome)


def capture_planning(raw, cache, *, enabled):
    """Copy committed sources once; never wait for new PDF rendering or live edits."""
    from app.mission.slide_cache import coordinator
    from app.mission.slide_cache.assembly import assemble_customer_pdf

    # Shared slide fingerprints use the renderer revision without export options.
    revision = raw.renderer_revision.removesuffix(":enabled").removesuffix(":disabled")
    metadata, sources, warnings, expected = normalize_capture(
        replace(raw, renderer_revision=revision)
    )
    available = cache.records(raw.mission_id)
    records = {}
    for leg, (fingerprint, _) in expected.items():
        record = available.get(leg)
        records[leg] = (
            record
            if record
            and record["fingerprint"] == fingerprint
            and record["state"] in {"ready", "failed"}
            else {
                "snapshot": None,
                "state": "failed",
                "warning": "runtime" if coordinator._runtime is None else "busy",
            }
        )
    snapshot = captured_snapshot(metadata, sources, warnings, records)
    outcome = None
    if enabled:
        try:
            outcome = assemble_customer_pdf(snapshot, records)
        except EXPORT_ERRORS:
            outcome = CustomerBriefingOutcome("omitted", "runtime", None)
    return FrozenPlanning(snapshot, outcome)
