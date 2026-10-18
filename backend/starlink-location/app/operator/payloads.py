"""Closed version-one payloads; domain fixtures do not enable public CRUD."""

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from .common import Identifier, RecordId, SchemaVersion, StrictModel
from .time_models import UtcTimestamp


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
    status: Literal["tentative", "scheduled", "delayed", "completed", "cancelled"] = (
        "scheduled"
    )
    party: str | None = Field(default=None, max_length=200)
    coordinator: str | None = Field(default=None, max_length=200)
    communications_kind: Literal["voice", "vtc", "other"] | None = None
    prep_lead_minutes: Annotated[int, Field(strict=True, ge=0, le=10080)] | None = None
    conference_id: RecordId | None = None


class ConferencePayload(PayloadBase):
    entry_type: Literal["conference"] = "conference"
    status: (
        Literal["unknown", "preparing", "established", "interrupted", "closed"] | None
    ) = None
    coordinator: str | None = Field(default=None, max_length=200)
    verified_at: UtcTimestamp | None = None
    intended_transport: Literal["Starshield", "Ka", "X"] | None = None
    configured_transport: Literal["Starshield", "Ka", "X"] | None = None
    configuration_reported_at: UtcTimestamp | None = None

    @model_validator(mode="after")
    def verification_requires_established(self):
        if self.verified_at is not None and self.status != "established":
            raise ValueError("Verification requires an established conference")
        return self


class ParticipationPayload(PayloadBase):
    entry_type: Literal["participation"] = "participation"
    participant: str | None = Field(default=None, max_length=200)
    state: Literal["unknown", "connected", "interrupted", "left"] | None = None
    resumes_participation_id: RecordId | None = None
    call_id: RecordId | None = None
    conference_id: RecordId | None = None

    @model_validator(mode="after")
    def has_target(self):
        if self.call_id is None and self.conference_id is None:
            raise ValueError("Participation requires a call or conference")
        return self


class IssuePayload(PayloadBase):
    entry_type: Literal["issue"] = "issue"
    status: Literal["open", "resolved"] = "open"


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
