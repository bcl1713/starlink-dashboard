"""Pure chronological projection over existing records and model publications."""

from datetime import timedelta

from .event_ledger import identity
from .event_models import EventNotification, OperationalEvent
from .time_models import utc_timestamp


def _time(value):
    return utc_timestamp(value) if value is not None else None


def _state(due, end, now, active):
    if not active:
        return "inactive"
    if due is None:
        return "unknown"
    if now < due:
        return "upcoming"
    if end is not None and now <= end:
        return "active"
    return "overdue"


def _window_state(start, end, now, source):
    if end <= now:
        if source and source.aligned and source.freshness == "fresh":
            return {"active": False, "state": "inactive"}
        return {"active": True, "state": "unknown"}
    return {"active": True, "state": _state(start, end, now, True)}


def _protect(event, records):
    by_id = {str(r.record_id): r for r in records if not r.deleted}
    for participation in by_id.values():
        payload = participation.payload
        if payload.entry_type != "participation" or payload.state != "connected":
            continue
        if participation.leg_id and participation.leg_id != event.leg_id:
            continue
        conference = by_id.get(str(payload.conference_id))
        known = bool(
            conference
            and conference.payload.entry_type == "conference"
            and conference.payload.status == "established"
        )
        configured = conference.payload.configured_transport if known else None
        intended = conference.payload.intended_transport if known else None
        if (
            event.transport
            and known
            and (configured or intended)
            and event.transport not in (configured, intended)
        ):
            continue
        event.protected_participation_ids.append(str(participation.record_id))
        event.dependent_versions[str(participation.record_id)] = participation.version
        if conference:
            event.conference_ids.append(str(conference.record_id))
            event.dependent_versions[str(conference.record_id)] = conference.version
        if not known:
            event.discrepancies.append(
                "Connected customer; conference continuity unknown"
            )
            event.transport_relevance = "unknown"
            event.continuity_status = "unknown"
        elif not event.discrepancies:
            event.transport_relevance = (
                "call"
                if event.transport is None
                else (
                    "configured"
                    if configured == event.transport
                    else "intended" if intended == event.transport else "unknown"
                )
            )
    event.protected_participation_ids = sorted(set(event.protected_participation_ids))
    event.conference_ids = sorted(set(event.conference_ids))
    event.discrepancies = sorted(set(event.discrepancies))


def derive_events(inputs, *, as_of, policy):
    events = []
    for record in inputs.records:
        payload = record.payload
        common = {
            "mission_id": record.mission_id,
            "leg_id": record.leg_id,
            "source_ref": str(record.record_id),
            "source_revision": str(record.version),
            "source_captured_at": record.recorded_at,
            "dependent_versions": {str(record.record_id): record.version},
        }
        if payload.entry_type == "call":
            active = not record.deleted and payload.status not in (
                "completed",
                "cancelled",
            )
            start, end = record.time.planned_start_at, record.time.planned_end_at
            milestones = [("call_start", start)]
            if start is not None and payload.prep_lead_minutes is not None:
                milestones.append(
                    ("call_prep", start - timedelta(minutes=payload.prep_lead_minutes))
                )
            for kind, due in milestones:
                notification = EventNotification(
                    severity_generation=2,
                    available=active
                    and payload.status != "tentative"
                    and due is not None,
                )
                if not notification.available:
                    notification.reason = "Inactive, tentative or timing unknown"
                events.append(
                    OperationalEvent(
                        **common,
                        event_id=identity(record.record_id, kind),
                        kind=kind,
                        title=(
                            "Prepare: "
                            if kind == "call_prep"
                            else "Customer requirement: "
                        )
                        + payload.title,
                        due_at=due,
                        end_at=end
                        or (start + timedelta(minutes=15) if start else None),
                        active=active,
                        state=_state(due, end, as_of, active),
                        schedule_key=identity(kind, due),
                        notification=notification,
                    )
                )
        elif payload.entry_type == "issue":
            active = not record.deleted and payload.status != "resolved"
            due = payload.follow_up_at
            events.append(
                OperationalEvent(
                    **common,
                    event_id=identity(record.record_id, "followup"),
                    kind="issue_followup",
                    title="Follow up: " + payload.title,
                    due_at=due,
                    active=active,
                    provenance="operator_reported",
                    state=_state(due, None, as_of, active),
                    schedule_key=identity(due),
                )
            )
    mission_id = inputs.records[0].mission_id if inputs.records else None
    # Empty record sets still have model events for the requested mission.
    mission_id = getattr(inputs, "mission_id", None) or mission_id
    for leg_id, model in inputs.models.items():
        if not mission_id:
            continue
        source = next(
            (s for s in inputs.sources if s.source == "model:" + leg_id), None
        )
        freshness = (
            source.freshness
            if source and source.freshness in ("fresh", "stale")
            else "unknown"
        )
        common = {
            "mission_id": mission_id,
            "leg_id": leg_id,
            "provenance": "modeled",
            "source_ref": "model:" + leg_id,
            "source_revision": source.revision if source else None,
            "source_captured_at": source.captured_at if source else None,
            "freshness": freshness,
            "confidence": "Modeled estimate",
            "continuity_status": (
                "modeled"
                if source and source.aligned and model.get("call_continuity")
                else "unknown"
            ),
        }
        forecast = model.get("pop_forecast") or {}
        transitions = (
            forecast.get("transitions", []) if forecast.get("status") == "ready" else []
        )
        for window in transitions:
            crossing = window["crossing"]
            key = identity(
                mission_id,
                leg_id,
                "pop",
                forecast.get("catalog_fingerprint"),
                crossing.get("from_pop_id"),
                crossing.get("to_pop_id"),
                crossing.get("segment_index"),
                crossing.get("fraction"),
                crossing.get("latitude"),
                crossing.get("longitude"),
            )
            start, end = _time(window["window_start_utc"]), _time(
                window["window_end_utc"]
            )
            event = OperationalEvent(
                **common,
                event_id=key,
                kind="pop_advisory",
                title="Modeled PoP transition window",
                due_at=start,
                end_at=end,
                transport="Starshield",
                significance="advisory",
                **_window_state(start, end, as_of, source),
                schedule_key=key,
            )
            _protect(event, inputs.records)
            events.append(event)
        # #348 publishes observation/overdue advisories independently of its
        # future-window list. Missing observed PoP never means service down.
        for advisory in model.get("pop_advisories", []):
            kind = advisory.get("kind")
            if kind not in ("observation_unknown", "mismatch", "overdue"):
                continue
            key = identity(
                mission_id,
                leg_id,
                "pop-state",
                kind,
                advisory.get("transition_id") if kind == "overdue" else None,
            )
            values = dict(common)
            values["provenance"] = "observed" if kind != "overdue" else "modeled"
            values["freshness"] = (
                "unknown" if kind == "observation_unknown" else freshness
            )
            event = OperationalEvent(
                **values,
                event_id=key,
                kind="pop_advisory",
                title={
                    "observation_unknown": "PoP observation unknown",
                    "mismatch": "Observed PoP differs from route estimate",
                    "overdue": "PoP handover not confirmed",
                }[kind],
                significance="advisory",
                schedule_key=key,
                state="unknown",
                notification=EventNotification(
                    available=False,
                    acknowledgment_available=False,
                    reason="Continuity advisory; not an observed service outage",
                ),
            )
            _protect(event, inputs.records)
            events.append(event)
        spans = []
        for interval in (model.get("call_continuity") or {}).get("intervals", []):
            classification = interval["classification"]
            if classification in ("ordinary", "advisory", "x_fallback"):
                continue
            spans.append(
                (
                    None,
                    (
                        "call_outage"
                        if classification in ("planned_outage", "existing_outage")
                        else "advisory"
                    ),
                    tuple(sorted(interval.get("source_ids", []))),
                    _time(interval["start_utc"]),
                    _time(interval["end_utc"]),
                )
            )
        for capability in model.get("capability_spans", []):
            for transport, field in (
                ("Ka", "ka"),
                ("X", "x"),
                ("Starshield", "starshield"),
            ):
                if capability.get(field) != "unavailable":
                    continue
                concurrent = (
                    field == "x" and capability.get("x_concurrency_only") is True
                )
                spans.append(
                    (
                        transport,
                        "degraded" if concurrent else "unavailable",
                        (
                            ("x_concurrency_only",)
                            if concurrent
                            else ("modeled_capability", transport)
                        ),
                        _time(capability["start_utc"]),
                        _time(capability["end_utc"]),
                    )
                )
        for segment in (
            () if "capability_spans" in model else model.get("segments", [])
        ):
            for transport, field in (
                ("Ka", "ka_state"),
                ("X", "x_state"),
                ("Starshield", "ku_state"),
            ):
                state = segment.get(field)
                if state in ("offline", "degraded"):
                    spans.append(
                        (
                            transport,
                            "unavailable" if state == "offline" else "degraded",
                            tuple(sorted(segment.get("reasons") or [])),
                            _time(segment["start_time"]),
                            _time(segment["end_time"]),
                        )
                    )
        # Combine adjacent same-cause restrictions before assigning ordered occurrence.
        groups = {}
        for transport, severity, causes, start, end in spans:
            if end <= start:
                continue
            groups.setdefault((transport, causes), []).append((start, end, severity))
        for (transport, causes), windows in groups.items():
            merged = []
            for start, end, severity in sorted(windows):
                if merged and start <= merged[-1][1] and merged[-1][2] == severity:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], end), severity)
                else:
                    merged.append((start, end, severity))
            for index, (start, end, severity) in enumerate(merged):
                key = identity(
                    mission_id,
                    leg_id,
                    "restriction",
                    model.get("route_geometry_identity"),
                    transport,
                    causes,
                    index,
                )
                event = OperationalEvent(
                    **common,
                    event_id=key,
                    kind="restriction",
                    title=(transport + " " if transport else "Customer communications ")
                    + "modeled "
                    + (
                        "concurrency restriction"
                        if "x_concurrency_only" in causes
                        else severity.replace("_", " ")
                    ),
                    due_at=start,
                    end_at=end,
                    transport=transport,
                    significance=severity,
                    **_window_state(start, end, as_of, source),
                    schedule_key=key,
                    family_key=identity(
                        mission_id,
                        leg_id,
                        model.get("route_geometry_identity"),
                        transport,
                        causes,
                    ),
                    notification=EventNotification(
                        severity_generation={
                            "advisory": 0,
                            "degraded": 1,
                            "unavailable": 2,
                            "call_outage": 3,
                        }[severity]
                    ),
                )
                _protect(event, inputs.records)
                events.append(event)
    return sorted(
        events, key=lambda e: (e.due_at is None, e.due_at or as_of, e.event_id)
    )
