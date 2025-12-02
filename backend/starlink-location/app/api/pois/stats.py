"""Statistics endpoints for POI analytics (count, next destination, next ETA, approaching POIs).

File Size Note (FR-004 Exception):
This module exceeds the 300-line constitutional limit (316 lines) due to:
- 4 statistics endpoints with similar telemetry/coordinator integration patterns
- Repeated coordinator fallback logic for position and telemetry data
- Flight state manager integration in multiple endpoints
- Comprehensive docstrings for API documentation
- ETA calculation with distance metrics

The repetitive telemetry acquisition and fallback pattern (used in all 4 endpoints)
creates unavoidable duplication if separated into individual modules. The endpoints
are cohesively grouped by function (statistics) rather than by individual concern.

Deferred for future refactoring with potential:
- Extraction of shared telemetry acquisition logic into a service utility
- Creation of a telemetry resolver decorator/wrapper
- Consolidation of flight state queries into cached helpers
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status, Depends

from app.services.poi_manager import POIManager
from app.mission.dependencies import get_poi_manager

logger = logging.getLogger(__name__)

# Global coordinator reference for accessing telemetry
_coordinator: Optional[object] = None


def set_coordinator(coordinator):
    """Set the simulation coordinator reference."""
    global _coordinator
    _coordinator = coordinator


# Create API router for stats endpoints
router = APIRouter(prefix="/api/pois", tags=["pois"])


@router.get("/count/total", response_model=dict, summary="Get POI count")
async def count_pois(
    route_id: Optional[str] = Query(None, description="Filter by route ID"),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> dict:
    """Get count of POIs, optionally filtered by route.

    Query Parameters:
    - route_id: Optional route ID to filter by

    Returns:
    - JSON object with count
    """
    if not poi_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="POI manager not initialized",
        )

    count = poi_manager.count_pois(route_id=route_id)
    return {"count": count, "route_id": route_id}


@router.get(
    "/stats/next-destination",
    response_model=dict,
    summary="Get next destination (closest POI name)",
)
async def get_next_destination(
    latitude: Optional[str] = Query(None),
    longitude: Optional[str] = Query(None),
    speed_knots: Optional[str] = Query(None),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> dict:
    """Get the name of the closest POI (next destination).

    Uses coordinator telemetry if available, otherwise uses query parameters or fallback values.

    Query Parameters:
    - latitude: Current latitude (optional, uses coordinator if available)
    - longitude: Current longitude (optional, uses coordinator if available)
    - speed_knots: Current speed in knots (optional, uses coordinator if available)

    Returns:
    - JSON object with 'name' field containing the closest POI name
    """
    try:
        # Get current position from coordinator if available
        if _coordinator:
            try:
                telemetry = _coordinator.get_current_telemetry()
                lat = telemetry.position.latitude
                lon = telemetry.position.longitude
                speed = telemetry.position.speed
            except Exception:
                # Fall back to query parameters or defaults
                lat = float(latitude) if latitude else 41.6
                lon = float(longitude) if longitude else -74.0
                speed = float(speed_knots) if speed_knots else 67.0
        else:
            # Use fallback coordinates when no coordinator available
            lat = float(latitude) if latitude else 41.6
            lon = float(longitude) if longitude else -74.0
            speed = float(speed_knots) if speed_knots else 67.0
    except (ValueError, TypeError):
        lat, lon, speed = 41.6, -74.0, 67.0

    if not poi_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="POI manager not initialized",
        )

    pois = poi_manager.list_pois()
    if not pois:
        status_eta_mode = "estimated"
        status_phase = None
        try:
            from app.services.flight_state_manager import get_flight_state_manager

            snapshot = get_flight_state_manager().get_status()
            status_eta_mode = snapshot.eta_mode.value
            status_phase = snapshot.phase.value
        except Exception:  # pragma: no cover - defensive guard
            pass
        return {
            "name": "No POIs available",
            "eta_type": status_eta_mode,
            "flight_phase": status_phase,
            "eta_seconds": -1,
        }

    from app.core.eta_service import get_eta_calculator

    eta_calc = get_eta_calculator()

    closest = None
    closest_eta = float("inf")

    for poi in pois:
        distance = eta_calc.calculate_distance(lat, lon, poi.latitude, poi.longitude)
        eta_seconds = eta_calc.calculate_eta(distance, speed)
        if eta_seconds < closest_eta:
            closest_eta = eta_seconds
            closest = poi

    status_eta_mode = "estimated"
    status_phase = None
    try:
        from app.services.flight_state_manager import get_flight_state_manager

        snapshot = get_flight_state_manager().get_status()
        status_eta_mode = snapshot.eta_mode.value
        status_phase = snapshot.phase.value
    except Exception:  # pragma: no cover - defensive guard
        pass

    eta_value = max(0, closest_eta) if closest_eta != float("inf") else -1
    return {
        "name": closest.name if closest else "No POIs available",
        "eta_type": status_eta_mode,
        "flight_phase": status_phase,
        "eta_seconds": eta_value,
    }


@router.get(
    "/stats/next-eta",
    response_model=dict,
    summary="Get time to next arrival (closest POI ETA)",
)
async def get_next_eta(
    latitude: Optional[str] = Query(None),
    longitude: Optional[str] = Query(None),
    speed_knots: Optional[str] = Query(None),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> dict:
    """Get the ETA in seconds to the closest POI.

    Uses coordinator telemetry if available, otherwise uses query parameters or fallback values.

    Query Parameters:
    - latitude: Current latitude (optional, uses coordinator if available)
    - longitude: Current longitude (optional, uses coordinator if available)
    - speed_knots: Current speed in knots (optional, uses coordinator if available)

    Returns:
    - JSON object with:
      - `name`: Closest POI name (or fallback message)
      - `eta_seconds`: ETA in seconds (or -1 if unavailable)
      - `eta_type`: Current ETA mode (`anticipated` / `estimated`)
      - `flight_phase`: Current flight phase (may be null if unavailable)
    """
    try:
        # Get current position from coordinator if available
        if _coordinator:
            try:
                telemetry = _coordinator.get_current_telemetry()
                lat = telemetry.position.latitude
                lon = telemetry.position.longitude
                speed = telemetry.position.speed
            except Exception:
                # Fall back to query parameters or defaults
                lat = float(latitude) if latitude else 41.6
                lon = float(longitude) if longitude else -74.0
                speed = float(speed_knots) if speed_knots else 67.0
        else:
            # Use fallback coordinates when no coordinator available
            lat = float(latitude) if latitude else 41.6
            lon = float(longitude) if longitude else -74.0
            speed = float(speed_knots) if speed_knots else 67.0
    except (ValueError, TypeError):
        lat, lon, speed = 41.6, -74.0, 67.0

    if not poi_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="POI manager not initialized",
        )

    pois = poi_manager.list_pois()
    if not pois:
        status_eta_mode = "estimated"
        status_phase = None
        try:
            from app.services.flight_state_manager import get_flight_state_manager

            snapshot = get_flight_state_manager().get_status()
            status_eta_mode = snapshot.eta_mode.value
            status_phase = snapshot.phase.value
        except Exception:  # pragma: no cover - defensive guard
            pass
        return {
            "eta_seconds": -1,
            "eta_type": status_eta_mode,
            "flight_phase": status_phase,
        }

    from app.core.eta_service import get_eta_calculator

    eta_calc = get_eta_calculator()

    closest_eta = float("inf")

    for poi in pois:
        distance = eta_calc.calculate_distance(lat, lon, poi.latitude, poi.longitude)
        eta_seconds = eta_calc.calculate_eta(distance, speed)
        if eta_seconds < closest_eta:
            closest_eta = eta_seconds

    status_eta_mode = "estimated"
    status_phase = None
    try:
        from app.services.flight_state_manager import get_flight_state_manager

        snapshot = get_flight_state_manager().get_status()
        status_eta_mode = snapshot.eta_mode.value
        status_phase = snapshot.phase.value
    except Exception:  # pragma: no cover - defensive guard
        pass

    return {
        "eta_seconds": max(0, closest_eta) if closest_eta != float("inf") else -1,
        "eta_type": status_eta_mode,
        "flight_phase": status_phase,
    }


@router.get(
    "/stats/approaching",
    response_model=dict,
    summary="Get count of approaching POIs (< 30 min)",
)
async def get_approaching_pois(
    latitude: Optional[str] = Query(None),
    longitude: Optional[str] = Query(None),
    speed_knots: Optional[str] = Query(None),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> dict:
    """Get count of POIs that will be reached within 30 minutes.

    Uses coordinator telemetry if available, otherwise uses query parameters or fallback values.

    Query Parameters:
    - latitude: Current latitude (optional, uses coordinator if available)
    - longitude: Current longitude (optional, uses coordinator if available)
    - speed_knots: Current speed in knots (optional, uses coordinator if available)

    Returns:
    - JSON object with 'count' field containing number of approaching POIs
    """
    try:
        # Get current position from coordinator if available
        if _coordinator:
            try:
                telemetry = _coordinator.get_current_telemetry()
                lat = telemetry.position.latitude
                lon = telemetry.position.longitude
                speed = telemetry.position.speed
            except Exception:
                # Fall back to query parameters or defaults
                lat = float(latitude) if latitude else 41.6
                lon = float(longitude) if longitude else -74.0
                speed = float(speed_knots) if speed_knots else 67.0
        else:
            # Use fallback coordinates when no coordinator available
            lat = float(latitude) if latitude else 41.6
            lon = float(longitude) if longitude else -74.0
            speed = float(speed_knots) if speed_knots else 67.0
    except (ValueError, TypeError):
        lat, lon, speed = 41.6, -74.0, 67.0

    pois = poi_manager.list_pois()
    if not pois:
        return {"count": 0}

    from app.core.eta_service import get_eta_calculator

    eta_calc = get_eta_calculator()

    approaching_count = 0
    threshold_seconds = 1800  # 30 minutes

    for poi in pois:
        distance = eta_calc.calculate_distance(lat, lon, poi.latitude, poi.longitude)
        eta_seconds = eta_calc.calculate_eta(distance, speed)
        if 0 <= eta_seconds < threshold_seconds:
            approaching_count += 1

    return {"count": approaching_count}
