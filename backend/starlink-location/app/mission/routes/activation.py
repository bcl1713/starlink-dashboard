"""Mission activation and deactivation endpoints."""

# FR-004: File exceeds 300 lines (475 lines) because mission activation handles
# state transitions, timeline building, metric coordination, and flight status
# updates. Splitting would create coupling across state-dependent operations.
# Deferred to v0.4.0.

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends

from app.mission.models import MissionLeg, MissionPhase, MissionLegTimeline
from app.mission.storage import (
    load_mission,
    mission_exists,
    list_missions,
    save_mission,
    load_mission_timeline,
)
from app.services.flight_state_manager import get_flight_state_manager
from app.core.metrics import (
    update_mission_active_metric,
    clear_mission_metrics,
    update_mission_phase_metric,
)
from app.services.route_manager import RouteManager
from app.services.poi_manager import POIManager
from app.mission.dependencies import get_route_manager, get_poi_manager
from app.mission.timeline_service import TimelineComputationError
from .utils import (
    MissionActivationResponse,
    MissionDeactivationResponse,
    MissionErrorResponse,
    compute_and_store_timeline_for_mission,
    build_satellite_geojson,
)

logger = logging.getLogger(__name__)

# Create API router for mission activation operations
router = APIRouter(prefix="/api/missions", tags=["missions"])

# Global active mission ID (stored in memory; would be persisted in production)
_active_mission_id: Optional[str] = None


def get_active_mission_id() -> Optional[str]:
    """Return the currently active mission ID, if any.

    Returns:
        Active mission ID or None if no mission is active
    """
    return _active_mission_id


@router.post(
    "/{mission_id}/activate",
    response_model=MissionActivationResponse,
    responses={
        404: {
            "model": MissionErrorResponse,
            "description": "Mission not found",
        },
        409: {
            "model": MissionErrorResponse,
            "description": "Mission already active",
        },
    },
)
async def activate_mission(
    mission_id: str,
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> MissionActivationResponse:
    """Activate a mission (set as active and trigger timeline recomputation).

    Activation logic:
    - Sets mission as active (is_active=True)
    - Deactivates all other missions
    - Resets flight state to pre_departure
    - Returns activation confirmation

    Args:
        mission_id: Mission ID to activate
        route_manager: Route manager dependency
        poi_manager: POI manager dependency

    Returns:
        Activation response with timestamp and flight phase

    Raises:
        HTTPException: 404 if mission not found, 409 if already active
    """
    global _active_mission_id

    try:
        logger.info(
            "Activating mission",
        )

        # Check mission exists
        if not mission_exists(mission_id):
            logger.warning(
                "Mission not found for activation",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission {mission_id} not found",
            )

        # Load mission
        mission = load_mission(mission_id)

        # Check if already active
        if mission.is_active and _active_mission_id == mission_id:
            logger.warning(
                "Mission already active",
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Mission {mission_id} is already active",
            )

        # Deactivate all other missions
        all_missions = list_missions()
        for m_metadata in all_missions:
            m_id = m_metadata.get("id")
            if m_id and m_id != mission_id:
                try:
                    other_mission = load_mission(m_id)
                    if other_mission.is_active:
                        other_mission.is_active = False
                        other_mission.updated_at = datetime.now(timezone.utc)
                        save_mission(other_mission)
                        # Clear metrics for deactivated mission
                        clear_mission_metrics(m_id)
                        logger.debug(
                            "Deactivated mission",
                        )
                except Exception:  # pragma: no cover
                    logger.warning(
                        "Failed to deactivate mission",
                    )

        # Activate the target mission
        mission.is_active = True
        mission.updated_at = datetime.now(timezone.utc)
        save_mission(mission)
        _active_mission_id = mission_id

        # Ensure associated route is active
        if mission.route_id and route_manager:
            try:
                route_manager.activate_route(mission.route_id)
            except Exception:
                mission.is_active = False
                mission.updated_at = datetime.now(timezone.utc)
                save_mission(mission)
                _active_mission_id = None
                logger.error(
                    "Failed to activate route %s for mission %s",
                    mission.route_id,
                    mission_id,
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to activate route {mission.route_id} while activating mission",
                )

        try:
            compute_and_store_timeline_for_mission(
                mission,
                refresh_metrics=True,
                route_manager=route_manager,
                poi_manager=poi_manager,
            )
        except HTTPException:
            mission.is_active = False
            mission.updated_at = datetime.now(timezone.utc)
            save_mission(mission)
            _active_mission_id = None
            raise
        except TimelineComputationError as exc:
            mission.is_active = False
            mission.updated_at = datetime.now(timezone.utc)
            save_mission(mission)
            _active_mission_id = None
            logger.error(
                "Failed to compute mission timeline for %s", mission_id, exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to compute mission timeline: {type(exc).__name__}: {str(exc)}",
            ) from exc

        # Update metrics for activated mission
        update_mission_active_metric(mission_id, mission.route_id)
        update_mission_phase_metric(mission_id, MissionPhase.PRE_DEPARTURE.value)

        # Reset flight state to pre_departure
        try:
            flight_state = get_flight_state_manager()
            flight_state.reset_to_pre_departure(
                reason=f"mission_activated:{mission_id}"
            )
            logger.info(
                "Reset flight state to pre_departure",
            )
        except Exception:
            logger.warning(
                "Failed to reset flight state",
            )
            # Don't fail activation if flight state reset fails
            pass

        logger.info(
            "Mission activated successfully",
        )

        return MissionActivationResponse(
            mission_id=mission_id,
            is_active=True,
            activated_at=datetime.now(timezone.utc),
            flight_phase=MissionPhase.PRE_DEPARTURE.value,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to activate mission",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate mission: {type(e).__name__}: {str(e)}",
        )


@router.post(
    "/active/deactivate",
    response_model=MissionDeactivationResponse,
    responses={
        404: {
            "model": MissionErrorResponse,
            "description": "No active mission",
        }
    },
)
async def deactivate_mission(
    route_manager: RouteManager = Depends(get_route_manager),
) -> MissionDeactivationResponse:
    """Deactivate the currently active mission.

    Deactivation logic:
    - Gets the active mission (returns 404 if none)
    - Deactivates the associated route (if route_id exists)
    - Marks mission as inactive (is_active=False)
    - Clears mission metrics from Prometheus
    - Clears the active mission reference
    - Returns deactivation confirmation

    Args:
        route_manager: Route manager dependency

    Returns:
        Deactivation response with timestamp

    Raises:
        HTTPException: 404 if no mission is active
    """
    global _active_mission_id

    try:
        logger.info("Deactivating mission")

        # Get the active mission (this will raise HTTPException if not found)
        mission = await get_active_mission()

        # Deactivate the associated route if it's the active one
        if mission.route_id and route_manager:
            try:
                # Only deactivate if this mission's route is the currently active route
                if route_manager._active_route_id == mission.route_id:
                    route_manager.deactivate_route()
                    logger.info(
                        "Deactivated route %s associated with mission %s",
                        mission.route_id,
                        mission.id,
                    )
            except Exception as exc:
                logger.warning(
                    "Failed to deactivate route %s for mission %s: %s",
                    mission.route_id,
                    mission.id,
                    exc,
                )
                # Continue with mission deactivation even if route deactivation fails

        # Mark mission as inactive
        mission.is_active = False
        mission.updated_at = datetime.now(timezone.utc)
        save_mission(mission)

        # Clear mission metrics
        clear_mission_metrics(mission.id)

        # Clear active mission reference
        _active_mission_id = None

        logger.info("Mission deactivated successfully")

        return MissionDeactivationResponse(
            mission_id=mission.id,
            is_active=False,
            deactivated_at=datetime.now(timezone.utc),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to deactivate mission", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate mission: {type(e).__name__}: {str(e)}",
        )


async def get_active_mission() -> MissionLeg:
    """Get the currently active mission.

    Returns:
        Full active mission object

    Raises:
        HTTPException: 404 if no mission is active
    """
    global _active_mission_id

    try:
        logger.debug("Getting active mission")

        # If we have an in-memory active mission ID, use it
        if _active_mission_id:
            if mission_exists(_active_mission_id):
                mission = load_mission(_active_mission_id)
                if mission.is_active:
                    return mission
            else:
                # Stale reference, clear it
                _active_mission_id = None

        # Otherwise, search for any mission marked as active
        all_missions = list_missions()
        for m_metadata in all_missions:
            if m_metadata.get("is_active"):
                m_id = m_metadata.get("id")
                if m_id:
                    mission = load_mission(m_id)
                    _active_mission_id = m_id  # Update in-memory reference
                    return mission

        # No active mission found
        logger.debug("No active mission found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No mission is currently active",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get active mission",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active mission: {type(e).__name__}: {str(e)}",
        )


@router.get(
    "/active",
    response_model=MissionLeg,
    responses={
        404: {
            "model": dict,
            "description": "No active mission",
        }
    },
)
async def get_active_mission_endpoint() -> MissionLeg:
    """Get the currently active mission.

    Returns:
        Full active mission object

    Raises:
        HTTPException: 404 if no mission is active
    """
    return await get_active_mission()


@router.get(
    "/active/timeline",
    response_model=MissionLegTimeline,
    responses={
        404: {
            "model": dict,
            "description": "No active mission or timeline",
        }
    },
)
async def get_active_mission_timeline_endpoint() -> MissionLegTimeline:
    """Get the timeline for the currently active mission.

    Returns:
        Timeline for active mission

    Raises:
        HTTPException: 404 if no mission is active or timeline not found
    """
    mission = await get_active_mission()
    timeline = load_mission_timeline(mission.id)
    if not timeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timeline not found for active mission",
        )
    return timeline


@router.get(
    "/active/satellites",
    response_model=dict,
    responses={
        404: {
            "model": dict,
            "description": "No active mission",
        }
    },
)
async def get_active_mission_satellites_endpoint() -> dict:
    """Return satellite POIs for active mission in GeoJSON FeatureCollection format.

    Extracts satellite definitions from the active mission's transports and
    returns them as a GeoJSON FeatureCollection suitable for Grafana overlay
    visualization.

    Returns:
        GeoJSON FeatureCollection with satellite positions and metadata

    Raises:
        HTTPException: 404 if no mission is active
    """
    try:
        logger.debug("Getting active mission satellites for Grafana overlay")

        mission = await get_active_mission()
        geojson = build_satellite_geojson(mission)

        logger.debug(
            "Returning %d satellite features for mission %s",
            len(geojson["features"]),
            mission.id,
        )

        return geojson
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get active mission satellites",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active mission satellites: {type(e).__name__}: {str(e)}",
        )
