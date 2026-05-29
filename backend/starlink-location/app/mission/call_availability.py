"""Normalize mission timelines into operational call-availability blocks.

The raw mission timeline can carry overlapping context such as SOF/AAR windows
in statistics while transport state segments remain nominal. This module applies
a sweep-line pass so the primary table can show one chronological,
non-overlapping call posture per row.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from app.mission.models import (
    MissionLegTimeline,
    TimelineSegment,
    TimelineStatus,
    Transport,
    TransportState,
)


@dataclass(frozen=True)
class AARBlock:
    """Safety-of-flight AAR interval clipped into the mission timeline."""

    start: datetime
    end: datetime


@dataclass(frozen=True)
class AvailabilityDecision:
    """Resolved operational call posture for an atomic interval."""

    status: TimelineStatus
    call_posture: str
    primary_reason: str
    availability_label: str
    impacted_transports: tuple[Transport, ...]
    x_state: TransportState
    ka_state: TransportState
    ku_state: TransportState
    notes: tuple[str, ...]
    source_reasons: tuple[str, ...]
    source_segment_ids: tuple[str, ...]


_STATE_PRIORITY = {
    TransportState.AVAILABLE: 0,
    TransportState.DEGRADED: 1,
    TransportState.OFFLINE: 2,
}

_STATUS_PRIORITY = {
    TimelineStatus.NOMINAL: 0,
    TimelineStatus.SOF: 1,
    TimelineStatus.DEGRADED: 2,
    TimelineStatus.CRITICAL: 3,
}

_REASON_LABELS = {
    "outage": "system outage",
    "aar": "AAR window",
    "ku_x": "X Band / Ku conflict",
    "x_aar": "X Band / AAR conflict",
    "activity": "operational activity conflict",
    "nominal": "nominal window",
}

_KU_X_ADVISORY_LABEL = (
    "Transport concurrency advisory: X Band / Ku conflict — choose one "
    "transport; PACE preference Starlink > Comm Ka > X-Band"
)


def normalize_call_availability_timeline(timeline: MissionLegTimeline) -> None:
    """Replace timeline segments with merged, non-overlapping availability rows.

    The normalized segments retain the existing `TimelineSegment` model for API
    compatibility while adding table-ready labels in `metadata`:
    `call_posture`, `primary_reason`, `availability_label`, `systems_affected`,
    `notes`, `source_reasons`, and `source_segment_ids`.
    """

    if not timeline.segments:
        return

    source_segments = sorted(
        timeline.segments,
        key=lambda seg: (_ensure_utc(seg.start_time), _ensure_utc(seg.end_time)),
    )
    mission_start = min(_ensure_utc(seg.start_time) for seg in source_segments)
    mission_end = max(_ensure_utc(seg.end_time) for seg in source_segments)
    aar_blocks = _extract_aar_blocks(timeline, mission_start, mission_end)

    boundaries = {mission_start, mission_end}
    for segment in source_segments:
        boundaries.add(_ensure_utc(segment.start_time))
        boundaries.add(_ensure_utc(segment.end_time))
    for block in aar_blocks:
        boundaries.add(block.start)
        boundaries.add(block.end)

    normalized: list[TimelineSegment] = []
    ordered_boundaries = sorted(boundaries)
    for index in range(len(ordered_boundaries) - 1):
        start = ordered_boundaries[index]
        end = ordered_boundaries[index + 1]
        if start >= end:
            continue

        active_segments = [
            segment
            for segment in source_segments
            if _ensure_utc(segment.start_time) <= start < _ensure_utc(segment.end_time)
        ]
        if not active_segments:
            continue

        in_sof = any(block.start <= start < block.end for block in aar_blocks)
        decision = _decide_availability(active_segments, in_sof)
        segment = _build_segment(
            timeline.mission_leg_id,
            len(normalized) + 1,
            start,
            end,
            decision,
        )
        if normalized and _can_merge(normalized[-1], segment):
            normalized[-1] = _merge_segments(normalized[-1], segment)
        else:
            normalized.append(segment)

    timeline.segments = [
        _renumber_segment(timeline.mission_leg_id, idx, segment)
        for idx, segment in enumerate(normalized, start=1)
    ]


def _extract_aar_blocks(
    timeline: MissionLegTimeline,
    mission_start: datetime,
    mission_end: datetime,
) -> list[AARBlock]:
    blocks = []
    raw_blocks = (timeline.statistics or {}).get("_aar_blocks") or []
    for raw in raw_blocks:
        start_raw = raw.get("start") if isinstance(raw, dict) else None
        end_raw = raw.get("end") if isinstance(raw, dict) else None
        if not start_raw or not end_raw:
            continue
        start = max(_parse_timestamp(start_raw), mission_start)
        end = min(_parse_timestamp(end_raw), mission_end)
        if end > start:
            blocks.append(AARBlock(start=start, end=end))
    return blocks


def _decide_availability(
    segments: list[TimelineSegment], in_sof: bool
) -> AvailabilityDecision:
    x_state = _highest_state(segment.x_state for segment in segments)
    ka_state = _highest_state(segment.ka_state for segment in segments)
    ku_state = _highest_state(segment.ku_state for segment in segments)
    source_reasons = tuple(
        _unique(reason for segment in segments for reason in segment.reasons)
    )
    source_segment_ids = tuple(
        _unique(segment.id for segment in segments if segment.id)
    )
    notes = tuple(
        _unique(note for segment in segments for note in _segment_notes(segment))
    )
    source_status = max(
        (segment.status for segment in segments),
        key=lambda status: _STATUS_PRIORITY.get(status, 0),
    )

    has_ku_x_conflict = _has_ku_x_conflict(source_reasons)
    if (
        has_ku_x_conflict
        and x_state == TransportState.DEGRADED
        and not _has_actual_x_degradation(source_reasons, in_sof)
    ):
        x_state = TransportState.AVAILABLE

    if (
        has_ku_x_conflict
        and source_status == TimelineStatus.DEGRADED
        and all(
            state == TransportState.AVAILABLE for state in (x_state, ka_state, ku_state)
        )
    ):
        source_status = TimelineStatus.NOMINAL

    impacted = tuple(
        transport
        for transport, state in (
            (Transport.X, x_state),
            (Transport.KA, ka_state),
            (Transport.KU, ku_state),
        )
        if state != TransportState.AVAILABLE
    )

    if any(state == TransportState.OFFLINE for state in (x_state, ka_state, ku_state)):
        status = (
            TimelineStatus.CRITICAL if len(impacted) > 1 else TimelineStatus.DEGRADED
        )
        posture = "Unavailable"
        primary = _primary_outage_reason(source_reasons)
    elif has_ku_x_conflict and not impacted:
        status = TimelineStatus.SOF
        posture = "Transport concurrency advisory"
        primary = _REASON_LABELS["ku_x"]
    elif _has_x_aar_conflict(source_reasons, in_sof, impacted, x_state):
        status = TimelineStatus.DEGRADED
        posture = "Degraded"
        primary = _REASON_LABELS["x_aar"]
    elif impacted or source_status in (TimelineStatus.DEGRADED, TimelineStatus.CRITICAL):
        status = TimelineStatus.CRITICAL if (
            len(impacted) > 1 or source_status == TimelineStatus.CRITICAL
        ) else TimelineStatus.DEGRADED
        posture = "Degraded" if status == TimelineStatus.DEGRADED else "Critical"
        primary = _primary_activity_reason(source_reasons, skip_ku_x=has_ku_x_conflict)
    elif sof_reason := _primary_sof_reason(source_reasons):
        status = TimelineStatus.SOF
        posture = "Avoid calls"
        primary = sof_reason
    elif in_sof:
        status = TimelineStatus.SOF
        posture = "Safety-of-flight advised"
        primary = _REASON_LABELS["aar"]
    else:
        status = TimelineStatus.NOMINAL
        posture = "Nominal calls"
        primary = _REASON_LABELS["nominal"]

    if posture == "Transport concurrency advisory":
        label = _KU_X_ADVISORY_LABEL
    elif posture == "Nominal calls":
        label = posture
    elif posture == "Degraded" and primary.lower().endswith("activity conflict"):
        label = primary
    else:
        label = f"{posture} — {primary}"
    return AvailabilityDecision(
        status=status,
        call_posture=posture,
        primary_reason=primary,
        availability_label=label,
        impacted_transports=impacted,
        x_state=x_state,
        ka_state=ka_state,
        ku_state=ku_state,
        notes=notes,
        source_reasons=source_reasons,
        source_segment_ids=source_segment_ids,
    )


def _build_segment(
    mission_id: str,
    index: int,
    start: datetime,
    end: datetime,
    decision: AvailabilityDecision,
) -> TimelineSegment:
    systems = [transport.value for transport in decision.impacted_transports]
    metadata = {
        "call_posture": decision.call_posture,
        "primary_reason": decision.primary_reason,
        "availability_label": decision.availability_label,
        "systems_affected": systems,
        "notes": list(decision.notes),
        "source_reasons": list(decision.source_reasons),
        "source_segment_ids": list(decision.source_segment_ids),
    }
    return TimelineSegment(
        id=f"{mission_id}-availability-{index:03d}",
        start_time=start,
        end_time=end,
        status=decision.status,
        x_state=decision.x_state,
        ka_state=decision.ka_state,
        ku_state=decision.ku_state,
        reasons=[decision.availability_label],
        impacted_transports=list(decision.impacted_transports),
        metadata=metadata,
    )


def _can_merge(left: TimelineSegment, right: TimelineSegment) -> bool:
    left_meta = left.metadata or {}
    right_meta = right.metadata or {}
    return (
        _ensure_utc(left.end_time) == _ensure_utc(right.start_time)
        and left.status == right.status
        and left.x_state == right.x_state
        and left.ka_state == right.ka_state
        and left.ku_state == right.ku_state
        and left.impacted_transports == right.impacted_transports
        and left_meta.get("call_posture") == right_meta.get("call_posture")
        and left_meta.get("primary_reason") == right_meta.get("primary_reason")
        and left_meta.get("availability_label") == right_meta.get("availability_label")
        and left_meta.get("systems_affected") == right_meta.get("systems_affected")
        and left_meta.get("notes") == right_meta.get("notes")
        and left_meta.get("source_reasons") == right_meta.get("source_reasons")
    )


def _merge_segments(left: TimelineSegment, right: TimelineSegment) -> TimelineSegment:
    merged_metadata = dict(left.metadata or {})
    merged_metadata["source_segment_ids"] = list(
        _unique(
            list((left.metadata or {}).get("source_segment_ids", []))
            + list((right.metadata or {}).get("source_segment_ids", []))
        )
    )
    return left.model_copy(
        update={"end_time": right.end_time, "metadata": merged_metadata}
    )


def _renumber_segment(
    mission_id: str, index: int, segment: TimelineSegment
) -> TimelineSegment:
    return segment.model_copy(update={"id": f"{mission_id}-availability-{index:03d}"})


def _highest_state(states: Iterable[TransportState]) -> TransportState:
    ordered = list(states)
    if not ordered:
        return TransportState.AVAILABLE
    return max(ordered, key=lambda state: _STATE_PRIORITY[state])


def _segment_notes(segment: TimelineSegment) -> list[str]:
    metadata = segment.metadata or {}
    notes: list[str] = []
    raw_notes = metadata.get("notes")
    if isinstance(raw_notes, list):
        notes.extend(str(note) for note in raw_notes if str(note).strip())
    elif isinstance(raw_notes, str) and raw_notes.strip():
        notes.append(raw_notes)
    raw_note = metadata.get("note")
    if isinstance(raw_note, str) and raw_note.strip():
        notes.append(raw_note)
    return notes


def _primary_outage_reason(reasons: tuple[str, ...]) -> str:
    for reason in reasons:
        if "outage" in reason.lower():
            return "system outage"
    return "system outage"


def _primary_sof_reason(reasons: tuple[str, ...]) -> str | None:
    for reason in reasons:
        if "safety-of-flight" in reason.lower():
            return reason
    return None


def _primary_activity_reason(
    reasons: tuple[str, ...], *, skip_ku_x: bool = False
) -> str:
    filtered_reasons = tuple(
        reason for reason in reasons if not (skip_ku_x and _has_ku_x_conflict((reason,)))
    )
    for reason in filtered_reasons:
        if _is_satellite_swap_reason(reason):
            return f"Satellite swap: {reason}"
    for reason in filtered_reasons:
        if reason and reason.strip():
            return reason
    return _REASON_LABELS["activity"]


def _is_satellite_swap_reason(reason: str | None) -> bool:
    if not reason:
        return False
    normalized = reason.lower()
    return any(
        token in normalized
        for token in (
            "satellite swap",
            "transition",
            "coverage swap",
            "coverage lost",
            "coverage exit",
        )
    )


def _has_ku_x_conflict(reasons: tuple[str, ...]) -> bool:
    for reason in reasons:
        normalized = reason.lower().replace(" ", "")
        if "x-ku" in normalized or "ku-x" in normalized or "x/ku" in normalized:
            return True
        if "ku/x" in normalized or (
            "ku" in normalized and "x" in normalized and "conflict" in normalized
        ):
            return True
    return False


def _has_actual_x_degradation(reasons: tuple[str, ...], in_aar: bool) -> bool:
    for reason in reasons:
        if _has_ku_x_conflict((reason,)):
            continue
        if _is_satellite_swap_reason(reason):
            return True
        normalized = reason.lower().replace("-", " ").replace("/", " ")
        if any(
            marker in normalized
            for marker in ("x band", "xband", "x transition", "x azimuth")
        ):
            return True
        if in_aar and "x" in normalized and "aar" in normalized:
            return True
    return False


def _has_x_aar_conflict(
    reasons: tuple[str, ...],
    in_aar: bool,
    impacted: tuple[Transport, ...],
    x_state: TransportState,
) -> bool:
    for reason in reasons:
        normalized = reason.lower().replace("-", " ").replace("/", " ")
        has_x_band_marker = any(
            marker in normalized
            for marker in ("x band", "xband", "x aar", "x azimuth", "x conflict")
        )
        if "aar" in normalized and (has_x_band_marker or "azimuth" in normalized):
            return True
    return in_aar and Transport.X in impacted and x_state != TransportState.AVAILABLE


def _parse_timestamp(raw: str) -> datetime:
    return _ensure_utc(datetime.fromisoformat(raw.replace("Z", "+00:00")))


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
