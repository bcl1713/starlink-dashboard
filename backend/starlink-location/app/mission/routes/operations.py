"""Mission timeline and export operations endpoints."""

import io
import logging

from fastapi import APIRouter, HTTPException, Query, status, Depends, Request
from fastapi.responses import StreamingResponse
from app.core.limiter import limiter

from app.mission.models import MissionLegTimeline
from app.mission.storage import (
    load_mission,
    mission_exists,
    load_mission_timeline,
)
from app.mission.exporter import (
    ExportGenerationError,
    TimelineExportFormat,
    generate_timeline_export,
)
from app.services.route_manager import RouteManager
from app.services.poi_manager import POIManager
from app.mission.dependencies import get_route_manager, get_poi_manager
from app.mission.timeline_service import TimelineComputationError
from .utils import (
    MissionErrorResponse,
    compute_and_store_timeline_for_mission,
)

logger = logging.getLogger(__name__)

# Create API router for mission operations
router = APIRouter(prefix="/api/missions", tags=["missions"])


@router.get(
    "/{mission_id}/timeline",
    response_model=MissionLegTimeline,
    responses={
        404: {
            "model": MissionErrorResponse,
            "description": "Timeline not found",
        }
    },
)
async def get_mission_timeline_endpoint(mission_id: str) -> MissionLegTimeline:
    """Get the computed timeline for a mission.

    Args:
        mission_id: Mission ID to get timeline for

    Returns:
        Mission timeline object

    Raises:
        HTTPException: 404 if mission or timeline not found
    """
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
    response_model=MissionLegTimeline,
    responses={
        404: {
            "model": MissionErrorResponse,
            "description": "Mission or timeline prerequisites missing",
        }
    },
)
async def recompute_mission_timeline_endpoint(
    mission_id: str,
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> MissionLegTimeline:
    """Force a fresh mission timeline computation without altering activation.

    Args:
        mission_id: Mission ID to recompute timeline for
        route_manager: Route manager dependency
        poi_manager: POI manager dependency

    Returns:
        Recomputed timeline

    Raises:
        HTTPException: 404 if mission not found, 500 on computation error
    """
    mission = load_mission(mission_id)
    if not mission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mission {mission_id} not found",
        )

    try:
        timeline, _summary = compute_and_store_timeline_for_mission(
            mission,
            refresh_metrics=mission.is_active,
            route_manager=route_manager,
            poi_manager=poi_manager,
        )
    except TimelineComputationError as exc:
        logger.error("Failed to recompute timeline for %s", mission_id, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute mission timeline: {type(exc).__name__}: {str(exc)}",
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
@limiter.limit("10/minute")
async def export_mission_timeline_endpoint(
    request: Request,
    mission_id: str,
    format: str = Query("csv", description="Export format: csv, xlsx, or pdf"),
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> StreamingResponse:
    """Generate a downloadable mission timeline export.

    Args:
        request: FastAPI request object
        mission_id: Mission ID to export
        format: Export format (csv, xlsx, or pdf)
        route_manager: Route manager dependency
        poi_manager: POI manager dependency

    Returns:
        StreamingResponse with exported file

    Raises:
        HTTPException: 404 if mission not found, 400 if format unsupported
    """
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
        artifact = generate_timeline_export(
            export_format,
            mission,
            timeline,
            route_manager=route_manager,
            poi_manager=poi_manager,
        )
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
