"""Detached planning and already prepared customer pages for one export request."""

import base64
import json
from dataclasses import dataclass, replace

from app.mission.exporter.export_cancel import ExportCancelled, check_cancelled
from app.mission.exporter.snapshot import ExportSnapshot
from app.mission.slide_cache.capture import normalize_capture
from app.mission.slide_cache.identity import decode_snapshot, encode_snapshot
from app.mission.slide_cache.prepared_export import captured_snapshot

from .archive_errors import ArchiveDeadlineError
from .customer_artifacts import (
    EXPORT_ERRORS,
    CustomerBriefingArtifacts,
    CustomerBriefingOutcome,
)


class CaptureCancel:
    def __init__(self, check):
        self.check = check

    def is_set(self):
        self.check()
        return False


@dataclass(frozen=True)
class FrozenPlanning:
    snapshot: ExportSnapshot
    briefing: CustomerBriefingOutcome | None
    needs_preparation: bool = False

    def materialize(self, cancel):
        """Build forecast CSV inputs once, from copied sources, without PDF waits."""
        from app.mission.exporter.snapshot import prepare_export_snapshot

        check_cancelled(cancel)
        if not self.needs_preparation:
            return self
        leg_warnings = {
            warning for leg in self.snapshot.legs for warning in leg.warnings
        }
        snapshot = prepare_export_snapshot(
            self.snapshot.metadata_json,
            self.snapshot.source_payloads,
            tuple(
                warning
                for warning in self.snapshot.warnings
                if warning not in leg_warnings
            ),
            cancel=cancel,
        )
        check_cancelled(cancel)
        return replace(self, snapshot=snapshot, needs_preparation=False)

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
                "needs_preparation": self.needs_preparation,
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
        return cls(
            decode_snapshot(json.dumps(data["snapshot"]).encode()),
            outcome,
            data.get("needs_preparation", True),
        )


def capture_planning(raw, cache, *, enabled, cancel=None):
    """Copy committed sources once; never wait for new PDF rendering or live edits."""
    from app.mission.slide_cache import coordinator
    from app.mission.slide_cache.assembly import assemble_customer_pdf

    check_cancelled(cancel)
    # Shared slide fingerprints use the renderer revision without export options.
    revision = raw.renderer_revision.removesuffix(":enabled").removesuffix(":disabled")
    metadata, sources, warnings, expected = normalize_capture(
        replace(raw, renderer_revision=revision)
    )
    check_cancelled(cancel)
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
            outcome = assemble_customer_pdf(snapshot, records, cancel=cancel)
        except (ExportCancelled, ArchiveDeadlineError):
            raise
        except EXPORT_ERRORS:
            outcome = CustomerBriefingOutcome("omitted", "runtime", None)
    check_cancelled(cancel)
    return FrozenPlanning(
        snapshot,
        outcome,
        any(record["snapshot"] is None for record in records.values()),
    )
