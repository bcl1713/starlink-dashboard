"""Active X-band satellite link overlay endpoint."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request

from app.mission.dependencies import get_poi_manager, get_route_manager
from app.services.active_x_link import build_active_x_link
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager

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
    state: Literal["normal", "warning"] | None = Query(
        None,
        description="Optional state filter for split Grafana route layers",
    ),
    coordinator: Any = Depends(get_coordinator),
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> dict[str, Any]:
    """Return two route points for the current aircraft-to-active-X satellite link."""
    return build_active_x_link(
        coordinator=coordinator,
        route_manager=route_manager,
        poi_manager=poi_manager,
        state_filter=state,
    )
