from fastapi import Request

from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager


def get_route_manager(request: Request) -> RouteManager:
    """Get RouteManager instance from app state."""
    return request.app.state.route_manager


def get_poi_manager(request: Request) -> POIManager:
    """Get POIManager instance from app state."""
    return request.app.state.poi_manager
