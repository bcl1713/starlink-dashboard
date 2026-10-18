"""Versioned event, source publication and notification contracts."""

from typing import Annotated, Literal

from pydantic import Field

from .common import Identifier, RecordId, SchemaVersion, StrictModel
from .time_models import UtcTimestamp


class SourceCapture(StrictModel):
    source: str
    revision: str | None = None
    generation: str | None = None
    input_identity: str | None = None
    captured_at: UtcTimestamp | None = None
    freshness: Literal["fresh", "stale", "unknown", "disabled"] = "unknown"
    aligned: bool = False
    guardable: bool = False
    reason: str | None = None


class EventNotification(StrictModel):
    generation: str | None = None
    severity_generation: Annotated[int, Field(ge=0, le=3)] = 0
    acknowledged: bool = False
    acknowledged_at: UtcTimestamp | None = None
    retired: bool = False
    eligible: bool = False
    priority: Annotated[int, Field(ge=0, le=4)] = 4
    threshold_at: UtcTimestamp | None = None
    available: bool = True
    reason: str | None = None


class OperationalEvent(StrictModel):
    schema_version: SchemaVersion = 1
    event_id: str
    mission_id: Identifier
    leg_id: str | None = None
    kind: Literal[
        "call_prep", "call_start", "issue_followup", "pop_advisory", "restriction"
    ]
    title: str
    due_at: UtcTimestamp | None = None
    end_at: UtcTimestamp | None = None
    state: Literal["upcoming", "active", "overdue", "inactive", "unknown"] = "unknown"
    provenance: Literal["scheduled", "operator_reported", "modeled", "observed"] = (
        "scheduled"
    )
    source_ref: str | None = None
    source_revision: str | None = None
    source_captured_at: UtcTimestamp | None = None
    freshness: Literal["fresh", "stale", "unknown"] = "fresh"
    confidence: str | None = None
    transport: str | None = None
    protected_participation_ids: list[str] = Field(default_factory=list)
    conference_ids: list[str] = Field(default_factory=list)
    transport_relevance: Literal["configured", "intended", "unknown", "call"] = (
        "unknown"
    )
    continuity_status: Literal["modeled", "unknown"] = "unknown"
    discrepancies: list[str] = Field(default_factory=list)
    significance: Literal[
        "routine", "advisory", "degraded", "unavailable", "call_outage"
    ] = "routine"
    active: bool = True
    schedule_key: str = ""
    family_key: str = ""
    dependent_versions: dict[str, int] = Field(default_factory=dict)
    notification: EventNotification = Field(default_factory=EventNotification)


class EventSnapshot(StrictModel):
    schema_version: SchemaVersion = 1
    store_id: str
    api_epoch: str
    mission_id: Identifier
    source_mode: Literal["live", "simulation"]
    simulation_run_id: str | None = None
    as_of: UtcTimestamp
    H: int
    generation: str
    sources: list[SourceCapture] = Field(default_factory=list)
    coverage: Literal["available", "partial", "unknown"] = "unknown"
    events: list[OperationalEvent] = Field(default_factory=list)
    snapshot_token: str = ""
    cursor: str | None = None
    truncated: bool = False


class AckRequest(StrictModel):
    schema_version: SchemaVersion = 1
    occurrence_id: Annotated[str, Field(min_length=1, max_length=128)]
    severity_generation: Annotated[int, Field(ge=0, le=3)]
    snapshot_token: Annotated[str, Field(min_length=1, max_length=128)]


class AckReceipt(StrictModel):
    schema_version: SchemaVersion = 1
    receipt_type: Literal["event_acknowledgment"] = "event_acknowledgment"
    command_id: RecordId
    acknowledgment_id: RecordId
    occurrence_id: str
    severity_generation: Annotated[int, Field(ge=0, le=3)]
    acknowledged_at: UtcTimestamp
    replayed: bool = False
