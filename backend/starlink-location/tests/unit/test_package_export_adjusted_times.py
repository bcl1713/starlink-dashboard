"""Regression tests for mission package exports with adjusted takeoff times."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.mission.exporter import ExportArtifact
from app.mission.models import Mission, MissionLeg, MissionLegTimeline, TransportConfig
from app.mission.package.__main__ import _add_per_leg_exports_to_zip


def test_per_leg_exports_rebuild_timeline_before_using_cached_aar_blocks():
    """Package exports must not use stale cached AAR/event times after takeoff edits."""
    leg = MissionLeg(
        id="leg-1",
        name="Leg 1",
        route_id="route-1",
        adjusted_departure_time=datetime(2025, 10, 27, 12, 0, tzinfo=timezone.utc),
        transports=TransportConfig(
            initial_x_satellite_id="X-1",
            initial_ka_satellite_ids=["AOR", "POR", "IOR"],
            x_transitions=[],
            ka_outages=[],
            aar_windows=[],
            ku_overrides=[],
        ),
    )
    mission = Mission(id="mission-1", name="Mission 1", legs=[leg])
    stale_timeline = MissionLegTimeline(
        mission_leg_id="leg-1",
        statistics={
            "_aar_blocks": [
                {
                    "start": "2025-10-27T10:00:00+00:00",
                    "end": "2025-10-27T10:30:00+00:00",
                }
            ]
        },
    )
    rebuilt_timeline = MissionLegTimeline(
        mission_leg_id="leg-1",
        statistics={
            "_aar_blocks": [
                {
                    "start": "2025-10-27T12:00:00+00:00",
                    "end": "2025-10-27T12:30:00+00:00",
                }
            ]
        },
    )
    artifact = ExportArtifact(
        content=b"export", media_type="text/plain", extension="txt"
    )

    with (
        patch(
            "app.mission.package.__main__.build_mission_timeline",
            return_value=(rebuilt_timeline, MagicMock()),
        ) as mock_build,
        patch("app.mission.package.__main__.save_mission_timeline") as mock_save,
        patch(
            "app.mission.package.__main__.load_mission_timeline",
            return_value=stale_timeline,
        ) as mock_load,
        patch(
            "app.mission.package.__main__.generate_timeline_export",
            return_value=artifact,
        ) as mock_generate,
    ):
        manifest_files = {"per_leg_exports": []}
        _add_per_leg_exports_to_zip(
            zf=MagicMock(),
            mission=mission,
            route_manager=MagicMock(),
            poi_manager=MagicMock(),
            manifest_files=manifest_files,
        )

    mock_build.assert_called_once()
    mock_save.assert_called_once_with("leg-1", rebuilt_timeline)
    mock_load.assert_not_called()
    assert mock_generate.call_count == 2
    assert all(
        call.kwargs["timeline"] is rebuilt_timeline
        for call in mock_generate.call_args_list
    )
    assert stale_timeline.statistics["_aar_blocks"][0]["start"] == (
        "2025-10-27T10:00:00+00:00"
    )
    assert rebuilt_timeline.statistics["_aar_blocks"][0]["start"] == (
        "2025-10-27T12:00:00+00:00"
    )
