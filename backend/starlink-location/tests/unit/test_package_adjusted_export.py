"""Regression tests for adjusted takeoff times in mission package exports."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.mission.models import (
    Mission,
    MissionLeg,
    MissionLegTimeline,
    TimelineAdvisory,
    TimelineSegment,
    TimelineStatus,
    Transport,
    TransportConfig,
    TransportState,
)
from app.mission.package.__main__ import generate_mission_combined_csv


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
        patch("app.mission.package.__main__.save_mission_timeline"),
    ):
        csv_bytes = generate_mission_combined_csv(
            mission,
            route_manager=MagicMock(),
            poi_manager=MagicMock(),
        )

    assert csv_bytes is not None
    output = csv_bytes.decode("utf-8")
    mock_build.assert_called_once()
    assert "2025-11-05T00:40:00+00:00" in output
    assert "2025-11-05T00:50:00+00:00" in output
    assert "2025-11-05T00:00:00+00:00" not in output
    assert "2025-11-05T00:10:00+00:00" not in output
