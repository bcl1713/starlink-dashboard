"""API endpoint for truthful Overview upcoming mission POIs."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.eta_service import get_eta_calculator
from app.mission.dependencies import get_poi_manager, get_route_manager
from app.mission.routes import get_active_mission_id
from app.models.overview_upcoming_pois import OverviewUpcomingPoisResponse
from app.services.flight_state import get_flight_state_manager
from app.services.poi_manager import POIManager
from app.services.route_eta_calculator import RouteETACalculator
from app.services.route_manager import RouteManager
from app.services.overview_upcoming_pois import (
    calculate_route_aware_eta_results,
    project_overview_upcoming_pois,
)


router = APIRouter(prefix="/api/overview", tags=["overview"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _route_progress(active_route: object, latitude: float, longitude: float) -> float | None:
    try:
        return RouteETACalculator(active_route).get_route_progress(latitude, longitude).get(
            "progress_percent"
        )
    except (AttributeError, TypeError, ValueError, IndexError):
        return None


@router.get("/upcoming-pois", response_model=OverviewUpcomingPoisResponse)
async def get_overview_upcoming_pois(
    request: Request,
    route_manager: Annotated[RouteManager, Depends(get_route_manager)],
    poi_manager: Annotated[POIManager, Depends(get_poi_manager)],
) -> OverviewUpcomingPoisResponse:
    """Return active-mission POIs with schedule and estimate provenance preserved."""
    calculated_at = _utc_now()
    mission_id = get_active_mission_id()
    active_route = route_manager.get_active_route()
    if mission_id is None or active_route is None:
        return OverviewUpcomingPoisResponse(
            state="no_active_route", calculated_at=calculated_at, pois=[]
        )

    generated_pois = [
        poi
        for poi in poi_manager.list_pois(mission_id=mission_id)
        if poi.kind is not None and poi.generated_source == "mission-timeline"
    ]
    if not generated_pois:
        return OverviewUpcomingPoisResponse(
            state="no_generated_pois", calculated_at=calculated_at, pois=[]
        )

    flight_phase = get_flight_state_manager().get_status().phase.value
    latitude = longitude = speed_knots = None
    coordinator = getattr(request.app.state, "coordinator", None)
    if coordinator is not None:
        try:
            telemetry = coordinator.get_current_telemetry()
            latitude = telemetry.position.latitude
            longitude = telemetry.position.longitude
            speed_knots = telemetry.position.speed
        except (AttributeError, TypeError, ValueError):
            pass

    # In-flight estimates must derive from live telemetry and active-route geometry.
    # A missing telemetry sample means timing is honestly unavailable, not guessed.
    if flight_phase == "in_flight" and (
        latitude is None or longitude is None or speed_knots is None
    ):
        return OverviewUpcomingPoisResponse(
            state="unavailable", calculated_at=calculated_at, pois=[]
        )

    eta_results = calculate_route_aware_eta_results(
        pois=generated_pois,
        calculator=get_eta_calculator(),
        active_route=active_route,
        flight_phase=flight_phase,
        latitude=latitude,
        longitude=longitude,
        speed_knots=speed_knots,
    )
    current_progress = (
        _route_progress(active_route, latitude, longitude)
        if latitude is not None and longitude is not None
        else None
    )
    return project_overview_upcoming_pois(
        pois=generated_pois,
        eta_results=eta_results,
        flight_phase=flight_phase,
        current_progress=current_progress,
        calculated_at=calculated_at,
    )
