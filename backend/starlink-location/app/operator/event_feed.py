"""One captured feed with explicit per-source authority and pinned pagination."""

from datetime import timedelta

from .errors import OperatorError
from .event_eligibility import select_eligible
from .event_ledger import identity, reconcile
from .event_models import EventSnapshot, OperationalEvent, SourceCapture
from .event_projection import derive_events
from .maintenance import capacity_status
from .transport_review import derive_transport_review


def build_snapshot(runtime, mission_id, adapter):
    service, now = runtime.service, runtime.clock.now()
    inputs = adapter.capture(mission_id, as_of=now)
    events = derive_events(inputs, as_of=now, policy=runtime.event_policy)
    sources = [
        SourceCapture(
            source="operator",
            revision=str(inputs.H),
            generation=str(inputs.H),
            captured_at=now,
            aligned=True,
            guardable=True,
            freshness="fresh",
        )
    ] + inputs.sources
    guarded = tuple(
        s
        for s in inputs.sources
        if s.guardable and s.aligned and s.freshness == "fresh"
    )
    with runtime.event_publication.guard(guarded), service.store.connect(
        write=True
    ) as connection:
        versions = dict(
            connection.execute(
                "SELECT record_id, version FROM current_records WHERE mission_id=?",
                (mission_id,),
            )
        )
        if versions != {str(r.record_id): r.version for r in inputs.records}:
            raise OperatorError("event_snapshot_changed", retryable=True)
        if capacity_status(service.store)["exceeded"]:
            raise OperatorError("capacity_exceeded")
        old = [
            OperationalEvent.model_validate_json(row[0])
            for row in connection.execute(
                "SELECT o.event_json FROM event_heads h JOIN event_occurrences o USING (occurrence_id) WHERE o.mission_id=? AND h.retired=0",
                (mission_id,),
            )
        ]
        events = reconcile(
            connection,
            events,
            as_of=now,
            policy=runtime.event_policy,
            stability=runtime.event_stability,
        )
        present = {event.event_id for event in events}
        # Reconcile new candidates before retiring prior model families. Ambiguous
        # previews do not turn into durable refresh noise or an all-clear.
        for previous in old:
            if previous.event_id in present:
                continue
            if previous.source_ref and previous.source_ref.startswith("model:"):
                source = next(
                    (s for s in sources if s.source == previous.source_ref), None
                )
                waiting = any(
                    e.notification.preview and e.family_key == previous.family_key
                    for e in events
                )
                if (
                    waiting
                    or source is None
                    or source.freshness in ("stale", "unknown")
                    or not source.aligned
                ):
                    previous.freshness, previous.state = "unknown", "unknown"
                    previous.notification.available = False
                    previous.notification.reason = (
                        "Source unavailable or changing; last known prediction"
                    )
                    events.extend(
                        reconcile(
                            connection,
                            [previous],
                            as_of=now,
                            policy=runtime.event_policy,
                        )
                    )
                    continue
            previous.active = False
            events.extend(
                reconcile(
                    connection, [previous], as_of=now, policy=runtime.event_policy
                )
            )
        for event in events:
            if inputs.clock_regression:
                event.state = "unknown"
                event.notification.available = False
                event.notification.reason = "Clock regression; awaiting consistent time"
            if event.provenance == "modeled":
                source = next(
                    (s for s in sources if s.source == event.source_ref), None
                )
                if source is None or not source.aligned:
                    event.notification.available = False
                    event.notification.reason = "Prediction input alignment unknown"
                event.notification.acknowledgment_available = bool(
                    source
                    and source.guardable
                    and source.aligned
                    and source.freshness == "fresh"
                )
        select_eligible(events, as_of=now)
        current_occurrences = {e.notification.generation for e in events}
        for occurrence_id, event_json in connection.execute(
            "SELECT occurrence_id, event_json FROM event_occurrences WHERE mission_id=? AND created_at>=? ORDER BY created_at",
            (mission_id, (now - timedelta(hours=24)).isoformat()),
        ):
            if occurrence_id not in current_occurrences:
                historical = OperationalEvent.model_validate_json(event_json)
                historical.active, historical.state = False, "inactive"
                historical.notification.generation = occurrence_id
                historical.notification.retired = True
                historical.notification.eligible = False
                historical.notification.acknowledgment_available = False
                events.append(historical)
        transport_review = derive_transport_review(
            inputs.records, events, sources, as_of=now, H=inputs.H
        )
    events = [
        e
        for e in events
        if (e.due_at is None or e.due_at <= now + timedelta(hours=24))
        and (
            e.active or (e.due_at is not None and e.due_at >= now - timedelta(hours=24))
        )
    ]
    events.sort(key=lambda e: (e.due_at is None, e.due_at or now, e.event_id))
    coverage = (
        "available"
        if all(
            s.freshness in ("fresh", "disabled")
            and (s.aligned or s.freshness == "disabled")
            for s in sources
        )
        else "partial"
    )
    snapshot = EventSnapshot(
        store_id=inputs.store_id,
        api_epoch=inputs.api_epoch,
        mission_id=mission_id,
        source_mode=inputs.source_mode,
        simulation_run_id=inputs.simulation_run_id,
        as_of=now,
        H=inputs.H,
        generation=identity(
            inputs.api_epoch, inputs.H, [s.model_dump(mode="json") for s in sources]
        ),
        sources=sources,
        transport_review=transport_review,
        events=events,
        coverage=coverage,
    )
    snapshot.snapshot_token = runtime.event_snapshots.issue(snapshot)
    return snapshot


def snapshot_page(
    runtime, mission_id, *, adapter, cursor=None, limit=200, include_history=False
):
    if cursor:
        try:
            token, raw_offset = cursor.split(":")
            offset = int(raw_offset)
            if offset < 0:
                raise ValueError
            snapshot = runtime.event_snapshots.resolve(token)
        except (ValueError, TypeError):
            raise OperatorError("event_snapshot_changed", retryable=True) from None
        if snapshot.mission_id != mission_id or snapshot.api_epoch != str(
            runtime.health().api_epoch
        ):
            raise OperatorError("event_snapshot_changed", retryable=True)
        snapshot.snapshot_token = token
    else:
        snapshot, offset = build_snapshot(runtime, mission_id, adapter), 0
    events = [e for e in snapshot.events if include_history or e.active]
    page = snapshot.model_copy(deep=True)
    page.events = events[offset : offset + limit]
    page.truncated = offset + limit < len(events)
    page.cursor = (
        f"{snapshot.snapshot_token}:{offset+limit}" if page.truncated else None
    )
    return page
