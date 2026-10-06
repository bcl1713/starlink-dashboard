"""Provider-neutral product admission; all wire times are UTC epoch milliseconds."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.overview_weather import WeatherAttribution, WeatherManifest

Time = Annotated[int, Field(ge=0, le=9007199254740991)]
Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Identifier = Annotated[str, Field(pattern=r"^[a-z0-9_-]{1,64}$")]


class Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, allow_inf_nan=False
    )


class Surface(Contract):
    kind: Literal["surface"]


class NotApplicable(Contract):
    kind: Literal["not-applicable"]


class Pressure(Contract):
    kind: Literal["pressure"]
    pressure_pa: float = Field(gt=0, le=110000)


class FlightLevel(Contract):
    kind: Literal["flight-level"]
    flight_level: int = Field(ge=0, le=600)
    reference: Literal["pressure-altitude-1013.25hpa"]
    derivation: Literal["native", "isa-log-pressure-v1"]
    source_pressures_pa: list[float] = Field(max_length=2)

    @model_validator(mode="after")
    def pressures(self) -> Self:
        values = self.source_pressures_pa
        if self.derivation == "native":
            if values:
                raise ValueError(
                    "Native flight levels do not claim interpolated pressures"
                )
        elif len(values) != 2 or not 0 < values[0] < values[1] <= 110000:
            raise ValueError("Interpolated levels require ordered bracketing pressures")
        return self


class VerticalBounds(Contract):
    kind: Literal["bounds"]
    lower: float | None
    upper: float | None
    unit: Literal["m", "flight-level", "unknown"]
    reference: Literal["MSL", "AGL", "FL", "unknown"]

    @model_validator(mode="after")
    def bounds(self) -> Self:
        if (
            self.lower is not None
            and self.upper is not None
            and self.lower > self.upper
        ):
            raise ValueError("Reversed vertical bounds")
        if (self.reference == "FL") != (self.unit == "flight-level"):
            raise ValueError("Flight levels require an explicit pressure reference")
        if (self.reference == "unknown") != (self.unit == "unknown"):
            raise ValueError("Unknown vertical reference must stay unknown")
        return self


Vertical = Annotated[
    Surface | NotApplicable | Pressure | FlightLevel | VerticalBounds,
    Field(discriminator="kind"),
]


class Coverage(Contract):
    generation: str = Field(min_length=1, max_length=128)
    expires_at_ms: Time
    mask_encoding: Literal[
        "feature-collection-v1", "uint8-validity-v1", "absence-rgba-v1"
    ]
    missing_meaning: Literal["unknown-not-clear"]
    feed_completeness: Literal["unknown", "partial", "complete"]


class Payload(Contract):
    path: str = Field(
        pattern=r"^/api/aviation-weather/v1/products/[a-f0-9]{64}/[a-z0-9_-]+\.(json|bin)$",
        max_length=256,
    )
    sha256: Hash
    content_type: Literal[
        "application/json", "application/geo+json", "application/octet-stream"
    ]
    encoded_bytes: int = Field(gt=0, le=16 * 1024**2)
    decoded_bytes: int = Field(gt=0, le=32 * 1024**2)
    gpu_bytes: int = Field(ge=0, le=16 * 1024**2)


class GridComponent(Contract):
    quantity: Literal[
        "air-temperature", "wind-east", "wind-north", "brightness-temperature"
    ]
    unit: Literal["K", "m/s"]
    scale: float = Field(gt=0)
    offset: float

    @model_validator(mode="after")
    def units(self) -> Self:
        if self.unit != ("m/s" if self.quantity.startswith("wind-") else "K"):
            raise ValueError("Incompatible physical units")
        return self


class Grid(Contract):
    width: int = Field(ge=2, le=720)
    height: int = Field(ge=2, le=361)
    longitude_start: Literal[-180.0]
    latitude_start: Literal[90.0]
    longitude_step: float = Field(gt=0)
    latitude_step: float = Field(lt=0)
    mask_encoding: Literal["uint8-validity-v1"]
    components: list[GridComponent] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def geometry(self) -> Self:
        if (
            abs(self.width * self.longitude_step - 360) > 1e-9
            or abs((self.height - 1) * self.latitude_step + 180) > 1e-9
        ):
            raise ValueError("Grid must cover globe without duplicate longitude seam")
        if len({item.quantity for item in self.components}) != len(self.components):
            raise ValueError("Duplicate grid components")
        return self


class WeatherProduct(Contract):
    state: Literal["off", "ready", "stale", "unavailable"]
    layer_id: Identifier
    product_type: Literal[
        "observed-precipitation",
        "metar-speci",
        "taf",
        "international-sigmet",
        "winds",
        "air-temperature",
        "satellite-ir",
    ]
    representation: Literal[
        "xyz-rgba-pair-v1", "station-v1", "advisory-v1", "latlon-grid-v1"
    ]
    source_id: Identifier
    provenance: str = Field(min_length=1, max_length=512)
    attribution: list[WeatherAttribution] = Field(min_length=1, max_length=8)
    time_kind: Literal["observation", "forecast", "analysis"]
    method_kind: Literal["reported", "sensor", "numerical-model", "derived"]
    observed_at_ms: Time | None = None
    issued_at_ms: Time | None = None
    scan_start_ms: Time | None = None
    scan_end_ms: Time | None = None
    validity_kind: Literal["instant", "interval", "collection"]
    valid_at_ms: Time | None = None
    valid_from_ms: Time | None = None
    valid_to_ms: Time | None = None
    run_at_ms: Time | None = None
    lead_seconds: int | None = Field(default=None, ge=0, le=604800)
    vertical: Vertical
    coverage: Coverage | None = None
    generated_at_ms: Time
    retrieved_at_ms: Time | None = None
    fresh_until_ms: Time | None = None
    expires_at_ms: Time | None = None
    product_id: Hash
    instance_id: Hash | None = None
    payload: Payload | None = None
    radar: WeatherManifest | None = None
    grid: Grid | None = None

    @model_validator(mode="after")
    def coherent(self) -> Self:
        available = self.state in {"ready", "stale"}
        if not available:
            if any(
                value is not None
                for value in (
                    self.instance_id,
                    self.payload,
                    self.radar,
                    self.grid,
                    self.coverage,
                    self.observed_at_ms,
                    self.issued_at_ms,
                    self.scan_start_ms,
                    self.scan_end_ms,
                    self.valid_at_ms,
                    self.valid_from_ms,
                    self.valid_to_ms,
                    self.run_at_ms,
                    self.lead_seconds,
                    self.retrieved_at_ms,
                    self.fresh_until_ms,
                    self.expires_at_ms,
                )
            ):
                raise ValueError(
                    "Off/unavailable products cannot provide retained data"
                )
            return self
        if any(
            value is None
            for value in (
                self.instance_id,
                self.coverage,
                self.retrieved_at_ms,
                self.fresh_until_ms,
                self.expires_at_ms,
            )
        ):
            raise ValueError(
                "Available products require complete instance and deadlines"
            )
        if (
            not self.retrieved_at_ms <= self.generated_at_ms < self.expires_at_ms
            or self.fresh_until_ms > self.expires_at_ms
            or self.expires_at_ms > self.coverage.expires_at_ms
        ):
            raise ValueError("Incoherent freshness or expiry")
        if (self.state == "stale") != (self.generated_at_ms >= self.fresh_until_ms):
            raise ValueError("State must match original freshness deadline")
        if self.validity_kind == "instant":
            if (
                self.valid_at_ms is None
                or self.valid_from_ms is not None
                or self.valid_to_ms is not None
            ):
                raise ValueError("Instant requires only its valid instant")
        elif self.validity_kind == "interval":
            if (
                self.valid_at_ms is not None
                or self.valid_from_ms is None
                or self.valid_to_ms is None
                or self.valid_from_ms >= self.valid_to_ms
            ):
                raise ValueError("Validity interval must be finite and ordered")
            if self.generated_at_ms >= self.valid_to_ms:
                raise ValueError("Expired forecast interval")
        elif (
            any(
                value is not None
                for value in (self.valid_at_ms, self.valid_from_ms, self.valid_to_ms)
            )
            or self.method_kind != "reported"
            or self.representation not in {"station-v1", "advisory-v1"}
        ):
            raise ValueError("Collections retain per-feature times in their payload")
        if (self.scan_start_ms is None) != (self.scan_end_ms is None):
            raise ValueError("Incomplete observation scan")
        if self.scan_start_ms is not None and self.scan_start_ms > self.scan_end_ms:
            raise ValueError("Reversed observation scan")
        if self.time_kind == "observation":
            if (
                self.method_kind not in {"reported", "sensor", "derived"}
                or self.run_at_ms is not None
                or self.lead_seconds is not None
            ):
                raise ValueError("Observations cannot claim model identity")
            if (
                self.observed_at_ms is None
                and self.scan_end_ms is None
                and self.validity_kind != "collection"
            ):
                raise ValueError("Missing observation identity")
            for instant in (self.observed_at_ms, self.scan_end_ms):
                if instant is not None and instant > self.generated_at_ms + 60000:
                    raise ValueError("Unsupported future observation")
        else:
            if self.observed_at_ms is not None or self.scan_start_ms is not None:
                raise ValueError("Forecasts/analyses cannot claim sensor observations")
            if self.method_kind == "numerical-model":
                if (
                    self.run_at_ms is None
                    or self.lead_seconds is None
                    or self.validity_kind != "instant"
                    or self.valid_at_ms != self.run_at_ms + 1000 * self.lead_seconds
                    or (self.time_kind == "analysis" and self.lead_seconds != 0)
                ):
                    raise ValueError("Incoherent model run/lead/valid identity")
            elif (
                self.time_kind != "forecast"
                or self.method_kind != "reported"
                or self.run_at_ms is not None
                or self.lead_seconds is not None
                or (self.issued_at_ms is None and self.validity_kind != "collection")
            ):
                raise ValueError(
                    "Reported forecasts require issue identity without model run"
                )
        if self.representation == "xyz-rgba-pair-v1":
            if (
                self.product_type != "observed-precipitation"
                or self.radar is None
                or self.radar.state != "ready"
                or self.payload is not None
                or self.grid is not None
                or self.coverage.mask_encoding != "absence-rgba-v1"
                or self.product_id != self.radar.product_id
                or self.source_id != self.radar.source
                or self.observed_at_ms != self.radar.frame_time_ms
                or self.coverage.generation != str(self.radar.coverage_token)
                or self.coverage.expires_at_ms != self.radar.coverage_expires_at_ms
            ):
                raise ValueError(
                    "Radar binding must preserve the legacy capability and coverage"
                )
            frame = self.radar.frame_time_ms / 1000
            day = self.radar.generated_at_ms // 86400000
            age = self.radar.generated_at_ms - self.radar.frame_time_ms
            if (
                not frame.is_integer()
                or not -60000 <= age < 3600000
                or self.radar.coverage_token != day
                or self.radar.coverage_expires_at_ms != (day + 1) * 86400000
                or self.radar.radar_tile_template
                != f"/api/overview-weather/radar/{int(frame)}/{{z}}/{{x}}/{{y}}.png?product_id={self.product_id}"
                or self.radar.coverage_tile_template
                != f"/api/overview-weather/coverage/{day}/{{z}}/{{x}}/{{y}}.png?product_id={self.product_id}"
            ):
                raise ValueError(
                    "Radar templates must bind to the exact admitted same-origin paths"
                )
        elif (
            self.radar is not None
            or self.payload is None
            or self.payload.path.split("/")[5] != self.instance_id
        ):
            raise ValueError("Normalized payload must bind to the immutable instance")
        if self.representation == "latlon-grid-v1":
            if (
                self.grid is None
                or self.coverage.mask_encoding != "uint8-validity-v1"
                or self.payload.content_type != "application/json"
            ):
                raise ValueError("Scientific grids require geometry and validity mask")
            minimum = (
                self.grid.width * self.grid.height * (2 * len(self.grid.components) + 1)
            )
            if self.payload.decoded_bytes < minimum or self.payload.gpu_bytes < minimum:
                raise ValueError("Grid allocation underdeclared")
        elif self.grid is not None:
            raise ValueError("Only scientific grids declare grid geometry")
        elif self.representation != "xyz-rgba-pair-v1" and (
            self.coverage.mask_encoding != "feature-collection-v1"
            or self.payload.content_type != "application/geo+json"
        ):
            raise ValueError(
                "Station/advisory products require geographic feature collections"
            )
        return self


class AviationCatalog(Contract):
    schema_version: Literal["aviation-weather-v1"] = Field(alias="schema")
    generated_at_ms: Time
    settings_revision: Time
    products: list[WeatherProduct] = Field(max_length=16)

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len({product.layer_id for product in self.products}) != len(self.products):
            raise ValueError("Duplicate catalog layers")
        if any(
            product.generated_at_ms != self.generated_at_ms for product in self.products
        ):
            raise ValueError("Catalog entries require one admission clock")
        return self
