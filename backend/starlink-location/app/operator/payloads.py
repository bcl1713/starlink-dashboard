"""Closed version-one payloads; domain fixtures do not enable public CRUD."""

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from .common import RecordId
from .payload_base import PayloadBase
from .time_models import UtcTimestamp
from .transport_models import TransportDecisionPayload


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
    direct_transport: str | None = Field(default=None, min_length=1, max_length=200)
    established_at: UtcTimestamp | None = None


class ConferencePayload(PayloadBase):
    entry_type: Literal["conference"] = "conference"
    status: (
        Literal["unknown", "preparing", "established", "interrupted", "closed"] | None
    ) = None
    coordinator: str | None = Field(default=None, max_length=200)
    verified_at: UtcTimestamp | None = None
    intended_transport: str | None = Field(default=None, min_length=1, max_length=200)
    configured_transport: str | None = Field(default=None, min_length=1, max_length=200)
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
    status: Literal["open", "monitoring", "resolved", "reopened"] = "open"
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    mitigation: Literal["none_reported", "mitigated", "workaround", "unknown"] = (
        "unknown"
    )
    functional_area: str | None = Field(default=None, max_length=200)
    responsible_party: str | None = Field(default=None, max_length=200)
    follow_up_at: UtcTimestamp | None = None
    update_text: str = Field(default="", max_length=8000)
    capability_id: RecordId | None = None
    call_id: RecordId | None = None
    conference_id: RecordId | None = None
    transport: Literal["Starshield", "Ka", "X"] | None = None
    corrects_version: Annotated[int, Field(strict=True, ge=1)] | None = None
    corrected_update_at: UtcTimestamp | None = None

    @field_validator("functional_area", "responsible_party")
    @classmethod
    def optional_text(cls, value):
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def valid_issue(self):
        if self.status == "resolved" and self.follow_up_at is not None:
            raise ValueError("Resolved issues cannot schedule follow-up")
        if self.corrected_update_at is not None and self.corrects_version is None:
            raise ValueError("Corrected time requires correction target")
        if self.corrects_version is not None and not self.update_text.strip():
            raise ValueError("Correction requires replacement update")
        return self


class RiskPayload(PayloadBase):
    entry_type: Literal["risk"] = "risk"


class TransportReportPayload(PayloadBase):
    entry_type: Literal["transport_report"] = "transport_report"
    transport: Literal["Starshield", "Ka", "X"]
    status: Literal[
        "reported_available", "reported_degraded", "reported_unavailable", "unknown"
    ]


class CapabilityAssessmentPayload(PayloadBase):
    entry_type: Literal["capability_assessment"] = "capability_assessment"
    functional_status: Literal["unknown", "functional", "degraded", "unavailable"] = (
        "unknown"
    )
    redundancy_status: Literal["unknown", "available", "degraded", "unavailable"] = (
        "unknown"
    )
    functional_observed_at: UtcTimestamp | None = None
    redundancy_observed_at: UtcTimestamp | None = None
    functional_time_precision: Literal["exact", "approximate", "unknown"] = "unknown"
    redundancy_time_precision: Literal["exact", "approximate", "unknown"] = "unknown"

    @field_validator(
        "functional_time_precision", "redundancy_time_precision", mode="before"
    )
    @classmethod
    def unknown_precision(cls, value):
        return "unknown" if value is None else value

    @model_validator(mode="after")
    def observation_precision(self):
        for dimension in ("functional", "redundancy"):
            if (getattr(self, dimension + "_observed_at") is None) != (
                getattr(self, dimension + "_time_precision") == "unknown"
            ):
                raise ValueError("Observation time and precision must agree")
        return self


JournalPayload = Annotated[
    JournalNotePayload | CallObservationPayload | CapabilityAssessmentPayload,
    Field(discriminator="entry_type"),
]
OperatorPayload = Annotated[
    JournalNotePayload
    | CallObservationPayload
    | CapabilityAssessmentPayload
    | CallPayload
    | ConferencePayload
    | ParticipationPayload
    | IssuePayload
    | RiskPayload
    | TransportReportPayload
    | TransportDecisionPayload,
    Field(discriminator="entry_type"),
]
