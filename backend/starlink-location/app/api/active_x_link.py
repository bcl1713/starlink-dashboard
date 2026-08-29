"""Active X-band satellite link overlay endpoint."""

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request

from app.mission.dependencies import get_poi_manager, get_route_manager
from app.models.monitoring import ActiveXLinkResponse
from app.services.active_x_link import build_active_x_link
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager

router = APIRouter(prefix="/api", tags=["active-x-link"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_coordinator(request: Request) -> Any:
    """Get telemetry coordinator from app state."""
    return getattr(request.app.state, "coordinator", None)


@router.get(
    "/active-x-link",
    response_model=ActiveXLinkResponse,
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
) -> ActiveXLinkResponse:
    """Return two route points for the current aircraft-to-active-X satellite link."""
    telemetry = None
    try:
        telemetry = coordinator.get_current_telemetry() if coordinator else None
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
    ):
        telemetry = None
    observed_at = telemetry.timestamp if telemetry is not None else None
    generated_at = _utc_now()
    payload = build_active_x_link(
        coordinator=coordinator,
        route_manager=route_manager,
        poi_manager=poi_manager,
        state_filter=state,
    )
    for coordinate in payload["coordinates"]:
        coordinate["observed_at"] = observed_at
    for link in payload["links"]:
        for coordinate in link["coordinates"]:
            coordinate["observed_at"] = observed_at
    return ActiveXLinkResponse(
        **payload,
        observed_at=observed_at,
        generated_at=generated_at,
    )
