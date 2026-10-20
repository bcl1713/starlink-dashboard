"""Immutable, deterministic, versioned CSV mission packages."""

import io
import json
import zipfile

import pytest

from app.services.telemetry_archive.package import build_telemetry_package


def capture(leg, complete=True):
    return {
        "schema_version": 1,
        "mission_id": "m",
        "leg_id": leg,
        "revision": leg,
        "start": "2026-01-01T00:00:00+00:00",
        "end": "2026-01-01T01:00:00+00:00",
        "state": "sealed",
        "complete": complete,
        "source_mode": "live",
        "gaps": [],
        "events": [],
        "samples": [
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "metric": "starlink_ground_entry_point_info",
                "labels": {"city": "=formula"},
                "value": None,
                "observed_at": None,
            }
        ],
    }


def test_ordered_deterministic_and_safe_package():
    inputs = [capture("second"), capture("first")]
    payload = build_telemetry_package("m", inputs, allow_partial=False)
    assert payload == build_telemetry_package("m", inputs, allow_partial=False)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert [leg["leg_id"] for leg in manifest["legs"]] == ["second", "first"]
        assert manifest["schema_version"] == 1
        assert b"formula" in archive.read("legs/001/observations.csv")
        assert "checksum" in manifest["legs"][0]


def test_incomplete_requires_explicit_partial_and_live_only():
    with pytest.raises(ValueError, match="incomplete"):
        build_telemetry_package("m", [capture("one", False)], allow_partial=False)
    payload = build_telemetry_package("m", [capture("one", False)], allow_partial=True)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert json.loads(archive.read("manifest.json"))["partial"]
    simulated = capture("one") | {"source_mode": "simulation"}
    with pytest.raises(ValueError, match="simulation"):
        build_telemetry_package("m", [simulated], allow_partial=True)
