"""Regression tests for operator-created manual AAR tracks."""

import pytest
from pydantic import ValidationError

from app.mission.models import ManualAARTrack, ManualAARTrackPoint, Mission, MissionLeg, TransportConfig
from app.mission.storage import load_mission_v2, save_mission_v2


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
