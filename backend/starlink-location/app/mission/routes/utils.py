"""Utility functions for mission route management."""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from pydantic import BaseModel, Field

from app.mission.models import MissionLeg, TransportState, MissionLegTimeline
from app.mission.timeline_service import (
    TimelineComputationError,
    TimelineSummary,
    build_mission_timeline,
)
from app.mission.storage import save_mission_timeline
from app.core.metrics import (
    update_mission_duration_metrics,
    update_mission_next_conflict_metric,
    update_mission_comm_state_metric,
    update_mission_timeline_timestamp,
)
from app.services.route_manager import RouteManager
from app.services.poi_manager import POIManager

logger = logging.getLogger(__name__)


class MissionListResponse(BaseModel):
    """Response for mission list endpoint."""

    total: int = Field(..., description="Total number of missions")
    limit: int = Field(..., description="Pagination limit")
    offset: int = Field(..., description="Pagination offset")
    missions: list[dict] = Field(..., description="List of mission metadata")


class MissionActivationResponse(BaseModel):
    """Response for mission activation endpoint."""

    mission_id: str = Field(..., description="Activated mission ID")
    is_active: bool = Field(..., description="Whether mission is now active")
    activated_at: datetime = Field(..., description="Activation timestamp")
    flight_phase: str = Field(
        ..., description="Flight phase after activation (pre_departure)"
    )


class MissionDeactivationResponse(BaseModel):
    """Response for mission deactivation endpoint."""

    mission_id: str = Field(..., description="Deactivated mission ID")
    is_active: bool = Field(..., description="Whether mission is now inactive")
    deactivated_at: datetime = Field(..., description="Deactivation timestamp")


class MissionErrorResponse(BaseModel):
    """Standard error response."""

    detail: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Error code")


def compute_and_store_timeline_for_mission(
    mission: MissionLeg,
    refresh_metrics: bool,
    route_manager: RouteManager,
    poi_manager: POIManager | None = None,
) -> tuple[MissionLegTimeline, TimelineSummary]:
    """Build, persist, and optionally publish metrics for a mission timeline.

    Args:
        mission: Mission to compute timeline for
        refresh_metrics: Whether to update Prometheus metrics
        route_manager: Route manager instance
        poi_manager: Optional POI manager instance

    Returns:
        Tuple of (timeline, summary)

    Raises:
        HTTPException: If route manager unavailable
    """
    if not route_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route manager unavailable for timeline computation",
        )

    timeline, summary = build_mission_timeline(
        mission,
        route_manager,
        poi_manager,
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


def refresh_timeline_after_save(
    mission: MissionLeg,
    route_manager: RouteManager,
    poi_manager: POIManager | None = None,
) -> None:
    """Attempt to compute a fresh timeline immediately after save operations.

    Args:
        mission: Mission to refresh timeline for
        route_manager: Route manager instance
        poi_manager: Optional POI manager instance
    """
    if not mission.route_id:
        return
    try:
        compute_and_store_timeline_for_mission(
            mission,
            refresh_metrics=False,
            route_manager=route_manager,
            poi_manager=poi_manager,
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
    """Convert TransportState to metric value.

    Args:
        state: Transport state enum

    Returns:
        Numeric metric value (0, 1, or 2)
    """
    mapping = {
        TransportState.AVAILABLE: 0,
        TransportState.DEGRADED: 1,
        TransportState.OFFLINE: 2,
    }
    return mapping.get(state, 0)


def build_satellite_geojson(mission: MissionLeg) -> dict:
    """Build GeoJSON FeatureCollection from mission satellites.

    Args:
        mission: Mission containing satellite definitions

    Returns:
        GeoJSON FeatureCollection with satellite features
    """
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

    return {
        "type": "FeatureCollection",
        "features": features,
    }
