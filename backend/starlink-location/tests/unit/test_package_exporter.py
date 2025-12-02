import pytest
from unittest.mock import MagicMock, patch
from app.mission.models import Mission, MissionLeg
from app.mission.package_exporter import (
    generate_mission_combined_xlsx,
    export_mission_package,
)
from app.mission.exporter import ExportGenerationError


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


@patch("app.mission.package_exporter.load_mission_timeline")
@patch("app.mission.package_exporter.generate_timeline_export")
@patch("openpyxl.load_workbook")
def test_generate_mission_combined_xlsx_export_error(
    mock_load_workbook, mock_generate_export, mock_load_timeline, mock_mission
):
    # Setup
    mock_load_timeline.return_value = MagicMock()  # Return a dummy timeline

    # Simulate ExportGenerationError for the first leg
    mock_generate_export.side_effect = [
        ExportGenerationError("Simulated export failure"),
        MagicMock(content=b"fake_xlsx_content"),  # Second leg succeeds
    ]

    # Mock load_workbook for the second leg
    mock_wb = MagicMock()
    mock_wb.sheetnames = ["Summary", "Timeline"]
    mock_sheet = MagicMock()
    mock_wb.__getitem__.return_value = mock_sheet
    mock_load_workbook.return_value = mock_wb

    # Execute
    xlsx_bytes = generate_mission_combined_xlsx(mock_mission)

    # Verify
    assert xlsx_bytes is not None
    assert len(xlsx_bytes) > 0

    # Verify that generate_timeline_export was called for both legs
    assert mock_generate_export.call_count == 2


@patch("app.mission.package_exporter.load_mission_v2")
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


@patch("app.mission.package_exporter.load_mission_v2")
@patch("app.mission.package_exporter.generate_mission_combined_xlsx")
def test_export_mission_package_uses_temp_files_for_large_exports(
    mock_gen_xlsx, mock_load_mission, mock_mission
):
    # Setup
    mock_load_mission.return_value = mock_mission
    mock_route_manager = MagicMock()
    mock_poi_manager = MagicMock()

    # Mock generate_mission_combined_xlsx to write to the path it's given
    def side_effect(mission, output_path=None, **kwargs):
        if output_path:
            with open(output_path, "w") as f:
                f.write("dummy xlsx content")
        return None

    mock_gen_xlsx.side_effect = side_effect

    # Execute
    zip_file = export_mission_package("mission1", mock_route_manager, mock_poi_manager)

    try:
        # Verify
        import zipfile

        with zipfile.ZipFile(zip_file, "r") as zf:
            assert "exports/mission/mission-timeline.xlsx" in zf.namelist()
            content = zf.read("exports/mission/mission-timeline.xlsx")
            assert content == b"dummy xlsx content"

        # Verify generate_mission_combined_xlsx was called with an output_path
        assert mock_gen_xlsx.called
        call_args = mock_gen_xlsx.call_args
        assert "output_path" in call_args.kwargs or len(call_args.args) > 1

    finally:
        zip_file.close()
