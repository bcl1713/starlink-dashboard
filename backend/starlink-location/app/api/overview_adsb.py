"""Shared ADS-B configuration and backend-owned traffic reads."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException

from app.models.overview_adsb import AdsbSettings, AdsbSettingsUpdate, AdsbTrafficBundle
from app.services.overview_adsb_settings import AdsbSettingsStore

if TYPE_CHECKING:
    from app.services.overview_adsb_traffic import AdsbTrafficService

router = APIRouter()
_store: AdsbSettingsStore | None = None
_service: AdsbTrafficService | None = None


def set_overview_adsb_runtime(
    store: AdsbSettingsStore | None,
    service: AdsbTrafficService | None,
) -> None:
    global _store, _service
    _store, _service = store, service


def _get_store() -> AdsbSettingsStore:
    if _store is None:
        raise HTTPException(503, "ADS-B settings are not initialized")
    return _store


@router.get("/api/overview-adsb/settings", response_model=AdsbSettings)
async def get_settings() -> AdsbSettings:
    try:
        return _get_store().get()
    except (OSError, ValueError, TypeError) as error:
        raise HTTPException(503, "ADS-B settings could not be read") from error


@router.put("/api/overview-adsb/settings", response_model=AdsbSettings)
async def update_settings(changes: AdsbSettingsUpdate) -> AdsbSettings:
    try:
        settings = _get_store().update(changes.model_dump(exclude_unset=True))
    except (OSError, ValueError, TypeError) as error:
        raise HTTPException(503, "ADS-B settings could not be saved") from error
    if _service is not None:
        _service.settings_changed()
    return settings


@router.get("/api/overview-adsb/traffic", response_model=AdsbTrafficBundle)
async def get_traffic() -> AdsbTrafficBundle:
    if _service is None:
        raise HTTPException(503, "ADS-B acquisition is not initialized")
    try:
        return _service.read()
    except (OSError, ValueError, TypeError) as error:
        raise HTTPException(503, "ADS-B settings could not be read") from error


@router.get("/api/overview-adsb/catalog", response_model=AdsbTrafficBundle)
async def get_catalog() -> AdsbTrafficBundle:
    if _service is None:
        raise HTTPException(503, "ADS-B acquisition is not initialized")
    try:
        return _service.read_catalog()
    except (OSError, ValueError, TypeError) as error:
        raise HTTPException(503, "ADS-B settings could not be read") from error
