"""Overview telemetry-history API."""

from collections.abc import Awaitable, Callable

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.overview_history_prometheus import (
    OverviewHistoryPrometheusResponseError,
)
from app.services.overview_history_settings import OverviewHistorySettingsStore

router = APIRouter()


class OverviewHistorySettingsUpdate(BaseModel):
    """Validated dashboard update for the Prometheus query lookback."""

    window_seconds: int = Field(gt=0, strict=True)


_overview_history_reader: Callable[[], Awaitable[dict]] | None = None
_overview_history_settings_store: OverviewHistorySettingsStore | None = None


def set_overview_history_reader(
    reader: Callable[[], Awaitable[dict]] | None,
) -> None:
    """Set the initialized overview-history runtime reader."""
    global _overview_history_reader
    _overview_history_reader = reader


def set_overview_history_settings_store(
    store: OverviewHistorySettingsStore | None,
) -> None:
    """Set the initialized persistent overview-history settings store."""
    global _overview_history_settings_store
    _overview_history_settings_store = store


@router.get("/api/overview-history")
async def get_overview_history():
    """Return the shared bounded overview telemetry-history bundle."""
    if _overview_history_reader is None:
        raise HTTPException(
            status_code=503,
            detail="Overview history is not yet initialized",
        )
    try:
        return await _overview_history_reader()
    except (httpx.HTTPError, OverviewHistoryPrometheusResponseError) as error:
        raise HTTPException(
            status_code=503,
            detail="Overview history is temporarily unavailable",
        ) from error


@router.get("/api/overview-history/settings")
async def get_overview_history_settings():
    """Return the persistent dashboard-selected history query window."""
    if _overview_history_settings_store is None:
        raise HTTPException(
            status_code=503,
            detail="Overview history settings are not yet initialized",
        )
    return {
        "window_seconds": _overview_history_settings_store.get_window_seconds(),
    }


@router.put("/api/overview-history/settings")
async def update_overview_history_settings(
    settings: OverviewHistorySettingsUpdate,
):
    """Persist the dashboard-selected Prometheus query window."""
    if _overview_history_settings_store is None:
        raise HTTPException(
            status_code=503,
            detail="Overview history settings are not yet initialized",
        )
    _overview_history_settings_store.set_window_seconds(
        settings.window_seconds,
    )
    return {
        "window_seconds": settings.window_seconds,
    }
