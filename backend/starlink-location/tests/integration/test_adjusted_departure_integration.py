"""Integration tests for adjusted departure time API endpoints."""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.mission.models import (
    Mission,
    MissionLeg,
    TransportConfig,
    TimelineSegment,
    TimelineStatus,
    MissionLegTimeline,
)
from app.mission.timeline_service import TimelineSummary
from app.models.route import ParsedRoute, RoutePoint, RouteTimingProfile, RouteMetadata


@pytest.fixture
def test_route_with_timing():
    """Create a mock route with timing information."""
    departure = datetime(2025, 10, 27, 16, 45, 0, tzinfo=timezone.utc)
    arrival = datetime(2025, 10, 27, 22, 15, 0, tzinfo=timezone.utc)

    return ParsedRoute(
        metadata=RouteMetadata(
            name="Test Route",
            file_path="test-route.kml",
            point_count=2,
        ),
        timing_profile=RouteTimingProfile(
            departure_time=departure,
            arrival_time=arrival,
        ),
        points=[
            RoutePoint(
                latitude=35.0,
                longitude=-120.0,
                altitude=10000.0,
                expected_arrival_time=departure,
            ),
            RoutePoint(
                latitude=36.0,
                longitude=-121.0,
                altitude=10000.0,
                expected_arrival_time=arrival,
            ),
        ],
        waypoints=[],
    )


@pytest.fixture
def mock_timeline_generation():
    """Mock timeline generation to avoid actual computation."""
    now = datetime.now(timezone.utc)
    segment = TimelineSegment(
        id="seg-1",
        start_time=now,
        end_time=now + timedelta(hours=1),
        status=TimelineStatus.NOMINAL,
    )
    timeline = MissionLegTimeline(
        mission_leg_id="test-leg",
        segments=[segment],
    )
    summary = TimelineSummary(
        mission_start=now,
        mission_end=now + timedelta(hours=1),
        degraded_seconds=0,
        critical_seconds=0,
        next_conflict_seconds=-1,
        transport_states={},
        sample_count=1,
        sample_interval_seconds=60,
        generation_runtime_ms=10,
    )
    return timeline, summary


class TestAddLegWithAdjustedDepartureTime:
    """Tests for POST /api/v2/missions/{mission_id}/legs with adjusted_departure_time."""

    def test_create_leg_with_adjusted_departure_time(
        self,
        client: TestClient,
        test_route_with_timing,
        mock_timeline_generation,
    ):
        """Test creating a leg with adjusted_departure_time field."""
        # Create parent mission first
        mission_id = f"test-mission-{uuid4().hex[:8]}"
        mission = Mission(
            id=mission_id,
            name="Test Mission",
            description="Test mission for adjusted departure",
            legs=[],
        )

        create_mission_response = client.post(
            "/api/v2/missions",
            json=mission.model_dump(mode="json"),
        )
        assert create_mission_response.status_code == 201

        # Create leg with adjusted departure time
        leg_id = f"test-leg-{uuid4().hex[:8]}"
        adjusted_time = "2025-10-27T17:25:00Z"  # 40 minutes later than original

        leg = MissionLeg(
            id=leg_id,
            name="Test Leg with Adjusted Time",
            route_id="test-route-001",
            transports=TransportConfig(initial_x_satellite_id="X-1"),
            adjusted_departure_time=adjusted_time,
        )

        with patch("app.mission.routes_v2.build_mission_timeline") as mock_build, patch(
            "app.mission.routes_v2.save_mission_timeline"
        ) as _mock_save:

            mock_build.return_value = mock_timeline_generation

            response = client.post(
                f"/api/v2/missions/{mission_id}/legs",
                json=leg.model_dump(mode="json"),
            )

            assert response.status_code == 201
            data = response.json()

            assert data["id"] == leg_id
            assert data["adjusted_departure_time"] == adjusted_time

        # Cleanup
        client.delete(f"/api/v2/missions/{mission_id}")

    def test_create_leg_without_adjusted_departure_time(
        self,
        client: TestClient,
        mock_timeline_generation,
    ):
        """Test creating a leg without adjusted_departure_time (None)."""
        # Create parent mission first
        mission_id = f"test-mission-{uuid4().hex[:8]}"
        mission = Mission(
            id=mission_id,
            name="Test Mission",
            legs=[],
        )

        create_mission_response = client.post(
            "/api/v2/missions",
            json=mission.model_dump(mode="json"),
        )
        assert create_mission_response.status_code == 201

        # Create leg without adjusted departure time
        leg_id = f"test-leg-{uuid4().hex[:8]}"

        leg = MissionLeg(
            id=leg_id,
            name="Test Leg",
            route_id="test-route-001",
            transports=TransportConfig(initial_x_satellite_id="X-1"),
            adjusted_departure_time=None,
        )

        with patch("app.mission.routes_v2.build_mission_timeline") as mock_build, patch(
            "app.mission.routes_v2.save_mission_timeline"
        ) as _mock_save:

            mock_build.return_value = mock_timeline_generation

            response = client.post(
                f"/api/v2/missions/{mission_id}/legs",
                json=leg.model_dump(mode="json"),
            )

            assert response.status_code == 201
            data = response.json()

            assert data["id"] == leg_id
            assert data["adjusted_departure_time"] is None

        # Cleanup
        client.delete(f"/api/v2/missions/{mission_id}")


class TestUpdateLegWithAdjustedDepartureTime:
    """Tests for PUT /api/v2/missions/{mission_id}/legs/{leg_id} with adjusted_departure_time."""

    def test_update_leg_to_set_adjusted_departure_time(
        self,
        client: TestClient,
        test_route_with_timing,
        mock_timeline_generation,
    ):
        """Test updating a leg to set adjusted_departure_time."""
        # Create mission with leg
        mission_id = f"test-mission-{uuid4().hex[:8]}"
        leg_id = f"test-leg-{uuid4().hex[:8]}"

        leg = MissionLeg(
            id=leg_id,
            name="Test Leg",
            route_id="test-route-001",
            transports=TransportConfig(initial_x_satellite_id="X-1"),
            adjusted_departure_time=None,
        )

        mission = Mission(
            id=mission_id,
            name="Test Mission",
            legs=[leg],
        )

        with patch("app.mission.routes_v2.build_mission_timeline") as mock_build, patch(
            "app.mission.routes_v2.save_mission_timeline"
        ) as _mock_save:

            mock_build.return_value = mock_timeline_generation

            create_response = client.post(
                "/api/v2/missions",
                json=mission.model_dump(mode="json"),
            )
            assert create_response.status_code == 201

            # Update leg to set adjusted departure time
            adjusted_time = "2025-10-27T16:05:00Z"  # 40 minutes earlier

            updated_leg = leg.model_copy(
                update={"adjusted_departure_time": adjusted_time}
            )

            # Mock route manager in app state to return test route for validation
            original_route_manager = client.app.state.route_manager
            mock_route_manager = MagicMock()
            mock_route_manager.get_route.return_value = test_route_with_timing
            client.app.state.route_manager = mock_route_manager

            try:
                with patch(
                    "app.mission.routes_v2.build_mission_timeline"
                ) as mock_build, patch(
                    "app.mission.routes_v2.save_mission_timeline"
                ) as _mock_save:

                    mock_build.return_value = mock_timeline_generation

                    update_response = client.put(
                        f"/api/v2/missions/{mission_id}/legs/{leg_id}",
                        json=updated_leg.model_dump(mode="json"),
                    )
            finally:
                # Restore original route manager
                client.app.state.route_manager = original_route_manager

            assert update_response.status_code == 200
            data = update_response.json()

            assert data["leg"]["adjusted_departure_time"] == adjusted_time
            assert data["warnings"] is None or data["warnings"] == []

        # Cleanup
        client.delete(f"/api/v2/missions/{mission_id}")

    def test_update_leg_to_clear_adjusted_departure_time(
        self,
        client: TestClient,
        test_route_with_timing,
        mock_timeline_generation,
    ):
        """Test updating a leg to clear adjusted_departure_time (set to null)."""
        # Create mission with leg that has adjusted time
        mission_id = f"test-mission-{uuid4().hex[:8]}"
        leg_id = f"test-leg-{uuid4().hex[:8]}"

        leg = MissionLeg(
            id=leg_id,
            name="Test Leg",
            route_id="test-route-001",
            transports=TransportConfig(initial_x_satellite_id="X-1"),
            adjusted_departure_time="2025-10-27T17:25:00Z",
        )

        mission = Mission(
            id=mission_id,
            name="Test Mission",
            legs=[leg],
        )

        with patch("app.mission.routes_v2.build_mission_timeline") as mock_build, patch(
            "app.mission.routes_v2.save_mission_timeline"
        ) as _mock_save:

            mock_build.return_value = mock_timeline_generation

            create_response = client.post(
                "/api/v2/missions",
                json=mission.model_dump(mode="json"),
            )
            assert create_response.status_code == 201

            # Update leg to clear adjusted departure time
            updated_leg = leg.model_copy(update={"adjusted_departure_time": None})

            update_response = client.put(
                f"/api/v2/missions/{mission_id}/legs/{leg_id}",
                json=updated_leg.model_dump(mode="json"),
            )

            assert update_response.status_code == 200
            data = update_response.json()

            assert data["leg"]["adjusted_departure_time"] is None

        # Cleanup
        client.delete(f"/api/v2/missions/{mission_id}")

    def test_update_leg_with_large_offset_returns_warning(
        self,
        client: TestClient,
        test_route_with_timing,
        mock_timeline_generation,
    ):
        """Test that updating a leg with large offset (> 8 hours) returns warning."""
        # Create mission with leg
        mission_id = f"test-mission-{uuid4().hex[:8]}"
        leg_id = f"test-leg-{uuid4().hex[:8]}"

        leg = MissionLeg(
            id=leg_id,
            name="Test Leg",
            route_id="test-route-001",
            transports=TransportConfig(initial_x_satellite_id="X-1"),
            adjusted_departure_time=None,
        )

        mission = Mission(
            id=mission_id,
            name="Test Mission",
            legs=[leg],
        )

        with patch("app.mission.routes_v2.build_mission_timeline") as mock_build, patch(
            "app.mission.routes_v2.save_mission_timeline"
        ) as _mock_save:

            mock_build.return_value = mock_timeline_generation

            create_response = client.post(
                "/api/v2/missions",
                json=mission.model_dump(mode="json"),
            )
            assert create_response.status_code == 201

            # Update leg with large offset (10 hours later)
            # Original: 2025-10-27T16:45:00Z, Adjusted: 2025-10-28T02:45:00Z
            adjusted_time = "2025-10-28T02:45:00Z"

            updated_leg = leg.model_copy(
                update={"adjusted_departure_time": adjusted_time}
            )

            # Mock route manager in app state to return test route for validation
            original_route_manager = client.app.state.route_manager
            mock_route_manager = MagicMock()
            mock_route_manager.get_route.return_value = test_route_with_timing
            client.app.state.route_manager = mock_route_manager

            try:
                with patch(
                    "app.mission.routes_v2.build_mission_timeline"
                ) as mock_build, patch(
                    "app.mission.routes_v2.save_mission_timeline"
                ) as _mock_save:

                    mock_build.return_value = mock_timeline_generation

                    update_response = client.put(
                        f"/api/v2/missions/{mission_id}/legs/{leg_id}",
                        json=updated_leg.model_dump(mode="json"),
                    )
            finally:
                # Restore original route manager
                client.app.state.route_manager = original_route_manager

            assert update_response.status_code == 200
            data = update_response.json()

            assert data["leg"]["adjusted_departure_time"] == adjusted_time
            assert (
                data["warnings"] is not None
            ), f"Expected warnings but got None. Full response: {data}"
            assert len(data["warnings"]) > 0
            assert "Large time shift detected" in data["warnings"][0]

        # Cleanup
        client.delete(f"/api/v2/missions/{mission_id}")


class TestRouteUpdateClearsAdjustedDepartureTime:
    """Tests for PUT /api/v2/missions/{mission_id}/legs/{leg_id}/route clearing adjusted_departure_time."""

    def test_route_update_clears_adjusted_departure_time(
        self,
        client: TestClient,
        tmp_path,
        mock_timeline_generation,
    ):
        """Test that uploading a new route KML clears the adjusted_departure_time field."""
        # Create mission with leg that has adjusted departure time
        mission_id = f"test-mission-{uuid4().hex[:8]}"
        leg_id = f"test-leg-{uuid4().hex[:8]}"

        leg = MissionLeg(
            id=leg_id,
            name="Test Leg",
            route_id="test-route-001",
            transports=TransportConfig(initial_x_satellite_id="X-1"),
            adjusted_departure_time="2025-10-27T17:25:00Z",
        )

        mission = Mission(
            id=mission_id,
            name="Test Mission",
            legs=[leg],
        )

        with patch("app.mission.routes_v2.build_mission_timeline") as mock_build, patch(
            "app.mission.routes_v2.save_mission_timeline"
        ) as _mock_save:

            mock_build.return_value = mock_timeline_generation

            create_response = client.post(
                "/api/v2/missions",
                json=mission.model_dump(mode="json"),
            )
            assert create_response.status_code == 201

            # Verify adjusted_departure_time is set
            get_response = client.get(f"/api/v2/missions/{mission_id}")
            assert get_response.status_code == 200
            mission_data = get_response.json()
            assert (
                mission_data["legs"][0]["adjusted_departure_time"]
                == "2025-10-27T17:25:00Z"
            )

            # Create a simple KML file for upload
            kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Test Route</name>
      <LineString>
        <coordinates>-120.0,35.0,10000 -121.0,36.0,10000</coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>"""

            kml_file = tmp_path / "new-route.kml"
            kml_file.write_text(kml_content)

            # Save original route manager and poi manager
            original_route_manager = client.app.state.route_manager
            original_poi_manager = client.app.state.poi_manager

            # Mock route manager for upload
            mock_route_manager = MagicMock()
            mock_route_manager.routes_dir = str(tmp_path)

            # Mock the old route
            mock_old_route = MagicMock()
            mock_old_route.metadata.file_path = str(tmp_path / "test-route-001.kml")

            # Mock the new route after upload
            mock_new_route = MagicMock()
            mock_new_route.metadata.file_path = str(tmp_path / "new-route.kml")

            # get_route returns old route first (for deletion), then new route (for validation)
            mock_route_manager.get_route.side_effect = [mock_old_route, mock_new_route]
            mock_route_manager._load_route_file = MagicMock()
            mock_route_manager._routes = {}

            mock_poi_manager = MagicMock()
            mock_poi_manager.delete_route_pois.return_value = 0

            # Replace app state with mocks
            client.app.state.route_manager = mock_route_manager
            client.app.state.poi_manager = mock_poi_manager

            try:
                # Upload new route via multipart form
                with open(kml_file, "rb") as f:
                    files = {
                        "file": (
                            "new-route.kml",
                            f,
                            "application/vnd.google-earth.kml+xml",
                        )
                    }

                    response = client.put(
                        f"/api/v2/missions/{mission_id}/legs/{leg_id}/route",
                        files=files,
                    )

                    assert response.status_code == 200
                    response_data = response.json()

                    # Verify adjusted_departure_time was cleared in the response
                    assert response_data["leg"]["adjusted_departure_time"] is None

                # Verify via GET that adjusted_departure_time is now None
                get_response_after = client.get(f"/api/v2/missions/{mission_id}")
                assert get_response_after.status_code == 200
                mission_data_after = get_response_after.json()
                assert mission_data_after["legs"][0]["adjusted_departure_time"] is None

            finally:
                # Restore original managers
                client.app.state.route_manager = original_route_manager
                client.app.state.poi_manager = original_poi_manager

        # Cleanup
        client.delete(f"/api/v2/missions/{mission_id}")
