"""Conference snapshot invariants and specific automatic audit descriptions."""

from .errors import OperatorError


def validate_conference_update(current, replacement, clock, connection=None):
    if current is None:
        return
    if replacement.record_type == "call":
        if (
            current.payload.direct_transport != replacement.payload.direct_transport
            and replacement.payload.established_at is not None
            and not getattr(replacement, "establish_session", False)
        ):
            raise OperatorError(
                "validation_error",
                fields={
                    "payload.established_at": "Clear the direct two-way check when changing reported transport"
                },
            )
        return
    if replacement.record_type != "conference":
        return
    before, after = current.payload, replacement.payload
    if (
        before.configured_transport != after.configured_transport
        and after.verified_at is not None
        and not (
            getattr(replacement, "establish_session", False)
            and after.verified_at == replacement.time.occurred_at
        )
    ):
        raise OperatorError(
            "validation_error",
            fields={
                "payload.verified_at": "Clear verification when changing reported configuration"
            },
        )

    if (
        after.status == "closed"
        and before.status != "closed"
        and connection is not None
    ):
        blockers = conference_close_blockers(connection, current)
        if blockers:
            raise OperatorError("dependency_conflict", record_ids=blockers)


def conference_close_blockers(connection, conference):
    """Runs under the command transaction, against current authoritative pointers."""
    from .queries import select_records

    records = select_records(
        connection,
        "SELECT * FROM current_records WHERE mission_id=? AND deleted=0 AND record_type IN ('call', 'participation')",
        (conference.mission_id,),
    )
    calls = {
        record.record_id: record
        for record in records
        if record.record_type == "call"
        and record.payload.conference_id == conference.record_id
    }
    blockers = set()
    for record in records:
        if record.record_type == "call":
            if (
                record.record_id in calls
                and record.time.occurred_at is not None
                and record.time.ended_at is None
                and record.payload.status not in ("completed", "cancelled")
            ):
                blockers.add(str(record.record_id))
        elif (
            (
                record.payload.conference_id == conference.record_id
                or record.payload.call_id in calls
            )
            and record.payload.state != "left"
            and (
                record.payload.state != "interrupted"
                or record.time.ended_at is None
                or record.time.end_state != "known"
            )
        ):
            blockers.add(str(record.record_id))
    return sorted(blockers)


def conference_audit_reason(current, replacement):
    payload = replacement.payload
    if replacement.record_type == "participation":
        if current is None and payload.resumes_participation_id is not None:
            return "Customer connection restored"
        previous = current.payload.state if current is not None else None
        if payload.state != previous:
            return {
                "connected": "Customer joined",
                "left": "Customer left",
                "interrupted": "Customer connection interrupted",
            }.get(payload.state)
    if replacement.record_type == "conference":
        previous = current.payload.status if current is not None else None
        if payload.status != previous:
            if previous == "interrupted" and payload.status == "established":
                return "Conference connection restored"
            return {
                "established": "Conference established",
                "interrupted": "Conference interrupted",
                "closed": "Conference closed",
                "preparing": "Conference preparation",
            }.get(payload.status)
        if current is not None and payload.verified_at != current.payload.verified_at:
            return "Conference verification updated"
    return None


def validate_customer_connection(
    connection, command, replay_run_id, operating_context_id
):
    """Explicit live connection intent is checked inside the same write lock as Close.

    Historical/manual interval capture has no intent marker and remains supported.
    """
    if not getattr(command, "connect_customer", False):
        return
    if command.record_type != "participation" or command.payload.state != "connected":
        raise OperatorError(
            "validation_error",
            fields={"connect_customer": "Requires a connected customer report"},
        )
    from .queries import get_record

    payload = command.payload
    call = get_record(connection, payload.call_id) if payload.call_id else None
    if call is not None and call.time.occurred_at is None:
        raise OperatorError("dependency_conflict", record_ids=[str(call.record_id)])
    validate_connection_target(
        connection,
        command.mission_id,
        call,
        payload.conference_id,
        replay_run_id,
        operating_context_id,
    )


def validate_call_begin(
    connection, current, command, replay_run_id, operating_context_id
):
    if not getattr(command, "begin_customer_connect", False):
        return
    if (
        current is None
        or current.record_type != "call"
        or command.record_type != "call"
        or current.time.occurred_at is not None
        or command.time.occurred_at is None
        or command.payload.conference_id != current.payload.conference_id
    ):
        raise OperatorError(
            "validation_error",
            fields={
                "begin_customer_connect": "Requires starting an unchanged call before customer connection"
            },
        )
    validate_connection_target(
        connection,
        current.mission_id,
        current,
        current.payload.conference_id,
        replay_run_id,
        operating_context_id,
    )


def validate_connection_target(
    connection, mission_id, call, conference_id, replay_run_id, operating_context_id
):
    from .queries import get_record

    if call is not None and (
        call.deleted
        or call.record_type != "call"
        or call.mission_id != mission_id
        or call.payload.status in ("completed", "cancelled")
    ):
        raise OperatorError("dependency_conflict", record_ids=[str(call.record_id)])
    if call and conference_id and call.payload.conference_id != conference_id:
        raise OperatorError("dependency_conflict", record_ids=[str(call.record_id)])
    conference_id = conference_id or (call.payload.conference_id if call else None)
    target = get_record(connection, conference_id) if conference_id else call
    ready = (
        target is not None and not target.deleted and target.mission_id == mission_id
    )
    if ready and target.record_type == "conference":
        ready = (
            target.payload.status == "established"
            and target.payload.verified_at is not None
        )
    elif ready and target.record_type == "call":
        ready = target.payload.established_at is not None
    else:
        ready = False
    if ready:
        ready = (
            target.provenance.replay_run_id == replay_run_id
            and target.provenance.operating_context_id == operating_context_id
        )
    if not ready:
        raise OperatorError(
            "dependency_conflict", record_ids=[str(target.record_id)] if target else []
        )
