"""Active X-band satellite link overlay endpoint."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from filelock import Timeout
from pydantic import BaseModel, ConfigDict, StrictStr, field_validator

from app.mission.dependencies import (
    get_optional_simulation_run_service,
    get_poi_manager,
    get_route_manager,
)
from app.mission.storage import get_active_leg_lock
from app.services.active_x_link import build_active_x_link, find_active_mission_leg
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from app.services.x_band_selection import XBandSelectionStore
from app.simulation.run_service import SimulationRunService
from app.simulation.run_timing import published_replay

router = APIRouter(prefix="/api", tags=["active-x-link"])


def get_coordinator(request: Request) -> Any:
    """Get telemetry coordinator from app state."""
    return getattr(request.app.state, "coordinator", None)


def get_selection_store(request: Request) -> XBandSelectionStore | None:
    return getattr(request.app.state, "x_band_selection_store", None)


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
    selection_store: Annotated[
        XBandSelectionStore | None, Depends(get_selection_store)
    ] = None,
) -> dict[str, Any]:
    """Return two route points for the current aircraft-to-active-X satellite link."""
    try:
        with get_active_leg_lock():
            selection = published_replay(run_service)
            manual_unavailable = False
            try:
                manual_id = selection_store.get() if selection_store else None
            except (OSError, ValueError, TypeError, Timeout):
                if find_active_mission_leg() is None:
                    raise
                # Dormant manual settings must not hide a healthy mission link.
                manual_id = None
                manual_unavailable = True
            response = build_active_x_link(
                coordinator=coordinator,
                route_manager=route_manager,
                poi_manager=poi_manager,
                state_filter=state,
                manual_satellite_id=manual_id,
                **({"paced_context": selection[1].x_context} if selection else {}),
            )
            if manual_unavailable:
                response["manual_selection_unavailable"] = True
            return response
    except (OSError, ValueError, TypeError, Timeout) as error:
        raise HTTPException(503, "Satellite selection could not be read") from error


class ManualXSelectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    satellite_id: StrictStr | None

    @field_validator("satellite_id")
    @classmethod
    def nonempty_id(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Select a configured X-band satellite or None")
        return value


@router.put("/active-x-link/selection", response_model=dict)
def update_manual_x_selection(
    settings: ManualXSelectionUpdate,
    selection_store: Annotated[
        XBandSelectionStore | None, Depends(get_selection_store)
    ],
    coordinator: Annotated[Any, Depends(get_coordinator)],
    route_manager: Annotated[RouteManager, Depends(get_route_manager)],
    poi_manager: Annotated[POIManager, Depends(get_poi_manager)],
) -> dict[str, Any]:
    """Save planning selection only; an active mission remains authoritative."""
    if selection_store is None or poi_manager is None:
        raise HTTPException(503, "Satellite selection is not initialized")
    try:
        with get_active_leg_lock():
            if find_active_mission_leg() is not None:
                raise HTTPException(
                    409, "An active mission controls satellite selection"
                )
            satellite_id = settings.satellite_id
            if satellite_id is not None and not any(
                poi.category == "satellite"
                and poi.name == satellite_id
                and (poi.icon or "X") == "X"
                for poi in poi_manager.list_pois()
            ):
                raise HTTPException(422, "Select a configured X-band satellite")
            # Validate response construction before the durable commit point.
            response = build_active_x_link(
                coordinator,
                route_manager,
                poi_manager,
                manual_satellite_id=satellite_id,
            )
            selection_store.update(satellite_id)
            return response
    except (OSError, ValueError, TypeError, Timeout) as error:
        raise HTTPException(503, "Satellite selection could not be saved") from error
