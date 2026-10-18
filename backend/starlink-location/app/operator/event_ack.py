"""Durable acknowledgment with receipt-first retries and local publication leases."""

from dataclasses import replace
from uuid import UUID, uuid4

from .commands import receipt_for_key
from .errors import OperatorError
from .event_ledger import identity, reconcile
from .event_models import AckReceipt
from .event_projection import derive_events
from .event_sources import EventSourceAdapter
from .maintenance import capacity_status
from .queries import select_records
from .time_models import utc_timestamp


def acknowledge(request, *, key, epoch, runtime, adapter=None):
    service = runtime.service
    health = runtime.health()
    if epoch != str(health.api_epoch):
        raise OperatorError("store_epoch_changed")
    try:
        key = str(UUID(key))
    except (ValueError, TypeError, AttributeError):
        raise OperatorError(
            "validation_error", fields={"key": "Expected UUID"}
        ) from None
    request_hash = identity("event_acknowledgment", request.model_dump(mode="json"))
    with service.store.connect() as connection:
        receipt = receipt_for_key(connection, key, request_hash)
        if receipt is not None:
            return receipt, True
    snapshot = runtime.event_snapshots.resolve(request.snapshot_token)
    if snapshot.api_epoch != epoch or snapshot.store_id != str(health.store_id):
        raise OperatorError("event_snapshot_changed", retryable=True)
    event = next(
        (
            e
            for e in snapshot.events
            if e.notification.generation == request.occurrence_id
            and e.notification.severity_generation == request.severity_generation
            and e.active
            and not e.notification.retired
        ),
        None,
    )
    if event is None:
        raise OperatorError("event_snapshot_changed", retryable=True)
    if health.clock_regression:
        raise OperatorError("event_source_unavailable", retryable=True)
    adapter = (
        adapter
        or getattr(runtime, "event_source_adapter", None)
        or EventSourceAdapter(service)
    )
    now = runtime.clock.now()
    inputs = adapter.capture(snapshot.mission_id, as_of=now)
    expected = ()
    if event.provenance == "modeled":
        source = next((s for s in inputs.sources if s.source == event.source_ref), None)
        previous = next(
            (s for s in snapshot.sources if s.source == event.source_ref), None
        )
        if (
            source is None
            or not source.guardable
            or not source.aligned
            or source.freshness != "fresh"
        ):
            raise OperatorError("event_source_unavailable", retryable=True)
        if previous is None or (
            source.generation,
            source.revision,
            source.input_identity,
        ) != (previous.generation, previous.revision, previous.input_identity):
            raise OperatorError("event_snapshot_changed", retryable=True)
        expected = (source,)
    with runtime.event_publication.guard(expected), service.store.connect(
        write=True
    ) as connection:
        receipt = receipt_for_key(connection, key, request_hash)
        if receipt is not None:
            return receipt, True
        if capacity_status(service.store)["exceeded"]:
            raise OperatorError("capacity_exceeded")
        records = select_records(
            connection,
            "SELECT * FROM current_records WHERE mission_id=?",
            (snapshot.mission_id,),
        )
        versions = {str(r.record_id): r.version for r in records}
        if any(
            versions.get(record_id) != version
            for record_id, version in event.dependent_versions.items()
        ):
            raise OperatorError("event_snapshot_changed", retryable=True)
        current = derive_events(
            replace(inputs, records=records), as_of=now, policy=runtime.event_policy
        )
        current = reconcile(
            connection,
            current,
            as_of=now,
            policy=runtime.event_policy,
            stability=runtime.event_stability,
        )
        target = next(
            (
                e
                for e in current
                if e.notification.generation == request.occurrence_id
                and e.notification.severity_generation == request.severity_generation
                and e.active
                and not e.notification.retired
            ),
            None,
        )
        if target is None or not target.notification.available:
            raise OperatorError("event_snapshot_changed", retryable=True)
        existing = connection.execute(
            "SELECT acknowledgment_id, acknowledged_at FROM event_acknowledgments WHERE occurrence_id=? AND severity_generation=?",
            (request.occurrence_id, request.severity_generation),
        ).fetchone()
        command_id = str(uuid4())
        ack_id, at = existing if existing else (str(uuid4()), now)
        receipt = AckReceipt(
            command_id=command_id,
            acknowledgment_id=ack_id,
            occurrence_id=request.occurrence_id,
            severity_generation=request.severity_generation,
            acknowledged_at=utc_timestamp(at),
        )
        if not existing:
            connection.execute(
                "INSERT INTO event_acknowledgments VALUES (?, ?, ?, ?, ?)",
                (
                    ack_id,
                    request.occurrence_id,
                    request.severity_generation,
                    command_id,
                    receipt.acknowledged_at.isoformat(),
                ),
            )
        connection.execute(
            "INSERT INTO commands VALUES (?, ?, ?, 1, ?, 200, ?)",
            (command_id, key, request_hash, now.isoformat(), receipt.model_dump_json()),
        )
        return receipt, False
