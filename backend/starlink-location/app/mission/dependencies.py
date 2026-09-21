from fastapi import Request

from app.services.overview_clock_settings import OverviewClockSettingsStore
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager


def get_route_manager(request: Request) -> RouteManager:
    """Get RouteManager instance from app state."""
    return request.app.state.route_manager


def get_poi_manager(request: Request) -> POIManager:
    """Get POIManager instance from app state."""
    return request.app.state.poi_manager


def get_overview_clock_settings_store(
    request: Request,
) -> OverviewClockSettingsStore:
    """Get the overview-clock settings store from application state."""
    return request.app.state.overview_clock_settings_store
