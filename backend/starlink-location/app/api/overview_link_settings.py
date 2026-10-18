from dataclasses import asdict
from typing import Literal, Self

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from app.models.overview_presets import PresetWeatherVisibility
from app.services.overview_link_settings import (
    OverviewLinkSettingsStore,
    OverviewSettingsConflict,
    _validate_fields,
)

router = APIRouter()


class OverviewLinkSettingsUpdate(BaseModel):
    """Strict, nonempty partial update of shared map-layer visibility."""

    model_config = ConfigDict(extra="forbid")

    expected_values: dict[str, StrictBool] | None = None

    starshield_link_enabled: StrictBool | None = None
    x_band_link_enabled: StrictBool | None = None
    orbital_traffic_enabled: StrictBool | None = None
    aircraft_history_enabled: StrictBool | None = None
    country_borders_enabled: StrictBool | None = None
    state_borders_enabled: StrictBool | None = None
    operational_clocks_enabled: StrictBool | None = None
    arrival_panel_enabled: StrictBool | None = None
    planned_satellite_panel_enabled: StrictBool | None = None
    map_status_enabled: StrictBool | None = None
    legend_enabled: StrictBool | None = None
    latency_panel_enabled: StrictBool | None = None
    downlink_panel_enabled: StrictBool | None = None
    uplink_panel_enabled: StrictBool | None = None
    packet_loss_panel_enabled: StrictBool | None = None
    obstruction_panel_enabled: StrictBool | None = None
    aircraft_marker_enabled: StrictBool | None = None
    planned_route_enabled: StrictBool | None = None
    poi_markers_enabled: StrictBool | None = None
    flight_events_enabled: StrictBool | None = None
    x_band_events_enabled: StrictBool | None = None
    ka_events_enabled: StrictBool | None = None
    starshield_events_enabled: StrictBool | None = None
    ground_entry_point_enabled: StrictBool | None = None
    configured_satellites_enabled: StrictBool | None = None

    @model_validator(mode="after")
    def validate_supplied_fields(self) -> Self:
        fields = self.model_fields_set - {"expected_values"}
        if not fields:
            raise ValueError("At least one overview link setting is required")
        if any(getattr(self, field) is None for field in fields):
            raise ValueError("Overview link settings cannot be null")
        if "expected_values" in self.model_fields_set and (
            self.expected_values is None or self.expected_values.keys() != fields
        ):
            raise ValueError("Expected values must match changed fields")
        return self


_overview_link_settings_store: OverviewLinkSettingsStore | None = None


def set_overview_link_settings_store(
    store: OverviewLinkSettingsStore | None,
) -> None:
    """Register or clear the application-owned persistent settings store."""
    global _overview_link_settings_store
    _overview_link_settings_store = store


def _get_store() -> OverviewLinkSettingsStore:
    if _overview_link_settings_store is None:
        raise HTTPException(
            status_code=503,
            detail="Overview link settings are not yet initialized",
        )
    return _overview_link_settings_store


@router.get("/api/overview-links/settings")
def get_overview_link_settings():
    """Return the full confirmed visibility settings."""
    store = _get_store()
    try:
        return asdict(store.get())
    except (OSError, ValueError, TypeError) as error:
        raise HTTPException(
            status_code=503,
            detail="Overview link settings could not be read",
        ) from error


@router.put("/api/overview-links/settings")
def update_overview_link_settings(settings: OverviewLinkSettingsUpdate):
    """Persist supplied switches and return the complete confirmed settings."""
    store = _get_store()
    try:
        return asdict(
            store.update(
                settings.model_dump(exclude_unset=True, exclude={"expected_values"}),
                settings.expected_values,
            )
        )
    except OverviewSettingsConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (OSError, ValueError, TypeError) as error:
        raise HTTPException(
            status_code=503,
            detail="Overview link settings could not be saved",
        ) from error


class OverviewPresetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    settings: dict[str, StrictBool]
    expected_version: int = Field(ge=0, strict=True)
    weather_visibility: PresetWeatherVisibility | None = None

    @model_validator(mode="after")
    def validate_settings(self) -> Self:
        if not _validate_fields(self.settings):
            raise ValueError("A preset must contain existing visibility switches")
        return self


@router.get("/api/overview-links/presets")
def get_overview_presets():
    try:
        return _get_store().get_presets()
    except (OSError, ValueError, TypeError) as error:
        raise HTTPException(
            status_code=503, detail="Overview presets could not be read"
        ) from error


@router.put("/api/overview-links/presets/{name}")
def save_overview_preset(
    name: Literal["normal", "communications", "weather"], settings: OverviewPresetUpdate
):
    try:
        return _get_store().save_preset(
            name,
            settings.settings,
            settings.expected_version,
            (
                settings.weather_visibility.model_dump()
                if settings.weather_visibility
                else None
            ),
        )
    except OverviewSettingsConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (OSError, ValueError, TypeError) as error:
        raise HTTPException(
            status_code=503, detail="Overview preset could not be saved"
        ) from error
