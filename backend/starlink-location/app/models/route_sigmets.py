"""Bounded route-linked SIGMET identities, geometry and notice wire contracts."""

from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from app.models.aviation_weather import Contract, Hash, Time, WeatherProduct

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


class RouteSigmetEntry(Contract):
    notice_key: Hash
    bulletin_key: Hash
    semantic_digest: Hash
    feature_ids: list[TextId] = Field(min_length=1, max_length=MAX_ADVISORIES)
    spans: list[IntersectionSpan] = Field(min_length=1, max_length=MAX_SPANS)
    attention_order: Time
    acknowledged: bool
    valid_from_ms: Time
    expires_at_ms: Time
    identity_uncertain: bool

    @model_validator(mode="after")
    def identity(self) -> Self:
        unique(self.feature_ids, "entry feature IDs")
        if self.valid_from_ms >= self.expires_at_ms:
            raise ValueError("Empty or reversed notice validity")
        return self


class RouteSigmetSnapshot(Contract):
    schema_version: Literal["route-sigmets-v1"] = Field(alias="schema")
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
        unique([entry.notice_key for entry in self.entries], "notice keys")
        unique([entry.bulletin_key for entry in self.entries], "bulletin keys")
        unique(
            [feature for entry in self.entries for feature in entry.feature_ids],
            "entry feature IDs",
        )
        unique([item.feature_id for item in self.unresolved], "unresolved feature IDs")
        unique(self.future_feature_ids, "future feature IDs")
        if (
            len(
                {feature for entry in self.entries for feature in entry.feature_ids}
                | {item.feature_id for item in self.unresolved}
                | set(self.future_feature_ids)
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
        if self.entries and self.context is None:
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


class NoticeConfirmation(NoticeMutation):
    state_revision: Time
    attention_order: Time
