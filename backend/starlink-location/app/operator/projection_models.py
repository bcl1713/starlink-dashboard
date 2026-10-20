"""Schema-v1 projection contracts, independent of ZIPs, routes or workers."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import JsonValue

from .common import Identifier, RecordId, SchemaVersion, StrictModel
from .models import Operation, PositiveVersion, RecordType, Scope
from .provenance import Actor, SourceProvenance
from .time_models import RecordTime, UtcTimestamp


class RevisionIdentity(StrictModel):
    store_id: RecordId
    record_id: RecordId
    version: PositiveVersion


class Association(StrictModel):
    mission_id: Identifier
    leg_id: Identifier | None
    scope: Scope
    previous_leg_id: Identifier | None
    next_leg_id: Identifier | None


class AssociationChange(StrictModel):
    before: Association | None
    after: Association


class FieldChange(StrictModel):
    before: JsonValue
    after: JsonValue


class IssueUpdate(StrictModel):
    kind: Literal["update", "correction"]
    root_identity: RevisionIdentity
    corrects_identity: RevisionIdentity | None
    selected_identity: RevisionIdentity
    superseded_by: RevisionIdentity | None
    effective_at: UtcTimestamp | None
    text: str
    is_selected: bool
    entered_later: bool | None


class ActivityItem(StrictModel):
    schema_version: SchemaVersion = 1
    identity: RevisionIdentity
    record_id: RecordId
    record_type: RecordType
    version: PositiveVersion
    previous_version: PositiveVersion | None
    command_id: RecordId
    journal_seq: PositiveVersion
    operation: Operation
    reason: str | None
    reason_origin: Literal["automatic", "operator"] | None
    author: Actor
    provenance: SourceProvenance
    recorded_at: UtcTimestamp
    time: RecordTime
    retrospective: bool
    title: str
    association: AssociationChange
    changes: dict[str, FieldChange]
    text_changes: list[str]
    description: str
    description_origin: Literal["generated"] = "generated"
    issue_update: IssueUpdate | None = None


class ProjectionManifest(StrictModel):
    replay_run_id: str | None = None
    mission_journal: bool = False
    schema_version: SchemaVersion = 1
    store_id: RecordId
    api_epoch: RecordId
    mission_id: Identifier
    source_mode: Literal["live", "simulation"]
    simulation_run_id: str | None
    high_water: int
    activity_included: Literal[True] = True
    audit_included: bool
    projections: dict[str, str]
    checksums: dict[str, str]
    component_capture_times: dict[str, UtcTimestamp | None]
    source_capture_revisions: dict[str, int | str | None]
    capture_policy: Literal[
        "operator_snapshot; planning_associations_derived_unpinned"
    ] = "operator_snapshot; planning_associations_derived_unpinned"
    capture_time_basis: Literal[
        "operator_recorded_at_at_H; no_wall_clock_capture_time"
    ] = "operator_recorded_at_at_H; no_wall_clock_capture_time"
    unresolved_associations: list[dict[str, JsonValue]]


@dataclass(frozen=True)
class ProjectionBundle:
    """Canonical UTF-8 files and their manifest; persist these together in #370."""

    high_water: int
    manifest: ProjectionManifest
    files: Mapping[str, bytes]
    checksums: Mapping[str, str]
    store_id: UUID
    api_epoch: UUID
    source_mode: Literal["live", "simulation"]
    simulation_run_id: str | None
