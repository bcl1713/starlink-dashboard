"""Integration tests for mission v2 API endpoints."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.mission.routes_v2 as mission_routes_v2
from app.mission.models import (
    Mission,
    MissionLeg,
    MissionLegTimeline,
    TimelineSegment,
    TimelineStatus,
    TransportConfig,
)
from app.mission.storage import load_mission_v2, save_mission_v2
from app.mission.timeline_service import TimelineSummary
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
from app.services.overview_clock_location import ClockLocation
from app.services.overview_clock_settings import OverviewClockSettingsStore
from main import app


class TestMissionV2ClockLifecycle:
    def test_deactivating_legs_resets_only_the_mission_clock_slots(
        self,
        client: TestClient,
        test_mission_v2,
        tmp_path,
    ):
        original_store = app.state.overview_clock_settings_store
        store = OverviewClockSettingsStore(
            tmp_path / "overview-clock-settings.json",
        )
        app.state.overview_clock_settings_store = store
        original_clocks = [
            ClockLocation(
                label="Zulu Custom",
                time_zone="UTC",
            ),
            ClockLocation(
                label="Denver, CO",
                time_zone="America/Denver",
            ),
            ClockLocation(
                label="Washington, DC",
                time_zone="America/New_York",
            ),
            ClockLocation(
                label="Paris, FR",
                time_zone="Europe/Paris",
            ),
        ]
        store.set_clocks(original_clocks)
        try:
            create_response = client.post(
                "/api/v2/missions",
                json=test_mission_v2.model_dump(mode="json"),
            )
            assert create_response.status_code == 201
            _add_activation_route(client, test_mission_v2.legs[0])
            with patch(
                "app.mission.routes_v2.build_mission_timeline",
                side_effect=lambda mission, **_kwargs: _activation_timeline(mission.id),
            ):
                assert (
                    client.post(
                        f"/api/v2/missions/{test_mission_v2.id}/legs/"
                        f"{test_mission_v2.legs[0].id}/activate",
                    ).status_code
                    == 200
                )
            deactivate_response = client.post(
                f"/api/v2/missions/{test_mission_v2.id}/legs/deactivate",
            )
            assert deactivate_response.status_code == 200
            assert store.get_clocks() == [
                original_clocks[0],
                original_clocks[1],
                ClockLocation(
                    label="Omaha, NE",
                    time_zone="America/Chicago",
                ),
                ClockLocation(
                    label="Tokyo, JP",
                    time_zone="Asia/Tokyo",
                ),
            ]
        finally:
            app.state.overview_clock_settings_store = original_store

    def test_activating_a_leg_replaces_the_two_mission_clock_slots(
        self,
        client: TestClient,
        test_mission_v2,
        tmp_path,
    ):
        original_store = app.state.overview_clock_settings_store
        store = OverviewClockSettingsStore(
            tmp_path / "overview-clock-settings.json",
        )
        app.state.overview_clock_settings_store = store
        route_manager = app.state.route_manager
        route_id = test_mission_v2.legs[0].route_id
        original_route = route_manager.get_route(route_id)
        route_manager.add_route(
            route_id,
            ParsedRoute(
                metadata=RouteMetadata(
                    name="Clock lifecycle route",
                    file_path="/tmp/clock-lifecycle-route.kml",
                    point_count=2,
                ),
                points=[
                    RoutePoint(
                        latitude=38.9072,
                        longitude=-77.0369,
                    ),
                    RoutePoint(
                        latitude=48.8566,
                        longitude=2.3522,
                    ),
                ],
            ),
        )
        original_clocks = [
            ClockLocation(
                label="Zulu Custom",
                time_zone="UTC",
            ),
            ClockLocation(
                label="Denver, CO",
                time_zone="America/Denver",
            ),
            ClockLocation(
                label="Manual Takeoff",
                time_zone="America/Los_Angeles",
            ),
            ClockLocation(
                label="Manual Landing",
                time_zone="Europe/London",
            ),
        ]
        store.set_clocks(original_clocks)
        try:
            create_response = client.post(
                "/api/v2/missions",
                json=test_mission_v2.model_dump(mode="json"),
            )
            assert create_response.status_code == 201
            with patch(
                "app.mission.routes_v2.build_mission_timeline",
                side_effect=lambda mission, **_kwargs: _activation_timeline(mission.id),
            ):
                activate_response = client.post(
                    f"/api/v2/missions/{test_mission_v2.id}/legs/"
                    f"{test_mission_v2.legs[0].id}/activate",
                )
            assert activate_response.status_code == 200
            assert store.get_clocks() == [
                original_clocks[0],
                original_clocks[1],
                ClockLocation(
                    label="Washington, DC",
                    time_zone="America/New_York",
                ),
                ClockLocation(
                    label="Paris, FR",
                    time_zone="Europe/Paris",
                ),
            ]
        finally:
            app.state.overview_clock_settings_store = original_store
            if original_route is None:
                route_manager._routes.pop(route_id, None)
            else:
                route_manager.add_route(route_id, original_route)

    def test_deactivating_legs_persists_mission_when_clock_write_fails(
        self,
        client: TestClient,
        test_mission_v2,
        monkeypatch,
        caplog,
    ):
        assert (
            client.post(
                "/api/v2/missions",
                json=test_mission_v2.model_dump(mode="json"),
            ).status_code
            == 201
        )
        _add_activation_route(client, test_mission_v2.legs[0])
        with patch(
            "app.mission.routes_v2.build_mission_timeline",
            side_effect=lambda mission, **_kwargs: _activation_timeline(mission.id),
        ):
            assert (
                client.post(
                    f"/api/v2/missions/{test_mission_v2.id}/legs/"
                    f"{test_mission_v2.legs[0].id}/activate",
                ).status_code
                == 200
            )
        monkeypatch.setattr(
            mission_routes_v2,
            "apply_mission_deactivation_clock_settings",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")),
        )

        response = client.post(
            f"/api/v2/missions/{test_mission_v2.id}/legs/deactivate",
        )

        assert response.status_code == 200
        mission = client.get(f"/api/v2/missions/{test_mission_v2.id}").json()
        assert mission["legs"][0]["is_active"] is False
        assert (
            "Could not persist overview clock settings after deactivating mission legs"
            in caplog.text
        )

    def test_deactivating_legs_skips_corrupt_clock_settings_without_blocking_mission(
        self,
        client: TestClient,
        test_mission_v2,
        tmp_path,
        caplog,
    ):
        original_store = app.state.overview_clock_settings_store
        path = tmp_path / "overview-clock-settings.json"
        store = OverviewClockSettingsStore(path)
        app.state.overview_clock_settings_store = store
        corrupt_settings = b'{"clocks": ['
        try:
            assert (
                client.post(
                    "/api/v2/missions",
                    json=test_mission_v2.model_dump(mode="json"),
                ).status_code
                == 201
            )
            _add_activation_route(client, test_mission_v2.legs[0])
            with patch(
                "app.mission.routes_v2.build_mission_timeline",
                side_effect=lambda mission, **_kwargs: _activation_timeline(mission.id),
            ):
                assert (
                    client.post(
                        f"/api/v2/missions/{test_mission_v2.id}/legs/"
                        f"{test_mission_v2.legs[0].id}/activate",
                    ).status_code
                    == 200
                )
            path.write_bytes(corrupt_settings)

            response = client.post(
                f"/api/v2/missions/{test_mission_v2.id}/legs/deactivate",
            )

            assert response.status_code == 200
            assert (
                client.get(f"/api/v2/missions/{test_mission_v2.id}").json()["legs"][0][
                    "is_active"
                ]
                is False
            )
            assert path.read_bytes() == corrupt_settings
            assert (
                "Skipped overview clock settings persistence after deactivating "
                "mission legs because stored settings are invalid" in caplog.text
            )
        finally:
            app.state.overview_clock_settings_store = original_store


@pytest.fixture
def test_mission_v2():
    """Create a test mission object with unique ID."""
    unique_id = f"test-mission-v2-{uuid4().hex[:8]}"
    leg_id = f"test-leg-{uuid4().hex[:8]}"

    leg = MissionLeg(
        id=leg_id,
        name="Test Leg",
        description="A test leg",
        route_id="test-route-001",
        transports=TransportConfig(
            initial_x_satellite_id="X-1",
            initial_ka_satellite_ids=["AOR"],
        ),
        is_active=False,
    )

    return Mission(
        id=unique_id,
        name="Test Mission V2",
        description="A test mission v2",
        legs=[leg],
    )


@pytest.fixture
def two_parent_missions():
    """Provide two stored parents whose legs use different routes."""
    suffix = uuid4().hex[:8]
    mission_a = Mission(
        id=f"mission-a-{suffix}",
        name="Mission A",
        legs=[
            MissionLeg(
                id=f"leg-a-{suffix}",
                name="Leg A",
                route_id=f"route-a-{suffix}",
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            )
        ],
    )
    mission_b = Mission(
        id=f"mission-b-{suffix}",
        name="Mission B",
        legs=[
            MissionLeg(
                id=f"leg-b-{suffix}",
                name="Leg B",
                route_id=f"route-b-{suffix}",
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            )
        ],
    )
    save_mission_v2(mission_a)
    save_mission_v2(mission_b)
    return mission_a, mission_b


def _activation_timeline(leg_id: str) -> tuple[MissionLegTimeline, TimelineSummary]:
    now = datetime.now(timezone.utc)
    timeline = MissionLegTimeline(
        mission_leg_id=leg_id,
        segments=[
            TimelineSegment(
                id=f"segment-{leg_id}",
                start_time=now,
                end_time=now + timedelta(minutes=1),
                status=TimelineStatus.NOMINAL,
            )
        ],
    )
    return timeline, TimelineSummary(
        mission_start=now,
        mission_end=now + timedelta(minutes=1),
        degraded_seconds=0,
        critical_seconds=0,
        next_conflict_seconds=-1,
        transport_states={},
        sample_count=1,
        sample_interval_seconds=60,
        generation_runtime_ms=1,
    )


def _add_activation_routes(
    client: TestClient, missions: tuple[Mission, Mission]
) -> None:
    for mission in missions:
        _add_activation_route(client, mission.legs[0])


def _add_activation_route(client: TestClient, leg: MissionLeg) -> None:
    route_manager = client.app.state.route_manager
    route_manager.add_route(
        leg.route_id,
        ParsedRoute(
            metadata=RouteMetadata(
                name=leg.route_id,
                file_path=f"/tmp/{leg.route_id}.kml",
                point_count=2,
            ),
            points=[
                RoutePoint(latitude=0.0, longitude=0.0),
                RoutePoint(latitude=1.0, longitude=1.0),
            ],
        ),
    )


class TestMissionV2GlobalActivationLifecycle:
    def test_activation_clears_active_leg_in_other_parent(
        self, client: TestClient, two_parent_missions
    ):
        mission_a, mission_b = two_parent_missions
        _add_activation_routes(client, two_parent_missions)

        with patch(
            "app.mission.routes_v2.build_mission_timeline",
            side_effect=lambda mission, **_kwargs: _activation_timeline(mission.id),
        ):
            assert (
                client.post(
                    f"/api/v2/missions/{mission_a.id}/legs/{mission_a.legs[0].id}/activate"
                ).status_code
                == 200
            )
            response = client.post(
                f"/api/v2/missions/{mission_b.id}/legs/{mission_b.legs[0].id}/activate"
            )

        assert response.status_code == 200
        assert load_mission_v2(mission_a.id).legs[0].is_active is False
        assert load_mission_v2(mission_b.id).legs[0].is_active is True
        assert (
            client.app.state.route_manager.get_active_route_id()
            == mission_b.legs[0].route_id
        )

    def test_route_activation_failure_restores_flags_and_returns_non_2xx(
        self, client: TestClient, monkeypatch, two_parent_missions
    ):
        mission_a, mission_b = two_parent_missions
        _add_activation_routes(client, two_parent_missions)
        with patch(
            "app.mission.routes_v2.build_mission_timeline",
            side_effect=lambda mission, **_kwargs: _activation_timeline(mission.id),
        ):
            assert (
                client.post(
                    f"/api/v2/missions/{mission_a.id}/legs/{mission_a.legs[0].id}/activate"
                ).status_code
                == 200
            )
            monkeypatch.setattr(
                client.app.state.route_manager,
                "activate_route",
                lambda _route_id: False,
            )
            response = client.post(
                f"/api/v2/missions/{mission_b.id}/legs/{mission_b.legs[0].id}/activate"
            )

        assert response.status_code >= 400
        assert load_mission_v2(mission_a.id).legs[0].is_active is True
        assert load_mission_v2(mission_b.id).legs[0].is_active is False

    def test_timeline_failure_restores_flags_and_returns_non_2xx(
        self, client: TestClient, monkeypatch, two_parent_missions
    ):
        mission_a, mission_b = two_parent_missions
        _add_activation_routes(client, two_parent_missions)
        with patch(
            "app.mission.routes_v2.build_mission_timeline",
            side_effect=lambda mission, **_kwargs: _activation_timeline(mission.id),
        ):
            assert (
                client.post(
                    f"/api/v2/missions/{mission_a.id}/legs/{mission_a.legs[0].id}/activate"
                ).status_code
                == 200
            )

        def raise_timeline_error(*_args, **_kwargs):
            raise RuntimeError("timeline failed")

        monkeypatch.setattr(
            mission_routes_v2, "build_mission_timeline", raise_timeline_error
        )
        response = client.post(
            f"/api/v2/missions/{mission_b.id}/legs/{mission_b.legs[0].id}/activate"
        )

        assert response.status_code >= 400
        assert load_mission_v2(mission_a.id).legs[0].is_active is True
        assert load_mission_v2(mission_b.id).legs[0].is_active is False
        assert (
            client.app.state.route_manager.get_active_route_id()
            == mission_a.legs[0].route_id
        )

    def test_deactivating_an_inactive_parent_preserves_active_route_and_clocks(
        self, client: TestClient, monkeypatch, two_parent_missions
    ):
        mission_a, mission_b = two_parent_missions
        _add_activation_routes(client, two_parent_missions)
        clock_updates = []
        monkeypatch.setattr(
            mission_routes_v2,
            "apply_mission_deactivation_clock_settings",
            lambda *_args, **_kwargs: clock_updates.append("deactivated"),
        )
        with patch(
            "app.mission.routes_v2.build_mission_timeline",
            side_effect=lambda mission, **_kwargs: _activation_timeline(mission.id),
        ):
            assert (
                client.post(
                    f"/api/v2/missions/{mission_b.id}/legs/{mission_b.legs[0].id}/activate"
                ).status_code
                == 200
            )

        response = client.post(f"/api/v2/missions/{mission_a.id}/legs/deactivate")

        assert response.status_code == 200
        assert (
            client.app.state.route_manager.get_active_route_id()
            == mission_b.legs[0].route_id
        )
        assert clock_updates == []
        assert load_mission_v2(mission_b.id).legs[0].is_active is True


@pytest.fixture(autouse=True)
def cleanup_test_missions_v2():
    """Clean up test missions after each test."""
    yield
    # Clean up after test

    # Note: list_missions returns dicts, check keys
    # But wait, list_missions in storage.py lists V1 missions (flat).
    # V2 missions are directories.
    # We should rely on the test to delete, or implement a cleanup that scans directories.
    # For now, we'll try to delete specifically created missions in tests if possible,
    # or rely on unique IDs to avoid collision.


class TestMissionV2CreateEndpoint:
    """Tests for POST /api/v2/missions endpoint."""

    def test_create_mission_triggers_timeline_generation(
        self, client: TestClient, test_mission_v2
    ):
        """Test that creating a mission triggers timeline generation for its legs."""

        # Mock build_mission_timeline and save_mission_timeline
        with (
            patch("app.mission.routes_v2.build_mission_timeline") as mock_build,
            patch("app.mission.routes_v2.save_mission_timeline") as mock_save,
        ):
            # Setup mock return values
            now = datetime.now(timezone.utc)
            segment = TimelineSegment(
                id="seg-1",
                start_time=now,
                end_time=now + timedelta(hours=1),
                status=TimelineStatus.NOMINAL,
            )
            timeline = MissionLegTimeline(
                mission_leg_id=test_mission_v2.legs[0].id, segments=[segment]
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
            mock_build.return_value = (timeline, summary)

            # Call endpoint
            response = client.post(
                "/api/v2/missions",
                json=test_mission_v2.model_dump(mode="json"),
            )

            assert response.status_code == 201

            # Verify build_mission_timeline was called
            assert mock_build.called
            # Verify save_mission_timeline was called
            assert mock_save.called

            # Verify arguments
            call_args = mock_save.call_args
            assert call_args[0][0] == test_mission_v2.legs[0].id
            assert call_args[0][1] == timeline


class TestMissionV2ListEndpoint:
    """Tests for the paginated v2 mission listing contract."""

    def test_cors_exposes_total_header_to_the_mission_planner(self, client):
        """Browser clients can read the pagination total from a CORS response."""
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:5173"},
        )

        assert response.status_code == 200
        assert response.headers["access-control-expose-headers"] == "X-Total-Count"

    def test_list_missions_returns_total_header_and_requested_page(self, monkeypatch):
        """The additive total header lets clients paginate without breaking arrays."""
        from fastapi import Response

        from app.mission.routes_v2 import list_missions

        missions = [
            Mission(id=f"mission-{index}", name=f"Mission {index}")
            for index in range(26)
        ]
        monkeypatch.setattr(
            "app.mission.routes_v2.list_mission_metadata_v2",
            lambda: missions,
        )
        response = Response()

        page = asyncio.run(list_missions(response, limit=25, offset=25))

        assert response.headers["X-Total-Count"] == "26"
        assert [mission.id for mission in page] == ["mission-25"]


class TestMissionV2UpdateEndpoint:
    """Tests for PATCH /api/v2/missions/{mission_id} endpoint."""

    def test_update_mission_name(self, client: TestClient, test_mission_v2):
        """Test updating mission name."""
        # Create mission first
        create_response = client.post(
            "/api/v2/missions",
            json=test_mission_v2.model_dump(mode="json"),
        )
        assert create_response.status_code == 201

        # Update name
        new_name = "Updated Mission Name"
        update_response = client.patch(
            f"/api/v2/missions/{test_mission_v2.id}",
            json={"name": new_name},
        )
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["name"] == new_name
        assert data["description"] == test_mission_v2.description

        # Verify updated_at changed
        assert data["updated_at"] != data["created_at"]

    def test_update_mission_description(self, client: TestClient, test_mission_v2):
        """Test updating mission description."""
        # Create mission first
        create_response = client.post(
            "/api/v2/missions",
            json=test_mission_v2.model_dump(mode="json"),
        )
        assert create_response.status_code == 201

        # Update description
        new_description = "This is a new detailed description of the mission"
        update_response = client.patch(
            f"/api/v2/missions/{test_mission_v2.id}",
            json={"description": new_description},
        )
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["name"] == test_mission_v2.name
        assert data["description"] == new_description

        # Verify updated_at changed
        assert data["updated_at"] != data["created_at"]

    def test_update_mission_both_fields(self, client: TestClient, test_mission_v2):
        """Test updating both name and description at once."""
        # Create mission first
        create_response = client.post(
            "/api/v2/missions",
            json=test_mission_v2.model_dump(mode="json"),
        )
        assert create_response.status_code == 201

        # Update both fields
        new_name = "New Mission Name"
        new_description = "New mission description"
        update_response = client.patch(
            f"/api/v2/missions/{test_mission_v2.id}",
            json={"name": new_name, "description": new_description},
        )
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["name"] == new_name
        assert data["description"] == new_description

    def test_update_mission_empty_name_validation_error(
        self, client: TestClient, test_mission_v2
    ):
        """Test that empty name triggers validation error."""
        # Create mission first
        create_response = client.post(
            "/api/v2/missions",
            json=test_mission_v2.model_dump(mode="json"),
        )
        assert create_response.status_code == 201

        # Try to update with empty name
        update_response = client.patch(
            f"/api/v2/missions/{test_mission_v2.id}",
            json={"name": ""},
        )
        assert update_response.status_code == 422

    def test_update_mission_whitespace_name_validation_error(
        self, client: TestClient, test_mission_v2
    ):
        """Test that whitespace-only name triggers validation error."""
        # Create mission first
        create_response = client.post(
            "/api/v2/missions",
            json=test_mission_v2.model_dump(mode="json"),
        )
        assert create_response.status_code == 201

        # Try to update with whitespace name
        update_response = client.patch(
            f"/api/v2/missions/{test_mission_v2.id}",
            json={"name": "   "},
        )
        assert update_response.status_code == 422

    def test_update_mission_not_found(self, client: TestClient):
        """Test updating nonexistent mission returns 404."""
        update_response = client.patch(
            "/api/v2/missions/nonexistent-mission-id",
            json={"name": "New Name"},
        )
        assert update_response.status_code == 404

    def test_update_mission_timestamp_changes(
        self, client: TestClient, test_mission_v2
    ):
        """Test that updated_at timestamp changes on update."""
        import time

        # Create mission first
        create_response = client.post(
            "/api/v2/missions",
            json=test_mission_v2.model_dump(mode="json"),
        )
        assert create_response.status_code == 201
        created_data = create_response.json()

        # Wait a moment to ensure timestamp difference
        time.sleep(0.1)

        # Update mission
        update_response = client.patch(
            f"/api/v2/missions/{test_mission_v2.id}",
            json={"name": "Updated Name"},
        )
        assert update_response.status_code == 200
        updated_data = update_response.json()

        # Verify updated_at changed
        assert updated_data["updated_at"] > created_data["updated_at"]
        # Verify created_at stayed the same
        assert updated_data["created_at"] == created_data["created_at"]


class TestMissionPackageImportLimits:
    """Regression coverage for the mission-package upload contract."""

    def test_import_rejects_an_oversize_package_with_attributable_413(self, client):
        """The application layer preserves its documented package-size rejection."""
        package = b"x" * (100 * 1024 * 1024 + 1)

        response = client.post(
            "/api/v2/missions/import",
            files={"file": ("oversize.zip", package, "application/zip")},
        )

        assert response.status_code == 413
        assert response.json()["detail"] == {
            "code": "mission_package_too_large",
            "layer": "application",
            "max_bytes": 100 * 1024 * 1024,
            "received_bytes": len(package),
        }
