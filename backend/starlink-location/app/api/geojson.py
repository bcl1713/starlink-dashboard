"""GeoJSON serving API endpoint for map visualization."""

from typing import Any, Optional

from fastapi import APIRouter, Query

from app.core.config import ConfigManager
from app.models.telemetry import PositionData
from app.services.geojson import GeoJSONBuilder
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager

# Initialize services
config_manager = ConfigManager()
route_manager = RouteManager()
poi_manager = POIManager()

# Start watching for route changes
route_manager.start_watching()

# Create API router
router = APIRouter(prefix="/api", tags=["geojson"])


@router.get("/route.geojson", response_model=dict, summary="Get route as GeoJSON")
async def get_route_geojson(
    include_pois: bool = Query(True, description="Include POIs in response"),
    include_position: bool = Query(False, description="Include current position"),
    route_id: Optional[str] = Query(None, description="Specific route ID (uses active if not provided)"),
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
    if route_id:
        route = route_manager.get_route(route_id)
    else:
        route = route_manager.get_active_route()

    # Get POIs if requested
    if include_pois:
        route_id_for_pois = route.metadata.file_path.split("/")[-1].split(".")[0] if route else None
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


@router.get("/route.json", response_model=dict, summary="Get route as JSON")
async def get_route_json(
    route_id: Optional[str] = Query(None, description="Specific route ID (uses active if not provided)"),
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
    pois = poi_manager.list_pois(route_id=route_id)

    feature_collection = GeoJSONBuilder.build_feature_collection(pois=pois)

    return feature_collection


@router.get("/position.geojson", response_model=dict, summary="Get current position as GeoJSON")
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

    feature_collection = GeoJSONBuilder.build_feature_collection(current_position=position)

    return feature_collection
