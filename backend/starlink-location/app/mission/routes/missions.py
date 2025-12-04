"""Mission CRUD operations endpoints."""

# FR-004: File exceeds 300 lines (408 lines) because mission CRUD combines
# storage operations, timeline building, export handling, and state validation.
# Separation would create circular dependencies with exporter and storage modules.
# Deferred to v0.4.0.

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status, Depends

from app.mission.models import MissionLeg
from app.mission.storage import (
    delete_mission,
    list_missions,
    load_mission,
    mission_exists,
    save_mission,
)
from app.services.route_manager import RouteManager
from app.services.poi_manager import POIManager
from app.mission.dependencies import get_route_manager, get_poi_manager
from app.core.metrics import clear_mission_metrics
from .utils import (
    MissionListResponse,
    MissionErrorResponse,
    refresh_timeline_after_save,
)

logger = logging.getLogger(__name__)

# Create API router for mission CRUD operations
router = APIRouter(prefix="/api/missions", tags=["missions"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=MissionLeg,
    responses={
        422: {
            "model": MissionErrorResponse,
            "description": "Validation error",
        }
    },
)
async def create_mission(
    mission: MissionLeg,
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> MissionLeg:
    """Create a new mission.

    Args:
        mission: Mission object to create

    Returns:
        Created mission with 201 status

    Raises:
        HTTPException: 422 if mission validation fails
    """
    try:
        logger.info(
            "Creating mission",
        )

        # Ensure route exists
        if route_manager and not route_manager.get_route(mission.route_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Route {mission.route_id} not found",
            )

        # Ensure timestamps are set
        now = datetime.now(timezone.utc)
        if not mission.created_at or mission.created_at.tzinfo is None:
            mission.created_at = now
        if not mission.updated_at or mission.updated_at.tzinfo is None:
            mission.updated_at = now

        # Save mission to storage
        save_mission(mission)
        if route_manager:
            refresh_timeline_after_save(mission, route_manager, poi_manager)

        logger.info(
            "Mission created successfully",
        )

        return mission
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Mission creation failed with validation error",
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "Mission creation failed: %s",
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create mission: {type(e).__name__}: {str(e)}",
        )


@router.get(
    "",
    response_model=MissionListResponse,
)
async def list_missions_endpoint(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    route_id: Optional[str] = Query(None, description="Filter by route ID"),
) -> MissionListResponse:
    """List all missions with optional filtering.

    Args:
        limit: Maximum number of missions to return (1-100, default 10)
        offset: Number of missions to skip (default 0)
        route_id: Optional filter by route ID

    Returns:
        Paginated list of mission metadata
    """
    try:
        logger.debug(
            "Listing missions",
        )

        # Get all missions from storage
        all_missions = list_missions()

        # Filter by route_id if provided
        if route_id:
            missions = [m for m in all_missions if m.get("route_id") == route_id]
        else:
            missions = all_missions

        # Apply pagination
        total = len(missions)
        paginated = missions[offset : offset + limit]

        return MissionListResponse(
            total=total,
            limit=limit,
            offset=offset,
            missions=paginated,
        )
    except Exception as e:
        logger.error(
            "Failed to list missions",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list missions: {type(e).__name__}: {str(e)}",
        )


@router.get(
    "/{mission_id}",
    response_model=MissionLeg,
    responses={
        404: {
            "model": MissionErrorResponse,
            "description": "Mission not found",
        }
    },
)
async def get_mission(mission_id: str) -> MissionLeg:
    """Get a specific mission by ID.

    Args:
        mission_id: Mission ID to retrieve

    Returns:
        Full mission object

    Raises:
        HTTPException: 404 if mission not found
    """
    try:
        logger.debug("Getting mission")

        if not mission_exists(mission_id):
            logger.warning(
                "Mission not found",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission {mission_id} not found",
            )

        mission = load_mission(mission_id)
        return mission
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get mission",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mission: {type(e).__name__}: {str(e)}",
        )


@router.put(
    "/{mission_id}",
    response_model=MissionLeg,
    responses={
        404: {
            "model": MissionErrorResponse,
            "description": "Mission not found",
        },
        422: {
            "model": MissionErrorResponse,
            "description": "Validation error",
        },
    },
)
async def update_mission(
    mission_id: str,
    mission_update: MissionLeg,
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> MissionLeg:
    """Update an existing mission (merge logic).

    Args:
        mission_id: Mission ID to update
        mission_update: Updated mission object

    Returns:
        Updated mission

    Raises:
        HTTPException: 404 if mission not found, 422 if validation fails
    """
    try:
        logger.info(
            "Updating mission",
        )

        if not mission_exists(mission_id):
            logger.warning(
                "Mission not found for update",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission {mission_id} not found",
            )

        # Load existing mission
        existing_mission = load_mission(mission_id)

        # Ensure route exists
        if route_manager and not route_manager.get_route(mission_update.route_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Route {mission_update.route_id} not found",
            )

        # Merge: preserve original created_at, update updated_at
        merged = MissionLeg(
            id=mission_id,
            name=mission_update.name,
            description=mission_update.description,
            route_id=mission_update.route_id,
            transports=mission_update.transports,
            created_at=existing_mission.created_at,
            updated_at=datetime.now(timezone.utc),
            is_active=existing_mission.is_active,  # Don't change via PUT
            notes=mission_update.notes,
        )

        # Save merged mission
        save_mission(merged)
        if route_manager:
            refresh_timeline_after_save(merged, route_manager, poi_manager)

        logger.info(
            "Mission updated successfully",
        )

        return merged
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Mission update failed with validation error",
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "Failed to update mission",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update mission: {type(e).__name__}: {str(e)}",
        )


@router.delete(
    "/{mission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {
            "model": MissionErrorResponse,
            "description": "Mission not found",
        }
    },
)
async def delete_mission_endpoint(
    mission_id: str,
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> None:
    """Delete a mission by ID.

    Args:
        mission_id: Mission ID to delete
        route_manager: Route manager dependency
        poi_manager: POI manager dependency

    Raises:
        HTTPException: 404 if mission not found
    """
    try:
        logger.info(
            "Deleting mission",
        )

        if not mission_exists(mission_id):
            logger.warning(
                "Mission not found for deletion",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission {mission_id} not found",
            )

        # Load mission to get route_id before deletion
        mission = load_mission(mission_id)

        # Deactivate associated route if it's the active one
        if mission.route_id and route_manager:
            try:
                # Only deactivate if this mission's route is the currently active route
                if route_manager._active_route_id == mission.route_id:
                    route_manager.deactivate_route()
                    logger.info(
                        "Deactivated route %s associated with mission %s",
                        mission.route_id,
                        mission_id,
                    )
            except Exception as exc:
                logger.warning(
                    "Failed to deactivate route %s for mission %s: %s",
                    mission.route_id,
                    mission_id,
                    exc,
                )
                # Continue with mission deletion even if route deactivation fails

        # Remove related mission POIs
        if poi_manager:
            try:
                removed = poi_manager.delete_mission_pois(mission_id)
                if removed:
                    logger.info(
                        "Deleted %d mission-scoped POIs for %s", removed, mission_id
                    )
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "Failed to delete mission POIs for %s: %s", mission_id, exc
                )

        # Remove from storage
        delete_mission(mission_id)

        # Clear mission metrics
        clear_mission_metrics(mission_id)

        logger.info(
            "Mission deleted successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to delete mission",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete mission: {type(e).__name__}: {str(e)}",
        )
