"""The diagnostic reports actual failed predicates and refuses changed inputs."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def probe_module():
    spec = importlib.util.spec_from_file_location(
        "map_probe", ROOT / "tools/acceptance/itinerary-planning/map_probe.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_probe_preserves_input_hashes(tmp_path):
    module = probe_module()
    source = tmp_path / "original.kml"
    source.write_bytes(b"original input")
    expected = module.input_hashes(tmp_path)
    module.verify_input_hashes(tmp_path, expected)
    assert source.read_bytes() == b"original input"
    source.write_bytes(b"changed input")
    with pytest.raises(ValueError, match="hash"):
        module.verify_input_hashes(tmp_path, expected)


def test_probe_names_failed_predicate():
    module = probe_module()
    root = ROOT / "backend/starlink-location"
    import sys

    sys.path.insert(0, str(root))
    from tests.unit.test_map_real_input_boundaries import boundary

    captured, projected, recipe = boundary("map-density-one")
    result = module.probe_snapshot(captured, projected)
    assert result["failed_predicate"] == "route_marker_limit"
    assert result["marker_count"] == recipe["windowCount"]
    assert not result["scene_available"]


def test_probe_supports_customer_overview_without_hidden_marker_capacity():
    module = probe_module()
    import sys

    sys.path.insert(0, str(ROOT / "backend/starlink-location"))
    from tests.unit.test_map_real_input_boundaries import boundary

    captured, projected, _ = boundary("map-density-three")
    result = module.probe_snapshot(captured, projected, include_markers=False)
    assert result["scene_available"] and result["failed_predicate"] is None
    assert result["display_marker_count"] == 0
    assert result["marker_count"] == 279
