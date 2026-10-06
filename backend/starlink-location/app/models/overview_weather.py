"""Strict weather contracts; wire timestamps are UTC epoch milliseconds."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WeatherSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    enabled: bool = False
    revision: int = Field(default=0, ge=0)


class WeatherSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    enabled: bool


class WeatherAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    label: str = Field(min_length=1, max_length=256)
    url: str = Field(pattern=r"^https://[^\s]+$", max_length=2048)


class WeatherManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    state: Literal["off", "ready", "unavailable"]
    settings_revision: int = Field(ge=0)
    generated_at_ms: int = Field(ge=0)
    frame_time_ms: int | None = Field(default=None, ge=0)
    coverage_token: int | None = Field(default=None, ge=0)
    coverage_expires_at_ms: int | None = Field(default=None, ge=0)
    source: str = Field(pattern=r"^[a-z0-9_-]{1,64}$")
    provenance: str = Field(min_length=1, max_length=256)
    product: Literal["observed-precipitation"]
    product_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    tile_schema: Literal["xyz-rgba-pair-v1"]
    coverage_encoding: Literal["absence-rgba-v1"]
    attribution: WeatherAttribution
    max_zoom: int = Field(ge=2, le=7)
    zoom: Literal[2] = 2
    tile_size: Literal[512] = 512
    radar_tile_template: str | None = None
    coverage_tile_template: str | None = None

    @model_validator(mode="after")
    def coherent_state(self) -> Self:
        values = (
            self.frame_time_ms,
            self.coverage_token,
            self.coverage_expires_at_ms,
            self.radar_tile_template,
            self.coverage_tile_template,
        )
        if self.state == "ready":
            if any(value is None for value in values):
                raise ValueError("Ready weather requires complete frame and coverage")
        elif any(value is not None for value in values):
            raise ValueError("Unavailable weather cannot supply imagery")
        return self
