"""Helper functions for POI endpoints (bearing, course status, active status calculation)."""

import logging
import math
from pathlib import Path

from app.models.poi import POI
from app.services.route_manager import RouteManager
from app.mission.storage import load_mission

logger = logging.getLogger(__name__)


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate bearing from point 1 to point 2 in degrees (0=North, 90=East).

    Args:
        lat1: Starting latitude in decimal degrees
        lon1: Starting longitude in decimal degrees
        lat2: Ending latitude in decimal degrees
        lon2: Ending longitude in decimal degrees

    Returns:
        Bearing in degrees (0-360)
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)

    x = math.sin(dlon) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(
        lat2_rad
    ) * math.cos(dlon)

    bearing_rad = math.atan2(x, y)
    bearing_deg = math.degrees(bearing_rad)

    # Normalize to 0-360 range
    return (bearing_deg + 360) % 360


def calculate_course_status(heading: float, bearing: float) -> str:
    """Determine course status relative to vessel heading.

    Calculates the shortest angular difference between current heading
    and bearing to POI, then categorizes as one of four statuses.

    Args:
        heading: Current vessel heading in degrees (0=North)
        bearing: Bearing to POI in degrees (0=North)

    Returns:
        Course status string: 'on_course', 'slightly_off', 'off_track', or 'behind'
    """
    # Calculate shortest angular difference
    course_diff = abs(heading - bearing)
    if course_diff > 180:
        course_diff = 360 - course_diff

    # Categorize based on angle thresholds
    if course_diff < 10:
        return "on_course"
    elif course_diff < 45:
        return "slightly_off"
    elif course_diff < 65:
        return "off_track"
    else:
        return "behind"


def calculate_poi_active_status(
    poi: POI,
    route_manager: RouteManager | None,
) -> bool:
    """Calculate whether a POI is currently active based on its associated route or mission.

    Logic:
    - Global POIs (no route_id/mission_id): always active
    - Route POIs: active if their route is the active route
    - Mission POIs: active if their mission has is_active=true

    Args:
        poi: The POI to check
        route_manager: RouteManager instance to check active route

    Returns:
        bool: True if POI is active, False otherwise
    """
    # Global POIs are always active
    if poi.route_id is None and poi.mission_id is None:
        return True

    # Check route-based POIs
    if poi.route_id is not None and route_manager:
        active_route = route_manager.get_active_route()
        if active_route is not None:
            # Extract route ID from metadata file_path (e.g., "/data/routes/route-name.kml" -> "route-name")
            try:
                active_route_id = Path(active_route.metadata.file_path).stem
                return active_route_id == poi.route_id
            except Exception as e:
                logger.warning(
                    "Failed to extract active route ID from path '%s': %s",
                    active_route.metadata.file_path,
                    e,
                )
                return False
        return False

    # Check mission-based POIs
    if poi.mission_id is not None:
        try:
            mission = load_mission(poi.mission_id)
            return mission.is_active if mission else False
        except Exception as e:
            # Mission not found or error loading
            logger.warning(
                "Failed to load mission '%s' for active status check: %s",
                poi.mission_id,
                e,
            )
            return False

    return False
