"""Validated ADS-B wire contracts; all timestamps are epoch milliseconds."""

import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AdsbSettingsFields(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    enabled: bool = False
    mode: Literal["military_and_included", "included_only"] = "military_and_included"
    include_hexes: list[str] = Field(default_factory=list)
    exclude_hexes: list[str] = Field(default_factory=list)
    callsign_substrings: list[str] = Field(default_factory=list)

    @field_validator("include_hexes", "exclude_hexes", "callsign_substrings")
    @classmethod
    def normalize_entries(cls, values: list[str], info) -> list[str]:
        normalized = [value.strip().upper() for value in values]
        if info.field_name != "callsign_substrings":
            if any(re.fullmatch(r"[0-9A-F]{6}", value) is None for value in normalized):
                raise ValueError("ICAO hex must contain exactly six hexadecimal digits")
        else:
            normalized = [value for value in normalized if value]
        return list(dict.fromkeys(normalized))


class AdsbSettings(AdsbSettingsFields):
    revision: int = Field(default=0, ge=0)


class AdsbSettingsUpdate(AdsbSettingsFields):
    @model_validator(mode="after")
    def nonempty(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one ADS-B setting is required")
        return self


class AdsbAltitude(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, allow_inf_nan=False
    )
    value: float
    unit: Literal["ft"] = "ft"
    source: Literal["barometric", "geometric"]


class AdsbContact(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, allow_inf_nan=False
    )
    hex: str = Field(pattern=r"^[0-9A-F]{6}$")
    callsign: str | None = None
    registration: str | None = None
    aircraft_type: str | None = None
    military: bool | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    altitude: AdsbAltitude | None = None
    ground_speed_knots: float | None = Field(default=None, ge=0)
    track_degrees: float | None = Field(default=None, ge=0, lt=360)
    position_observed_at_ms: float = Field(ge=0)
    acquired_at_ms: float = Field(ge=0)


class AdsbSourceStatus(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, allow_inf_nan=False
    )
    key: str = Field(pattern=r"^(military|hex:[0-9A-F]{6})$")
    last_success_at_ms: float | None = None
    error: str | None = None
    retry_at_ms: float | None = None


class AdsbTrafficBundle(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, allow_inf_nan=False
    )
    settings_revision: int = Field(ge=0)
    generated_at_ms: float
    contacts: list[AdsbContact]
    sources: list[AdsbSourceStatus]
