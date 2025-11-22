"""Unit tests for POI manager functionality."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from app.models.poi import POICreate, POIUpdate
from app.services.poi_manager import POIManager


@pytest.fixture
def temp_pois_file():
    """Create temporary POI file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pois_file = Path(tmpdir) / "pois.json"
        yield pois_file


@pytest.fixture
def poi_manager(temp_pois_file):
    """Create a POI manager with temp file."""
    return POIManager(pois_file=temp_pois_file)


class TestPOIManager:
    """Test suite for POI manager."""

    def test_initialization(self, poi_manager):
        """Test POI manager initialization."""
        assert poi_manager.pois_file.exists()
        assert len(poi_manager.list_pois()) == 0

    def test_create_poi(self, poi_manager):
        """Test creating a POI."""
        poi_create = POICreate(
            name="Test POI",
            latitude=40.7128,
            longitude=-74.0060,
            icon="marker",
            category="test",
            description="A test POI",
        )

        poi = poi_manager.create_poi(poi_create)

        assert poi.id is not None
        assert poi.name == "Test POI"
        assert poi.latitude == 40.7128
        assert poi.longitude == -74.0060
        assert poi.icon == "marker"
        assert poi.category == "test"
        assert poi.description == "A test POI"
        assert poi.created_at is not None
        assert poi.updated_at is not None

    def test_create_poi_without_optional_fields(self, poi_manager):
        """Test creating POI with minimal fields."""
        poi_create = POICreate(name="Minimal POI", latitude=0.0, longitude=0.0)

        poi = poi_manager.create_poi(poi_create)

        assert poi.name == "Minimal POI"
        assert poi.icon == "marker"
        assert poi.category is None
        assert poi.description is None

    def test_list_pois(self, poi_manager):
        """Test listing POIs."""
        poi_create1 = POICreate(name="POI 1", latitude=1.0, longitude=1.0)
        poi_create2 = POICreate(name="POI 2", latitude=2.0, longitude=2.0)

        poi_manager.create_poi(poi_create1)
        poi_manager.create_poi(poi_create2)

        pois = poi_manager.list_pois()
        assert len(pois) == 2

    def test_get_poi(self, poi_manager):
        """Test retrieving a specific POI."""
        poi_create = POICreate(name="Test POI", latitude=40.0, longitude=-74.0)
        created_poi = poi_manager.create_poi(poi_create)

        retrieved_poi = poi_manager.get_poi(created_poi.id)

        assert retrieved_poi is not None
        assert retrieved_poi.id == created_poi.id
        assert retrieved_poi.name == "Test POI"

    def test_get_nonexistent_poi(self, poi_manager):
        """Test retrieving non-existent POI."""
        poi = poi_manager.get_poi("nonexistent")
        assert poi is None

    def test_update_poi(self, poi_manager):
        """Test updating a POI."""
        poi_create = POICreate(name="Original", latitude=40.0, longitude=-74.0)
        created_poi = poi_manager.create_poi(poi_create)

        poi_update = POIUpdate(name="Updated", category="updated_category")
        updated_poi = poi_manager.update_poi(created_poi.id, poi_update)

        assert updated_poi is not None
        assert updated_poi.name == "Updated"
        assert updated_poi.category == "updated_category"
        assert updated_poi.latitude == 40.0  # Unchanged

    def test_update_nonexistent_poi(self, poi_manager):
        """Test updating non-existent POI."""
        poi_update = POIUpdate(name="Updated")
        result = poi_manager.update_poi("nonexistent", poi_update)
        assert result is None

    def test_delete_poi(self, poi_manager):
        """Test deleting a POI."""
        poi_create = POICreate(name="To Delete", latitude=1.0, longitude=1.0)
        created_poi = poi_manager.create_poi(poi_create)

        assert len(poi_manager.list_pois()) == 1

        success = poi_manager.delete_poi(created_poi.id)

        assert success is True
        assert len(poi_manager.list_pois()) == 0

    def test_delete_nonexistent_poi(self, poi_manager):
        """Test deleting non-existent POI."""
        success = poi_manager.delete_poi("nonexistent")
        assert success is False

    def test_count_pois(self, poi_manager):
        """Test counting POIs."""
        poi_create1 = POICreate(name="POI 1", latitude=1.0, longitude=1.0)
        poi_create2 = POICreate(name="POI 2", latitude=2.0, longitude=2.0)

        poi_manager.create_poi(poi_create1)
        poi_manager.create_poi(poi_create2)

        count = poi_manager.count_pois()
        assert count == 2

    def test_list_pois_by_route(self, poi_manager):
        """Test listing POIs filtered by route."""
        poi_create_global = POICreate(name="Global POI", latitude=1.0, longitude=1.0)
        poi_create_route1 = POICreate(
            name="Route1 POI", latitude=2.0, longitude=2.0, route_id="route1"
        )
        poi_create_route2 = POICreate(
            name="Route2 POI", latitude=3.0, longitude=3.0, route_id="route2"
        )

        poi_manager.create_poi(poi_create_global)
        poi_manager.create_poi(poi_create_route1)
        poi_manager.create_poi(poi_create_route2)

        # Get POIs for route1 (should include only route1 specific)
        route1_pois = poi_manager.list_pois(route_id="route1")
        assert len(route1_pois) == 1
        assert route1_pois[0].name == "Route1 POI"

        # Get POIs for route2
        route2_pois = poi_manager.list_pois(route_id="route2")
        assert len(route2_pois) == 1
        assert route2_pois[0].name == "Route2 POI"

    def test_count_pois_by_route(self, poi_manager):
        """Test counting POIs by route."""
        poi_create_global = POICreate(name="Global POI", latitude=1.0, longitude=1.0)
        poi_create_route1 = POICreate(
            name="Route1 POI", latitude=2.0, longitude=2.0, route_id="route1"
        )

        poi_manager.create_poi(poi_create_global)
        poi_manager.create_poi(poi_create_route1)

        count = poi_manager.count_pois(route_id="route1")
        assert count == 1

    def test_delete_route_pois(self, poi_manager):
        """Test deleting all POIs for a route."""
        poi_create_global = POICreate(name="Global POI", latitude=1.0, longitude=1.0)
        poi_create_route1 = POICreate(
            name="Route1 POI", latitude=2.0, longitude=2.0, route_id="route1"
        )
        poi_create_route2 = POICreate(
            name="Route2 POI", latitude=3.0, longitude=3.0, route_id="route2"
        )

        poi_manager.create_poi(poi_create_global)
        poi_manager.create_poi(poi_create_route1)
        poi_manager.create_poi(poi_create_route2)

        deleted_count = poi_manager.delete_route_pois("route1")

        assert deleted_count == 1
        remaining_pois = poi_manager.list_pois()
        assert len(remaining_pois) == 2
        assert any(p.name == "Global POI" for p in remaining_pois)

    def test_find_global_poi_by_name(self, poi_manager):
        """Ensure only global POIs are returned."""
        poi_manager.create_poi(POICreate(name="Sat", latitude=1.0, longitude=1.0))
        poi_manager.create_poi(
            POICreate(name="Sat", latitude=2.0, longitude=2.0, mission_id="mission-1")
        )
        poi_manager.create_poi(
            POICreate(name="Sat", latitude=3.0, longitude=3.0, route_id="route-1")
        )

        poi = poi_manager.find_global_poi_by_name("Sat")
        assert poi is not None
        assert poi.longitude == 1.0

    def test_delete_scoped_pois_by_names(self, poi_manager):
        """Delete mission/route scoped POIs matching satellite names."""
        poi_manager.create_poi(
            POICreate(name="X-Band-7", latitude=1.0, longitude=1.0, mission_id="mission-1")
        )
        poi_manager.create_poi(
            POICreate(name="X-Band-8", latitude=2.0, longitude=2.0, route_id="route-1")
        )
        poi_manager.create_poi(
            POICreate(name="X-Band-7", latitude=3.0, longitude=3.0)  # global
        )

        removed = poi_manager.delete_scoped_pois_by_names({"X-Band-7", "X-Band-8"})
        assert removed == 2
        remaining = poi_manager.list_pois()
        assert len(remaining) == 1
        assert remaining[0].name == "X-Band-7"
        assert remaining[0].mission_id is None and remaining[0].route_id is None

    def test_delete_mission_pois_by_category(self, poi_manager):
        """Ensure mission category deletions only remove targeted POIs."""
        poi_manager.create_poi(
            POICreate(
                name="Transition",
                latitude=1.0,
                longitude=1.0,
                mission_id="mission-1",
                category="mission-event",
            )
        )
        poi_manager.create_poi(
            POICreate(
                name="Ka Gap",
                latitude=2.0,
                longitude=2.0,
                mission_id="mission-1",
                category="mission-event",
            )
        )
        poi_manager.create_poi(
            POICreate(
                name="Other Mission",
                latitude=3.0,
                longitude=3.0,
                mission_id="mission-2",
                category="mission-event",
            )
        )

        removed = poi_manager.delete_mission_pois_by_category(
            "mission-1", {"mission-event"}
        )
        assert removed == 2
        remaining = poi_manager.list_pois(mission_id="mission-1")
        assert len(remaining) == 0
        other_mission_pois = poi_manager.list_pois(mission_id="mission-2")
        assert len(other_mission_pois) == 1
        assert other_mission_pois[0].name == "Other Mission"

    def test_delete_mission_pois_by_name_prefixes(self, poi_manager):
        poi_manager.create_poi(
            POICreate(
                name="Ka Coverage Exit - POR",
                latitude=1.0,
                longitude=1.0,
                mission_id="mission-1",
                category="mission-event",
            )
        )
        poi_manager.create_poi(
            POICreate(
                name="AAR Start 1 - WP",
                latitude=2.0,
                longitude=2.0,
                mission_id="mission-1",
                category="mission-event",
            )
        )

        removed = poi_manager.delete_mission_pois_by_name_prefixes(
            "mission-1", ["Ka Coverage Exit"]
        )
        assert removed == 1
        remaining = poi_manager.list_pois(mission_id="mission-1")
        assert len(remaining) == 1
        assert remaining[0].name.startswith("AAR Start")

    def test_persistence(self, temp_pois_file):
        """Test that POIs are persisted to file."""
        manager1 = POIManager(pois_file=temp_pois_file)
        poi_create = POICreate(name="Persistent POI", latitude=1.0, longitude=1.0)
        created_poi = manager1.create_poi(poi_create)

        # Create new manager instance and verify POI is still there
        manager2 = POIManager(pois_file=temp_pois_file)
        pois = manager2.list_pois()

        assert len(pois) == 1
        assert pois[0].name == "Persistent POI"
        assert pois[0].id == created_poi.id

    def test_reload_pois(self, poi_manager):
        """Test reloading POIs from disk."""
        poi_create = POICreate(name="POI 1", latitude=1.0, longitude=1.0)
        poi_manager.create_poi(poi_create)

        assert len(poi_manager.list_pois()) == 1

        # Reload from disk
        poi_manager.reload_pois()

        assert len(poi_manager.list_pois()) == 1

    def test_unique_id_generation(self, poi_manager):
        """Test that POI IDs are unique."""
        poi_create1 = POICreate(name="Test POI", latitude=1.0, longitude=1.0)
        poi_create2 = POICreate(name="Test POI", latitude=2.0, longitude=2.0)

        poi1 = poi_manager.create_poi(poi_create1)
        poi2 = poi_manager.create_poi(poi_create2)

        assert poi1.id != poi2.id

    def test_update_timestamp(self, poi_manager):
        """Test that updated_at changes on update."""
        poi_create = POICreate(name="Test POI", latitude=1.0, longitude=1.0)
        poi = poi_manager.create_poi(poi_create)

        original_updated_at = poi.updated_at

        # Small delay to ensure timestamp difference
        import time

        time.sleep(0.01)

        poi_update = POIUpdate(name="Updated Name")
        updated_poi = poi_manager.update_poi(poi.id, poi_update)

        assert updated_poi.updated_at > original_updated_at

    def test_file_structure(self, poi_manager, temp_pois_file):
        """Test that file has correct JSON structure."""
        poi_create = POICreate(name="Test POI", latitude=1.0, longitude=1.0)
        poi_manager.create_poi(poi_create)

        with open(temp_pois_file, "r") as f:
            data = json.load(f)

        assert "pois" in data
        assert "routes" in data
        assert isinstance(data["pois"], dict)
        assert len(data["pois"]) == 1

    def test_empty_pois_file_creation(self, temp_pois_file):
        """Test that empty pois file is created on first init."""
        assert not temp_pois_file.exists()

        POIManager(pois_file=temp_pois_file)

        assert temp_pois_file.exists()

        with open(temp_pois_file, "r") as f:
            data = json.load(f)

        assert "pois" in data
        assert "routes" in data
        assert len(data["pois"]) == 0

    def test_coordinates_validation(self, poi_manager):
        """Test creating POI with extreme coordinates."""
        # Valid extreme coordinates should work
        poi_create = POICreate(name="Extreme POI", latitude=85.0, longitude=179.9)
        poi = poi_manager.create_poi(poi_create)

        assert poi.latitude == 85.0
        assert poi.longitude == 179.9

    def test_special_characters_in_name(self, poi_manager):
        """Test POI with special characters in name."""
        poi_create = POICreate(
            name="POI: Test & Validation #1",
            latitude=1.0,
            longitude=1.0,
            description="Description with 'quotes' and \"double quotes\"",
        )

        poi = poi_manager.create_poi(poi_create)

        assert poi.name == "POI: Test & Validation #1"
        assert "quotes" in poi.description

    def test_longitude_conversion(self, poi_manager):
        """Test that longitude is converted to -180 to 180 range."""
        poi_create = POICreate(name="Test POI", latitude=0.0, longitude=270.0)
        assert poi_create.longitude == -90.0

    def test_create_poi_slugifies_newlines(self, poi_manager):
        """Ensure newline-heavy names still produce stable IDs."""
        poi_create = POICreate(
            name="X-Band\nBeam Swap",
            latitude=1.0,
            longitude=1.0,
            mission_id="mission-1",
        )
        poi = poi_manager.create_poi(poi_create)
        assert "x-band-beam-swap" in poi.id
