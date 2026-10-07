from dataclasses import asdict
from typing import Self

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, StrictBool, model_validator

from app.services.overview_link_settings import OverviewLinkSettingsStore

router = APIRouter()


class OverviewLinkSettingsUpdate(BaseModel):
    """Strict, nonempty partial update of shared map-layer visibility."""

    model_config = ConfigDict(extra="forbid")

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
    ground_entry_point_enabled: StrictBool | None = None
    configured_satellites_enabled: StrictBool | None = None

    @model_validator(mode="after")
    def validate_supplied_fields(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one overview link setting is required")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Overview link settings cannot be null")
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
        return asdict(store.update(settings.model_dump(exclude_unset=True)))
    except (OSError, ValueError, TypeError) as error:
        raise HTTPException(
            status_code=503,
            detail="Overview link settings could not be saved",
        ) from error
