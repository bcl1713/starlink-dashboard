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


def get_optional_simulation_run_service(request: Request):
    """Optional for legacy handlers and application startup."""
    return getattr(request.app.state, "simulation_run_service", None)


def get_simulation_run_service(request: Request):
    from fastapi import HTTPException

    service = get_optional_simulation_run_service(request)
    if service is None:
        raise HTTPException(503, "Simulation runtime is not initialized")
    return service
