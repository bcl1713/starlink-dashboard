"""Unit tests for GeoJSON generation service."""

import pytest

from app.models.poi import POI
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
from app.models.telemetry import PositionData
from app.services.geojson import GeoJSONBuilder


@pytest.fixture
def sample_route():
    """Create a sample route for testing."""
    points = [
        RoutePoint(latitude=40.7128, longitude=-74.0060, altitude=100, sequence=0),
        RoutePoint(latitude=40.7138, longitude=-74.0070, altitude=110, sequence=1),
        RoutePoint(latitude=40.7148, longitude=-74.0080, altitude=120, sequence=2),
    ]

    metadata = RouteMetadata(
        name="Test Route",
        description="A test route",
        file_path="/data/routes/test_route.kml",
        point_count=3,
    )

    return ParsedRoute(metadata=metadata, points=points)


@pytest.fixture
def sample_pois():
    """Create sample POIs for testing."""
    pois = [
        POI(
            id="poi-1",
            name="Point A",
            latitude=40.7128,
            longitude=-74.0060,
            icon="marker",
            category="waypoint",
        ),
        POI(
            id="poi-2",
            name="Point B",
            latitude=40.7148,
            longitude=-74.0080,
            icon="flag",
            category="destination",
        ),
    ]
    return pois


@pytest.fixture
def sample_position():
    """Create sample position data."""
    return PositionData(
        latitude=40.7138,
        longitude=-74.0070,
        altitude=105,
        speed=150.0,
        heading=45.0,
    )


class TestGeoJSONBuilder:
    """Test suite for GeoJSON builder."""

    def test_build_route_feature(self, sample_route):
        """Test building a route feature."""
        feature = GeoJSONBuilder.build_route_feature(sample_route)

        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "LineString"
        assert len(feature["geometry"]["coordinates"]) == 3

    def test_route_coordinates_order(self, sample_route):
        """Test that route coordinates are in [lon, lat] order."""
        feature = GeoJSONBuilder.build_route_feature(sample_route)
        coords = feature["geometry"]["coordinates"]

        # First coordinate should be [longitude, latitude]
        assert coords[0][0] == -74.0060  # longitude
        assert coords[0][1] == 40.7128   # latitude

    def test_route_feature_properties(self, sample_route):
        """Test route feature properties."""
        feature = GeoJSONBuilder.build_route_feature(sample_route)
        props = feature["properties"]

        assert props["name"] == "Test Route"
        assert props["description"] == "A test route"
        assert props["type"] == "route"
        assert props["point_count"] == 3
        assert "min_lat" in props
        assert "max_lat" in props
        assert "min_lon" in props
        assert "max_lon" in props

    def test_build_poi_feature(self, sample_pois):
        """Test building a POI feature."""
        poi = sample_pois[0]
        feature = GeoJSONBuilder.build_poi_feature(poi)

        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        assert len(feature["geometry"]["coordinates"]) == 2

    def test_poi_coordinates_order(self, sample_pois):
        """Test that POI coordinates are in [lon, lat] order."""
        poi = sample_pois[0]
        feature = GeoJSONBuilder.build_poi_feature(poi)
        coords = feature["geometry"]["coordinates"]

        assert coords[0] == -74.0060  # longitude
        assert coords[1] == 40.7128   # latitude

    def test_poi_feature_properties(self, sample_pois):
        """Test POI feature properties."""
        poi = sample_pois[0]
        feature = GeoJSONBuilder.build_poi_feature(poi)
        props = feature["properties"]

        assert props["id"] == "poi-1"
        assert props["name"] == "Point A"
        assert props["icon"] == "marker"
        assert props["category"] == "waypoint"
        assert props["type"] == "poi"

    def test_build_current_position_feature(self, sample_position):
        """Test building a current position feature."""
        feature = GeoJSONBuilder.build_current_position_feature(sample_position)

        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        assert feature["properties"]["type"] == "current_position"

    def test_position_coordinates_order(self, sample_position):
        """Test that position coordinates are in [lon, lat] order."""
        feature = GeoJSONBuilder.build_current_position_feature(sample_position)
        coords = feature["geometry"]["coordinates"]

        assert coords[0] == -74.0070  # longitude
        assert coords[1] == 40.7138   # latitude

    def test_position_feature_properties(self, sample_position):
        """Test position feature properties."""
        feature = GeoJSONBuilder.build_current_position_feature(sample_position)
        props = feature["properties"]

        assert props["type"] == "current_position"
        assert props["altitude"] == 105
        assert props["speed_knots"] == 150.0
        assert props["heading_degrees"] == 45.0
        assert "timestamp" in props

    def test_build_feature_collection_all(self, sample_route, sample_pois, sample_position):
        """Test building a feature collection with all components."""
        collection = GeoJSONBuilder.build_feature_collection(
            route=sample_route,
            pois=sample_pois,
            current_position=sample_position,
        )

        assert collection["type"] == "FeatureCollection"
        assert len(collection["features"]) == 4  # 1 route + 2 pois + 1 position
        assert collection["properties"]["feature_count"] == 4
        assert collection["properties"]["has_route"] is True
        assert collection["properties"]["has_pois"] is True
        assert collection["properties"]["has_position"] is True

    def test_build_feature_collection_route_only(self, sample_route):
        """Test building a feature collection with only route."""
        collection = GeoJSONBuilder.build_feature_collection(route=sample_route)

        assert len(collection["features"]) == 1
        assert collection["features"][0]["properties"]["type"] == "route"
        assert collection["properties"]["has_route"] is True
        assert collection["properties"]["has_pois"] is False
        assert collection["properties"]["has_position"] is False

    def test_build_feature_collection_pois_only(self, sample_pois):
        """Test building a feature collection with only POIs."""
        collection = GeoJSONBuilder.build_feature_collection(pois=sample_pois)

        assert len(collection["features"]) == 2
        assert all(f["properties"]["type"] == "poi" for f in collection["features"])
        assert collection["properties"]["has_route"] is False
        assert collection["properties"]["has_pois"] is True
        assert collection["properties"]["has_position"] is False

    def test_build_feature_collection_position_only(self, sample_position):
        """Test building a feature collection with only position."""
        collection = GeoJSONBuilder.build_feature_collection(current_position=sample_position)

        assert len(collection["features"]) == 1
        assert collection["features"][0]["properties"]["type"] == "current_position"
        assert collection["properties"]["has_route"] is False
        assert collection["properties"]["has_pois"] is False
        assert collection["properties"]["has_position"] is True

    def test_build_feature_collection_empty(self):
        """Test building an empty feature collection."""
        collection = GeoJSONBuilder.build_feature_collection()

        assert collection["type"] == "FeatureCollection"
        assert len(collection["features"]) == 0
        assert collection["properties"]["feature_count"] == 0

    def test_feature_collection_has_metadata(self, sample_route):
        """Test that feature collection includes metadata."""
        collection = GeoJSONBuilder.build_feature_collection(route=sample_route)

        assert "properties" in collection
        assert "generated_at" in collection["properties"]
        assert "feature_count" in collection["properties"]

    def test_validate_geojson_valid_feature_collection(self, sample_route):
        """Test validation of valid FeatureCollection."""
        collection = GeoJSONBuilder.build_feature_collection(route=sample_route)
        is_valid, error = GeoJSONBuilder.validate_geojson(collection)

        assert is_valid is True
        assert error is None

    def test_validate_geojson_valid_feature(self, sample_route):
        """Test validation of valid Feature."""
        feature = GeoJSONBuilder.build_route_feature(sample_route)
        is_valid, error = GeoJSONBuilder.validate_geojson(feature)

        assert is_valid is True
        assert error is None

    def test_validate_geojson_missing_type(self):
        """Test validation catches missing type."""
        invalid_geojson = {"features": []}
        is_valid, error = GeoJSONBuilder.validate_geojson(invalid_geojson)

        assert is_valid is False
        assert error is not None

    def test_validate_geojson_missing_features(self):
        """Test validation catches missing features in FeatureCollection."""
        invalid_geojson = {"type": "FeatureCollection"}
        is_valid, error = GeoJSONBuilder.validate_geojson(invalid_geojson)

        assert is_valid is False
        assert error is not None

    def test_validate_geojson_invalid_feature_in_collection(self):
        """Test validation catches invalid feature in collection."""
        invalid_geojson = {
            "type": "FeatureCollection",
            "features": [{"type": "InvalidType"}],  # Missing geometry
        }
        is_valid, error = GeoJSONBuilder.validate_geojson(invalid_geojson)

        assert is_valid is False
        assert error is not None

    def test_route_bounds_calculation(self, sample_route):
        """Test that route feature includes correct bounds."""
        feature = GeoJSONBuilder.build_route_feature(sample_route)
        props = feature["properties"]

        assert props["min_lat"] == 40.7128
        assert props["max_lat"] == 40.7148
        assert props["min_lon"] == -74.0080
        assert props["max_lon"] == -74.0060

    def test_geojson_serialization(self, sample_route):
        """Test that GeoJSON can be serialized to JSON."""
        import json

        collection = GeoJSONBuilder.build_feature_collection(route=sample_route)
        json_str = json.dumps(collection)

        assert json_str is not None
        assert "FeatureCollection" in json_str

    def test_poi_without_optional_fields(self):
        """Test POI feature with minimal fields."""
        poi = POI(
            id="minimal-poi",
            name="Minimal",
            latitude=0.0,
            longitude=0.0,
        )

        feature = GeoJSONBuilder.build_poi_feature(poi)

        assert feature["properties"]["name"] == "Minimal"
        assert feature["properties"]["icon"] == "marker"
        assert feature["properties"]["category"] is None

    def test_multiple_pois_feature_collection(self, sample_pois):
        """Test feature collection with multiple POIs."""
        collection = GeoJSONBuilder.build_feature_collection(pois=sample_pois)

        assert len(collection["features"]) == 2
        assert collection["features"][0]["properties"]["id"] == "poi-1"
        assert collection["features"][1]["properties"]["id"] == "poi-2"
