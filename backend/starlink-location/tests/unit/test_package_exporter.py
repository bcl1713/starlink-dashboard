from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.mission.models import (
    Mission,
    MissionLeg,
    MissionLegTimeline,
    TimelineSegment,
    TimelineStatus,
    TransportState,
)
from app.mission.package.__main__ import generate_mission_combined_csv
from app.mission.package import export_mission_package


@pytest.fixture
def mock_mission():
    transports = {
        "initial_x_satellite_id": "X-1",
        "initial_ka_satellite_ids": ["AOR", "POR", "IOR"],
        "x_transitions": [],
        "ka_outages": [],
        "aar_windows": [],
        "ku_overrides": [],
    }
    leg1 = MissionLeg(id="leg1", name="Leg 1", route_id="route1", transports=transports)
    leg2 = MissionLeg(id="leg2", name="Leg 2", route_id="route2", transports=transports)
    return Mission(id="mission1", name="Test Mission", legs=[leg1, leg2])


def _sample_timeline(leg_id: str, status: TimelineStatus) -> MissionLegTimeline:
    start = datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 30, 12, 5, tzinfo=timezone.utc)
    return MissionLegTimeline(
        mission_leg_id=leg_id,
        segments=[
            TimelineSegment(
                id=f"{leg_id}-segment-1",
                start_time=start,
                end_time=end,
                status=status,
                x_state=TransportState.AVAILABLE,
                ka_state=TransportState.AVAILABLE,
                ku_state=TransportState.AVAILABLE,
                reasons=["sof_demo"] if status == TimelineStatus.SOF else [],
            )
        ],
    )


@patch("app.mission.package.__main__.load_mission_timeline")
def test_generate_mission_combined_csv_continues_after_leg_error(
    mock_load_timeline, mock_mission
):
    mock_load_timeline.side_effect = [
        RuntimeError("Simulated timeline load failure"),
        _sample_timeline("leg2", TimelineStatus.SOF),
    ]

    csv_bytes = generate_mission_combined_csv(mock_mission)

    assert csv_bytes is not None
    csv_text = csv_bytes.decode("utf-8")
    assert "Leg 2" in csv_text
    assert "ADVISORY" in csv_text
    assert "sof_demo" in csv_text
    assert mock_load_timeline.call_count == 2


@patch("app.mission.package.__main__.load_mission_v2")
def test_export_mission_package_returns_file_object(mock_load_mission, mock_mission):
    # Setup
    mock_load_mission.return_value = mock_mission
    mock_route_manager = MagicMock()
    mock_poi_manager = MagicMock()

    # Execute
    # This will actually create a temp file and zip it, so we test the real logic mostly
    # We mock load_mission_v2 to return our test mission

    zip_file = export_mission_package("mission1", mock_route_manager, mock_poi_manager)

    try:
        # Verify
        assert zip_file is not None
        # Check if it's a file-like object
        assert hasattr(zip_file, "read")
        assert hasattr(zip_file, "seek")

        # Check content
        import zipfile

        with zipfile.ZipFile(zip_file, "r") as zf:
            assert "mission.json" in zf.namelist()
            assert "manifest.json" in zf.namelist()
            # Check for leg files
            assert "legs/leg1.json" in zf.namelist()
            assert "legs/leg2.json" in zf.namelist()

    finally:
        zip_file.close()


@patch("app.mission.package.__main__.load_mission_v2")
@patch("app.mission.package.__main__.generate_mission_combined_pptx")
@patch("app.mission.package.__main__.generate_mission_combined_csv")
def test_export_mission_package_uses_temp_files_for_mission_exports(
    mock_gen_csv, mock_gen_pptx, mock_load_mission, mock_mission
):
    mock_load_mission.return_value = mock_mission
    mock_route_manager = MagicMock()
    mock_poi_manager = MagicMock()

    def csv_side_effect(mission, output_path=None, **kwargs):
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("dummy csv content")
        return None

    def pptx_side_effect(mission, output_path=None, **kwargs):
        if output_path:
            with open(output_path, "wb") as f:
                f.write(b"dummy pptx content")
        return None

    mock_gen_csv.side_effect = csv_side_effect
    mock_gen_pptx.side_effect = pptx_side_effect

    zip_file = export_mission_package("mission1", mock_route_manager, mock_poi_manager)

    try:
        import zipfile

        with zipfile.ZipFile(zip_file, "r") as zf:
            assert "exports/mission/mission-timeline.csv" in zf.namelist()
            assert "exports/mission/mission-slides.pptx" in zf.namelist()
            assert "exports/mission/mission-timeline.xlsx" not in zf.namelist()
            assert (
                zf.read("exports/mission/mission-timeline.csv") == b"dummy csv content"
            )
            assert (
                zf.read("exports/mission/mission-slides.pptx") == b"dummy pptx content"
            )

        assert mock_gen_csv.called
        assert mock_gen_pptx.called
        csv_call_args = mock_gen_csv.call_args
        pptx_call_args = mock_gen_pptx.call_args
        assert "output_path" in csv_call_args.kwargs or len(csv_call_args.args) > 1
        assert "output_path" in pptx_call_args.kwargs or len(pptx_call_args.args) > 1

    finally:
        zip_file.close()
