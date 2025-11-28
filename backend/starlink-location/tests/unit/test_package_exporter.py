
import pytest
from unittest.mock import MagicMock, patch
from app.mission.models import Mission, MissionLeg
from app.mission.package_exporter import generate_mission_combined_xlsx
from app.mission.exporter import ExportGenerationError, TimelineExportFormat

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
def test_generate_mission_combined_xlsx_export_error(mock_load_workbook, mock_generate_export, mock_load_timeline, mock_mission):
    # Setup
    mock_load_timeline.return_value = MagicMock() # Return a dummy timeline
    
    # Simulate ExportGenerationError for the first leg
    mock_generate_export.side_effect = [
        ExportGenerationError("Simulated export failure"),
        MagicMock(content=b"fake_xlsx_content") # Second leg succeeds
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
    
    # We can't easily inspect the resulting bytes without saving and opening, 
    # but we can verify the code path didn't crash.
