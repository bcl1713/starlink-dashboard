"""Closed version-one payloads; domain fixtures do not enable public CRUD."""

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from .common import Identifier, RecordId, SchemaVersion, StrictModel


class PayloadBase(StrictModel):
    schema_version: SchemaVersion = 1
    title: str = Field(min_length=1, max_length=200)
    note: str = Field(default="", max_length=8000)
    previous_leg_id: Identifier | None = None
    next_leg_id: Identifier | None = None

    @field_validator("title")
    @classmethod
    def nonblank_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title cannot be blank")
        return value


class JournalNotePayload(PayloadBase):
    entry_type: Literal["note"] = "note"


class CallObservationPayload(PayloadBase):
    entry_type: Literal["call_observation"] = "call_observation"


class CallPayload(PayloadBase):
    entry_type: Literal["call"] = "call"
    conference_id: RecordId | None = None


class ConferencePayload(PayloadBase):
    entry_type: Literal["conference"] = "conference"


class ParticipationPayload(PayloadBase):
    entry_type: Literal["participation"] = "participation"
    call_id: RecordId | None = None
    conference_id: RecordId | None = None

    @model_validator(mode="after")
    def has_target(self):
        if self.call_id is None and self.conference_id is None:
            raise ValueError("Participation requires a call or conference")
        return self


class IssuePayload(PayloadBase):
    entry_type: Literal["issue"] = "issue"


class RiskPayload(PayloadBase):
    entry_type: Literal["risk"] = "risk"


class TransportReportPayload(PayloadBase):
    entry_type: Literal["transport_report"] = "transport_report"
    transport: Literal["Starshield", "Ka", "X"]
    status: Literal[
        "reported_available", "reported_degraded", "reported_unavailable", "unknown"
    ]


JournalPayload = Annotated[
    JournalNotePayload | CallObservationPayload, Field(discriminator="entry_type")
]
OperatorPayload = Annotated[
    JournalNotePayload
    | CallObservationPayload
    | CallPayload
    | ConferencePayload
    | ParticipationPayload
    | IssuePayload
    | RiskPayload
    | TransportReportPayload,
    Field(discriminator="entry_type"),
]
