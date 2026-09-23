"""Regression coverage for the test bootstrap manager patches."""

import subprocess
import sys
from pathlib import Path


def test_bootstrap_patches_are_observed_by_application_lifecycle():
    """A clean interpreter must give app startup the test manager instances."""
    backend_root = Path(__file__).resolve().parents[2]
    probe = f"""
import importlib.util
import sys
from pathlib import Path

from fastapi.testclient import TestClient

backend_root = Path({str(backend_root)!r})
conftest_path = backend_root / "tests" / "conftest.py"
assert "main" not in sys.modules

spec = importlib.util.spec_from_file_location("bootstrap_lifecycle_probe", conftest_path)
assert spec is not None
assert spec.loader is not None
bootstrap = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bootstrap
spec.loader.exec_module(bootstrap)

from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from main import POIManager as ApplicationPOIManager
from main import RouteManager as ApplicationRouteManager

assert RouteManager.__init__ is bootstrap.patched_route_init
assert POIManager.__init__ is bootstrap.patched_poi_init
assert ApplicationRouteManager is RouteManager
assert ApplicationPOIManager is POIManager

with TestClient(bootstrap.app):
    assert bootstrap.app.state.route_manager.routes_dir == Path("/tmp/test_data/routes")
    assert bootstrap.app.state.poi_manager.pois_file == Path("/tmp/test_data/pois.json")
"""

    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=backend_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
