"""API endpoint for truthful Overview upcoming mission POIs."""

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.eta_service import get_eta_calculator
from app.mission.active_context import resolve_active_mission_leg_context
from app.mission.dependencies import get_poi_manager, get_route_manager
from app.models.flight_status import FlightPhase
from app.models.overview_upcoming_pois import (
    OverviewUpcomingPoi,
    OverviewUpcomingPoisResponse,
)
from app.services.flight_state import get_flight_state_manager
from app.services.manual_destination import ManualDestination
from app.services.overview_upcoming_pois import (
    calculate_route_aware_eta_results,
    project_overview_upcoming_pois,
)
from app.services.poi_manager import POIManager
from app.services.position_freshness import position_observation, speed_is_fresh
from app.services.route_eta_calculator import RouteETACalculator
from app.services.route_manager import RouteManager
from app.simulation.run_timing import planned_poi_eta, published_replay

router = APIRouter(prefix="/api/overview", tags=["overview"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _route_progress(
    active_route: object, latitude: float, longitude: float
) -> float | None:
    try:
        return (
            RouteETACalculator(active_route)
            .get_route_progress(latitude, longitude)
            .get("progress_percent")
        )
    except (AttributeError, TypeError, ValueError, IndexError):
        return None


def _manual_destination_response(
    request: Request, destination: ManualDestination, calculated_at: datetime
) -> OverviewUpcomingPoisResponse:
    """Project one direct-distance estimate without consulting mission state."""
    observed_at = speed_observed_at = None
    position_state = "unavailable"
    eta = None
    arrival_time = None
    try:
        position = request.app.state.coordinator.get_current_telemetry().position
        observed_at, position_state = position_observation(
            position.latitude,
            position.longitude,
            getattr(position, "observed_at", None),
            calculated_at,
        )
        speed = getattr(position, "speed", None)
        speed_observed_at = getattr(position, "speed_observed_at", None)
        if (
            position_state == "fresh"
            and speed_is_fresh(speed, speed_observed_at, calculated_at)
            and speed > 0
        ):
            distance = get_eta_calculator().calculate_distance(
                position.latitude,
                position.longitude,
                destination.latitude,
                destination.longitude,
            )
            seconds = distance / 1852 / speed * 3600
            if (
                isfinite(seconds)
                and 0
                <= seconds
                <= (
                    datetime.max.replace(tzinfo=timezone.utc) - calculated_at
                ).total_seconds()
            ):
                arrival_time = calculated_at + timedelta(seconds=seconds)
                eta = seconds
    except (AttributeError, TypeError, ValueError, RuntimeError, OverflowError):
        pass
    return OverviewUpcomingPoisResponse(
        source="manual",
        state="available" if eta is not None else "unavailable",
        calculated_at=calculated_at,
        position_observed_at=observed_at,
        position_state=position_state,
        speed_observed_at=speed_observed_at if eta is not None else None,
        pois=[
            OverviewUpcomingPoi(
                poi_id="manual-destination",
                name=destination.name,
                kind="arrival",
                latitude=destination.latitude,
                longitude=destination.longitude,
                eta_seconds=eta,
                estimated_arrival_time=arrival_time,
                eta_type="estimated",
                flight_phase=None,
                upcoming=True,
                map_retained=True,
            )
        ],
    )


@router.get("/upcoming-pois", response_model=OverviewUpcomingPoisResponse)
async def get_overview_upcoming_pois(
    request: Request,
    route_manager: Annotated[RouteManager, Depends(get_route_manager)],
    poi_manager: Annotated[POIManager, Depends(get_poi_manager)],
) -> OverviewUpcomingPoisResponse:
    """Return active-mission POIs with schedule and estimate provenance preserved."""
    calculated_at = _utc_now()
    resolution = resolve_active_mission_leg_context(route_manager)
    if resolution.context is None:
        store = getattr(request.app.state, "manual_destination_store", None)
        if resolution.state == "no_active_mission" and store is not None:
            destination = store.get().destination
            if destination is not None:
                return _manual_destination_response(request, destination, calculated_at)
        return OverviewUpcomingPoisResponse(
            state=resolution.state, calculated_at=calculated_at, pois=[]
        )
    mission_id = resolution.context.parent_mission_id
    active_route_id = resolution.context.route_id
    active_route = resolution.context.route

    selection = published_replay(
        getattr(request.app.state, "simulation_run_service", None)
    )
    context = selection[2] if selection else None
    if selection:
        active_route = selection[0].artifacts.route
    flight_phase = (
        context.phase
        if context
        else get_flight_state_manager().get_status().phase.value
    )
    generated_pois = [
        poi
        for poi in poi_manager.list_pois(mission_id=mission_id)
        if poi.kind is not None
        and poi.generated_source == "mission-timeline"
        and (poi.route_id is None or poi.route_id == active_route_id)
    ]
    if not generated_pois:
        return OverviewUpcomingPoisResponse(
            state="no_generated_pois",
            calculated_at=calculated_at,
            flight_phase=FlightPhase(flight_phase),
            pois=[],
        )

    observed_at: datetime | None = None
    position_state = "unavailable"
    latitude = longitude = speed_knots = None
    speed_observed_at = None
    coordinator = getattr(request.app.state, "coordinator", None)
    if coordinator is not None:
        try:
            telemetry = coordinator.get_current_telemetry()
            latitude = telemetry.position.latitude
            longitude = telemetry.position.longitude
            speed_knots = telemetry.position.speed
            speed_observed_at = getattr(telemetry.position, "speed_observed_at", None)
            observed_at, position_state = position_observation(
                latitude,
                longitude,
                getattr(telemetry.position, "observed_at", None),
                calculated_at,
            )
        except (AttributeError, TypeError, ValueError, RuntimeError):
            pass

    # Suppress timing while retaining generated records and last-known map context.
    usable_speed = speed_is_fresh(speed_knots, speed_observed_at, calculated_at)
    timing_unavailable = flight_phase == "in_flight" and (
        position_state != "fresh" or not usable_speed
    )
    eta_results = (
        {}
        if timing_unavailable
        else calculate_route_aware_eta_results(
            pois=generated_pois,
            calculator=get_eta_calculator(),
            active_route=active_route,
            flight_phase=flight_phase,
            latitude=latitude,
            longitude=longitude,
            speed_knots=speed_knots,
        )
    )
    if selection and not timing_unavailable:
        eta_results = {
            poi.id: planned_poi_eta(selection[0], selection[1], poi)
            for poi in generated_pois
        }
    current_progress = (
        _route_progress(active_route, latitude, longitude)
        if position_state != "unavailable"
        and latitude is not None
        and longitude is not None
        else None
    )
    response = project_overview_upcoming_pois(
        pois=generated_pois,
        eta_results=eta_results,
        flight_phase=flight_phase,
        current_progress=current_progress,
        calculated_at=calculated_at,
        mission_time=context,
    )
    departures = [poi for poi in generated_pois if poi.kind == "departure"]
    response.scheduled_departure_time = (
        departures[0].expected_arrival_time if len(departures) == 1 else None
    )
    response.position_observed_at = observed_at
    response.position_state = position_state
    runtime = getattr(request.app.state, "flight_event_runtime", None)
    if runtime is not None and not selection:
        for key, value in runtime.status(mission_id, resolution.context.leg.id).items():
            setattr(response, key, value)
    if timing_unavailable:
        response.state = "unavailable"
    return response
