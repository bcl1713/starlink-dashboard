"""Pure, bounded planned-UTC interpolation of admitted geographic spans."""

import hashlib
import json
from datetime import datetime, timedelta, timezone

from app.models.route import ParsedRoute
from app.models.sigmet_encounters import (
    EncounterEvidence,
    EncounterPlan,
    PassageEvidence,
)

METHOD = "segment-linear-utc-v1"
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def capture_encounter_plan(
    route: ParsedRoute, context_key: str, source: str, source_revision: str | None
) -> EncounterPlan:
    times, reasons = [], []
    for point in route.points:
        value = point.expected_arrival_time
        instant, reason = None, "missing-timing"
        if value is not None:
            reason = "invalid-timing"
            if value.tzinfo is not None and value.utcoffset() is not None:
                delta = value.astimezone(timezone.utc) - EPOCH
                candidate = delta // timedelta(milliseconds=1)
                if 0 <= candidate <= 9007199254740991:
                    instant, reason = candidate, None
        times.append(instant)
        reasons.append(reason)
    revision = hashlib.sha256(
        json.dumps(
            [METHOD, source, source_revision, times, reasons, "unknown"],
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return EncounterPlan(
        context_key=context_key,
        revision=revision,
        source=source,
        source_revision=source_revision,
        times_ms=tuple(times),
        reasons=tuple(reasons),
    )


def evaluate_encounters(
    plan, spans, valid_from_ms: int, expires_at_ms: int
) -> EncounterEvidence:
    passages = []
    for span in spans:
        index = span.segment_index
        reason = None
        if plan is None:
            reason = "unavailable-plan"
        elif index + 1 >= len(plan.times_ms):
            reason = "ambiguous-association"
        else:
            reason = plan.reasons[index] or plan.reasons[index + 1]
            if reason is None and plan.times_ms[index] >= plan.times_ms[index + 1]:
                reason = "invalid-timing"
        if reason:
            passages.append(
                PassageEvidence(
                    entry_ms=None, exit_ms=None, status="unknown", reason=reason
                )
            )
            continue
        start, end = plan.times_ms[index : index + 2]
        entry = start + round(span.start_fraction * (end - start))
        exit = start + round(span.end_fraction * (end - start))
        overlap = exit >= valid_from_ms and entry < expires_at_ms
        passages.append(
            PassageEvidence(
                entry_ms=entry,
                exit_ms=exit,
                status="overlap" if overlap else "no-overlap",
                reason=None,
            )
        )
    unknown = sum(p.status == "unknown" for p in passages)
    status = (
        "overlap"
        if any(p.status == "overlap" for p in passages)
        else "unknown" if unknown else "no-overlap"
    )
    return EncounterEvidence(
        spans=passages,
        status=status,
        unknown_count=unknown,
        reason=(
            next((p.reason for p in passages if p.reason), None)
            if status == "unknown"
            else None
        ),
    )
