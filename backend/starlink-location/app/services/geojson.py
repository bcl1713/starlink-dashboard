"""GeoJSON generation service for converting routes and POIs to GeoJSON format."""

import logging
from datetime import datetime
from typing import Any, Optional

from app.models.poi import POI
from app.models.route import ParsedRoute
from app.models.telemetry import PositionData

logger = logging.getLogger(__name__)


class GeoJSONBuilder:
    """
    Builds GeoJSON features and feature collections for routes, POIs, and current position.

    GeoJSON Standard:
    - Coordinates are in [longitude, latitude] order (NOT lat, lon)
    - LineString uses coordinates array
    - Point uses single coordinate array
    """

    @staticmethod
    def build_route_feature(route: ParsedRoute) -> dict[str, Any]:
        """
        Convert a ParsedRoute to a GeoJSON LineString feature.

        Args:
            route: ParsedRoute object

        Returns:
            GeoJSON Feature with LineString geometry
        """
        # Extract coordinates in [lon, lat] order (GeoJSON standard)
        coordinates = [[point.longitude, point.latitude] for point in route.points]

        # Calculate route distance and bounds
        bounds = route.get_bounds()

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates,
            },
            "properties": {
                "name": route.metadata.name,
                "description": route.metadata.description,
                "type": "route",
                "point_count": len(route.points),
                "min_lat": bounds["min_lat"],
                "max_lat": bounds["max_lat"],
                "min_lon": bounds["min_lon"],
                "max_lon": bounds["max_lon"],
                "file_path": route.metadata.file_path,
            },
        }

        return feature

    @staticmethod
    def build_poi_feature(poi: POI) -> dict[str, Any]:
        """
        Convert a POI to a GeoJSON Point feature.

        Args:
            poi: POI object

        Returns:
            GeoJSON Feature with Point geometry
        """
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [poi.longitude, poi.latitude],
            },
            "properties": {
                "id": poi.id,
                "name": poi.name,
                "icon": poi.icon,
                "category": poi.category,
                "description": poi.description,
                "route_id": poi.route_id,
                "type": "poi",
                "created_at": poi.created_at.isoformat() if poi.created_at else None,
                "updated_at": poi.updated_at.isoformat() if poi.updated_at else None,
            },
        }

        return feature

    @staticmethod
    def build_current_position_feature(position: PositionData) -> dict[str, Any]:
        """
        Create a GeoJSON Point feature for current position.

        Args:
            position: Current PositionData

        Returns:
            GeoJSON Feature with Point geometry for current position
        """
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [position.longitude, position.latitude],
            },
            "properties": {
                "type": "current_position",
                "name": "Current Position",
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

        return feature

    @staticmethod
    def build_feature_collection(
        route: Optional[ParsedRoute] = None,
        pois: Optional[list[POI]] = None,
        current_position: Optional[PositionData] = None,
    ) -> dict[str, Any]:
        """
        Combine route, POIs, and current position into a FeatureCollection.

        Args:
            route: Optional ParsedRoute object
            pois: Optional list of POI objects
            current_position: Optional current PositionData

        Returns:
            GeoJSON FeatureCollection with all features
        """
        features = []

        # Add route if available
        if route:
            features.append(GeoJSONBuilder.build_route_feature(route))

        # Add POIs if available
        if pois:
            for poi in pois:
                features.append(GeoJSONBuilder.build_poi_feature(poi))

        # Add current position if available
        if current_position:
            features.append(GeoJSONBuilder.build_current_position_feature(current_position))

        feature_collection = {
            "type": "FeatureCollection",
            "features": features,
        }

        return feature_collection

    @staticmethod
    def validate_geojson(geojson_obj: dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate GeoJSON structure.

        Args:
            geojson_obj: GeoJSON object to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for required fields
        if "type" not in geojson_obj:
            return False, "Missing 'type' field"

        if geojson_obj["type"] == "FeatureCollection":
            if "features" not in geojson_obj:
                return False, "FeatureCollection missing 'features' array"

            for i, feature in enumerate(geojson_obj["features"]):
                if feature.get("type") != "Feature":
                    return False, f"Feature {i} missing or invalid 'type' field"

                if "geometry" not in feature:
                    return False, f"Feature {i} missing 'geometry'"

                geom = feature["geometry"]
                if "type" not in geom or "coordinates" not in geom:
                    return False, f"Feature {i} geometry missing type or coordinates"

        elif geojson_obj["type"] == "Feature":
            if "geometry" not in geojson_obj:
                return False, "Feature missing 'geometry'"

            geom = geojson_obj["geometry"]
            if "type" not in geom or "coordinates" not in geom:
                return False, "Feature geometry missing type or coordinates"

        return True, None
