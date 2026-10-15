"""Bounded route-linked SIGMET identities, geometry and notice wire contracts."""

from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from app.models.aviation_weather import Contract, Hash, Time, WeatherProduct
from app.models.route import ParsedRoute
from app.models.sigmet_encounters import (
    EncounterEvidence,
    EncounterPlan,
    EncounterPlanSummary,
)

MAX_ROUTE_POINTS = 20_000
MAX_ADVISORIES = 500
MAX_SPANS = 100_000
MAX_RESULT_BYTES = 8 * 1024**2
TextId = Annotated[str, Field(min_length=1, max_length=256)]
Position = Annotated[list[float], Field(min_length=2, max_length=2)]
UnresolvedReason = Literal[
    "unlocated", "boundary-uncertain", "identity-uncertain", "invalid-route", "limit"
]


def validate_position(point: list[float]) -> None:
    if not -180 <= point[0] <= 180 or not -90 <= point[1] <= 90:
        raise ValueError("Coordinates must be finite longitude/latitude pairs")


def unique(values: list, label: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"Duplicate {label}")


def bounded_result(value: Contract) -> None:
    if len(value.model_dump_json(by_alias=True).encode("utf-8")) > MAX_RESULT_BYTES:
        raise ValueError("Encoded result exceeds 8 MiB")


class WireRouteContext(Contract):
    context_key: Hash
    source: Literal["ordinary", "simulation"]
    route_id: TextId
    route_name: Annotated[str, Field(max_length=512)]
    runtime_id: TextId | None
    run_id: TextId | None

    @model_validator(mode="after")
    def source_identity(self) -> Self:
        if self.source == "simulation":
            if self.runtime_id is None or self.run_id is None:
                raise ValueError("Simulation context requires runtime and run IDs")
        elif self.runtime_id is not None or self.run_id is not None:
            raise ValueError("Ordinary context has no replay IDs")
        return self


class RouteContext(WireRouteContext):
    selection_epoch: Time = Field(default=0, exclude=True)
    route: ParsedRoute | None = Field(default=None, exclude=True)
    encounter_plan: EncounterPlan | None = Field(default=None, exclude=True)
    points: list[Position] = Field(max_length=MAX_ROUTE_POINTS, exclude=True)
    waypoint_occurrences: dict[str, int] = Field(default_factory=dict, exclude=True)

    @model_validator(mode="after")
    def coordinates(self) -> Self:
        for point in self.points:
            validate_position(point)
        return self


class IntersectionSpan(Contract):
    segment_index: Time
    start_fraction: float = Field(ge=0, le=1)
    end_fraction: float = Field(ge=0, le=1)
    entry: Position
    exit: Position
    boundary_error_m: float = Field(ge=0, le=18.52)

    @model_validator(mode="after")
    def positions(self) -> Self:
        validate_position(self.entry)
        validate_position(self.exit)
        if self.start_fraction > self.end_fraction:
            raise ValueError("Reversed intersection span")
        return self


class GeometryMatch(Contract):
    feature_id: TextId
    spans: list[IntersectionSpan] = Field(min_length=1, max_length=MAX_SPANS)


class UnresolvedFeature(Contract):
    feature_id: TextId
    reason: UnresolvedReason


class GeometryResult(Contract):
    matches: list[GeometryMatch] = Field(max_length=MAX_ADVISORIES)
    unresolved: list[UnresolvedFeature] = Field(max_length=MAX_ADVISORIES)
    complete: bool
    reason: Annotated[str, Field(max_length=512)] | None

    @model_validator(mode="after")
    def limits(self) -> Self:
        unique([match.feature_id for match in self.matches], "matched feature IDs")
        unique([item.feature_id for item in self.unresolved], "unresolved feature IDs")
        if (
            len(
                {m.feature_id for m in self.matches}
                | {u.feature_id for u in self.unresolved}
            )
            > MAX_ADVISORIES
        ):
            raise ValueError("Too many advisory features")
        if sum(len(match.spans) for match in self.matches) > MAX_SPANS:
            raise ValueError("Too many aggregate spans")
        if self.complete and self.unresolved:
            raise ValueError("Unresolved geometry cannot be complete")
        bounded_result(self)
        return self


class SigmetSelectionCandidate(Contract):
    bulletin_key: Hash
    semantic_digest: Hash
    feature_ids: list[TextId] = Field(min_length=1, max_length=MAX_ADVISORIES)


class SelectedSigmetEntry(Contract):
    notice_key: Hash
    bulletin_key: Hash
    semantic_digest: Hash
    feature_ids: list[TextId] = Field(min_length=1, max_length=MAX_ADVISORIES)
    attention_order: Time
    acknowledged: bool
    selected: bool = False
    valid_from_ms: Time
    expires_at_ms: Time
    identity_uncertain: bool

    @model_validator(mode="after")
    def identity(self) -> Self:
        unique(self.feature_ids, "entry feature IDs")
        if self.valid_from_ms >= self.expires_at_ms:
            raise ValueError("Empty or reversed notice validity")
        return self


class RouteSigmetEntry(SelectedSigmetEntry):
    encounter: EncounterEvidence

    @model_validator(mode="after")
    def aligned_encounters(self) -> Self:
        if len(self.encounter.spans) != len(self.spans):
            raise ValueError("Encounter evidence must align with geographic spans")
        for passage in self.encounter.spans:
            if passage.status not in {"unknown", "passed"}:
                overlap = (
                    passage.exit_ms >= self.valid_from_ms
                    and passage.entry_ms < self.expires_at_ms
                )
                if overlap != (passage.status == "overlap"):
                    raise ValueError("Passage validity classification mismatch")
        return self

    spans: list[IntersectionSpan] = Field(min_length=1, max_length=MAX_SPANS)


class RouteSigmetSnapshot(Contract):
    schema_version: Literal["route-sigmets-v2"] = Field(alias="schema")
    service_instance_id: Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
    observation_revision: Time
    encounter_plan: EncounterPlanSummary | None
    generated_at_ms: Time
    settings_revision: Time
    state_revision: Time
    generation_id: Hash
    context: WireRouteContext | None
    sigmet_product: WeatherProduct
    status: Literal[
        "off", "no-route", "evaluating", "ready", "stale", "incomplete", "unavailable"
    ]
    reason: Annotated[str, Field(max_length=512)] | None
    complete: bool
    truncated: Literal[False]
    entries: list[RouteSigmetEntry] = Field(max_length=MAX_ADVISORIES)
    selected_entries: list[SelectedSigmetEntry] = Field(
        default_factory=list, max_length=MAX_ADVISORIES
    )
    selection_candidates: list[SigmetSelectionCandidate] = Field(
        default_factory=list, max_length=MAX_ADVISORIES
    )
    unresolved: list[UnresolvedFeature] = Field(max_length=MAX_ADVISORIES)
    future_feature_ids: list[TextId] = Field(max_length=MAX_ADVISORIES)
    omitted_features: Time

    @field_validator("truncated", mode="before")
    @classmethod
    def no_truncation(cls, value):
        if value is not False:
            raise ValueError("Results must never be truncated")
        return value

    @model_validator(mode="after")
    def limits(self) -> Self:
        if self.context is None and self.encounter_plan is not None:
            raise ValueError("Encounter plan requires a route context")
        if (
            self.context
            and self.encounter_plan
            and self.context.source != self.encounter_plan.source
        ):
            raise ValueError("Encounter plan source mismatch")
        all_entries = [*self.entries, *self.selected_entries]
        unique([entry.notice_key for entry in all_entries], "notice keys")
        unique([entry.bulletin_key for entry in all_entries], "bulletin keys")
        unique(
            [entry.bulletin_key for entry in self.selection_candidates],
            "selection bulletin keys",
        )
        unique(
            [
                feature
                for entry in self.selection_candidates
                for feature in entry.feature_ids
            ],
            "selection feature IDs",
        )
        unique(
            [feature for entry in all_entries for feature in entry.feature_ids],
            "entry feature IDs",
        )
        unique([item.feature_id for item in self.unresolved], "unresolved feature IDs")
        unique(self.future_feature_ids, "future feature IDs")
        if (
            len(
                {feature for entry in all_entries for feature in entry.feature_ids}
                | {item.feature_id for item in self.unresolved}
                | set(self.future_feature_ids)
                | {
                    feature
                    for candidate in self.selection_candidates
                    for feature in candidate.feature_ids
                }
            )
            > MAX_ADVISORIES
        ):
            raise ValueError("Too many advisory features")
        if sum(len(entry.spans) for entry in self.entries) > MAX_SPANS:
            raise ValueError("Too many aggregate spans")
        if self.complete and (self.unresolved or self.omitted_features):
            raise ValueError("Unknown or omitted features cannot be complete")
        if self.status == "ready" and not self.complete:
            raise ValueError("Ready requires complete evaluation")
        if all_entries and self.context is None:
            raise ValueError("Notices require a route context")
        if self.sigmet_product.product_type != "international-sigmet":
            raise ValueError("Route notices require a SIGMET product")
        bounded_result(self)
        return self


class NoticeMutation(Contract):
    context_key: Hash
    notice_key: Hash
    semantic_digest: Hash
    acknowledged: bool


class NoticeSelection(Contract):
    context_key: Hash
    bulletin_key: Hash
    semantic_digest: Hash


class NoticeConfirmation(NoticeMutation):
    state_revision: Time
    attention_order: Time
