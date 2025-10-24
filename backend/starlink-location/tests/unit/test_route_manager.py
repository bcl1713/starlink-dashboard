"""Unit tests for RouteManager functionality."""

import tempfile
import time
from pathlib import Path

import pytest

from app.services.route_manager import RouteManager

VALID_KML_CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Test Route</name>
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

ANOTHER_KML_CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Second Route</name>
    <Placemark>
      <LineString>
        <coordinates>
          0.0,0.0,0.0
          1.0,1.0,100.0
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>"""

INVALID_KML_CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Invalid</name>
  </Document>
</kml>"""


@pytest.fixture
def temp_routes_dir():
    """Create temporary directory for route files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def route_manager(temp_routes_dir):
    """Create a RouteManager instance with temp directory."""
    return RouteManager(routes_dir=temp_routes_dir)


@pytest.fixture
def route_manager_with_file(temp_routes_dir):
    """Create RouteManager with a pre-existing KML file."""
    kml_file = temp_routes_dir / "route1.kml"
    kml_file.write_text(VALID_KML_CONTENT)

    manager = RouteManager(routes_dir=temp_routes_dir)
    manager.start_watching()
    return manager


class TestRouteManager:
    """Test suite for RouteManager."""

    def test_initialization(self, route_manager):
        """Test RouteManager initialization."""
        assert route_manager.routes_dir.exists()
        assert len(route_manager.list_routes()) == 0
        assert route_manager.get_active_route() is None

    def test_load_existing_routes(self, temp_routes_dir):
        """Test loading existing routes on startup."""
        # Create KML files before initializing manager
        kml_file1 = temp_routes_dir / "route1.kml"
        kml_file1.write_text(VALID_KML_CONTENT)

        kml_file2 = temp_routes_dir / "route2.kml"
        kml_file2.write_text(ANOTHER_KML_CONTENT)

        manager = RouteManager(routes_dir=temp_routes_dir)
        manager.start_watching()

        routes = manager.list_routes()
        assert len(routes) == 2
        assert "route1" in routes
        assert "route2" in routes

    def test_get_route(self, route_manager_with_file):
        """Test retrieving a specific route."""
        route = route_manager_with_file.get_route("route1")

        assert route is not None
        assert route.metadata.name == "Test Route"
        assert len(route.points) == 3

    def test_get_nonexistent_route(self, route_manager):
        """Test retrieving a non-existent route."""
        route = route_manager.get_route("nonexistent")
        assert route is None

    def test_list_routes(self, route_manager_with_file):
        """Test listing routes."""
        routes = route_manager_with_file.list_routes()

        assert len(routes) == 1
        assert "route1" in routes
        assert routes["route1"]["name"] == "Test Route"
        assert routes["route1"]["point_count"] == 3
        assert routes["route1"]["is_active"] is False

    def test_activate_route(self, route_manager_with_file):
        """Test activating a route."""
        result = route_manager_with_file.activate_route("route1")

        assert result is True
        assert route_manager_with_file.get_active_route() is not None
        assert route_manager_with_file.get_active_route().metadata.name == "Test Route"

    def test_activate_nonexistent_route(self, route_manager):
        """Test activating a non-existent route."""
        result = route_manager.activate_route("nonexistent")

        assert result is False
        assert route_manager.get_active_route() is None

    def test_deactivate_route(self, route_manager_with_file):
        """Test deactivating active route."""
        route_manager_with_file.activate_route("route1")
        assert route_manager_with_file.get_active_route() is not None

        route_manager_with_file.deactivate_route()
        assert route_manager_with_file.get_active_route() is None

    def test_list_routes_shows_active_status(self, route_manager_with_file):
        """Test that list_routes shows active status correctly."""
        routes = route_manager_with_file.list_routes()
        assert routes["route1"]["is_active"] is False

        route_manager_with_file.activate_route("route1")
        routes = route_manager_with_file.list_routes()
        assert routes["route1"]["is_active"] is True

    def test_load_route_file(self, route_manager, temp_routes_dir):
        """Test loading a route file."""
        kml_file = temp_routes_dir / "test_route.kml"
        kml_file.write_text(VALID_KML_CONTENT)

        route_manager._load_route_file(str(kml_file))

        routes = route_manager.list_routes()
        assert len(routes) == 1
        assert "test_route" in routes

    def test_load_invalid_route_file(self, route_manager, temp_routes_dir):
        """Test loading an invalid route file."""
        kml_file = temp_routes_dir / "invalid.kml"
        kml_file.write_text(INVALID_KML_CONTENT)

        route_manager._load_route_file(str(kml_file))

        routes = route_manager.list_routes()
        assert len(routes) == 0

        # Should be in errors
        errors = route_manager.get_route_errors()
        assert "invalid" in errors

    def test_get_route_errors(self, route_manager, temp_routes_dir):
        """Test error tracking."""
        kml_file = temp_routes_dir / "bad_route.kml"
        kml_file.write_text(INVALID_KML_CONTENT)

        route_manager._load_route_file(str(kml_file))

        errors = route_manager.get_route_errors()
        assert len(errors) == 1
        assert "bad_route" in errors
        assert "No coordinate data found" in errors["bad_route"]

    def test_has_errors(self, route_manager, temp_routes_dir):
        """Test error detection."""
        assert route_manager.has_errors() is False

        kml_file = temp_routes_dir / "bad.kml"
        kml_file.write_text(INVALID_KML_CONTENT)

        route_manager._load_route_file(str(kml_file))
        assert route_manager.has_errors() is True

    def test_remove_route(self, route_manager_with_file):
        """Test removing a route."""
        assert len(route_manager_with_file.list_routes()) == 1

        route_manager_with_file._remove_route("route1")

        assert len(route_manager_with_file.list_routes()) == 0
        assert route_manager_with_file.get_route("route1") is None

    def test_remove_active_route(self, route_manager_with_file):
        """Test that removing active route clears active status."""
        route_manager_with_file.activate_route("route1")
        assert route_manager_with_file.get_active_route() is not None

        route_manager_with_file._remove_route("route1")

        assert route_manager_with_file.get_active_route() is None

    def test_reload_all_routes(self, temp_routes_dir):
        """Test reloading all routes."""
        kml_file1 = temp_routes_dir / "route1.kml"
        kml_file1.write_text(VALID_KML_CONTENT)

        manager = RouteManager(routes_dir=temp_routes_dir)
        manager.start_watching()

        assert len(manager.list_routes()) == 1
        manager.activate_route("route1")

        # Reload should reset everything
        manager.reload_all_routes()

        assert len(manager.list_routes()) == 1
        assert manager.get_active_route() is None

    def test_start_stop_watching(self, route_manager):
        """Test starting and stopping file watching."""
        assert route_manager._observer is None

        route_manager.start_watching()
        assert route_manager._observer is not None

        route_manager.stop_watching()
        assert route_manager._observer is None

    def test_start_watching_already_watching(self, route_manager):
        """Test that starting watch when already watching doesn't create duplicate."""
        route_manager.start_watching()
        observer1 = route_manager._observer

        route_manager.start_watching()
        observer2 = route_manager._observer

        assert observer1 is observer2

        route_manager.stop_watching()

    def test_file_watching_new_kml(self, temp_routes_dir):
        """Test that new KML files are detected."""
        manager = RouteManager(routes_dir=temp_routes_dir)
        manager.start_watching()

        # Initially no routes
        assert len(manager.list_routes()) == 0

        # Add a KML file
        kml_file = temp_routes_dir / "new_route.kml"
        kml_file.write_text(VALID_KML_CONTENT)

        # Wait a moment for watchdog to detect the change
        time.sleep(0.5)

        # Route should be detected
        routes = manager.list_routes()
        assert len(routes) == 1
        assert "new_route" in routes

        manager.stop_watching()

    def test_file_watching_deleted_kml(self, temp_routes_dir):
        """Test that deleted KML files are detected."""
        kml_file = temp_routes_dir / "delete_me.kml"
        kml_file.write_text(VALID_KML_CONTENT)

        manager = RouteManager(routes_dir=temp_routes_dir)
        manager.start_watching()

        assert len(manager.list_routes()) == 1

        # Delete the file
        kml_file.unlink()

        # Wait for watchdog to detect the change
        time.sleep(0.5)

        # Route should be removed
        routes = manager.list_routes()
        assert len(routes) == 0

        manager.stop_watching()

    def test_route_metadata(self, route_manager_with_file):
        """Test that route metadata is correctly populated."""
        routes = route_manager_with_file.list_routes()
        route_info = routes["route1"]

        assert route_info["id"] == "route1"
        assert route_info["name"] == "Test Route"
        assert route_info["point_count"] == 3
        assert "imported_at" in route_info
        assert route_info["is_active"] is False

    def test_multiple_routes(self, temp_routes_dir):
        """Test managing multiple routes."""
        for i in range(3):
            kml_file = temp_routes_dir / f"route{i}.kml"
            kml_file.write_text(VALID_KML_CONTENT)

        manager = RouteManager(routes_dir=temp_routes_dir)
        manager.start_watching()

        routes = manager.list_routes()
        assert len(routes) == 3

        # Activate one
        assert manager.activate_route("route1")
        assert not manager.activate_route("route1")  # Already active
        active = manager.get_active_route()
        assert active.metadata.name == "Test Route"

        manager.stop_watching()
