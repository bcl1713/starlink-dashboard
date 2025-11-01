"""Integration tests for KML, POI, and GeoJSON system."""

import json
import tempfile
import textwrap
from pathlib import Path

import pytest

from app.models.poi import POICreate
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
from app.services.geojson import GeoJSONBuilder
from app.services.kml_parser import parse_kml_file
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from app.simulation.kml_follower import KMLRouteFollower


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_kml_file(temp_data_dir):
    """Create a sample KML file."""
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Document>
        <name>Integration Test Route</name>
        <description>Route for integration testing</description>
        <Placemark>
          <LineString>
            <coordinates>
              -74.0060,40.7128,100
              -74.0070,40.7138,110
              -74.0080,40.7148,120
            </coordinates>
          </LineString>
        </Placemark>
      </Document>
    </kml>"""

    kml_file = temp_data_dir / "integration_test.kml"
    kml_file.write_text(kml_content)
    return kml_file


@pytest.fixture
def route_manager_instance(temp_data_dir):
    """Create RouteManager with temp directory."""
    manager = RouteManager(routes_dir=temp_data_dir)
    return manager


@pytest.fixture
def poi_manager_instance(temp_data_dir):
    """Create POIManager with temp directory."""
    pois_file = temp_data_dir / "pois.json"
    return POIManager(pois_file=pois_file)


class TestKMLPOIIntegration:
    """Integration tests for KML, POI, and routing system."""

    def test_kml_to_route_to_geojson_pipeline(self, sample_kml_file):
        """Test complete pipeline: KML -> Route -> GeoJSON."""
        # Parse KML
        route = parse_kml_file(sample_kml_file)
        assert route is not None

        # Convert to GeoJSON
        feature = GeoJSONBuilder.build_route_feature(route)
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "LineString"

        # Validate GeoJSON
        is_valid, error = GeoJSONBuilder.validate_geojson(feature)
        assert is_valid is True
        assert error is None

    def test_route_manager_kml_workflow(self, sample_kml_file, route_manager_instance):
        """Test RouteManager with KML file loading."""
        # Load route file
        route_manager_instance._load_route_file(sample_kml_file)

        # List routes
        routes = route_manager_instance.list_routes()
        assert len(routes) > 0

        # Get specific route
        route_id = list(routes.keys())[0]
        route = route_manager_instance.get_route(route_id)
        assert route is not None

        # Activate route
        assert route_manager_instance.activate_route(route_id)

        # Verify active route
        active = route_manager_instance.get_active_route()
        assert active is not None

    def test_kml_follower_with_parsed_route(self, sample_kml_file):
        """Test KMLRouteFollower with parsed route."""
        # Parse KML
        route = parse_kml_file(sample_kml_file)

        # Create follower
        follower = KMLRouteFollower(route)

        # Get positions along route
        positions = [follower.get_position(i * 0.25) for i in range(5)]

        # Verify all positions are valid
        for pos in positions:
            assert pos["latitude"] is not None
            assert pos["longitude"] is not None
            assert pos["heading"] is not None

    def test_poi_creation_and_geojson_export(self, poi_manager_instance):
        """Test POI creation and GeoJSON export."""
        # Create POIs
        poi1 = poi_manager_instance.create_poi(
            POICreate(name="POI 1", latitude=40.7128, longitude=-74.0060)
        )
        poi2 = poi_manager_instance.create_poi(
            POICreate(name="POI 2", latitude=40.7138, longitude=-74.0070)
        )

        # Get POIs
        pois = poi_manager_instance.list_pois()
        assert len(pois) == 2

        # Convert to GeoJSON
        collection = GeoJSONBuilder.build_feature_collection(pois=pois)

        # Verify structure
        assert collection["type"] == "FeatureCollection"
        assert len(collection["features"]) == 2

        # Verify each feature
        for feature in collection["features"]:
            assert feature["type"] == "Feature"
            assert feature["geometry"]["type"] == "Point"

    def test_route_with_pois_geojson(self, sample_kml_file, poi_manager_instance):
        """Test combining route and POIs in GeoJSON."""
        # Parse route
        route = parse_kml_file(sample_kml_file)

        # Create POIs
        poi_manager_instance.create_poi(
            POICreate(name="Start", latitude=40.7128, longitude=-74.0060)
        )
        poi_manager_instance.create_poi(
            POICreate(name="End", latitude=40.7148, longitude=-74.0080)
        )

        pois = poi_manager_instance.list_pois()

        # Build combined GeoJSON
        collection = GeoJSONBuilder.build_feature_collection(route=route, pois=pois)

        # Verify combined structure
        assert collection["type"] == "FeatureCollection"
        assert len(collection["features"]) == 3  # 1 route + 2 POIs
        assert collection["properties"]["has_route"] is True
        assert collection["properties"]["has_pois"] is True

    def test_poi_persistence_workflow(self, temp_data_dir):
        """Test POI persistence across manager instances."""
        pois_file = temp_data_dir / "pois.json"

        # Create first manager and add POI
        manager1 = POIManager(pois_file=pois_file)
        poi1 = manager1.create_poi(
            POICreate(name="Persistent POI", latitude=1.0, longitude=1.0)
        )

        # Create second manager and verify POI persists
        manager2 = POIManager(pois_file=pois_file)
        pois = manager2.list_pois()

        assert len(pois) == 1
        assert pois[0].name == "Persistent POI"

    def test_route_and_poi_integration(self, sample_kml_file, poi_manager_instance):
        """Test route-specific POI association."""
        # Parse route
        route = parse_kml_file(sample_kml_file)
        route_id = "test_route"

        # Create route-specific POI
        route_poi = poi_manager_instance.create_poi(
            POICreate(
                name="Route POI",
                latitude=40.7138,
                longitude=-74.0070,
                route_id=route_id,
            )
        )

        # Create global POI
        global_poi = poi_manager_instance.create_poi(
            POICreate(name="Global POI", latitude=0.0, longitude=0.0)
        )

        # Get POIs for route
        route_pois = poi_manager_instance.list_pois(route_id=route_id)

        # Only route-specific POIs should be returned when filtering by route
        assert len(route_pois) == 1
        assert route_pois[0].name == "Route POI"

    def test_geojson_serialization(self, sample_kml_file, poi_manager_instance):
        """Test that generated GeoJSON is JSON-serializable."""
        # Parse route
        route = parse_kml_file(sample_kml_file)

        # Create POIs
        poi_manager_instance.create_poi(
            POICreate(name="Test POI", latitude=40.7128, longitude=-74.0060)
        )
        pois = poi_manager_instance.list_pois()

        # Build GeoJSON
        collection = GeoJSONBuilder.build_feature_collection(route=route, pois=pois)

        # Verify JSON serialization
        json_str = json.dumps(collection)
        assert json_str is not None

        # Verify round-trip
        parsed = json.loads(json_str)
        assert parsed["type"] == "FeatureCollection"

    def test_kml_route_follower_geojson_export(self, sample_kml_file):
        """Test exporting route follower positions as GeoJSON."""
        # Parse route
        route = parse_kml_file(sample_kml_file)

        # Create follower
        follower = KMLRouteFollower(route)

        # Get position
        pos = follower.get_position(0.5)

        # Verify position can be exported to GeoJSON
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [pos["longitude"], pos["latitude"]],
            },
            "properties": {
                "altitude": pos["altitude"],
                "heading": pos["heading"],
                "progress": pos["progress"],
            },
        }

        # Validate structure
        assert feature["geometry"]["coordinates"][0] == pos["longitude"]
        assert feature["geometry"]["coordinates"][1] == pos["latitude"]

    def test_upload_route_with_poi_import(self, test_client):
        """Verify uploading a route with import_pois creates POIs from waypoints."""
        routes_dir = Path("/tmp/test_data/routes")
        for existing in routes_dir.glob("*.kml"):
            existing.unlink()

        pois_file = Path("/tmp/test_data/pois.json")
        pois_file.write_text(json.dumps({"pois": {}, "routes": {}}, indent=2))

        kml_content = textwrap.dedent(
            """
            <?xml version="1.0" encoding="UTF-8"?>
            <kml xmlns="http://www.opengis.net/kml/2.2">
              <Document>
                <name>KSEA-KLAX Demo</name>
                <Placemark>
                  <name>KSEA</name>
                  <Point>
                    <coordinates>-122.3088,47.4502,128</coordinates>
                  </Point>
                </Placemark>
                <Placemark>
                  <name>Leg One</name>
                  <LineString>
                    <coordinates>
                      -122.3088,47.4502,128
                      -121.0000,45.5000,150
                    </coordinates>
                  </LineString>
                </Placemark>
                <Placemark>
                  <name>Leg Two</name>
                  <LineString>
                    <coordinates>
                      -121.0000,45.5000,150
                      -118.4085,33.9416,62
                    </coordinates>
                  </LineString>
                </Placemark>
                <Placemark>
                  <name>KLAX</name>
                  <Point>
                    <coordinates>-118.4085,33.9416,62</coordinates>
                  </Point>
                </Placemark>
              </Document>
            </kml>
            """
        ).strip()

        files = {"file": ("ksea-klax.kml", kml_content, "application/vnd.google-earth.kml+xml")}

        response = test_client.post("/api/routes/upload?import_pois=true", files=files)
        assert response.status_code == 201

        payload = response.json()
        assert payload["imported_poi_count"] == 2
        assert payload["skipped_poi_count"] == 0

        route_id = payload["id"]

        poi_response = test_client.get(f"/api/pois?route_id={route_id}")
        assert poi_response.status_code == 200

        poi_payload = poi_response.json()
        assert poi_payload["total"] == 2
        names = {poi["name"] for poi in poi_payload["pois"]}
        assert names == {"KSEA", "KLAX"}

        detail_response = test_client.get(f"/api/routes/{route_id}")
        assert detail_response.status_code == 200
        detail_payload = detail_response.json()
        assert detail_payload["poi_count"] == 2
        assert len(detail_payload["waypoints"]) == 2

    def test_complete_workflow_simulation(self, sample_kml_file, poi_manager_instance, route_manager_instance):
        """Test complete workflow: KML load -> Route follow -> POI proximity."""
        # Load and manage route
        route_manager_instance._load_route_file(sample_kml_file)
        routes = route_manager_instance.list_routes()
        route_id = list(routes.keys())[0]
        route_manager_instance.activate_route(route_id)

        # Get active route
        active_route = route_manager_instance.get_active_route()
        assert active_route is not None

        # Create KML follower
        follower = KMLRouteFollower(active_route)

        # Create POIs at start and end of route
        start_poi = poi_manager_instance.create_poi(
            POICreate(
                name="Start",
                latitude=40.7128,
                longitude=-74.0060,
                route_id=route_id,
            )
        )
        end_poi = poi_manager_instance.create_poi(
            POICreate(
                name="End",
                latitude=40.7148,
                longitude=-74.0080,
                route_id=route_id,
            )
        )

        pois = poi_manager_instance.list_pois(route_id=route_id)
        assert len(pois) == 2

        # Simulate moving along route
        positions = []
        for progress in [0.0, 0.25, 0.5, 0.75, 0.99]:
            pos = follower.get_position(progress)
            positions.append(pos)

            # Build GeoJSON with current position
            from app.models.telemetry import PositionData

            position_data = PositionData(
                latitude=pos["latitude"],
                longitude=pos["longitude"],
                altitude=pos["altitude"],
                speed=150.0,
                heading=pos["heading"],
            )

            # This would normally be used for ETA calculations
            assert position_data is not None

        # Verify we got positions along the entire route
        assert len(positions) == 5
