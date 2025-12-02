"""Unit tests for mission storage utilities."""

import json
import tempfile
from pathlib import Path

import pytest

from app.mission.models import Mission, MissionLeg, TransportConfig
from app.mission.storage import (
    compute_file_checksum,
    compute_mission_checksum,
    delete_mission,
    get_mission_checksum_path,
    get_mission_directory,
    get_mission_file_path,
    get_mission_leg_file_path,
    get_mission_legs_dir,
    get_mission_path,
    list_missions,
    load_mission,
    load_mission_v2,
    load_mission_metadata_v2,
    mission_exists,
    save_mission,
    save_mission_v2,
)


@pytest.fixture
def sample_mission():
    """Create a sample mission for testing."""
    return MissionLeg(
        id="test-mission-001",
        name="Test Mission",
        description="A test mission",
        route_id="test-route",
        transports=TransportConfig(initial_x_satellite_id="X-1"),
        notes="Test notes",
    )


@pytest.fixture
def temp_missions_dir(monkeypatch):
    """Create a temporary directory for mission storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)
        monkeypatch.setattr("app.mission.storage.MISSIONS_DIR", temp_path)
        yield temp_path


class TestMissionStorage:
    """Tests for mission storage functions."""

    def test_get_mission_path(self):
        """Test get_mission_path returns correct path."""
        path = get_mission_path("mission-001")
        assert "mission-001.json" in str(path)

    def test_get_mission_checksum_path(self):
        """Test get_mission_checksum_path returns correct path."""
        path = get_mission_checksum_path("mission-001")
        assert "mission-001.sha256" in str(path)

    def test_compute_mission_checksum(self, sample_mission):
        """Test mission checksum computation."""
        checksum1 = compute_mission_checksum(sample_mission)
        checksum2 = compute_mission_checksum(sample_mission)

        # Same mission should produce same checksum
        assert checksum1 == checksum2
        # Checksum should be 64 character hex string
        assert len(checksum1) == 64
        assert all(c in "0123456789abcdef" for c in checksum1)

    def test_save_mission(self, sample_mission, temp_missions_dir):
        """Test saving a mission."""
        result = save_mission(sample_mission)

        assert result["mission_id"] == "test-mission-001"
        assert "path" in result
        assert "checksum" in result
        assert "saved_at" in result

        # Verify file exists
        mission_file = temp_missions_dir / "test-mission-001.json"
        assert mission_file.exists()

        # Verify checksum file exists
        checksum_file = temp_missions_dir / "test-mission-001.sha256"
        assert checksum_file.exists()

    def test_load_mission(self, sample_mission, temp_missions_dir):
        """Test loading a saved mission."""
        # Save first
        save_mission(sample_mission)

        # Load
        loaded = load_mission("test-mission-001")

        assert loaded is not None
        assert loaded.id == "test-mission-001"
        assert loaded.name == "Test Mission"
        assert loaded.route_id == "test-route"
        assert loaded.notes == "Test notes"

    def test_load_mission_not_found(self, temp_missions_dir):
        """Test loading a non-existent mission."""
        loaded = load_mission("nonexistent-mission")
        assert loaded is None

    def test_mission_roundtrip(self, sample_mission, temp_missions_dir):
        """Test save and load roundtrip preserves data."""
        # Save
        save_mission(sample_mission)

        # Load
        loaded = load_mission("test-mission-001")

        # Verify all fields match
        assert loaded.id == sample_mission.id
        assert loaded.name == sample_mission.name
        assert loaded.route_id == sample_mission.route_id
        assert loaded.transports.initial_x_satellite_id == "X-1"
        assert loaded.notes == sample_mission.notes

    def test_mission_exists(self, sample_mission, temp_missions_dir):
        """Test mission_exists checks."""
        assert not mission_exists("test-mission-001")

        save_mission(sample_mission)

        assert mission_exists("test-mission-001")

    def test_delete_mission(self, sample_mission, temp_missions_dir):
        """Test deleting a mission."""
        save_mission(sample_mission)
        assert mission_exists("test-mission-001")

        deleted = delete_mission("test-mission-001")

        assert deleted is True
        assert not mission_exists("test-mission-001")

    def test_delete_nonexistent_mission(self, temp_missions_dir):
        """Test deleting a non-existent mission returns False."""
        deleted = delete_mission("nonexistent-mission")
        assert deleted is False

    def test_list_missions(self, temp_missions_dir):
        """Test listing missions."""
        # Create multiple missions
        for i in range(3):
            mission = MissionLeg(
                id=f"mission-{i:03d}",
                name=f"Test Mission {i}",
                route_id=f"route-{i}",
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            )
            save_mission(mission)

        missions = list_missions()

        assert len(missions) == 3
        ids = [m["id"] for m in missions]
        assert "mission-000" in ids
        assert "mission-001" in ids
        assert "mission-002" in ids

    def test_list_missions_empty(self, temp_missions_dir):
        """Test listing missions when none exist."""
        missions = list_missions()
        assert missions == []

    def test_mission_update_timestamp(self, sample_mission, temp_missions_dir):
        """Test that updated_at changes when mission is saved."""
        import time

        original_time = sample_mission.updated_at

        # Small delay to ensure timestamp changes
        time.sleep(0.01)

        save_mission(sample_mission)
        loaded = load_mission("test-mission-001")

        assert loaded.updated_at > original_time

    def test_compute_file_checksum(self, temp_missions_dir):
        """Test file checksum computation."""
        test_file = temp_missions_dir / "test-file.txt"
        test_file.write_text("test content")

        checksum = compute_file_checksum(test_file)

        # Verify checksum is valid hex
        assert len(checksum) == 64
        assert all(c in "0123456789abcdef" for c in checksum)

    def test_checksum_integrity(self, sample_mission, temp_missions_dir):
        """Test checksum verification on load."""
        save_mission(sample_mission)

        # Verify checksum matches
        loaded = load_mission("test-mission-001")
        assert loaded is not None

        # Modify the mission file directly
        mission_file = temp_missions_dir / "test-mission-001.json"
        data = json.loads(mission_file.read_text())
        data["name"] = "Modified Name"
        mission_file.write_text(json.dumps(data))

        # Should still load but checksum will differ (logged as warning)
        loaded_modified = load_mission("test-mission-001")
        assert loaded_modified.name == "Modified Name"

    def test_mission_with_complex_transports(self, temp_missions_dir, sample_mission):
        """Test saving/loading mission with complex transport configuration."""
        from datetime import datetime, timezone

        from app.mission.models import XTransition, AARWindow, KaOutage

        mission = MissionLeg(
            id="complex-mission",
            name="Complex Mission",
            route_id="complex-route",
            transports=TransportConfig(
                initial_x_satellite_id="X-1",
                x_transitions=[
                    XTransition(
                        id="trans-1",
                        latitude=35.0,
                        longitude=-120.0,
                        target_satellite_id="X-2",
                    ),
                ],
                aar_windows=[
                    AARWindow(
                        id="aar-1",
                        start_waypoint_name="AAR-Start",
                        end_waypoint_name="AAR-End",
                    ),
                ],
                ka_outages=[
                    KaOutage(
                        id="ka-out-1",
                        start_time=datetime.now(timezone.utc),
                        duration_seconds=300.0,
                    ),
                ],
            ),
        )

        save_mission(mission)
        loaded = load_mission("complex-mission")

        assert len(loaded.transports.x_transitions) == 1
        assert len(loaded.transports.aar_windows) == 1
        assert len(loaded.transports.ka_outages) == 1
        assert loaded.transports.x_transitions[0].target_satellite_id == "X-2"

    def test_list_missions_metadata(self, temp_missions_dir):
        """Test that list_missions returns correct metadata."""
        mission = MissionLeg(
            id="meta-mission",
            name="Metadata Test",
            route_id="meta-route",
            is_active=True,
            transports=TransportConfig(initial_x_satellite_id="X-1"),
        )
        save_mission(mission)

        missions = list_missions()

        assert len(missions) == 1
        meta = missions[0]
        assert meta["id"] == "meta-mission"
        assert meta["name"] == "Metadata Test"
        assert meta["route_id"] == "meta-route"
        assert meta["is_active"] is True


class TestHierarchicalMissionStorageV2:
    """Tests for hierarchical v2 mission storage (Mission with nested Legs)."""

    @pytest.fixture
    def sample_mission_with_legs(self):
        """Create a sample hierarchical mission with multiple legs."""
        leg1 = MissionLeg(
            id="leg-1",
            name="Leg 1",
            description="First leg",
            route_id="route-1",
            transports=TransportConfig(initial_x_satellite_id="X-1"),
            notes="First leg notes",
        )
        leg2 = MissionLeg(
            id="leg-2",
            name="Leg 2",
            description="Second leg",
            route_id="route-2",
            transports=TransportConfig(initial_x_satellite_id="X-2"),
            notes="Second leg notes",
        )

        return Mission(
            id="operation-falcon",
            name="Operation Falcon",
            description="Multi-leg transcontinental mission",
            legs=[leg1, leg2],
            metadata={"customer": "Test Corp", "classification": "unclassified"},
        )

    def test_save_mission_v2_creates_directory_structure(
        self, sample_mission_with_legs, temp_missions_dir
    ):
        """Test that save_mission_v2 creates correct directory structure."""
        result = save_mission_v2(sample_mission_with_legs)

        # Verify result metadata
        assert result["mission_id"] == "operation-falcon"
        assert result["leg_count"] == 2
        assert "path" in result
        assert "saved_at" in result

        # Verify mission directory exists
        mission_dir = temp_missions_dir / "operation-falcon"
        assert mission_dir.exists()
        assert mission_dir.is_dir()

        # Verify legs directory exists
        legs_dir = mission_dir / "legs"
        assert legs_dir.exists()
        assert legs_dir.is_dir()

    def test_save_mission_v2_saves_mission_metadata(
        self, sample_mission_with_legs, temp_missions_dir
    ):
        """Test that mission metadata is saved without legs."""
        save_mission_v2(sample_mission_with_legs)

        mission_file = temp_missions_dir / "operation-falcon" / "mission.json"
        assert mission_file.exists()

        # Load and verify content
        with open(mission_file, "r") as f:
            mission_data = json.load(f)

        assert mission_data["id"] == "operation-falcon"
        assert mission_data["name"] == "Operation Falcon"
        assert mission_data["description"] == "Multi-leg transcontinental mission"
        # Legs should be empty (stored separately)
        assert mission_data["legs"] == []
        assert mission_data["metadata"]["customer"] == "Test Corp"

    def test_save_mission_v2_saves_legs_separately(
        self, sample_mission_with_legs, temp_missions_dir
    ):
        """Test that each leg is saved to separate file."""
        save_mission_v2(sample_mission_with_legs)

        legs_dir = temp_missions_dir / "operation-falcon" / "legs"

        # Verify leg files exist
        leg1_file = legs_dir / "leg-1.json"
        leg2_file = legs_dir / "leg-2.json"

        assert leg1_file.exists()
        assert leg2_file.exists()

        # Verify leg 1 content
        with open(leg1_file, "r") as f:
            leg1_data = json.load(f)

        assert leg1_data["id"] == "leg-1"
        assert leg1_data["name"] == "Leg 1"
        assert leg1_data["description"] == "First leg"
        assert leg1_data["route_id"] == "route-1"
        assert leg1_data["notes"] == "First leg notes"

        # Verify leg 2 content
        with open(leg2_file, "r") as f:
            leg2_data = json.load(f)

        assert leg2_data["id"] == "leg-2"
        assert leg2_data["name"] == "Leg 2"
        assert leg2_data["description"] == "Second leg"
        assert leg2_data["route_id"] == "route-2"
        assert leg2_data["notes"] == "Second leg notes"

    def test_load_mission_v2_loads_metadata(
        self, sample_mission_with_legs, temp_missions_dir
    ):
        """Test that mission metadata is loaded correctly."""
        save_mission_v2(sample_mission_with_legs)

        loaded = load_mission_v2("operation-falcon")

        assert loaded is not None
        assert loaded.id == "operation-falcon"
        assert loaded.name == "Operation Falcon"
        assert loaded.description == "Multi-leg transcontinental mission"
        assert loaded.metadata["customer"] == "Test Corp"

    def test_load_mission_v2_loads_all_legs(
        self, sample_mission_with_legs, temp_missions_dir
    ):
        """Test that all legs are loaded and reconstructed."""
        save_mission_v2(sample_mission_with_legs)

        loaded = load_mission_v2("operation-falcon")

        # Verify legs are loaded
        assert len(loaded.legs) == 2

        # Verify leg 1
        assert loaded.legs[0].id == "leg-1"
        assert loaded.legs[0].name == "Leg 1"
        assert loaded.legs[0].route_id == "route-1"

        # Verify leg 2
        assert loaded.legs[1].id == "leg-2"
        assert loaded.legs[1].name == "Leg 2"
        assert loaded.legs[1].route_id == "route-2"

    def test_load_mission_v2_preserves_leg_order(
        self, sample_mission_with_legs, temp_missions_dir
    ):
        """Test that leg loading preserves sorted order."""
        save_mission_v2(sample_mission_with_legs)

        loaded = load_mission_v2("operation-falcon")

        # Legs should be sorted alphabetically by filename (leg-1.json, leg-2.json)
        leg_ids = [leg.id for leg in loaded.legs]
        assert leg_ids == ["leg-1", "leg-2"]

    def test_load_mission_v2_not_found(self, temp_missions_dir):
        """Test that loading nonexistent mission returns None."""
        loaded = load_mission_v2("nonexistent-mission")
        assert loaded is None

    def test_load_mission_v2_with_no_legs(self, temp_missions_dir):
        """Test loading mission with empty legs directory."""
        mission_dir = temp_missions_dir / "empty-mission"
        mission_dir.mkdir(parents=True, exist_ok=True)

        legs_dir = mission_dir / "legs"
        legs_dir.mkdir(parents=True, exist_ok=True)

        # Create mission.json
        mission_data = {
            "id": "empty-mission",
            "name": "Empty Mission",
            "description": None,
            "created_at": "2025-11-24T00:00:00+00:00",
            "updated_at": "2025-11-24T00:00:00+00:00",
            "metadata": {},
            "legs": [],
        }

        mission_file = mission_dir / "mission.json"
        with open(mission_file, "w") as f:
            json.dump(mission_data, f)

        # Load should succeed with empty legs list
        loaded = load_mission_v2("empty-mission")

        assert loaded is not None
        assert loaded.id == "empty-mission"
        assert len(loaded.legs) == 0

    def test_mission_v2_roundtrip(self, sample_mission_with_legs, temp_missions_dir):
        """Test that save and load v2 preserves complete mission structure."""
        # Save
        save_mission_v2(sample_mission_with_legs)

        # Load
        loaded = load_mission_v2("operation-falcon")

        # Verify complete structure
        assert loaded.id == sample_mission_with_legs.id
        assert loaded.name == sample_mission_with_legs.name
        assert loaded.description == sample_mission_with_legs.description
        assert len(loaded.legs) == len(sample_mission_with_legs.legs)

        # Verify first leg details
        assert loaded.legs[0].id == sample_mission_with_legs.legs[0].id
        assert loaded.legs[0].name == sample_mission_with_legs.legs[0].name
        assert (
            loaded.legs[0].transports.initial_x_satellite_id
            == sample_mission_with_legs.legs[0].transports.initial_x_satellite_id
        )

        # Verify second leg details
        assert loaded.legs[1].id == sample_mission_with_legs.legs[1].id
        assert loaded.legs[1].name == sample_mission_with_legs.legs[1].name

    def test_save_mission_v2_overwrites_existing(
        self, sample_mission_with_legs, temp_missions_dir
    ):
        """Test that saving existing mission overwrites files."""
        # Save first version
        save_mission_v2(sample_mission_with_legs)

        # Create modified version with different metadata
        modified_mission = Mission(
            id="operation-falcon",
            name="Operation Falcon (Updated)",
            description="Updated description",
            legs=sample_mission_with_legs.legs,
            metadata={"customer": "Updated Corp"},
        )

        # Save again
        save_mission_v2(modified_mission)

        # Load and verify overwrite
        loaded = load_mission_v2("operation-falcon")

        assert loaded.name == "Operation Falcon (Updated)"
        assert loaded.description == "Updated description"
        assert loaded.metadata["customer"] == "Updated Corp"

    def test_save_mission_v2_with_complex_transports(self, temp_missions_dir):
        """Test v2 storage with complex transport configurations."""
        from datetime import datetime, timezone

        from app.mission.models import AARWindow, KaOutage, XTransition

        leg = MissionLeg(
            id="complex-leg",
            name="Complex Leg",
            route_id="complex-route",
            transports=TransportConfig(
                initial_x_satellite_id="X-1",
                x_transitions=[
                    XTransition(
                        id="trans-1",
                        latitude=35.0,
                        longitude=-120.0,
                        target_satellite_id="X-2",
                    ),
                ],
                aar_windows=[
                    AARWindow(
                        id="aar-1",
                        start_waypoint_name="AAR-Start",
                        end_waypoint_name="AAR-End",
                    ),
                ],
                ka_outages=[
                    KaOutage(
                        id="ka-out-1",
                        start_time=datetime.now(timezone.utc),
                        duration_seconds=300.0,
                    ),
                ],
            ),
        )

        mission = Mission(
            id="complex-mission",
            name="Complex Mission",
            legs=[leg],
        )

        # Save and load
        save_mission_v2(mission)
        loaded = load_mission_v2("complex-mission")

        # Verify complex structures are preserved
        assert len(loaded.legs) == 1
        loaded_leg = loaded.legs[0]
        assert len(loaded_leg.transports.x_transitions) == 1
        assert len(loaded_leg.transports.aar_windows) == 1
        assert len(loaded_leg.transports.ka_outages) == 1
        assert loaded_leg.transports.x_transitions[0].target_satellite_id == "X-2"

    def test_get_mission_directory_path(self):
        """Test get_mission_directory returns correct path."""
        path = get_mission_directory("test-mission")
        assert "test-mission" in str(path)
        assert str(path).endswith("test-mission")

    def test_get_mission_file_path(self):
        """Test get_mission_file_path returns correct path."""
        path = get_mission_file_path("test-mission")
        assert "test-mission" in str(path)
        assert str(path).endswith("mission.json")

    def test_get_mission_legs_dir(self):
        """Test get_mission_legs_dir returns correct path."""
        path = get_mission_legs_dir("test-mission")
        assert "test-mission" in str(path)
        assert str(path).endswith("legs")

    def test_get_mission_leg_file_path(self):
        """Test get_mission_leg_file_path returns correct path."""
        path = get_mission_leg_file_path("test-mission", "leg-1")
        assert "test-mission" in str(path)
        assert "legs" in str(path)
        assert str(path).endswith("leg-1.json")

    def test_save_mission_v2_with_single_leg(self, temp_missions_dir):
        """Test v2 storage with single leg mission."""
        leg = MissionLeg(
            id="single-leg",
            name="Single Leg",
            route_id="route-1",
            transports=TransportConfig(initial_x_satellite_id="X-1"),
        )

        mission = Mission(
            id="single-mission",
            name="Single Mission",
            legs=[leg],
        )

        result = save_mission_v2(mission)

        assert result["leg_count"] == 1

        # Verify structure
        loaded = load_mission_v2("single-mission")
        assert len(loaded.legs) == 1
        assert loaded.legs[0].id == "single-leg"

    def test_load_mission_v2_handles_missing_mission_file(self, temp_missions_dir):
        """Test that load_mission_v2 handles missing mission.json gracefully."""
        # Create mission directory but no mission.json
        mission_dir = temp_missions_dir / "incomplete-mission"
        mission_dir.mkdir(parents=True, exist_ok=True)

        loaded = load_mission_v2("incomplete-mission")
        assert loaded is None

    def test_load_mission_metadata_v2_returns_leg_stubs(
        self, sample_mission_with_legs, temp_missions_dir
    ):
        """Test that metadata loading returns mission with leg stubs."""
        # Save mission with legs
        save_mission_v2(sample_mission_with_legs)

        # Load metadata only
        loaded = load_mission_metadata_v2("operation-falcon")

        assert loaded is not None
        assert loaded.id == "operation-falcon"
        assert loaded.name == "Operation Falcon"
        assert loaded.description == "Multi-leg transcontinental mission"
        assert loaded.metadata["customer"] == "Test Corp"
        # Critical: legs should contain stubs with correct count
        assert len(loaded.legs) == 2
        # Verify stubs have IDs but minimal data
        assert loaded.legs[0].id == "leg-1"
        assert loaded.legs[1].id == "leg-2"

    def test_load_mission_metadata_v2_not_found(self, temp_missions_dir):
        """Test metadata loading for non-existent mission."""
        loaded = load_mission_metadata_v2("nonexistent")
        assert loaded is None

    def test_load_mission_metadata_v2_preserves_metadata(
        self, sample_mission_with_legs, temp_missions_dir
    ):
        """Test that all metadata fields are preserved."""
        save_mission_v2(sample_mission_with_legs)

        loaded = load_mission_metadata_v2("operation-falcon")

        assert loaded is not None
        assert loaded.id == sample_mission_with_legs.id
        assert loaded.name == sample_mission_with_legs.name
        assert loaded.description == sample_mission_with_legs.description
        assert loaded.created_at == sample_mission_with_legs.created_at
        assert loaded.updated_at == sample_mission_with_legs.updated_at
        assert loaded.metadata == sample_mission_with_legs.metadata
        # Verify leg count matches
        assert len(loaded.legs) == len(sample_mission_with_legs.legs)

    def test_load_mission_metadata_v2_handles_invalid_json(self, temp_missions_dir):
        """Test that invalid JSON is handled gracefully."""
        # Create mission directory with invalid JSON
        mission_dir = temp_missions_dir / "invalid-mission"
        mission_dir.mkdir(parents=True, exist_ok=True)

        mission_file = mission_dir / "mission.json"
        mission_file.write_text("{invalid json content")

        loaded = load_mission_metadata_v2("invalid-mission")
        assert loaded is None

    def test_load_mission_metadata_v2_with_empty_mission(self, temp_missions_dir):
        """Test loading metadata for mission with no legs."""
        mission = Mission(
            id="empty-mission",
            name="Empty Mission",
            description="Mission with no legs",
            legs=[],
        )

        save_mission_v2(mission)
        loaded = load_mission_metadata_v2("empty-mission")

        assert loaded is not None
        assert loaded.id == "empty-mission"
        assert loaded.name == "Empty Mission"
        assert loaded.legs == []
