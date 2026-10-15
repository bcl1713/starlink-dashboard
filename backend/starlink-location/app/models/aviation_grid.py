"""Strict public grid descriptors and private acquisition records."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from app.models.aviation_weather import (
    Contract,
    FlightLevel,
    Grid,
    Hash,
    Pressure,
    Time,
)

PRESSURES = (85000, 50000, 30000, 25000, 20000)
HORIZONS = (0, 3, 6, 9, 12, 18, 24, 36, 48)
FLIGHT_LEVELS = (50, 100, 180, 240, 300, 340, 390, 450)


class PressureSelection(Contract):
    kind: Literal["pressure"] = "pressure"
    pressure_pa: int = 50000

    @field_validator("pressure_pa")
    @classmethod
    def pressure(cls, value):
        if value not in PRESSURES:
            raise ValueError("Unsupported GFS pressure selection")
        return value


class FlightLevelSelection(Contract):
    kind: Literal["flight-level"]
    flight_level: int

    @field_validator("flight_level")
    @classmethod
    def level(cls, value):
        if value not in FLIGHT_LEVELS:
            raise ValueError("Unsupported GFS flight level")
        return value


class GfsSelection(Contract):
    vertical: Annotated[
        PressureSelection | FlightLevelSelection, Field(discriminator="kind")
    ] = Field(default_factory=PressureSelection)
    horizon_hours: int = 0

    @model_validator(mode="before")
    @classmethod
    def legacy_pressure(cls, value):
        if (
            isinstance(value, dict)
            and "pressure_pa" in value
            and "vertical" not in value
        ):
            value = dict(value)
            value["vertical"] = {
                "kind": "pressure",
                "pressure_pa": value.pop("pressure_pa"),
            }
        return value

    @property
    def pressure_pa(self):
        # Compatibility for foundation pressure-only callers. FL consumers use
        # the tagged vertical and explicit ISA conversion instead.
        return self.vertical.pressure_pa

    @field_validator("horizon_hours")
    @classmethod
    def horizon(cls, value):
        if value not in HORIZONS:
            raise ValueError("Unsupported GFS forecast horizon")
        return value


class GridBuffer(Contract):
    path: str = Field(
        pattern=r"^/api/aviation-weather/v1/products/[a-f0-9]{64}/(u|v|t|mask)\.bin$"
    )
    sha256: Hash
    byte_length: int = Field(gt=0, le=16 * 1024**2)
    dtype: Literal["int16-le", "uint8"]


class GridDescriptor(Contract):
    schema_version: Literal["aviation-weather-v1"] = Field(alias="schema")
    representation: Literal["latlon-grid-v1"]
    mask_scope: Literal["shared-conservative-uvt"] = "shared-conservative-uvt"
    product_id: Hash
    instance_id: Hash
    normalization_version: Literal["gfs-regular-ll-v1"]
    run_at_ms: Time
    lead_seconds: int = Field(ge=0, le=172800)
    valid_at_ms: Time
    retrieved_at_ms: Time
    generated_at_ms: Time
    vertical: Annotated[Pressure | FlightLevel, Field(discriminator="kind")]
    grid: Grid
    buffers: dict[str, GridBuffer]

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if isinstance(self.vertical, FlightLevel):
            from app.services.aviation_weather.gfs.vertical import flight_level_pressure

            target = flight_level_pressure(self.vertical.flight_level)
            if self.vertical.derivation != "isa-log-pressure-v1" or not (
                self.vertical.source_pressures_pa[0]
                < target
                < self.vertical.source_pressures_pa[1]
            ):
                raise ValueError("GFS flight levels require actual ISA brackets")
        if (
            self.valid_at_ms != self.run_at_ms + 1000 * self.lead_seconds
            or self.lead_seconds // 3600 not in HORIZONS
            or self.lead_seconds % 3600
            or self.retrieved_at_ms > self.generated_at_ms
            or self.run_at_ms > self.generated_at_ms + 60000
        ):
            raise ValueError("Incoherent GFS time identity")
        if self.grid.width != 720 or self.grid.height != 361:
            raise ValueError("Unsupported production GFS dimensions")
        expected = ("wind-east", "wind-north", "air-temperature")
        if tuple(item.quantity for item in self.grid.components) != expected:
            raise ValueError("GFS requires ordered U/V/T components")
        for component in self.grid.components:
            if component.scale != 0.01 or component.offset != (
                273.15 if component.quantity == "air-temperature" else 0.0
            ):
                raise ValueError("Unsupported GFS quantization")
        if set(self.buffers) != {"u", "v", "t", "mask"}:
            raise ValueError("GFS requires complete field and validity buffers")
        cells = self.grid.width * self.grid.height
        for name, buffer in self.buffers.items():
            if (
                buffer.path
                != f"/api/aviation-weather/v1/products/{self.instance_id}/{name}.bin"
                or buffer.byte_length != cells * (1 if name == "mask" else 2)
                or buffer.dtype != ("uint8" if name == "mask" else "int16-le")
            ):
                raise ValueError("Buffer identity, length or encoding mismatch")
        return self


@dataclass(frozen=True)
class SourceRef:
    key: str
    etag: str
    size: int


@dataclass(frozen=True)
class RangeRef:
    source: SourceRef
    start: int
    end: int
    quantity: str
    pressure_pa: int | None


@dataclass(frozen=True)
class SourceBundle:
    run_at_ms: int
    lead_seconds: int
    ranges: tuple[RangeRef, ...]
    paths: tuple[Path, ...]
    hashes: tuple[str, ...]
    retrieved_at_ms: int
    available_leads: tuple[int, ...] = ()


@dataclass(frozen=True)
class GridCandidate:
    descriptor: GridDescriptor
    directory: Path
