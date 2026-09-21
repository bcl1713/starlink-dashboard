from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.overview_clock_location import ClockLocation
from app.services.overview_clock_settings import OverviewClockSettingsStore

router = APIRouter()


class OverviewClockSettingUpdate(BaseModel):
    """One editable operational-clock record from the dashboard."""

    label: str
    time_zone: str


class OverviewClockSettingsUpdate(BaseModel):
    """Complete replacement payload for the fixed four-slot clock collection."""

    clocks: list[OverviewClockSettingUpdate]


_overview_clock_settings_store: OverviewClockSettingsStore | None = None


def set_overview_clock_settings_store(
    store: OverviewClockSettingsStore | None,
) -> None:
    """Set the initialized persistent overview-clock settings store."""
    global _overview_clock_settings_store
    _overview_clock_settings_store = store


@router.get("/api/overview-clocks/settings")
async def get_overview_clock_settings():
    """Return the persistent operational-clock preferences."""
    if _overview_clock_settings_store is None:
        raise HTTPException(
            status_code=503,
            detail="Overview clock settings are not yet initialized",
        )
    return {
        "clocks": [
            {
                "label": clock.label,
                "time_zone": clock.time_zone,
            }
            for clock in _overview_clock_settings_store.get_clocks()
        ]
    }


@router.put("/api/overview-clocks/settings")
async def update_overview_clock_settings(
    settings: OverviewClockSettingsUpdate,
):
    """Persist the complete editable operational-clock collection."""
    if _overview_clock_settings_store is None:
        raise HTTPException(
            status_code=503,
            detail="Overview clock settings are not yet initialized",
        )
    clocks = [
        ClockLocation(
            label=clock.label,
            time_zone=clock.time_zone,
        )
        for clock in settings.clocks
    ]
    try:
        _overview_clock_settings_store.set_clocks(clocks)
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error
    return {
        "clocks": [
            {
                "label": clock.label,
                "time_zone": clock.time_zone,
            }
            for clock in clocks
        ]
    }
