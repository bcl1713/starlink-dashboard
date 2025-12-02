"""GeoJSON serving API endpoint for map visualization."""

from typing import Any, Optional

from fastapi import APIRouter, Query, Depends

from app.core.config import ConfigManager
from app.services.geojson import GeoJSONBuilder
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from app.mission.dependencies import get_route_manager, get_poi_manager

# Initialize services
config_manager = ConfigManager()

# Create API router
router = APIRouter(prefix="/api", tags=["geojson"])


@router.get("/route.geojson", response_model=dict, summary="Get route as GeoJSON")
async def get_route_geojson(
    include_pois: bool = Query(True, description="Include POIs in response"),
    include_position: bool = Query(False, description="Include current position"),
    route_id: Optional[str] = Query(
        None, description="Specific route ID (uses active if not provided)"
    ),
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> dict[str, Any]:
    """
    Get active route and optionally POIs as GeoJSON FeatureCollection.

    This endpoint serves the route data in GeoJSON format suitable for mapping
    libraries like Leaflet, Mapbox, or Grafana Geomap plugin.

    Query Parameters:
    - include_pois: Include POI features in the collection (default: true)
    - include_position: Include current position feature (default: false)
    - route_id: Use specific route ID instead of active route

    Returns:
    - GeoJSON FeatureCollection with:
      - Route as LineString feature (if available)
      - POIs as Point features (if include_pois=true)
      - Current position as Point feature (if include_position=true)

    Properties:
    - Coordinates are in [longitude, latitude] order (GeoJSON standard)
    - Route features include waypoint count and bounds
    - POI features include name, icon, and category
    - Position features include current altitude, speed, and heading
    """
    route = None
    pois = None
    position = None

    # Get route (specified or active)
    # Get route (specified or active)
    if route_id:
        route = route_manager.get_route(route_id)
    else:
        route = route_manager.get_active_route()

    # Get POIs if requested
    if include_pois and poi_manager:
        route_id_for_pois = (
            route.metadata.file_path.split("/")[-1].split(".")[0] if route else None
        )
        pois = poi_manager.list_pois(route_id=route_id_for_pois)

    # Get current position if requested
    if include_position:
        try:
            # Try to get current telemetry from coordinator
            # This is a placeholder - the actual implementation would get
            # the current position from the simulation/live coordinator
            from app.simulation.coordinator import SimulationCoordinator

            coordinator = SimulationCoordinator(config=config_manager.get_config())
            telemetry = coordinator.get_current_telemetry()
            position = telemetry.position if telemetry else None
        except Exception:
            # If coordinator not available, skip position
            position = None

    # Build GeoJSON feature collection
    feature_collection = GeoJSONBuilder.build_feature_collection(
        route=route, pois=pois or [], current_position=position
    )

    return feature_collection


def _get_route_coordinates_filtered(
    route_id: Optional[str],
    route_manager: RouteManager,
    hemisphere: Optional[str] = None,
) -> dict[str, Any]:
    """
    Helper function to get route coordinates, optionally filtered by hemisphere.

    Args:
        route_id: Route ID or None for active route
        hemisphere: "west" (lon < 0), "east" (lon >= 0), or None for all

    Returns:
        Dictionary with coordinates, total, route_id, route_name
    """
    if not route_manager:
        return {
            "coordinates": [],
            "total": 0,
            "route_id": None,
            "route_name": None,
        }

    route = None

    # Get route (specified or active)
    # Get route (specified or active)
    if route_id:
        route = route_manager.get_route(route_id)
    else:
        route = route_manager.get_active_route()

    if not route:
        return {
            "coordinates": [],
            "total": 0,
            "route_id": None,
            "route_name": None,
        }

    # Convert route points to tabular format with IDL handling
    coordinates = []
    points = route.points

    for i in range(len(points)):
        p1 = points[i]

        # Determine if we should include p1 based on hemisphere
        include_p1 = True
        if hemisphere == "west" and p1.longitude >= 0:
            include_p1 = False
        if hemisphere == "east" and p1.longitude < 0:
            include_p1 = False

        if include_p1:
            coordinates.append(
                {
                    "latitude": p1.latitude,
                    "longitude": p1.longitude,
                    "altitude": p1.altitude,
                    "sequence": p1.sequence,
                }
            )

        # Check for IDL crossing to next point
        if i < len(points) - 1:
            p2 = points[i + 1]

            # Detect crossing: longitude difference > 180
            if abs(p2.longitude - p1.longitude) > 180:
                # Calculate intersection point at 180/-180
                d_lon = 360 - abs(p1.longitude - p2.longitude)
                if d_lon > 0:
                    fraction = (180 - abs(p1.longitude)) / d_lon
                    lat_at_180 = p1.latitude + (p2.latitude - p1.latitude) * fraction

                    # Calculate interpolated altitude (handle None values)
                    if p1.altitude is not None and p2.altitude is not None:
                        alt_at_180 = (
                            p1.altitude + (p2.altitude - p1.altitude) * fraction
                        )
                    else:
                        alt_at_180 = (
                            p1.altitude if p1.altitude is not None else p2.altitude
                        )

                    # If we are in the hemisphere that the segment is LEAVING, add the exit point
                    # If we are in the hemisphere that the segment is ENTERING, add the entry point

                    # Determine which longitude value to use based on crossing direction and hemisphere
                    lon_to_add = None

                    # Case 1: East -> West (e.g., 170 -> -170)
                    if p1.longitude > 0 and p2.longitude < 0:
                        if hemisphere == "east":
                            # Leaving East: Add point at 180
                            lon_to_add = 180.0
                        elif hemisphere == "west":
                            # Entering West: Add point at -180
                            lon_to_add = -180.0

                    # Case 2: West -> East (e.g., -170 -> 170)
                    elif p1.longitude < 0 and p2.longitude > 0:
                        if hemisphere == "west":
                            # Leaving West: Add point at -180
                            lon_to_add = -180.0
                        elif hemisphere == "east":
                            # Entering East: Add point at 180
                            lon_to_add = 180.0

                    # Add interpolated boundary point if determined
                    if lon_to_add is not None:
                        coordinates.append(
                            {
                                "latitude": lat_at_180,
                                "longitude": lon_to_add,
                                "altitude": alt_at_180,
                                "sequence": p1.sequence + fraction,
                            }
                        )

    # Extract route ID from file path (e.g., "test_fix.kml" -> "test_fix")
    route_id_str = route.metadata.file_path.split("/")[-1].split(".")[0]

    return {
        "coordinates": coordinates,
        "total": len(coordinates),
        "route_id": route_id_str,
        "route_name": route.metadata.name,
    }


@router.get(
    "/route/coordinates",
    response_model=dict,
    summary="Get route coordinates as tabular data",
)
async def get_route_coordinates(
    route_id: Optional[str] = Query(
        None, description="Specific route ID (uses active if not provided)"
    ),
    route_manager: RouteManager = Depends(get_route_manager),
) -> dict[str, Any]:
    """
    Get active route coordinates in tabular format for Grafana geomap route layer.

    This endpoint returns route data in a tabular format that Grafana can directly
    consume for route layer visualization. Unlike the GeoJSON endpoint, this returns
    a flat array with explicit latitude/longitude fields, making it compatible with
    Grafana's route layer location mapping.

    Query Parameters:
    - route_id: Use specific route ID instead of active route

    Returns:
    - JSON object with:
      - coordinates: Array of coordinate objects with lat/lon/sequence/altitude
      - total: Total number of coordinates
      - route_id: Route identifier
      - route_name: Route name
    """
    return _get_route_coordinates_filtered(route_id, route_manager, hemisphere=None)


@router.get(
    "/route/coordinates/west",
    response_model=dict,
    summary="Get route coordinates in western hemisphere (IDL-safe)",
)
async def get_route_coordinates_west(
    route_id: Optional[str] = Query(
        None, description="Specific route ID (uses active if not provided)"
    ),
    route_manager: RouteManager = Depends(get_route_manager),
) -> dict[str, Any]:
    """
    Get active route coordinates in western hemisphere (longitude < 0) for Grafana geomap.

    This endpoint is designed to handle International Date Line (IDL) crossings by splitting
    routes into hemisphere-specific segments. Use in combination with the /east endpoint
    for routes that cross the IDL.

    Query Parameters:
    - route_id: Use specific route ID instead of active route

    Returns:
    - JSON object with coordinates in western hemisphere only (lon < 0)
    """
    return _get_route_coordinates_filtered(route_id, route_manager, hemisphere="west")


@router.get(
    "/route/coordinates/east",
    response_model=dict,
    summary="Get route coordinates in eastern hemisphere (IDL-safe)",
)
async def get_route_coordinates_east(
    route_id: Optional[str] = Query(
        None, description="Specific route ID (uses active if not provided)"
    ),
    route_manager: RouteManager = Depends(get_route_manager),
) -> dict[str, Any]:
    """
    Get active route coordinates in eastern hemisphere (longitude >= 0) for Grafana geomap.

    This endpoint is designed to handle International Date Line (IDL) crossings by splitting
    routes into hemisphere-specific segments. Use in combination with the /west endpoint
    for routes that cross the IDL.

    Query Parameters:
    - route_id: Use specific route ID instead of active route

    Returns:
    - JSON object with coordinates in eastern hemisphere only (lon >= 0)
    """
    return _get_route_coordinates_filtered(route_id, route_manager, hemisphere="east")


@router.get("/route.json", response_model=dict, summary="Get route as JSON")
async def get_route_json(
    route_id: Optional[str] = Query(
        None, description="Specific route ID (uses active if not provided)"
    ),
    route_manager: RouteManager = Depends(get_route_manager),
) -> dict[str, Any]:
    """
    Get active route metadata as JSON.

    This endpoint returns route information (without coordinates) in JSON format.

    Query Parameters:
    - route_id: Use specific route ID instead of active route

    Returns:
    - JSON object with route metadata:
      - name: Route name
      - description: Route description
      - point_count: Number of waypoints
      - bounds: Geographic bounding box (min/max lat/lon)
      - file_path: Source KML file path
    """
    route = None

    # Get route (specified or active)
    # Get route (specified or active)
    if route_id:
        route = route_manager.get_route(route_id)
    else:
        route = route_manager.get_active_route()

    if not route:
        return {
            "error": "No active route",
            "available_routes": list(route_manager.list_routes().keys()),
        }

    bounds = route.get_bounds()
    distance_m = route.get_total_distance()

    return {
        "metadata": {
            "name": route.metadata.name,
            "description": route.metadata.description,
            "file_path": route.metadata.file_path,
            "imported_at": route.metadata.imported_at.isoformat(),
        },
        "statistics": {
            "point_count": len(route.points),
            "distance_meters": distance_m,
            "distance_km": distance_m / 1000.0,
        },
        "bounds": bounds,
    }


@router.get("/pois.geojson", response_model=dict, summary="Get POIs as GeoJSON")
async def get_pois_geojson(
    route_id: Optional[str] = Query(None, description="Filter POIs by route ID"),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> dict[str, Any]:
    """
    Get all POIs as GeoJSON FeatureCollection.

    This endpoint serves POI data in GeoJSON format for map visualization.

    Query Parameters:
    - route_id: Filter to POIs for specific route (includes global POIs)

    Returns:
    - GeoJSON FeatureCollection with POI Point features
    - Each POI includes name, icon, category, and description
    """
    pois = []
    if poi_manager:
        pois = poi_manager.list_pois(route_id=route_id)

    feature_collection = GeoJSONBuilder.build_feature_collection(pois=pois)

    return feature_collection


@router.get(
    "/position.geojson", response_model=dict, summary="Get current position as GeoJSON"
)
async def get_position_geojson() -> dict[str, Any]:
    """
    Get current position as GeoJSON Point feature.

    Returns:
    - GeoJSON FeatureCollection with single Point feature for current position
    - Includes latitude, longitude, altitude, speed, and heading
    """
    position = None

    try:
        # Try to get current telemetry from coordinator
        from app.simulation.coordinator import SimulationCoordinator

        coordinator = SimulationCoordinator(config=config_manager.get_config())
        telemetry = coordinator.get_current_telemetry()
        position = telemetry.position if telemetry else None
    except Exception:
        # If coordinator not available, return empty collection
        pass

    feature_collection = GeoJSONBuilder.build_feature_collection(
        current_position=position
    )

    return feature_collection
