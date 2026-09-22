"""Regression coverage for repository-owned Pydantic deprecation sources."""

from __future__ import annotations

import configparser
import importlib
import json
import subprocess
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


def test_telemetry_serializes_datetime_without_deprecated_json_encoder_warning():
    """Telemetry JSON retains ISO timestamps without the legacy encoder setting."""
    from app.models import telemetry

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        telemetry = importlib.reload(telemetry)
        sample = telemetry.TelemetryData(
            timestamp=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
            position=telemetry.PositionData(latitude=1.0, longitude=2.0, altitude=3.0),
            network=telemetry.NetworkData(
                latency_ms=4.0,
                throughput_down_mbps=5.0,
                throughput_up_mbps=6.0,
                packet_loss_percent=7.0,
            ),
            obstruction=telemetry.ObstructionData(obstruction_percent=8.0),
        )
        payload = json.loads(sample.model_dump_json())

    assert payload["timestamp"] == "2026-01-02T03:04:05+00:00"
    assert not any("json_encoders" in str(warning.message) for warning in captured)


def test_satellite_response_accepts_attributes_without_class_config_warning():
    """Satellite responses keep ORM-style attribute validation without Config."""
    from app.satellites import routes

    source = SimpleNamespace(
        satellite_id="X-1",
        transport="X",
        longitude=-120.0,
        slot="X-Slot-1",
        color="#FF6B6B",
    )

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        routes = importlib.reload(routes)
        response = routes.SatelliteResponse.model_validate(source)

    assert response.model_dump() == {
        "satellite_id": "X-1",
        "transport": "X",
        "longitude": -120.0,
        "slot": "X-Slot-1",
        "color": "#FF6B6B",
    }
    assert not any(
        "class-based `Config`" in str(warning.message) for warning in captured
    )


def test_repository_configuration_has_no_deprecated_warning_sources():
    """Repository configuration must not recreate the removed warning sources."""
    project_root = Path(__file__).parents[2]
    pytest_config = configparser.ConfigParser()
    pytest_config.read(project_root / "pytest.ini")

    result = subprocess.run(
        [
            sys.executable,
            "-W",
            "always",
            "-c",
            "import app.models.telemetry; import app.satellites.routes",
        ],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "json_encoders" not in result.stderr
    assert "class-based `config`" not in result.stderr
    assert "anyio_backend" not in pytest_config["pytest"]
