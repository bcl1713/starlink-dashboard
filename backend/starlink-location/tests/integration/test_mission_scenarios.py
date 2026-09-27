"""Integration regression tests for scoped mission runtime persistence."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.mission.models import (
    Mission,
    MissionLeg,
    MissionLegTimeline,
    TimelineSegment,
    TimelineStatus,
    TransportConfig,
)
from app.mission.timeline_service import TimelineSummary
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint


def test_startup_and_v2_activation_leave_flat_legacy_artifacts_untouched(client):
    """The v2 runtime must neither read, migrate, nor delete v1 flat artifacts."""
    from app.mission import storage

    legacy_artifacts = {
        "legacy.json": b'{"id":"legacy"}',
        "legacy.sha256": b"legacy-checksum",
        "legacy-leg.timeline.json": b'{"mission_leg_id":"legacy-leg"}',
    }
    for name, contents in legacy_artifacts.items():
        (storage.MISSIONS_DIR / name).write_bytes(contents)

    leg = MissionLeg(
        id="scoped-leg",
        name="Scoped leg",
        route_id="scoped-route",
        transports=TransportConfig(initial_x_satellite_id="X-1"),
    )
    mission = Mission(id="scoped-mission", name="Scoped mission", legs=[leg])
    assert (
        client.post(
            "/api/v2/missions", json=mission.model_dump(mode="json")
        ).status_code
        == 201
    )

    client.app.state.route_manager.add_route(
        leg.route_id,
        ParsedRoute(
            metadata=RouteMetadata(
                name=leg.route_id,
                file_path="/tmp/scoped-route.kml",
                point_count=2,
            ),
            points=[
                RoutePoint(latitude=0.0, longitude=0.0),
                RoutePoint(latitude=1.0, longitude=1.0),
            ],
        ),
    )
    now = datetime.now(timezone.utc)
    timeline = MissionLegTimeline(
        mission_leg_id=leg.id,
        segments=[
            TimelineSegment(
                id="scoped-segment",
                start_time=now,
                end_time=now + timedelta(minutes=1),
                status=TimelineStatus.NOMINAL,
            )
        ],
    )
    summary = TimelineSummary(
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
    with patch(
        "app.mission.routes_v2.build_mission_timeline", return_value=(timeline, summary)
    ):
        response = client.post(
            f"/api/v2/missions/{mission.id}/legs/{leg.id}/activate",
        )

    assert response.status_code == 200
    assert {
        name: (storage.MISSIONS_DIR / name).read_bytes() for name in legacy_artifacts
    } == legacy_artifacts
