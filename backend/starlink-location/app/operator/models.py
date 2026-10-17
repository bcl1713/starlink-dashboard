"""Strict schema-v1 commands, complete revisions, and read projections."""

from typing import Annotated, Literal

from pydantic import Field, JsonValue, model_validator

from .clock import Clock
from .common import Identifier, RecordId, SchemaVersion, StrictModel
from .payloads import OperatorPayload
from .provenance import Actor, SourceProvenance, StoreHealth
from .time_models import RecordTime, UtcTimestamp

__all__ = [
    "Actor",
    "CommandReceipt",
    "CreateRecord",
    "HistoryPage",
    "OperatorCommand",
    "RecordFilter",
    "RecordInput",
    "RecordPage",
    "RecordTime",
    "RemoveRecord",
    "RestoreRecord",
    "SavedRecord",
    "SourceProvenance",
    "StoreHealth",
    "UpdateRecord",
]

Scope = Literal["mission", "preflight", "leg", "between_legs", "postflight"]
RecordType = Literal[
    "journal_entry",
    "call",
    "conference",
    "participation",
    "issue",
    "risk",
    "transport_report",
]
Operation = Literal["create", "update", "remove", "restore"]
PositiveVersion = Annotated[int, Field(strict=True, ge=1)]
AuditNote = Annotated[str, Field(max_length=1000)]


class RecordInput(StrictModel):
    schema_version: SchemaVersion = 1
    record_type: RecordType
    mission_id: Identifier
    leg_id: Identifier | None = None
    scope: Scope
    time: RecordTime
    payload: OperatorPayload

    @model_validator(mode="after")
    def valid_association_and_type(self):
        if (self.scope == "leg") != (self.leg_id is not None):
            raise ValueError("Only leg scope requires a leg ID")
        payload_type = self.payload.entry_type
        expected_type = (
            "journal_entry"
            if payload_type in ("note", "call_observation")
            else payload_type
        )
        if self.record_type != expected_type:
            raise ValueError("Payload does not match record type")
        return self

    def validate_for_acceptance(self, clock: Clock) -> None:
        self.time.validate_for_acceptance(clock)
        if self.record_type == "conference":
            from datetime import timedelta

            from .errors import OperatorError
            from .time_models import utc_timestamp

            latest = utc_timestamp(clock.now()) + timedelta(seconds=60)
            fields = {
                f"payload.{name}": "Actual time exceeds the acceptance clock tolerance"
                for name in ("verified_at", "configuration_reported_at")
                if (value := getattr(self.payload, name)) is not None and value > latest
            }
            if fields:
                raise OperatorError("validation_error", fields=fields)


class CreateRecord(RecordInput):
    operation: Literal["create"] = "create"
    operator_label: str | None = Field(default=None, max_length=200)


class UpdateRecord(RecordInput):
    operation: Literal["update"] = "update"
    record_id: RecordId
    expected_version: PositiveVersion
    audit_note: AuditNote | None = None
    operator_label: str | None = Field(default=None, max_length=200)


class RemoveRecord(StrictModel):
    schema_version: SchemaVersion = 1
    operation: Literal["remove"] = "remove"
    record_id: RecordId
    expected_version: PositiveVersion
    audit_note: AuditNote | None = None
    operator_label: str | None = Field(default=None, max_length=200)


class RestoreRecord(StrictModel):
    schema_version: SchemaVersion = 1
    operation: Literal["restore"] = "restore"
    record_id: RecordId
    expected_version: PositiveVersion
    audit_note: AuditNote | None = None
    operator_label: str | None = Field(default=None, max_length=200)


OperatorCommand = Annotated[
    CreateRecord | UpdateRecord | RemoveRecord | RestoreRecord,
    Field(discriminator="operation"),
]


class SavedRecord(RecordInput):
    record_id: RecordId
    version: PositiveVersion
    previous_version: PositiveVersion | None
    journal_seq: PositiveVersion
    command_id: RecordId
    operation: Operation
    reason: Annotated[str, Field(min_length=1, max_length=1000)] | None = None
    reason_origin: Literal["automatic", "operator"] | None = None
    deleted: bool
    recorded_at: UtcTimestamp
    author: Actor
    provenance: SourceProvenance

    @model_validator(mode="after")
    def valid_revision(self):
        if self.operation == "create":
            if self.version != 1 or self.previous_version is not None:
                raise ValueError("Create requires version one and no predecessor")
        elif self.version <= 1 or self.previous_version != self.version - 1:
            raise ValueError("Revision requires its immediate predecessor")
        if self.deleted != (self.operation == "remove"):
            raise ValueError("Only removal revisions are deleted")
        if (self.reason is None) != (self.reason_origin is None):
            raise ValueError("Reason and origin must be supplied together")
        if self.operation != "create" and (
            self.reason is None or not self.reason.strip()
        ):
            raise ValueError("Mutation requires a nonblank audit reason")
        return self


class CommandReceipt(StrictModel):
    schema_version: SchemaVersion = 1
    command_id: RecordId
    response_status: Annotated[int, Field(strict=True, ge=200, le=299)]
    saved_records: Annotated[list[SavedRecord], Field(min_length=1)]
    canonical_response: dict[str, JsonValue]


class RecordFilter(StrictModel):
    mission_id: Identifier
    scope: Scope | None = None
    leg_id: Identifier | None = None
    record_type: RecordType | None = None
    include_removed: bool = False


class RecordPage(StrictModel):
    schema_version: SchemaVersion = 1
    items: list[SavedRecord]
    cursor: str | None = None
    H: Annotated[int, Field(strict=True, ge=0)]
    as_of: UtcTimestamp


class HistoryPage(RecordPage):
    """Immutable audit versions in acceptance sequence at the pinned H."""
