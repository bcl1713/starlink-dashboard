"""Regression tests for operator-created manual AAR tracks."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.mission.models import (
    ManualAARTrack,
    ManualAARTrackPoint,
    Mission,
    MissionLeg,
    TimelineStatus,
    TransportConfig,
)
from app.mission.storage import load_mission_v2, save_mission_v2
from app.mission.timeline_service import build_mission_timeline
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint, RouteTimingProfile


def _timed_manual_track_route(start: datetime) -> ParsedRoute:
    return ParsedRoute(
        metadata=RouteMetadata(
            name="Manual track route", file_path="manual-track.kml", point_count=3
        ),
        points=[
            RoutePoint(
                latitude=60.0,
                longitude=-50.0,
                sequence=0,
                expected_arrival_time=start,
            ),
            RoutePoint(
                latitude=40.0,
                longitude=-50.0,
                sequence=1,
                expected_arrival_time=start + timedelta(hours=1),
            ),
            RoutePoint(
                latitude=20.0,
                longitude=-50.0,
                sequence=2,
                expected_arrival_time=start + timedelta(hours=2),
            ),
        ],
        timing_profile=RouteTimingProfile(
            departure_time=start,
            arrival_time=start + timedelta(hours=2),
            has_timing_data=True,
            segment_count_with_timing=3,
        ),
    )


def test_manual_aar_track_persists_ordered_deviation_points(isolate_mission_storage):
    """A manual track remains separate from the planned route after reload."""
    track = ManualAARTrack(
        id="deviation-track",
        name="Deviation AR",
        points=[
            ManualAARTrackPoint(latitude=35.0, longitude=179.5),
            ManualAARTrackPoint(latitude=35.2, longitude=-179.7),
        ],
    )
    mission = Mission(
        id="manual-track-mission",
        name="Manual track mission",
        legs=[
            MissionLeg(
                id="deviation-leg",
                name="Deviation leg",
                route_id="planned-route",
                transports=TransportConfig(
                    initial_x_satellite_id="X-1", manual_aar_tracks=[track]
                ),
            )
        ],
    )

    save_mission_v2(mission)
    reloaded = load_mission_v2(mission.id)

    assert reloaded is not None
    saved_track = reloaded.legs[0].transports.manual_aar_tracks[0]
    assert saved_track.name == "Deviation AR"
    assert [(point.latitude, point.longitude) for point in saved_track.points] == [
        (35.0, 179.5),
        (35.2, -179.7),
    ]


@pytest.mark.parametrize(
    "points, message",
    [
        ([{"latitude": 35.0, "longitude": -120.0}], "at least two points"),
        (
            [
                {"latitude": 35.0, "longitude": -120.0},
                {"latitude": 35.0, "longitude": -120.0},
            ],
            "duplicate consecutive point",
        ),
    ],
)
def test_manual_aar_track_rejects_insufficient_or_duplicate_points(points, message):
    """Tracks require a usable ordered line rather than ambiguous point input."""
    with pytest.raises(ValidationError, match=message):
        ManualAARTrack(id="manual-track", name="Deviation", points=points)


@pytest.mark.parametrize(
    "points",
    [
        None,
        "not a point list",
        [
            {"latitude": 35.0, "longitude": -120.0},
            "not a coordinate mapping",
        ],
    ],
)
def test_manual_aar_track_rejects_malformed_point_collections(points):
    """Malformed request data produces Pydantic validation errors rather than crashes."""
    with pytest.raises(ValidationError):
        ManualAARTrack(id="manual-track", name="Deviation", points=points)


@pytest.mark.parametrize(
    "point, message",
    [
        ({"latitude": 90.1, "longitude": 0}, "Latitude must be between -90 and 90"),
        ({"latitude": 0, "longitude": 180.1}, "Longitude must be between -180 and 180"),
    ],
)
def test_manual_aar_track_rejects_out_of_range_coordinates(point, message):
    """Manual position entry accepts only decimal-degree geographic coordinates."""
    with pytest.raises(ValidationError, match=message):
        ManualAARTrackPoint(**point)


def test_manual_aar_track_degrades_x_between_projected_endpoints():
    """A track creates an X degradation over its route-projected time span."""
    start = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
    route_manager = MagicMock()
    route_manager.get_route.return_value = _timed_manual_track_route(start)
    base_leg = MissionLeg(
        id="manual-track-leg",
        name="Manual track leg",
        route_id="manual-track-route",
        transports=TransportConfig(initial_x_satellite_id="X-1"),
    )
    manual_track = ManualAARTrack(
        id="manual-track",
        name="AR deviation",
        points=[
            ManualAARTrackPoint(latitude=50.0, longitude=-50.0),
            ManualAARTrackPoint(latitude=30.0, longitude=-50.0),
        ],
    )
    tracked_leg = base_leg.model_copy(
        update={
            "transports": base_leg.transports.model_copy(
                update={"manual_aar_tracks": [manual_track]}
            )
        }
    )

    baseline, _ = build_mission_timeline(
        base_leg, route_manager=route_manager, coverage_sampler=None
    )
    tracked, _ = build_mission_timeline(
        tracked_leg, route_manager=route_manager, coverage_sampler=None
    )

    assert baseline.statistics["degraded_seconds"] == 0
    assert tracked.statistics["degraded_seconds"] == 3600
    degraded = [
        segment
        for segment in tracked.segments
        if segment.status == TimelineStatus.DEGRADED
    ]
    assert [(segment.start_time, segment.end_time) for segment in degraded] == [
        (start + timedelta(minutes=30), start + timedelta(minutes=90))
    ]
    assert "Manual AR Track: AR deviation" in degraded[0].reasons[0]
