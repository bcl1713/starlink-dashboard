"""Ephemeral, version-pinned human decision context; never routing telemetry."""

from typing import Literal

from pydantic import Field

from .common import StrictModel
from .time_models import UtcTimestamp


class CommunicationWindow(StrictModel):
    record_id: str
    version: int
    leg_id: str | None = None
    kind: Literal["call", "preparation", "conference", "connected"]
    title: str
    start_at: UtcTimestamp | None = None
    end_at: UtcTimestamp | None = None
    basis: Literal["scheduled", "operator_reported"]
    call_id: str | None = None
    conference_id: str | None = None
    ongoing: bool = False


class TransportAssessment(StrictModel):
    change_basis: Literal["planned_change", "reported_application"] | None = None
    decision_id: str
    row_id: str
    service: str
    subject: Literal["change_vs_activity", "communications_vs_restriction"]
    report_stage: Literal["intended", "requested", "applied", "unknown"] = "unknown"
    transport: str | None = None
    status: Literal["overlap", "possible_impact", "unknown", "no_overlap_found"]
    message: str
    activity_id: str | None = None
    event_ids: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    dependent_versions: dict[str, int] = Field(default_factory=dict)
    time_basis: str | None = None
    freshness: Literal["fresh", "stale", "unknown"] = "unknown"


class TransportReview(StrictModel):
    as_of: UtcTimestamp
    H: int
    actual_routing: Literal["unknown"] = "unknown"
    coverage: Literal["available", "partial", "unknown"] = "unknown"
    horizon_end_at: UtcTimestamp
    activities: list[CommunicationWindow] = Field(default_factory=list)
    assessments: list[TransportAssessment] = Field(default_factory=list)
