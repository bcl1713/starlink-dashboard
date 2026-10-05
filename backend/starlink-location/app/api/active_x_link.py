"""Active X-band satellite link overlay endpoint."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request

from app.mission.dependencies import (
    get_optional_simulation_run_service,
    get_poi_manager,
    get_route_manager,
)
from app.services.active_x_link import build_active_x_link
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from app.simulation.run_service import SimulationRunService
from app.simulation.run_timing import published_replay

router = APIRouter(prefix="/api", tags=["active-x-link"])


def get_coordinator(request: Request) -> Any:
    """Get telemetry coordinator from app state."""
    return getattr(request.app.state, "coordinator", None)


@router.get(
    "/active-x-link",
    response_model=dict,
    summary="Get active X-band aircraft-to-satellite link coordinates",
)
async def get_active_x_link(
    state: Annotated[
        Literal["normal", "warning"] | None,
        Query(
            description="Optional state filter for split Grafana route layers",
        ),
    ] = None,
    coordinator: Annotated[Any, Depends(get_coordinator)] = None,
    route_manager: Annotated[RouteManager, Depends(get_route_manager)] = None,
    poi_manager: Annotated[POIManager, Depends(get_poi_manager)] = None,
    run_service: Annotated[
        SimulationRunService | None, Depends(get_optional_simulation_run_service)
    ] = None,
) -> dict[str, Any]:
    """Return two route points for the current aircraft-to-active-X satellite link."""
    selection = published_replay(run_service)
    return build_active_x_link(
        coordinator=coordinator,
        route_manager=route_manager,
        poi_manager=poi_manager,
        state_filter=state,
        **({"paced_context": selection[1].x_context} if selection else {}),
    )
