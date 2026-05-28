"""Regression tests for adjusted takeoff times in mission package exports."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.mission.models import (
    AARWindow,
    Mission,
    MissionLeg,
    MissionLegTimeline,
    TimelineAdvisory,
    TimelineSegment,
    TimelineStatus,
    Transport,
    TransportConfig,
    TransportState,
    XTransition,
)
from app.mission.package.__main__ import generate_mission_combined_csv
from app.mission.timeline_builder.calculator import route_with_adjusted_departure
from app.mission.timeline_service import build_mission_timeline
from app.models.route import (
    ParsedRoute,
    RouteMetadata,
    RoutePoint,
    RouteTimingProfile,
    RouteWaypoint,
)


def _timeline_at(start: datetime) -> MissionLegTimeline:
    return MissionLegTimeline(
        mission_leg_id="leg-adjusted",
        segments=[
            TimelineSegment(
                id="seg-1",
                start_time=start,
                end_time=start + timedelta(minutes=30),
                status=TimelineStatus.NOMINAL,
                x_state=TransportState.AVAILABLE,
                ka_state=TransportState.AVAILABLE,
                ku_state=TransportState.AVAILABLE,
                reasons=[],
                impacted_transports=[],
                metadata={},
            )
        ],
        advisories=[
            TimelineAdvisory(
                id="aar-1",
                timestamp=start + timedelta(minutes=10),
                event_type="aar_window",
                transport=Transport.X,
                severity="warning",
                message="AAR window active",
                metadata={},
            )
        ],
        statistics={},
    )


def _timed_route(start: datetime) -> ParsedRoute:
    return ParsedRoute(
        metadata=RouteMetadata(
            name="Timed Route",
            file_path="timed-route.kml",
            point_count=5,
        ),
        points=[
            RoutePoint(
                latitude=0.0,
                longitude=0.0,
                sequence=0,
                expected_arrival_time=start,
            ),
            RoutePoint(
                latitude=0.0,
                longitude=0.5,
                sequence=1,
                expected_arrival_time=start + timedelta(minutes=30),
            ),
            RoutePoint(
                latitude=0.0,
                longitude=1.0,
                sequence=2,
                expected_arrival_time=start + timedelta(hours=1),
            ),
            RoutePoint(
                latitude=0.0,
                longitude=1.5,
                sequence=3,
                expected_arrival_time=start + timedelta(minutes=90),
            ),
            RoutePoint(
                latitude=0.0,
                longitude=2.0,
                sequence=4,
                expected_arrival_time=start + timedelta(hours=2),
            ),
        ],
        waypoints=[
            RouteWaypoint(
                name="AAR-START",
                latitude=0.0,
                longitude=0.5,
                order=1,
                expected_arrival_time=start + timedelta(minutes=30),
            ),
            RouteWaypoint(
                name="AAR-END",
                latitude=0.0,
                longitude=1.5,
                order=2,
                expected_arrival_time=start + timedelta(minutes=90),
            ),
        ],
        timing_profile=RouteTimingProfile(
            departure_time=start,
            arrival_time=start + timedelta(hours=2),
            has_timing_data=True,
            segment_count_with_timing=5,
        ),
    )


def test_combined_csv_rebuilds_adjusted_leg_timeline_instead_of_cached_stale_times():
    original_takeoff = datetime(2025, 11, 5, 0, 0, tzinfo=timezone.utc)
    adjusted_takeoff = original_takeoff + timedelta(minutes=40)
    leg = MissionLeg(
        id="leg-adjusted",
        name="Adjusted Leg",
        route_id="route-1",
        adjusted_departure_time=adjusted_takeoff,
        transports=TransportConfig(initial_x_satellite_id="X-1"),
    )
    mission = Mission(id="mission-adjusted", name="Adjusted Mission", legs=[leg])

    stale_timeline = _timeline_at(original_takeoff)
    adjusted_timeline = _timeline_at(adjusted_takeoff)

    with (
        patch(
            "app.mission.package.__main__.load_mission_timeline",
            return_value=stale_timeline,
        ),
        patch(
            "app.mission.package.__main__.build_mission_timeline",
            return_value=(adjusted_timeline, MagicMock()),
        ) as mock_build,
        patch(
            "app.mission.package.__main__.save_mission_timeline", create=True
        ) as mock_save,
    ):
        csv_bytes = generate_mission_combined_csv(
            mission,
            route_manager=MagicMock(),
            poi_manager=MagicMock(),
        )

    assert csv_bytes is not None
    output = csv_bytes.decode("utf-8")
    mock_build.assert_called_once()
    mock_save.assert_not_called()
    assert "2025-11-05T00:40:00+00:00" in output
    assert "2025-11-05T00:50:00+00:00" in output
    assert "2025-11-05T00:00:00+00:00" not in output
    assert "2025-11-05T00:10:00+00:00" not in output


def test_route_time_shift_applies_uniform_delta_to_every_timed_route_point():
    original_takeoff = datetime(2025, 11, 5, 0, 0, tzinfo=timezone.utc)
    delta = timedelta(minutes=40)
    route = _timed_route(original_takeoff)

    shifted = route_with_adjusted_departure(route, original_takeoff + delta)

    assert shifted is not route
    assert shifted.timing_profile is not None
    assert route.timing_profile is not None
    assert shifted.timing_profile.departure_time == original_takeoff + delta
    assert (
        shifted.timing_profile.arrival_time
        == original_takeoff + timedelta(hours=2) + delta
    )
    assert [point.expected_arrival_time for point in shifted.points] == [
        point.expected_arrival_time + delta
        for point in route.points
        if point.expected_arrival_time is not None
    ]
    assert [waypoint.expected_arrival_time for waypoint in shifted.waypoints] == [
        waypoint.expected_arrival_time + delta
        for waypoint in route.waypoints
        if waypoint.expected_arrival_time is not None
    ]
    assert route.timing_profile.departure_time == original_takeoff
    assert route.points[0].expected_arrival_time == original_takeoff


def test_adjusted_takeoff_delta_shifts_transition_aar_and_landing_times():
    original_takeoff = datetime(2025, 11, 5, 0, 0, tzinfo=timezone.utc)
    adjusted_takeoff = original_takeoff + timedelta(minutes=40)
    route = _timed_route(original_takeoff)
    route_manager = MagicMock()
    route_manager.get_route.return_value = route
    leg = MissionLeg(
        id="leg-adjusted",
        name="Adjusted Leg",
        route_id="route-1",
        adjusted_departure_time=adjusted_takeoff,
        transports=TransportConfig(
            initial_x_satellite_id="X-1",
            x_transitions=[
                XTransition(
                    id="transition-1",
                    latitude=0.0,
                    longitude=1.0,
                    target_satellite_id="X-2",
                )
            ],
            aar_windows=[
                AARWindow(
                    id="aar-1",
                    start_waypoint_name="AAR-START",
                    end_waypoint_name="AAR-END",
                )
            ],
        ),
    )

    timeline, summary = build_mission_timeline(
        leg,
        route_manager=route_manager,
        coverage_sampler=None,
    )

    assert summary.mission_start == adjusted_takeoff
    assert summary.mission_end == adjusted_takeoff + timedelta(hours=2)
    assert timeline.segments[-1].end_time == adjusted_takeoff + timedelta(hours=2)
    assert timeline.statistics["_aar_blocks"] == [
        {
            "start": (adjusted_takeoff + timedelta(minutes=30)).isoformat(),
            "end": (adjusted_takeoff + timedelta(minutes=90)).isoformat(),
        }
    ]
    transition_segments = [
        segment
        for segment in timeline.segments
        if "X Transition to X-2" in segment.reasons
    ]
    assert transition_segments
    assert min(segment.start_time for segment in transition_segments) == (
        adjusted_takeoff + timedelta(minutes=45)
    )
    assert max(segment.end_time for segment in transition_segments) == (
        adjusted_takeoff + timedelta(minutes=75)
    )
