"""Route timing profile endpoints."""

from fastapi import APIRouter, HTTPException, Depends, status

from app.core.logging import get_logger
from app.services.route_manager import RouteManager
from app.mission.dependencies import get_route_manager

logger = get_logger(__name__)

router = APIRouter()


def _format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable HH:MM:SS format.

    Converts a duration in seconds to a formatted string in the format
    HH:MM:SS. Returns "Unknown" for negative or None values.

    Args:
        seconds: Duration in seconds to format

    Returns:
        Formatted string in HH:MM:SS format, or "Unknown" if invalid
    """
    if not seconds or seconds < 0:
        return "Unknown"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


@router.get("/active/timing")
async def get_active_route_timing(
    route_manager: RouteManager = Depends(get_route_manager),
) -> dict:
    """Get timing profile data for the currently active route.

    Retrieves comprehensive timing information including planned and actual
    departure/arrival times, flight status, and duration calculations for
    the currently active route.

    Args:
        route_manager: Injected RouteManager dependency for route operations

    Returns:
        Dictionary containing timing profile with keys including has_timing_data,
        departure_time, arrival_time, flight_status, total_expected_duration_seconds.
        Returns minimal dict with has_timing_data=False if no active route.

    Raises:
        HTTPException: 500 if route manager not initialized
    """
    if not route_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route manager not initialized",
        )

    active_route = route_manager.get_active_route()
    if not active_route:
        return {"has_timing_data": False, "message": "No active route"}

    if not active_route.timing_profile:
        return {"has_timing_data": False, "message": "Active route has no timing data"}

    timing = active_route.timing_profile
    flight_status = timing.flight_status
    is_departed = timing.is_departed()
    is_in_flight = timing.is_in_flight()

    return {
        "route_name": active_route.metadata.name or "Unknown",
        "has_timing_data": timing.has_timing_data,
        "departure_time": (
            timing.departure_time.isoformat() if timing.departure_time else None
        ),
        "arrival_time": (
            timing.arrival_time.isoformat() if timing.arrival_time else None
        ),
        "actual_departure_time": (
            timing.actual_departure_time.isoformat()
            if timing.actual_departure_time
            else None
        ),
        "actual_arrival_time": (
            timing.actual_arrival_time.isoformat()
            if timing.actual_arrival_time
            else None
        ),
        "flight_status": flight_status,
        "is_departed": is_departed,
        "is_in_flight": is_in_flight,
        "total_expected_duration_seconds": timing.total_expected_duration_seconds,
        "segment_count_with_timing": timing.segment_count_with_timing,
        "total_duration_readable": (
            _format_duration(timing.total_expected_duration_seconds)
            if timing.total_expected_duration_seconds
            else None
        ),
    }
