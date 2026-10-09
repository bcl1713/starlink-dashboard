"""Pure briefing presentation projection; legacy domain states are never mutated.

Rules follow replay_state, timeline_builder/events and call_availability:
Coverage gaps, X transitions, manual AR tracks and recognized X conflicts
prove Down. Other degradation needs independent usability proof.
SOF and resolved AR are coordination context, never availability evidence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from hashlib import sha256
from itertools import groupby, pairwise
from typing import Literal

from app.mission.models import Transport, TransportState

from .briefing_clocks import ensure_utc, format_clocks
from .snapshot import LegSnapshot
from .snapshot_inputs import canonical_json

TRANSPORTS = (Transport.KA, Transport.KU, Transport.X)
TRANSPORT_NAMES = ("Commercial Ka", "Starshield", "X-Band MILSATCOM")
PREDICTION_CAVEAT = (
    "Communications posture is a prediction, not a throughput guarantee."
)
QUIET_SUMMARY = (
    "No communications degradation or coordination windows beyond standard SOF "
    "restrictions identified for this leg."
)


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    leg_id: str
    transport: Transport | None
    source_type: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    timestamp: datetime | None = None
    reason: str = ""
    metadata_json: bytes = b"{}"
    source_revision: str = ""
    source_digest: str = ""
    derived_identity: bool = False
    state: TransportState | None = None
    original_json: bytes = b"{}"

    @property
    def metadata(self) -> dict:
        """A private copy: mutations cannot affect the captured record."""
        return json.loads(self.metadata_json)


@dataclass(frozen=True)
class UsabilityDecision:
    value: Literal["Up", "Down", "?"]
    rule_id: str
    source_ids: tuple[str, ...]
    limitation: str | None = None


@dataclass(frozen=True)
class BriefingRestriction:
    source_id: str
    kind: str
    label: str
    start_time: datetime
    end_time: datetime


@dataclass(frozen=True)
class BriefingInterval:
    id: str
    window_number: int
    start_time: datetime
    end_time: datetime
    decisions: tuple[UsabilityDecision, ...]  # Ka, Ku, X; matches the briefing lanes.
    posture: str
    restrictions: tuple[BriefingRestriction, ...]
    active_source_ids: tuple[str, ...]
    causes: tuple[str, ...]
    limitations: tuple[str, ...]
    remaining_transports: tuple[str, ...]


@dataclass(frozen=True)
class BriefingLeg:
    leg_id: str
    utc_bounds: tuple[datetime, datetime] | None
    intervals: tuple[BriefingInterval, ...]
    coordination_rows: tuple[BriefingInterval, ...]
    sources: tuple[SourceRecord, ...]
    notes: tuple[str, ...]
    planned_departure_basis: str
    quiet_summary: str | None
    prediction_caveat: str = PREDICTION_CAVEAT


def _unique(values) -> tuple:
    return tuple(dict.fromkeys(v for v in values if v))


def _proven_down(source: SourceRecord) -> bool:
    meta = source.metadata
    if (
        source.state == TransportState.OFFLINE
        or meta.get("independent_usability") == "Down"
    ):
        return True
    if source.source_type in {
        "configured_outage",
        "ka_outage_start",
        "ku_outage_start",
    }:
        return True
    if source.transport == Transport.KA and (
        source.source_type == "ka_coverage_exit"
        or source.reason == "ka_no_coverage"
        or meta.get("condition_key") == "ka_no_coverage"
    ):
        return True
    return source.transport == Transport.X and (
        source.source_type in {"x_transition_start", "manual_aar_track_start"}
        or (
            source.source_type == "x_azimuth_violation"
            and source.reason.startswith(
                ("X-Ku Conflict", "X-AAR Conflict", "X azimuth conflict")
            )
        )
        or meta.get("line_of_sight_blocked") is True
        or meta.get("elevation_below_min") is True
    )


def classify_transport(
    state: TransportState | None, sources: tuple[SourceRecord, ...]
) -> UsabilityDecision:
    """Classify already active, transport-local evidence; keep every cause ID.

    A caller supplying AVAILABLE is asserting a known raw state. The leg
    projection below supplies that state only with current captured prerequisites
    and prediction coverage, never from normalized call-posture defaults.
    """
    ids = _unique(s.source_id for s in sources)
    limitations = _unique(
        s.reason for s in sources if s.source_type != "availability_basis"
    )
    text = "; ".join(limitations) or None
    fresh = tuple(s for s in sources if s.metadata.get("stale") is not True)
    has_stale = len(fresh) != len(sources)
    if (state == TransportState.OFFLINE and not has_stale) or any(
        _proven_down(s) for s in fresh
    ):
        return UsabilityDecision("Down", "independent-unavailability", ids, text)
    if has_stale and not any(
        s.metadata.get("independent_usability") == "Up" for s in fresh
    ):
        return UsabilityDecision(
            "?", "stale-evidence", ids, text or "Prediction basis is stale"
        )
    sources = fresh
    missing = any(s.metadata.get("prerequisites_available") is False for s in sources)
    if missing:
        return UsabilityDecision(
            "?",
            "missing-prerequisites",
            ids,
            text or "Coverage or geometry prerequisites unavailable",
        )
    conditions = [
        s
        for s in sources
        if s.source_type not in {"availability_basis", "transport_state"}
    ]
    independent_up = any(
        s.metadata.get("independent_usability") == "Up" for s in sources
    )
    if conditions and not independent_up:
        return UsabilityDecision(
            "?", "unresolved-condition", ids, text or "Transport usability unresolved"
        )
    if independent_up:
        return UsabilityDecision("Up", "independent-usability", ids, text)
    if state == TransportState.AVAILABLE:
        return UsabilityDecision("Up", "available", ids, text)
    return UsabilityDecision(
        "?",
        "missing-or-unrecognized-state",
        ids,
        text or "Transport usability unresolved",
    )


def _time(raw) -> datetime | None:
    return (
        ensure_utc(datetime.fromisoformat(raw.replace("Z", "+00:00"))) if raw else None
    )


def _source(
    raw: dict, leg_id: str, revision: str, kind: str | None = None
) -> SourceRecord:
    payload = canonical_json(raw)
    digest = sha256(payload).hexdigest()
    metadata = raw.get("metadata") or {}
    source_type = (
        kind
        or raw.get("source_type")
        or raw.get("event_type")
        or raw.get("kind")
        or "source"
    )
    identity = (
        raw.get("source_id")
        or raw.get("id")
        or metadata.get("transition_id")
        or metadata.get("track_id")
    )
    derived = not identity
    identity = identity or f"derived:{leg_id}:{source_type}:{digest[:20]}"
    transport = raw.get("affected_transport") or raw.get("transport")
    return SourceRecord(
        source_id=identity,
        leg_id=leg_id,
        transport=Transport(transport) if transport else None,
        source_type=source_type,
        start_time=_time(raw.get("start_time")),
        end_time=_time(raw.get("end_time")),
        timestamp=_time(raw.get("timestamp")),
        reason=raw.get("reason") or raw.get("label") or raw.get("message") or "",
        metadata_json=canonical_json(metadata),
        source_revision=raw.get("source_revision") or revision,
        source_digest=raw.get("source_digest") or digest,
        derived_identity=derived,
        state=TransportState(raw["state"]) if raw.get("state") else None,
        original_json=payload,
    )


@dataclass(frozen=True)
class _Span:
    start: datetime
    end: datetime
    source: SourceRecord


def _event_action(source: SourceRecord) -> tuple[str, bool] | None:
    kind, meta = source.source_type, source.metadata
    severity = json.loads(source.original_json).get("severity", "warning")
    if kind in {"takeoff_buffer", "landing_buffer", "aar_window", "availability_basis"}:
        return None
    for start, end, key in (
        (
            "x_transition_start",
            "x_transition_end",
            "x_transition:"
            + str(
                meta.get("transition_id")
                or json.loads(source.original_json).get("satellite_id")
            ),
        ),
        ("ka_coverage_exit", "ka_coverage_entry", "ka_no_coverage"),
        (
            "manual_aar_track_start",
            "manual_aar_track_end",
            "manual_ar:" + str(meta.get("track_id")),
        ),
        (
            "ka_outage_start",
            "ka_outage_end",
            "ka_outage:" + str(meta.get("id", "default")),
        ),
        (
            "ku_outage_start",
            "ku_outage_end",
            "ku_outage:" + str(meta.get("id", "default")),
        ),
    ):
        if kind in {start, end}:
            return key, kind == start
    if kind == "ka_transition":
        return "ka_transition:" + str(
            meta.get("transition_id")
            or json.loads(source.original_json).get("satellite_id")
        ), severity in {"warning", "critical"}
    if kind == "x_azimuth_violation":
        return "x_azimuth:" + str(meta.get("constraint") or "legacy"), severity in {
            "warning",
            "critical",
        }
    if severity in {"warning", "critical"}:
        return "unknown:" + kind, True
    return None


def _event_spans(
    records: tuple[SourceRecord, ...], end: datetime, configured: set[Transport]
) -> list[_Span]:
    active: dict[tuple[Transport, str], tuple[SourceRecord, ...]] = {}
    spans = []
    events = sorted(
        (s for s in records if s.timestamp is not None),
        key=lambda s: (s.timestamp, s.source_id, s.source_digest),
    )
    for timestamp, batch in groupby(events, key=lambda s: s.timestamp):
        changes: dict[tuple[Transport, str], list[tuple[SourceRecord, bool]]] = {}
        for source in batch:
            if (
                source.source_type
                in {
                    "ka_outage_start",
                    "ka_outage_end",
                    "ku_outage_start",
                    "ku_outage_end",
                }
                and source.transport in configured
            ):
                # Saved windows handle nested same-lane outages; the legacy
                # event producer omits those source identities.
                continue
            action = _event_action(source)
            if action is not None and source.transport is not None:
                key, activate = action
                changes.setdefault((source.transport, key), []).append(
                    (source, activate)
                )
        for key, change in changes.items():
            previous = active.pop(key, ())
            spans.extend(
                _Span(s.timestamp, timestamp, s)
                for s in previous
                if s.timestamp < timestamp
            )
            starting = tuple(s for s, activates in change if activates)
            ending = any(not activates for _, activates in change)
            # Combine simultaneous endpoints before evaluating the next span.
            # A start/end pair without a preceding condition is zero duration.
            if starting and (previous or not ending):
                active[key] = starting
    spans.extend(
        _Span(s.timestamp, end, s)
        for records in active.values()
        for s in records
        if s.timestamp < end
    )
    return spans


def _cached_spans(
    leg: LegSnapshot,
    committed: dict,
    timeline: dict,
    sources: tuple[SourceRecord, ...],
    start: datetime,
    end: datetime,
) -> list[_Span]:
    """Use exact producer reasons only on an unchanged, covered cache basis.

    Available/default fields and normalized call-posture strings are never
    evidence. Cache missing provenance therefore cannot become blanket Nominal
    or a definitive total outage. Shifted or older predictions stay uncertain.
    """
    cached = [
        s
        for s in sources
        if s.source_type == "cached_segment" and s.start_time and s.end_time
    ]
    created, updated = _time(timeline.get("created_at")), _time(
        committed.get("updated_at")
    )
    if (
        not cached
        or min(s.start_time for s in cached) != start
        or max(s.end_time for s in cached) != end
        or created is None
        or updated is None
        or created < updated
    ):
        return []
    spans = []
    for source in cached:
        raw = json.loads(source.original_json)
        reasons = source.metadata.get("source_reasons") or raw.get("reasons", [])
        if not isinstance(reasons, list):
            continue
        unknown_reason = False
        for reason in reasons:
            transport, kind, metadata = None, None, {}
            if reason == "ka_no_coverage" or reason.startswith("Ka coverage lost ("):
                transport, kind = Transport.KA, "ka_coverage_exit"
            elif reason.startswith("X line-of-sight blocked ("):
                transport, kind, metadata = (
                    Transport.X,
                    "x_azimuth_violation",
                    {"line_of_sight_blocked": True},
                )
            elif reason.startswith(
                ("X-Ku Conflict", "X-AAR Conflict", "X azimuth conflict")
            ):
                transport, kind = Transport.X, "x_azimuth_violation"
            elif reason.startswith("X Transition to "):
                transport, kind = Transport.X, "x_transition_start"
            elif reason.startswith("Manual AR Track:"):
                transport, kind = Transport.X, "manual_aar_track_start"
            elif reason.startswith("Ka transition "):
                transport, kind = Transport.KA, "ka_transition"
            elif not reason.startswith(
                ("Safety-of-Flight", "Takeoff", "Landing", "Ka outage", "Ku outage")
            ):
                unknown_reason = True
            state = raw.get(
                {Transport.KA: "ka_state", Transport.X: "x_state"}.get(transport)
            )
            if transport is not None and (
                state in {"degraded", "offline"}
                or (state == "available" and reason.startswith("X-Ku Conflict"))
            ):
                evidence = replace(
                    source,
                    transport=transport,
                    source_type=kind,
                    reason=reason,
                    state=None,
                    metadata_json=canonical_json(metadata),
                )
                spans.append(_Span(source.start_time, source.end_time, evidence))
        for transport, field in ((Transport.KA, "ka_state"), (Transport.X, "x_state")):
            known_x_down = transport == Transport.X and any(
                span.source.source_id == source.source_id and _proven_down(span.source)
                for span in spans
            )
            if (
                unknown_reason
                and (raw.get(field) in {"degraded", "offline"} or known_x_down)
            ) or (raw.get(field) == "offline" and known_x_down):
                unresolved = replace(
                    source,
                    transport=transport,
                    source_type="cached_unknown",
                    reason="Cached transport conditions are ambiguous",
                    state=None,
                )
                spans.append(_Span(source.start_time, source.end_time, unresolved))
    return spans


def _collect_sources(
    leg: LegSnapshot, committed: dict, timeline: dict
) -> tuple[SourceRecord, ...]:
    revision = sha256(leg.leg_json).hexdigest()
    sources = [_source(json.loads(v), leg.leg_id, revision) for v in leg.source_records]
    transports = committed.get("transports") or {}
    for key, transport in (("ka_outages", "Ka"), ("ku_overrides", "Ku")):
        for raw in transports.get(key, []):
            start = _time(raw["start_time"])
            sources.append(
                _source(
                    {
                        **raw,
                        "transport": transport,
                        "end_time": (
                            start + timedelta(seconds=raw["duration_seconds"])
                        ).isoformat(),
                        "reason": raw.get("reason") or f"{transport} outage",
                    },
                    leg.leg_id,
                    revision,
                    "configured_outage",
                )
            )
    for key in ("manual_aar_tracks", "x_transitions", "aar_windows"):
        sources.extend(
            _source(raw, leg.leg_id, revision, "configured_" + key)
            for raw in transports.get(key, [])
        )
    sources.extend(
        _source(json.loads(v), leg.leg_id, revision, "restriction")
        for v in leg.resolved_restrictions
    )
    if leg.preparation_origin == "cached":
        sources.extend(
            _source(
                raw,
                leg.leg_id,
                sha256(leg.timeline_json or b"").hexdigest(),
                "cached_segment",
            )
            for raw in timeline.get("segments", [])
        )
    for kind, key in (
        ("advisory", "advisories"),
        ("coverage_detail", "coverage_events"),
    ):
        sources.extend(
            _source(raw, leg.leg_id, revision, kind) for raw in timeline.get(key, [])
        )
    return tuple(sources)


def _restrictions(
    leg: LegSnapshot,
    committed: dict,
    sources: tuple[SourceRecord, ...],
    start: datetime,
    end: datetime,
    notes: list[str],
) -> tuple[BriefingRestriction, ...]:
    restrictions = []
    resolved_ids = set()
    for value in leg.resolved_restrictions:
        raw = json.loads(value)
        identity = raw["source_id"]
        resolved_ids.add(identity)
        a, b = _time(raw.get("start_time")), _time(raw.get("end_time"))
        if a is None or b is None or b <= a:
            notes.append(f"AR {identity}: timing unresolved; no timed window shown.")
        elif max(start, a) < min(end, b):
            restrictions.append(
                BriefingRestriction(
                    identity, raw["kind"], raw["label"], max(start, a), min(end, b)
                )
            )
    for source in sources:
        if (
            source.source_type == "configured_aar_windows"
            and source.source_id not in resolved_ids
        ):
            notes.append(
                f"AR {source.source_id}: timing unavailable; no timed window shown."
            )
        if (
            source.source_type == "configured_manual_aar_tracks"
            and source.source_id not in resolved_ids
        ):
            splice = (committed.get("transports") or {}).get(
                "manual_route_splice"
            ) or {}
            reason = (
                "selected splice unavailable or inapplicable"
                if splice.get("enabled_track_id") == source.source_id
                else "timing unresolved"
            )
            notes.append(
                f"Manual AR {source.source_id}: {reason}; no timed window shown."
            )
    if not {"sof-takeoff", "sof-landing"}.issubset(resolved_ids):
        notes.append(
            "SOF timing unavailable in captured preparation; standard windows cannot be verified."
        )
    return tuple(
        sorted(restrictions, key=lambda r: (r.start_time, r.end_time, r.source_id))
    )


def _posture(decisions: tuple[UsabilityDecision, ...]) -> str:
    if any(d.value == "?" for d in decisions):
        return "Posture uncertain"
    return (
        "Communications unavailable",
        "Limited / elevated risk",
        "Degraded",
        "Nominal",
    )[sum(d.value == "Up" for d in decisions)]


def _decisions(
    active: tuple[SourceRecord, ...], current: bool
) -> tuple[UsabilityDecision, ...]:
    decisions = []
    for transport in TRANSPORTS:
        records = tuple(s for s in active if s.transport == transport)
        basis = any(
            s.source_type == "availability_basis"
            and s.metadata.get("prerequisites_available") is True
            for s in records
        )
        state = TransportState.AVAILABLE if current and basis else None
        decisions.append(classify_transport(state, records))
    return tuple(decisions)


def _mergeable(left: BriefingInterval, right: BriefingInterval) -> bool:
    return (
        left.end_time == right.start_time
        and replace(left, start_time=right.start_time, end_time=right.end_time) == right
    )


def project_briefing_leg(leg: LegSnapshot) -> BriefingLeg:
    """Freeze full flight partition first; filter its exact objects afterward."""
    committed = json.loads(leg.leg_json)
    timeline = json.loads(leg.timeline_json) if leg.timeline_json else {}
    sources = _collect_sources(leg, committed, timeline)
    notes = list(leg.warnings)
    guidance = "Absolute conditions can shift relative to the aircraft after departure changes; re-export when assumptions or predictions change."
    if leg.utc_bounds is None:
        notes.append(
            "Flight timing unavailable; incomplete leg data, no timed partition shown."
        )
        return BriefingLeg(
            leg.leg_id,
            None,
            (),
            (),
            sources,
            _unique(notes),
            "Planned departure unavailable. " + guidance,
            None,
        )
    start, end = (ensure_utc(v) for v in leg.utc_bounds)
    if end <= start:
        raise ValueError("Briefing leg landing must follow takeoff")
    basis = f"Planned departure basis: {format_clocks(start, start).et} / {format_clocks(start, start).zulu}. {guidance}"
    if leg.preparation_origin != "rebuilt":
        notes.append(
            "Cached or missing predictions retain their original basis; current availability is uncertain without independent evidence."
        )
    if leg.effective_route_json is None:
        notes.append(
            "Effective route unavailable; route-based availability prerequisites cannot be verified."
        )
    restrictions = _restrictions(leg, committed, sources, start, end, notes)
    spans = [
        _Span(s.start_time, s.end_time, s)
        for s in sources
        if s.source_type
        in {"configured_outage", "availability_basis", "transport_state"}
        and s.start_time
        and s.end_time
        and s.end_time > s.start_time
    ]
    if leg.preparation_origin == "rebuilt":
        configured = {
            s.transport for s in sources if s.source_type == "configured_outage"
        }
        spans.extend(_event_spans(sources, end, configured))
    elif leg.preparation_origin == "cached":
        spans.extend(_cached_spans(leg, committed, timeline, sources, start, end))
    boundaries = {start, end}
    for span in spans:
        if max(start, span.start) < min(end, span.end):
            boundaries.update((max(start, span.start), min(end, span.end)))
    for restriction in restrictions:
        boundaries.update((restriction.start_time, restriction.end_time))
    segments = timeline.get("segments", [])
    for segment in segments:
        a, b = _time(segment.get("start_time")), _time(segment.get("end_time"))
        if a and b and max(start, a) < min(end, b):
            boundaries.update((max(start, a), min(end, b)))
    intervals = []
    ordered = sorted(boundaries)
    for a, b in pairwise(ordered):
        active = tuple(span.source for span in spans if span.start <= a < span.end)
        covered = any(
            _time(s.get("start_time")) <= a < _time(s.get("end_time"))
            for s in segments
            if s.get("start_time") and s.get("end_time")
        )
        current = (
            leg.preparation_origin == "rebuilt"
            and leg.effective_route_json is not None
            and covered
        )
        # Exclude unverified basis records when the predictions do not cover this
        # interval; independent current outage records still prove Down.
        if not current:
            active = tuple(
                s
                for s in active
                if s.source_type == "configured_outage"
                or (
                    leg.preparation_origin == "cached"
                    and s.source_digest
                    in {
                        c.source_digest
                        for c in sources
                        if c.source_type == "cached_segment"
                    }
                )
            )
        decisions = _decisions(active, current)
        context = tuple(r for r in restrictions if r.start_time <= a < r.end_time)
        causes = _unique(
            [s.reason for s in active if s.source_type != "availability_basis"]
            + [r.label for r in context]
        )
        limitations = _unique(d.limitation for d in decisions)
        interval = BriefingInterval(
            "",
            0,
            a,
            b,
            decisions,
            _posture(decisions),
            context,
            _unique([s.source_id for s in active] + [r.source_id for r in context]),
            causes,
            limitations,
            tuple(
                name
                for name, decision in zip(TRANSPORT_NAMES, decisions)
                if decision.value == "Up"
            ),
        )
        if intervals and _mergeable(intervals[-1], interval):
            intervals[-1] = replace(intervals[-1], end_time=b)
        else:
            intervals.append(interval)
    full = tuple(
        replace(i, id=f"{leg.leg_id}-window-{n:03d}", window_number=n)
        for n, i in enumerate(intervals, 1)
    )
    rows = tuple(
        i for i in full if i.restrictions or i.posture != "Nominal" or i.limitations
    )
    quiet = (
        all(
            i.posture == "Nominal"
            and not i.limitations
            and all(r.kind == "sof" for r in i.restrictions)
            for i in full
        )
        and not notes
    )
    return BriefingLeg(
        leg.leg_id,
        (start, end),
        full,
        rows,
        sources,
        _unique(notes),
        basis,
        QUIET_SUMMARY if quiet else None,
    )
