"""UI endpoints for POI, Route, and Mission interfaces."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from .templates import (
    get_mission_planner_template,
    get_poi_management_template,
    get_route_management_template,
)

router = APIRouter(prefix="/ui", tags=["UI"])


@router.get("/pois", response_class=HTMLResponse)
async def poi_management_ui() -> str:
    """Serve POI management user interface."""
    return get_poi_management_template()


@router.get("/routes", response_class=HTMLResponse)
async def route_management_ui() -> str:
    """Serve Route management user interface."""
    return get_route_management_template()


@router.get("/mission-planner", response_class=HTMLResponse)
async def mission_planner_ui() -> str:
    """Serve Mission Planner user interface."""
    return get_mission_planner_template()
