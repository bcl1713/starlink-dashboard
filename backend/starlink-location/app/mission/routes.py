"""Mission planning API endpoints for CRUD operations and lifecycle management."""

import io
import logging
import sys
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.mission.models import Mission, MissionPhase, MissionTimeline, TransportState
from app.mission.storage import (
    delete_mission,
    list_missions,
    load_mission,
    mission_exists,
    save_mission,
)
from app.mission.storage import load_mission_timeline, save_mission_timeline
from app.mission.timeline_service import (
    TimelineComputationError,
    TimelineSummary,
    build_mission_timeline,
)
from app.mission.exporter import (
    ExportGenerationError,
    TimelineExportFormat,
    generate_timeline_export,
)
from app.services.flight_state_manager import get_flight_state_manager
from app.core.metrics import (
    update_mission_active_metric,
    clear_mission_metrics,
    update_mission_phase_metric,
    update_mission_timeline_timestamp,
    update_mission_comm_state_metric,
    update_mission_duration_metrics,
    update_mission_next_conflict_metric,
)
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/api/missions", tags=["missions"])

# Global active mission ID (stored in memory; would be persisted in production)
_active_mission_id: Optional[str] = None
_poi_manager: Optional[POIManager] = None
_route_manager: Optional[RouteManager] = None


def set_poi_manager(poi_manager: POIManager) -> None:
    """Inject POI manager for mission-scoped POI cleanup."""
    global _poi_manager
    _poi_manager = poi_manager


def set_route_manager(route_manager: RouteManager) -> None:
    """Inject RouteManager so mission activation can ensure matching route activation."""
    global _route_manager
    _route_manager = route_manager


def _compute_and_store_timeline_for_mission(
    mission: Mission,
    refresh_metrics: bool,
) -> tuple[MissionTimeline, TimelineSummary]:
    """Build, persist, and optionally publish metrics for a mission timeline."""
    if not _route_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route manager unavailable for timeline computation",
        )

    timeline, summary = build_mission_timeline(
        mission,
        _route_manager,
        _poi_manager,
    )
    save_mission_timeline(mission.id, timeline)
    generated_ts = datetime.now(timezone.utc).timestamp()
    update_mission_timeline_timestamp(mission.id, generated_ts)

    if refresh_metrics:
        update_mission_duration_metrics(
            mission.id,
            summary.degraded_seconds,
            summary.critical_seconds,
        )
        update_mission_next_conflict_metric(
            mission.id,
            summary.next_conflict_seconds,
        )
        for transport, state in summary.transport_states.items():
            update_mission_comm_state_metric(
                mission.id,
                transport.value,
                _state_to_metric_value(state),
            )

    return timeline, summary


def _refresh_timeline_after_save(mission: Mission) -> None:
    """Attempt to compute a fresh timeline immediately after save operations."""
    if not mission.route_id:
        return
    try:
        _compute_and_store_timeline_for_mission(
            mission,
            refresh_metrics=False,
        )
    except HTTPException as exc:
        logger.warning(
            "Skipped timeline recompute for %s (route manager unavailable): %s",
            mission.id,
            exc.detail,
        )
    except TimelineComputationError as exc:
        logger.warning(
            "Timeline computation failed for %s during save: %s",
            mission.id,
            exc,
        )


def _state_to_metric_value(state: TransportState) -> int:
    mapping = {
        TransportState.AVAILABLE: 0,
        TransportState.DEGRADED: 1,
        TransportState.OFFLINE: 2,
    }
    return mapping.get(state, 0)


class MissionListResponse(BaseModel):
    """Response for mission list endpoint."""

    total: int = Field(..., description="Total number of missions")
    limit: int = Field(..., description="Pagination limit")
    offset: int = Field(..., description="Pagination offset")
    missions: list[dict] = Field(
        ..., description="List of mission metadata"
    )


class MissionActivationResponse(BaseModel):
    """Response for mission activation endpoint."""

    mission_id: str = Field(..., description="Activated mission ID")
    is_active: bool = Field(..., description="Whether mission is now active")
    activated_at: datetime = Field(..., description="Activation timestamp")
    flight_phase: str = Field(
        ..., description="Flight phase after activation (pre_departure)"
    )


class MissionErrorResponse(BaseModel):
    """Standard error response."""

    detail: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Error code")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=Mission,
    responses={
        422: {
            "model": MissionErrorResponse,
            "description": "Validation error",
        }
    },
)
async def create_mission(mission: Mission) -> Mission:
    """
    Create a new mission.

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

        # Ensure timestamps are set
        now = datetime.now(timezone.utc)
        if not mission.created_at or mission.created_at.tzinfo is None:
            mission.created_at = now
        if not mission.updated_at or mission.updated_at.tzinfo is None:
            mission.updated_at = now

        # Save mission to storage
        save_mission(mission)
        _refresh_timeline_after_save(mission)

        logger.info(
            "Mission created successfully",
        )

        return mission
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
            "Mission creation failed",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create mission",
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
    """
    List all missions with optional filtering.

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
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list missions",
        )


@router.get(
    "/active",
    response_model=Mission,
    responses={
        404: {
            "model": MissionErrorResponse,
            "description": "No active mission",
        }
    },
)
async def get_active_mission() -> Mission:
    """
    Get the currently active mission.

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
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get active mission",
        )


@router.get(
    "/active/timeline",
    response_model=MissionTimeline,
    responses={
        404: {
            "model": MissionErrorResponse,
            "description": "No active mission or timeline",
        }
    },
)
async def get_active_mission_timeline() -> MissionTimeline:
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
            "model": MissionErrorResponse,
            "description": "No active mission",
        }
    },
)
async def get_active_mission_satellites() -> dict:
    """
    Return satellite POIs for active mission in GeoJSON FeatureCollection format.

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

        # Build GeoJSON FeatureCollection with satellite points
        features = []

        # Add X satellite if configured
        if mission.transports.initial_x_satellite_id:
            x_sat_id = mission.transports.initial_x_satellite_id
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [0, 0],  # Geostationary; fixed position
                    },
                    "properties": {
                        "name": x_sat_id,
                        "satellite_id": x_sat_id,
                        "transport": "X",
                        "type": "satellite",
                    },
                }
            )

        # Add Ka satellites if configured
        for ka_sat_id in mission.transports.initial_ka_satellite_ids:
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [0, 0],  # Geostationary; fixed position
                    },
                    "properties": {
                        "name": ka_sat_id,
                        "satellite_id": ka_sat_id,
                        "transport": "Ka",
                        "type": "satellite",
                    },
                }
            )

        # Note: Ku is a constellation, not fixed satellites; may add later
        # For now, represent as a nominal marker
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [0, 0],  # Placeholder for LEO constellation
                },
                "properties": {
                    "name": "Ku-Constellation",
                    "satellite_id": "Ku-LEO",
                    "transport": "Ku",
                    "type": "constellation",
                },
            }
        )

        geojson = {
            "type": "FeatureCollection",
            "features": features,
        }

        logger.debug(
            "Returning %d satellite features for mission %s",
            len(features),
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
            detail="Failed to get active mission satellites",
        )


@router.get(
    "/{mission_id}",
    response_model=Mission,
    responses={
        404: {
            "model": MissionErrorResponse,
            "description": "Mission not found",
        }
    },
)
async def get_mission(mission_id: str) -> Mission:
    """
    Get a specific mission by ID.

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
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get mission",
        )


@router.get(
    "/{mission_id}/timeline",
    response_model=MissionTimeline,
    responses={
        404: {
            "model": MissionErrorResponse,
            "description": "Timeline not found",
        }
    },
)
async def get_mission_timeline_endpoint(mission_id: str) -> MissionTimeline:
    if not mission_exists(mission_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission {mission_id} not found",
        )

    timeline = load_mission_timeline(mission_id)
    if not timeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timeline not found",
        )

    return timeline


@router.post(
    "/{mission_id}/timeline/recompute",
    response_model=MissionTimeline,
    responses={
        404: {
            "model": MissionErrorResponse,
            "description": "Mission or timeline prerequisites missing",
        }
    },
)
async def recompute_mission_timeline_endpoint(
    mission_id: str,
) -> MissionTimeline:
    """Force a fresh mission timeline computation without altering activation."""
    mission = load_mission(mission_id)
    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission {mission_id} not found",
        )

    try:
        timeline, _summary = _compute_and_store_timeline_for_mission(
            mission,
            refresh_metrics=mission.is_active,
        )
    except TimelineComputationError as exc:
        logger.error(
            "Failed to recompute timeline for %s", mission_id, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute mission timeline",
        ) from exc

    return timeline


@router.post(
    "/{mission_id}/export",
    responses={
        200: {
            "content": {
                "text/csv": {},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {},
                "application/pdf": {},
            },
            "description": "Mission timeline export",
        },
        404: {
            "model": MissionErrorResponse,
            "description": "Mission or timeline not found",
        },
        400: {
            "model": MissionErrorResponse,
            "description": "Unsupported export format",
        },
    },
)
async def export_mission_timeline_endpoint(
    mission_id: str,
    format: str = Query("csv", description="Export format: csv, xlsx, or pdf"),
) -> StreamingResponse:
    """Generate a downloadable mission timeline export."""
    mission = load_mission(mission_id)
    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission {mission_id} not found",
        )

    timeline = load_mission_timeline(mission_id)
    if not timeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timeline not found",
        )

    try:
        export_format = TimelineExportFormat.from_string(format)
        artifact = generate_timeline_export(export_format, mission, timeline)
    except ExportGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    filename = f"{mission_id}-timeline.{artifact.extension}"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    return StreamingResponse(
        io.BytesIO(artifact.content),
        media_type=artifact.media_type,
        headers=headers,
    )


@router.put(
    "/{mission_id}",
    response_model=Mission,
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
    mission_update: Mission,
) -> Mission:
    """
    Update an existing mission (merge logic).

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

        # Merge: preserve original created_at, update updated_at
        merged = Mission(
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
        _refresh_timeline_after_save(merged)

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
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update mission",
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
async def delete_mission_endpoint(mission_id: str) -> None:
    """
    Delete a mission by ID.

    Args:
        mission_id: Mission ID to delete

    Raises:
        HTTPException: 404 if mission not found
    """
    global _active_mission_id

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

        # Remove related mission POIs
        if _poi_manager:
            try:
                removed = _poi_manager.delete_mission_pois(mission_id)
                if removed:
                    logger.info("Deleted %d mission-scoped POIs for %s", removed, mission_id)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to delete mission POIs for %s: %s", mission_id, exc)

        # Remove from storage
        delete_mission(mission_id)

        # Clear mission metrics
        clear_mission_metrics(mission_id)

        # If this was the active mission, clear it
        if _active_mission_id == mission_id:
            _active_mission_id = None
            logger.info(
                "Cleared active mission (was deleted)",
            )

        logger.info(
            "Mission deleted successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to delete mission",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete mission",
        )


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
async def activate_mission(mission_id: str) -> MissionActivationResponse:
    """
    Activate a mission (set as active and trigger timeline recomputation).

    Activation logic:
    - Sets mission as active (is_active=True)
    - Deactivates all other missions
    - Resets flight state to pre_departure
    - Returns activation confirmation

    Args:
        mission_id: Mission ID to activate

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
                except Exception as e:  # pragma: no cover
                    logger.warning(
                        "Failed to deactivate mission",
                    )

        # Activate the target mission
        mission.is_active = True
        mission.updated_at = datetime.now(timezone.utc)
        save_mission(mission)
        _active_mission_id = mission_id

        # Ensure associated route is active
        if mission.route_id and _route_manager:
            try:
                _route_manager.activate_route(mission.route_id)
            except Exception as exc:
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
            _compute_and_store_timeline_for_mission(
                mission,
                refresh_metrics=True,
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
                detail="Failed to compute mission timeline",
            ) from exc

        # Update metrics for activated mission
        update_mission_active_metric(mission_id, mission.route_id)
        update_mission_phase_metric(mission_id, MissionPhase.PRE_DEPARTURE.value)

        # Reset flight state to pre_departure
        try:
            flight_state = get_flight_state_manager()
            flight_state.reset_to_pre_departure(reason=f"mission_activated:{mission_id}")
            logger.info(
                "Reset flight state to pre_departure",
            )
        except Exception as e:
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
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate mission",
        )
def get_active_mission_id() -> Optional[str]:
    """Return the currently active mission ID, if any."""
    return _active_mission_id
