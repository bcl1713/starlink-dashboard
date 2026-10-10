"""Typed itinerary, draft, evaluation and wire records for planning v1."""

from pathlib import PurePosixPath
from typing import Literal

from pydantic import ConfigDict, Field, computed_field, field_validator, model_validator

from app.mission.models import (
    KaOutage,
    KuOutageOverride,
    ManualAARTrack,
    ManualRouteSplice,
    Mission,
)

from .types import (
    ContentHash,
    EvaluationContext,
    HeightProfilePoint,
    PlanningInputSnapshot,
    PlanningPolicy,
    PlanningRecord,
    RouteAnchor,
    UTCTimestamp,
    utc_timestamp,
)

__all__ = [
    "ARMatchCandidates",
    "AcceptRouteBinding",
    "AccessConfirmation",
    "AnchoredSwap",
    "ApplyProposal",
    "ApplyRevision",
    "BackupGap",
    "ConfirmItinerary",
    "EvaluationContext",
    "EvaluationInterval",
    "ExpectedLeg",
    "ExpectedLegCard",
    "GenerateProposal",
    "HeightProfilePoint",
    "ItineraryAR",
    "ItineraryData",
    "ItineraryPreview",
    "PlanningDraft",
    "PlanningError",
    "PlanningEvaluation",
    "PlanningInputs",
    "PlanningLock",
    "PlanningManifest",
    "PlanningPolicy",
    "PlanningProposal",
    "PlanningSatelliteOption",
    "PlanningSatelliteOptions",
    "PlanningView",
    "PreviewDraft",
    "ReviewRecord",
    "RevisionChange",
    "RevisionLegMapping",
    "RevisionPreview",
    "RevisionRequest",
    "RouteAnchor",
    "RouteBinding",
    "RouteBindingPreview",
    "SatelliteSelection",
    "SaveDraft",
    "SaveReviewed",
    "SourceEvidence",
    "SourceRevision",
]


class PlanningError(PlanningRecord):
    code: str
    message: str
    field: str | None = None
    retryable: bool = False
    action: str | None = None
    source_page: int | None = Field(default=None, ge=1)
    source_row: int | None = Field(default=None, ge=1)


class ItineraryAR(PlanningRecord):
    id: str = Field(min_length=1)
    track: str
    source_page: int | None = Field(default=None, ge=1)
    source_row: int | None = Field(default=None, ge=1)
    source_text: str = ""
    entry_time: UTCTimestamp
    exit_time: UTCTimestamp
    source_time_precision: Literal["minute", "second"]
    source_altitude: float | None = None
    confirmed_units: Literal["flight_level", "feet", "meters"] | None = None
    start_anchor: RouteAnchor | None = None
    end_anchor: RouteAnchor | None = None
    match_status: Literal["matched", "ambiguous", "unresolved", "excluded"] = (
        "unresolved"
    )
    confirmed: bool = False
    exclusion_note: str | None = None

    @model_validator(mode="after")
    def valid_window(self):
        if self.entry_time >= self.exit_time:
            raise ValueError("AR entry must precede exit")
        if self.match_status == "excluded" and not (self.exclusion_note or "").strip():
            raise ValueError("Excluded AR requires an exclusion note")
        if self.match_status == "matched" and (
            self.start_anchor is None or self.end_anchor is None
        ):
            raise ValueError("Matched AR requires both occurrence anchors")
        return self

    def geometric_height_meters(self) -> float:
        """Flight level conversion is approximate pressure-altitude geometry."""
        if self.confirmed_units is None or self.source_altitude is None:
            raise ValueError("Altitude and confirmed units are required for geometry")
        factor = {"flight_level": 30.48, "feet": 0.3048, "meters": 1.0}
        return self.source_altitude * factor[self.confirmed_units]


class AccessConfirmation(PlanningRecord):
    model_config = ConfigDict(frozen=True)

    satellite_ids: tuple[str, ...]
    confirmed: bool = False
    confirmed_at: UTCTimestamp | None = None


class SatelliteSelection(PlanningRecord):
    model_config = ConfigDict(validate_assignment=True)

    permitted_satellite_ids: tuple[str, ...] = Field(default_factory=tuple)
    access_confirmation: AccessConfirmation | None = None
    starshield_enabled: bool = True

    @field_validator("permitted_satellite_ids")
    @classmethod
    def unique_satellites(cls, values):
        if len(set(values)) != len(values) or any(not item.strip() for item in values):
            raise ValueError("Permitted satellite IDs must be nonempty and unique")
        return values

    @model_validator(mode="after")
    def bind_access(self):
        if self.access_confirmation is not None and set(
            self.access_confirmation.satellite_ids
        ) != set(self.permitted_satellite_ids):
            object.__setattr__(self, "access_confirmation", None)
        return self


class AnchoredSwap(PlanningRecord):
    id: str = Field(min_length=1)
    target_satellite_id: str = Field(min_length=1)
    anchor: RouteAnchor
    target_beam_id: str | None = None
    origin: Literal["manual", "generated"] = "manual"


class PlanningLock(PlanningRecord):
    id: str = Field(min_length=1)
    target_satellite_id: str = Field(min_length=1)
    anchor: RouteAnchor | None = None
    swap_id: str | None = None
    kind: Literal["initial", "swap"] = "swap"

    @model_validator(mode="after")
    def locked_anchor(self):
        if self.kind == "swap" and self.anchor is None:
            raise ValueError("Swap locks require an occurrence/time anchor")
        if self.kind == "initial" and (
            self.anchor is not None or self.swap_id is not None
        ):
            raise ValueError("Initial locks cannot carry swap anchors")
        return self


class PlanningDraft(SatelliteSelection):
    no_ars_confirmed: bool = False
    initial_x_satellite_id: str | None = None
    swaps: list[AnchoredSwap] = Field(default_factory=list)
    ar_corrections: list[ItineraryAR] = Field(default_factory=list)
    manual_aar_tracks: list[ManualAARTrack] = Field(default_factory=list)
    manual_route_splice: ManualRouteSplice | None = None
    ka_outages: list[KaOutage] = Field(default_factory=list)
    ku_overrides: list[KuOutageOverride] = Field(default_factory=list)
    adjusted_departure_time: UTCTimestamp | None = None
    locks: list[PlanningLock] = Field(default_factory=list)
    planning_policy: PlanningPolicy = "prefer_starshield_v1"
    evaluation_context: EvaluationContext | None = None

    @model_validator(mode="after")
    def operational_inputs(self):
        import math

        for outage in [*self.ka_outages, *self.ku_overrides]:
            outage.start_time = utc_timestamp(outage.start_time)
            if not math.isfinite(outage.duration_seconds):
                raise ValueError("Outage durations must be finite")
        locked = {}
        for lock in self.locks:
            key = (lock.kind, lock.anchor.source_time if lock.anchor else None)
            if key in locked and locked[key] != lock.target_satellite_id:
                raise ValueError("Conflicting locked assignments at one instant")
            locked[key] = lock.target_satellite_id
        return self


class ReviewRecord(PlanningRecord):
    input_identity: ContentHash
    confirmed_ar_ids: list[str] = Field(default_factory=list)
    excluded_ar_ids: list[str] = Field(default_factory=list)
    no_ars_confirmed: bool = False
    satellite_plan_confirmed: bool
    gap_acknowledged: bool = False
    saved_at: UTCTimestamp


class RouteBinding(PlanningRecord):
    model_config = ConfigDict(frozen=True)

    route_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    content_hash: ContentHash
    filename: str
    ingestion_profile: Literal["planning_v1"] = "planning_v1"

    @field_validator("ingestion_profile", mode="before")
    @classmethod
    def known_profile(cls, value):
        if value != "planning_v1":
            raise ValueError(
                "Unknown route ingestion profile; explicit migration required"
            )
        return value


class ExpectedLeg(PlanningRecord):
    id: str = Field(min_length=1)
    ordinal: int = Field(ge=1)
    departure_airport: str = Field(min_length=1)
    arrival_airport: str = Field(min_length=1)
    departure_time: UTCTimestamp
    arrival_time: UTCTimestamp
    ar_rows: list[ItineraryAR] = Field(default_factory=list)
    ar_section_status: Literal["listed", "empty", "unrecognized"] = "empty"
    route: RouteBinding | None = None
    draft: PlanningDraft | None = None
    review: ReviewRecord | None = None
    installed_leg_id: str | None = None
    retired: bool = False

    @model_validator(mode="after")
    def valid_times(self):
        if self.departure_time >= self.arrival_time:
            raise ValueError("Departure must precede arrival")
        for ar in self.ar_rows:
            if (
                not self.departure_time
                <= ar.entry_time
                < ar.exit_time
                <= self.arrival_time
            ):
                raise ValueError("AR must be inside its expected leg's UTC window")
        return self


class SourceRevision(PlanningRecord):
    id: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    kind: Literal["itinerary_pdf", "route_kml"]
    filename: str
    content_hash: ContentHash
    owned_relative_path: str = Field(exclude=True)
    expires_at: UTCTimestamp | None = None

    @field_validator("owned_relative_path")
    @classmethod
    def owned_path(cls, value):
        path = PurePosixPath(value)
        if not value or path.is_absolute() or ".." in path.parts or "\\" in value:
            raise ValueError("Source storage path must be an owned relative path")
        return value

    def storage_record(self) -> dict:
        """Only persistence deliberately includes the private relative path."""
        return {
            **self.model_dump(mode="json"),
            "owned_relative_path": self.owned_relative_path,
        }


class EvaluationInterval(PlanningRecord):
    start_time: UTCTimestamp
    end_time: UTCTimestamp
    satellite_id: str | None = None
    physical_x_state: Literal["available", "degraded", "offline"] = "available"
    physical_ka_state: Literal["available", "degraded", "offline"] = "available"
    physical_ku_state: Literal["available", "degraded", "offline"] = "available"
    policy_x_state: Literal["available", "degraded", "offline"] = "available"
    policy_ka_state: Literal["available", "degraded", "offline"] = "available"
    policy_ku_state: Literal["available", "degraded", "offline"] = "available"
    raw_constraints: list[str] = Field(default_factory=list)
    latitude: float | None = None
    longitude: float | None = None
    altitude_meters: float | None = None
    heading_degrees: float | None = None
    physical_reasons: list[str] = Field(default_factory=list)
    policy_reasons: list[str] = Field(default_factory=list)
    safety_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def nonempty_window(self):
        if self.start_time >= self.end_time:
            raise ValueError("Half-open intervals require start before end")
        return self


class BackupGap(PlanningRecord):
    start_time: UTCTimestamp
    end_time: UTCTimestamp
    reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def nonempty_window(self):
        if self.start_time >= self.end_time:
            raise ValueError("Backup gap start must precede end")
        return self


class PlanningEvaluation(PlanningRecord):
    context: EvaluationContext
    intervals: list[EvaluationInterval] = Field(default_factory=list)
    outage_seconds: float = Field(ge=0)
    swap_count: int = Field(ge=0)
    longest_gap_seconds: float = Field(ge=0)
    backup_gaps: list[BackupGap] = Field(default_factory=list)
    errors: list[PlanningError] = Field(default_factory=list)


class PlanningProposal(PlanningRecord):
    search_domain: Literal["generated_nonoverlap_plus_current_v1"] = (
        "generated_nonoverlap_plus_current_v1"
    )
    retained_current_draft: bool = False
    id: str = Field(min_length=1)
    expected_revision: int = Field(ge=1)
    input_identity: ContentHash
    context: EvaluationContext
    proposed_draft: PlanningDraft | None = None
    baseline_evaluation: PlanningEvaluation | None = None
    candidate_evaluation: PlanningEvaluation | None = None
    state: Literal["ready", "failed", "stale"]
    errors: list[PlanningError] = Field(default_factory=list)


class ProposalReference(PlanningRecord):
    """Manifest index; immutable payload location is derived from opaque IDs."""

    id: str
    leg_id: str
    expected_revision: int = Field(ge=1)
    input_identity: ContentHash
    structural_identity: ContentHash
    environment_identity: ContentHash
    payload_hash: ContentHash
    state: Literal["ready", "failed", "stale"]
    idempotency_hash: ContentHash | None = None


class PlanningManifest(PlanningRecord):
    schema_version: Literal[1] = 1
    revision: int = Field(default=1, ge=1)
    source_revisions: list[SourceRevision] = Field(default_factory=list)
    expected_legs: list[ExpectedLeg] = Field(default_factory=list)
    proposals: list[PlanningProposal] = Field(default_factory=list)
    proposal_refs: list[ProposalReference] = Field(default_factory=list)
    review_records: list[ReviewRecord] = Field(default_factory=list)
    route_bindings: list[RouteBinding] = Field(default_factory=list)
    route_history: list[RouteBinding] = Field(default_factory=list)

    @field_validator("schema_version", mode="before")
    @classmethod
    def known_version(cls, value):
        if value != 1:
            raise ValueError("Unknown manifest version; explicit migration required")
        return value

    @model_validator(mode="after")
    def valid_leg_links(self):
        live = [leg for leg in self.expected_legs if not leg.retired]
        if sorted(leg.ordinal for leg in live) != list(range(1, len(live) + 1)):
            raise ValueError("Live expected leg ordinals must be unique and contiguous")
        ids = [leg.id for leg in self.expected_legs]
        links = [
            leg.installed_leg_id
            for leg in self.expected_legs
            if leg.installed_leg_id is not None
        ]
        if len(set(ids)) != len(ids) or len(set(links)) != len(links):
            raise ValueError("Expected leg IDs and installed links must be unique")
        return self

    def storage_record(self) -> dict:
        record = self.model_dump(mode="json")
        record["source_revisions"] = [
            source.storage_record() for source in self.source_revisions
        ]
        return record


class ExpectedLegCard(PlanningRecord):
    leg: ExpectedLeg
    input_identity: ContentHash
    computation_status: Literal["idle", "calculating", "ready", "failed", "stale"] = (
        "idle"
    )
    errors: list[PlanningError] = Field(default_factory=list)

    @computed_field
    @property
    def review_status(self) -> Literal["awaiting_kml", "needs_review", "reviewed"]:
        if self.leg.route is None:
            return "awaiting_kml"
        if (
            self.leg.review is not None
            and self.leg.review.input_identity == self.input_identity
        ):
            return "reviewed"
        return "needs_review"


class PlanningView(PlanningRecord):
    mission: Mission
    revision: int = Field(ge=1)
    expected_legs: list[ExpectedLegCard]
    errors: list[PlanningError] = Field(default_factory=list)


class SourceEvidence(PlanningRecord):
    source_id: str | None = None
    source_page: int = Field(ge=1)
    source_row: int = Field(ge=1)
    source_text: str
    field: str | None = None


class ItineraryData(PlanningRecord):
    name: str = Field(min_length=1)
    itinerary_revision: int | None = Field(default=None, ge=1)
    aircraft: str | None = None
    call_sign: str | None = None
    expected_legs: list[ExpectedLeg] = Field(default_factory=list)


class ItineraryPreview(PlanningRecord):
    preview_id: str
    parsed_values: ItineraryData | None = None
    field_errors: list[PlanningError] = Field(default_factory=list)
    source_evidence: list[SourceEvidence] = Field(default_factory=list)
    source: SourceRevision | None = None
    confirmable: bool = False
    expires_at: UTCTimestamp


class ARMatchCandidates(PlanningRecord):
    ar_id: str
    start_candidates: list[RouteAnchor] = Field(default_factory=list)
    end_candidates: list[RouteAnchor] = Field(default_factory=list)


class RouteBindingPreview(PlanningRecord):
    preview_id: str
    expected_revision: int = Field(ge=1)
    binding: RouteBinding
    discrepancy_errors: list[PlanningError] = Field(default_factory=list)
    matched_ar_candidates: list[ARMatchCandidates] = Field(default_factory=list)
    expires_at: UTCTimestamp


class PlanningSatelliteOption(PlanningRecord):
    id: str
    label: str
    transport: Literal["X", "Ka", "Ku"]
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    eligible: bool
    error: PlanningError | None = None

    @model_validator(mode="after")
    def eligibility(self):
        if self.eligible and (
            self.transport != "X"
            or self.latitude is None
            or self.longitude is None
            or self.error is not None
        ):
            raise ValueError(
                "Eligible options require a validated configured X position"
            )
        return self


class PlanningSatelliteOptions(PlanningRecord):
    satellites: list[PlanningSatelliteOption]


class RevisionLegMapping(PlanningRecord):
    incoming_leg_id: str
    expected_leg_id: str | None = None
    action: Literal["retain", "add", "retire"]


class RevisionChange(PlanningRecord):
    field: str
    expected_leg_id: str | None = None
    before: str | None = None
    after: str | None = None
    requires_resolution: bool = False


class RevisionPreview(ItineraryPreview):
    expected_revision: int = Field(ge=1)
    input_identity: ContentHash
    changes: list[RevisionChange] = Field(default_factory=list)
    leg_mappings: list[RevisionLegMapping] = Field(default_factory=list)
    lower_revision: bool = False
    identical_content: bool = False


class ConfirmItinerary(SatelliteSelection):
    preview_id: str = Field(min_length=1)
    itinerary: ItineraryData
    idempotency_key: str = Field(min_length=1)


class RevisionRequest(PlanningRecord):
    expected_revision: int = Field(ge=1)


class AcceptRouteBinding(RevisionRequest):
    preview_id: str = Field(min_length=1)
    discrepancy_acknowledgments: list[str] = Field(default_factory=list)


class SaveDraft(RevisionRequest):
    draft: PlanningDraft
    ar_section_status: Literal["listed", "empty", "unrecognized"] | None = None


class PreviewDraft(SaveDraft):
    pass


class GenerateProposal(RevisionRequest):
    input_identity: ContentHash
    idempotency_key: str | None = Field(default=None, min_length=1)


class ApplyProposal(GenerateProposal):
    proposal_id: str = Field(min_length=1)


class SaveReviewed(GenerateProposal):
    confirmed_ar_ids: list[str] = Field(default_factory=list)
    excluded_ar_ids: list[str] = Field(default_factory=list)
    no_ars_confirmed: bool = False
    satellite_plan_confirmed: bool
    gap_acknowledged: bool = False


class ApplyRevision(GenerateProposal):
    preview_id: str = Field(min_length=1)
    itinerary: ItineraryData
    leg_mappings: list[RevisionLegMapping]
    discrepancy_acknowledgments: list[str] = Field(default_factory=list)
    allow_lower_revision: bool = False


class PlanningInputs(PlanningInputSnapshot):
    """Immutable shared evaluation snapshot (also persisted on installed legs)."""
