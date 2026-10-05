"""Flight status API endpoints for monitoring flight phase and ETA mode."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException

from app.mission.dependencies import get_optional_simulation_run_service
from app.models.flight_status import (
    ArrivalUpdateRequest,
    DepartureUpdateRequest,
    FlightStatusResponse,
    ManualFlightPhaseTransition,
)
from app.services.flight_state import get_flight_state_manager
from app.simulation.run_service import SimulationRunService
from app.simulation.run_timing import published_replay

router = APIRouter(prefix="/api/flight-status", tags=["flight-status"])


def _build_response(run_service=None) -> FlightStatusResponse:
    """Build a FlightStatusResponse from the current manager snapshot."""
    manager = get_flight_state_manager()
    selection = published_replay(run_service)
    context = selection[2] if selection else None
    status = (
        manager.get_status(mission_now=context.simulation_time)
        if context
        else manager.get_status()
    )
    return FlightStatusResponse(
        mission_time=context,
        phase=status.phase,
        eta_mode=status.eta_mode,
        active_route_id=status.active_route_id,
        active_route_name=status.active_route_name,
        has_timing_data=status.has_timing_data,
        scheduled_departure_time=status.scheduled_departure_time,
        scheduled_arrival_time=status.scheduled_arrival_time,
        departure_time=status.departure_time,
        arrival_time=status.arrival_time,
        time_until_departure_seconds=status.time_until_departure_seconds,
        time_since_departure_seconds=status.time_since_departure_seconds,
    )


@router.get(
    "", response_model=FlightStatusResponse, summary="Get current flight status"
)
async def get_flight_status(
    run_service: Annotated[
        SimulationRunService | None, Depends(get_optional_simulation_run_service)
    ] = None,
) -> FlightStatusResponse:
    """
    Get the current flight status including phase, ETA mode, countdowns, and route metadata.

    Returns:
        FlightStatusResponse with current phase, mode, route context, timing flags, and countdown timestamps

    Example:
        ```bash
        curl http://localhost:8000/api/flight-status | jq
        ```
    """
    try:
        return _build_response(run_service)
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        LookupError,
        ConnectionError,
        TimeoutError,
        ImportError,
        EOFError,
    ) as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/transition",
    response_model=FlightStatusResponse,
    summary="Manually transition flight phase",
)
async def transition_flight_phase(
    transition: ManualFlightPhaseTransition,
    run_service: Annotated[
        SimulationRunService | None, Depends(get_optional_simulation_run_service)
    ] = None,
) -> FlightStatusResponse:
    """
    Manually transition to a new flight phase.

    This endpoint allows manual control of the flight state machine,
    useful for testing or correcting automatic detection errors.
    """
    if run_service and run_service.status().run:
        run = run_service.status().run
        run_service.assert_plan_edit_allowed(run.mission_id, run.leg_id)
    try:
        manager = get_flight_state_manager()
        success = manager.transition_phase(transition.phase, transition.reason)

        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid phase transition to {transition.phase.value}",
            )

        return _build_response()
    except HTTPException:
        raise
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        LookupError,
        ConnectionError,
        TimeoutError,
        ImportError,
        EOFError,
    ) as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/depart",
    response_model=FlightStatusResponse,
    summary="Manually trigger departure",
)
async def manual_departure(
    update: Annotated[
        DepartureUpdateRequest, Body(default_factory=DepartureUpdateRequest)
    ],
    run_service: Annotated[
        SimulationRunService | None, Depends(get_optional_simulation_run_service)
    ] = None,
) -> FlightStatusResponse:
    """Force the flight into IN_FLIGHT phase with an optional departure timestamp."""
    if run_service and run_service.status().run:
        run = run_service.status().run
        run_service.assert_plan_edit_allowed(run.mission_id, run.leg_id)
    try:
        manager = get_flight_state_manager()
        triggered = manager.trigger_departure(update.timestamp, update.reason)
        if not triggered:
            raise HTTPException(
                status_code=400, detail="Flight already in-flight or beyond"
            )
        return _build_response()
    except HTTPException:
        raise
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        LookupError,
        ConnectionError,
        TimeoutError,
        ImportError,
        EOFError,
    ) as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/arrive",
    response_model=FlightStatusResponse,
    summary="Manually trigger arrival",
)
async def manual_arrival(
    update: Annotated[ArrivalUpdateRequest, Body(default_factory=ArrivalUpdateRequest)],
    run_service: Annotated[
        SimulationRunService | None, Depends(get_optional_simulation_run_service)
    ] = None,
) -> FlightStatusResponse:
    """Force the flight into POST_ARRIVAL phase with an optional arrival timestamp."""
    if run_service and run_service.status().run:
        run = run_service.status().run
        run_service.assert_plan_edit_allowed(run.mission_id, run.leg_id)
    try:
        manager = get_flight_state_manager()
        triggered = manager.trigger_arrival(update.timestamp, update.reason)
        if not triggered:
            raise HTTPException(status_code=400, detail="Flight already post-arrival")
        return _build_response()
    except HTTPException:
        raise
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        LookupError,
        ConnectionError,
        TimeoutError,
        ImportError,
        EOFError,
    ) as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("", response_model=FlightStatusResponse, summary="Reset flight status")
async def reset_flight_status(
    run_service: Annotated[
        SimulationRunService | None, Depends(get_optional_simulation_run_service)
    ] = None,
) -> FlightStatusResponse:
    """
    Reset flight status to PRE_DEPARTURE phase and clear timing metadata.
    """
    if run_service and run_service.status().run:
        run = run_service.status().run
        run_service.assert_plan_edit_allowed(run.mission_id, run.leg_id)
    try:
        manager = get_flight_state_manager()
        manager.reset()
        return _build_response()
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        LookupError,
        ConnectionError,
        TimeoutError,
        ImportError,
        EOFError,
    ) as exc:
        raise HTTPException(status_code=500, detail=str(exc))
