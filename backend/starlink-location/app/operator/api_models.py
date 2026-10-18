"""Public journal DTOs deliberately exclude trusted/internal producer commands."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import SchemaVersion, StrictModel
from .models import AuditNote, PositiveVersion, RecordInput
from .payloads import (
    CallPayload,
    ConferencePayload,
    IssuePayload,
    JournalPayload,
    ParticipationPayload,
)


class JournalCreate(RecordInput):
    record_type: Literal["journal_entry"]
    payload: JournalPayload
    operator_label: str | None = Field(default=None, max_length=200)


class JournalUpdate(JournalCreate):
    expected_version: PositiveVersion
    audit_note: AuditNote | None = None


class JournalTransition(StrictModel):
    schema_version: SchemaVersion = 1
    expected_version: PositiveVersion
    audit_note: AuditNote | None = None
    operator_label: str | None = Field(default=None, max_length=200)


class CallCreate(RecordInput):
    record_type: Literal["call"]
    payload: CallPayload
    operator_label: str | None = Field(default=None, max_length=200)

    @model_validator(mode="before")
    @classmethod
    def create_lead_default(cls, value):
        if isinstance(value, dict) and isinstance(value.get("payload"), dict):
            payload = value["payload"]
            if "prep_lead_minutes" not in payload:
                lead = (
                    10
                    if payload.get("status", "scheduled")
                    in ("tentative", "scheduled", "delayed")
                    else None
                )
                value = dict(value, payload=dict(payload, prep_lead_minutes=lead))
        return value

    @model_validator(mode="after")
    def scheduled_start(self):
        if self.payload.status == "scheduled" and self.time.planned_start_at is None:
            raise ValueError("Scheduled call requires planned start")
        return self


class CallUpdate(CallCreate):
    expected_version: PositiveVersion
    audit_note: AuditNote | None = None

    @model_validator(mode="after")
    def scheduled_start(self):
        # Creation requires a commitment time; corrections retain legacy unknowns.
        return self

    @model_validator(mode="before")
    @classmethod
    def create_lead_default(cls, value):
        if (
            isinstance(value, dict)
            and isinstance(value.get("payload"), dict)
            and "prep_lead_minutes" not in value["payload"]
        ):
            raise ValueError(
                "Call replacement requires explicit preparation lead or null"
            )
        return value


class ConferenceCreate(RecordInput):
    record_type: Literal["conference"]
    payload: ConferencePayload
    operator_label: str | None = Field(default=None, max_length=200)


class ConferenceUpdate(ConferenceCreate):
    expected_version: PositiveVersion
    audit_note: AuditNote | None = None


class ParticipationCreate(RecordInput):
    record_type: Literal["participation"]
    payload: ParticipationPayload
    operator_label: str | None = Field(default=None, max_length=200)


class ParticipationUpdate(ParticipationCreate):
    expected_version: PositiveVersion
    audit_note: AuditNote | None = None


class IssueCreate(RecordInput):
    record_type: Literal["issue"]
    payload: IssuePayload
    operator_label: str | None = Field(default=None, max_length=200)


class IssueUpdate(IssueCreate):
    expected_version: PositiveVersion
    audit_note: AuditNote | None = None


PublicCreate = Annotated[
    JournalCreate | CallCreate | ConferenceCreate | ParticipationCreate | IssueCreate,
    Field(discriminator="record_type"),
]
PublicUpdate = Annotated[
    JournalUpdate | CallUpdate | ConferenceUpdate | ParticipationUpdate | IssueUpdate,
    Field(discriminator="record_type"),
]
