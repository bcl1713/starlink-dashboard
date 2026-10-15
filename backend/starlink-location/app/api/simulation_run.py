"""Read-only replay status, effective route, and semantic planning endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from app.mission.dependencies import get_simulation_run_service
from app.models.route import RouteDetailResponse
from app.models.simulation_run import (
    PacingInput,
    SimulationPreview,
    SimulationRunStatus,
)
from app.simulation.run_service import SimulationRunService

router = APIRouter()
Service = Annotated[SimulationRunService, Depends(get_simulation_run_service)]


@router.post(
    "/api/v2/missions/{mission_id}/legs/{leg_id}/simulation/preview",
    response_model=SimulationPreview,
)
def preview(
    mission_id: str,
    leg_id: str,
    pacing: PacingInput,
    response: Response,
    service: Service,
):
    response.headers["Cache-Control"] = "no-store"
    return service.preview(mission_id, leg_id, pacing)


@router.get("/api/simulation/run", response_model=SimulationRunStatus)
def get_status(response: Response, service: Service):
    response.headers["Cache-Control"] = "no-store"
    return service.status()


@router.get("/api/simulation/run/{run_id}/route")
def get_route(run_id: str, response: Response, service: Service):
    from app.mission.storage import get_active_leg_lock

    with get_active_leg_lock():
        status = service.status()
        plan = service.runtime.selected_plan()
        if plan is None or status.run.run_id != run_id:
            raise HTTPException(404, "Run geometry unavailable")
        route = plan.artifacts.route
        response.headers["Cache-Control"] = "no-store"
        distance = route.get_total_distance()
        detail = RouteDetailResponse(
            id=plan.route_id,
            name=route.metadata.name,
            description=route.metadata.description,
            point_count=len(route.points),
            is_active=True,
            imported_at=route.metadata.imported_at,
            file_path=route.metadata.file_path,
            points=route.points,
            waypoints=route.waypoints,
            timing_profile=route.timing_profile,
            has_timing_data=True,
            flight_phase=status.run.phase,
            eta_mode="estimated",
            poi_count=service.poi_manager.count_pois(route_id=plan.route_id),
            statistics={
                "distance_meters": distance,
                "distance_km": distance / 1000,
                "bounds": route.get_bounds(),
            },
        )
        return {"runtime_id": status.runtime_id, "run_id": run_id, "route": detail}
