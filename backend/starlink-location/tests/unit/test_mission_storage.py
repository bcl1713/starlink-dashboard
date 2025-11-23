"""Unit tests for mission storage utilities."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.mission.models import MissionLeg, TransportConfig
from app.mission.storage import (
    compute_file_checksum,
    compute_mission_checksum,
    delete_mission,
    get_mission_checksum_path,
    get_mission_path,
    list_missions,
    load_mission,
    mission_exists,
    save_mission,
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
            mission = Mission(
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

        mission = Mission(
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
        mission = Mission(
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
