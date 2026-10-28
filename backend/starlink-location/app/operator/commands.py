"""One transaction owns full revisions, current pointers, links and receipts."""

import json
from uuid import uuid4

from .clock import observation_now
from .conference_actions import (
    conference_audit_reason,
    validate_call_begin,
    validate_conference_update,
    validate_customer_connection,
)
from .errors import OperatorError
from .event_models import AckReceipt
from .issue_actions import issue_audit_reason, validate_issue_update
from .models import CommandReceipt, CreateRecord, RecordInput, SavedRecord
from .provenance import SourceProvenance
from .queries import get_record
from .references import derive_links, validate_dependencies
from .transport_actions import transport_audit_reason, validate_transport_update


def receipt_for_key(connection, key, request_hash):
    row = connection.execute(
        "SELECT request_hash, response_json FROM commands WHERE idempotency_key=?",
        (key,),
    ).fetchone()
    if row is None:
        return None
    if row[0] != request_hash:
        raise OperatorError("idempotency_conflict")
    receipt_type = (
        AckReceipt
        if json.loads(row[1]).get("receipt_type") == "event_acknowledgment"
        else CommandReceipt
    )
    return receipt_type.model_validate_json(row[1])


def execute_in_transaction(
    connection,
    command,
    *,
    key,
    request_hash,
    clock,
    actor,
    replay_run_id=None,
    operating_context_id=None
) -> CommandReceipt:
    receipt = receipt_for_key(connection, key, request_hash)
    if receipt is not None:
        return receipt
    current = (
        None
        if isinstance(command, CreateRecord)
        else get_record(connection, command.record_id)
    )
    if current:
        if current.version != command.expected_version:
            raise OperatorError("version_conflict", current_version=current.version)
        if current.deleted != (command.operation == "restore"):
            raise OperatorError("invalid_transition")
    if command.operation in ("create", "update"):
        command.validate_for_acceptance(clock)
        validate_transport_update(current, command)
        validate_conference_update(current, command, clock, connection)
        validate_customer_connection(
            connection, command, replay_run_id, operating_context_id
        )
        validate_call_begin(
            connection, current, command, replay_run_id, operating_context_id
        )
        validate_issue_update(connection, current, command, clock)
        content = {name: getattr(command, name) for name in RecordInput.model_fields}
    else:
        content = {name: getattr(current, name) for name in RecordInput.model_fields}
    recorded_at = observation_now(clock)
    source_mode = connection.execute(
        "SELECT source_mode FROM store_metadata"
    ).fetchone()[0]
    reason = getattr(command, "audit_note", None)
    reason = reason.strip() if reason is not None else ""
    reason_origin = "operator" if reason else "automatic"
    if not reason and command.operation in ("create", "update"):
        reason = (
            transport_audit_reason(current, command)
            or issue_audit_reason(current, command)
            or conference_audit_reason(current, command)
            or ""
        )
    if not reason:
        reason = {
            "update": "Operator correction",
            "remove": "Operator removal",
            "restore": (
                "Operator record restored"
                if current is not None
                and current.record_type in ("conference", "participation")
                else "Operator restoration"
            ),
        }.get(command.operation)
    seq = connection.execute(
        "SELECT coalesce(max(journal_seq), 0)+1 FROM revisions"
    ).fetchone()[0]
    report_run = current.provenance.replay_run_id if current else replay_run_id
    if (
        current
        and current.record_type == "call"
        and command.operation == "update"
        and current.time.occurred_at is None
        and content["time"].occurred_at is not None
    ):
        # Starting a carried requirement is an explicit new operational report;
        # correcting an already started historical call never refreshes it.
        report_run = replay_run_id
    report_context = (
        current.provenance.operating_context_id if current else operating_context_id
    )
    if (
        current
        and command.operation == "update"
        and getattr(command, "establish_session", False)
    ):
        payload = content["payload"]
        conference_establishment = (
            current.record_type == "conference"
            and payload.status == "established"
            and (
                payload.verified_at is None
                or payload.verified_at == content["time"].occurred_at
            )
        )
        direct_establishment = (
            current.record_type == "call"
            and payload.conference_id is None
            and payload.established_at is not None
            and content["time"].occurred_at is not None
            and payload.status not in ("completed", "cancelled")
        )
        if not (conference_establishment or direct_establishment):
            raise OperatorError(
                "validation_error",
                fields={
                    "establish_session": "Establishment requires a conference or direct call with a two-way check"
                },
            )
        report_run, report_context = replay_run_id, operating_context_id
    if (
        current
        and current.record_type == "call"
        and current.time.occurred_at is None
        and content["time"].occurred_at is not None
    ):
        report_context = operating_context_id
    provenance = SourceProvenance(
        kind="operator_reported",
        replay_run_id=report_run,
        operating_context_id=report_context,
        source_mode=source_mode,
        source_ref=current.provenance.source_ref if current else None,
        mutation_origin=(
            "retrospective"
            if content["time"].occurred_at is not None
            and content["time"].occurred_at < clock.now()
            else "interactive"
        ),
    )
    saved = SavedRecord(
        **content,
        record_id=current.record_id if current else uuid4(),
        version=current.version + 1 if current else 1,
        previous_version=current.version if current else None,
        journal_seq=seq,
        command_id=uuid4(),
        operation=command.operation,
        reason=reason,
        reason_origin=reason_origin if reason else None,
        deleted=command.operation == "remove",
        recorded_at=recorded_at,
        author=actor.model_copy(update={"operator_label": command.operator_label}),
        provenance=provenance
    )
    validate_dependencies(connection, saved)
    body = {
        "schema_version": 1,
        "command_id": str(saved.command_id),
        "saved_records": [saved.model_dump(mode="json")],
    }
    receipt = CommandReceipt(
        command_id=saved.command_id,
        response_status=201 if current is None else 200,
        saved_records=[saved],
        canonical_response=body,
    )
    _persist_changes(connection, [saved], receipt, key=key, request_hash=request_hash)
    return receipt


def _persist_changes(
    connection,
    changes: list[SavedRecord],
    receipt: CommandReceipt,
    *,
    key: str,
    request_hash: str
) -> None:
    for saved in changes:
        data = saved.model_dump(mode="json")
        fields = [
            "journal_seq",
            "record_id",
            "version",
            "previous_version",
            "command_id",
            "operation",
            "reason",
            "reason_origin",
            "schema_version",
            "record_type",
            "mission_id",
            "leg_id",
            "scope",
            "deleted",
            "recorded_at",
        ]
        values = [
            int(data[name]) if name == "deleted" else data[name] for name in fields
        ]
        for name in ("author", "time", "provenance", "payload"):
            fields.append(name + "_json")
            values.append(json.dumps(data[name], separators=(",", ":")))
        connection.execute(
            "INSERT INTO revisions ("
            + ",".join(fields)
            + ") VALUES ("
            + ",".join("?" for _ in fields)
            + ")",
            values,
        )
        if saved.version == 1:
            connection.execute(
                "INSERT INTO records VALUES (?, ?)", (str(saved.record_id), 1)
            )
        else:
            result = connection.execute(
                "UPDATE records SET current_version=? WHERE record_id=? AND current_version=?",
                (saved.version, str(saved.record_id), saved.previous_version),
            )
            if result.rowcount != 1:
                raise OperatorError("version_conflict")
    for saved in changes:
        connection.execute(
            "DELETE FROM current_links WHERE from_id=?", (str(saved.record_id),)
        )
        for link in sorted(derive_links(saved)):
            connection.execute("INSERT INTO current_links VALUES (?, ?, ?)", link)
    connection.execute(
        "INSERT INTO commands VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            str(receipt.command_id),
            key,
            request_hash,
            1,
            receipt.saved_records[0].model_dump(mode="json")["recorded_at"],
            receipt.response_status,
            receipt.model_dump_json(),
        ),
    )
