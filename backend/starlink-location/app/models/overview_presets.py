"""Preset weather visibility excludes providers, forecast selection and ACKs."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class PresetWeatherVisibility(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    radar: bool
    metar: bool
    taf: bool
    departure_weather: bool = False
    arrival_weather: bool = False
    sigmet: bool
    sigmet_intersecting_only: bool
    winds: bool
    temperature: bool

    @model_validator(mode="after")
    def exclusive_gfs(self) -> Self:
        if self.winds and self.temperature:
            raise ValueError("Only one GFS layer may be enabled")
        return self
