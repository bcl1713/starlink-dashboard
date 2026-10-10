"""Regression coverage for the test bootstrap manager patches."""

import os
import subprocess
import sys
from pathlib import Path


def test_bootstrap_patches_are_observed_by_application_lifecycle(tmp_path):
    """A clean interpreter must give app startup the test manager instances."""
    backend_root = Path(__file__).resolve().parents[2]
    owned_root = tmp_path / "bootstrap"
    probe = f"""
import importlib.util
import sys
from pathlib import Path

from fastapi.testclient import TestClient

backend_root = Path({str(backend_root)!r})
owned_root = Path({str(tmp_path / "bootstrap")!r})
def reject_shared_root(event, args):
    if event in {{"open", "os.mkdir", "os.remove", "os.rmdir", "os.rename"}}:
        assert not any(isinstance(value, str) and value.startswith("/tmp/test_data") for value in args), (event, args)
sys.addaudithook(reject_shared_root)
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
    assert callable(bootstrap.app.state.route_manager._profile_resolver)
    assert bootstrap.app.state.route_manager.routes_dir == owned_root / "routes"
    assert bootstrap.app.state.poi_manager.pois_file == owned_root / "pois.json"
"""

    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=tmp_path,
        env={
            **os.environ,
            "STARLINK_TEST_DATA_DIR": str(owned_root),
            "PYTHONPATH": str(backend_root),
        },
        timeout=60,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_startup_reconciles_persisted_active_legs_before_route_manager_initializes(
    tmp_path,
):
    """A restart clears durable lifecycle flags without restoring a route."""
    backend_root = Path(__file__).resolve().parents[2]
    owned_root = tmp_path / "bootstrap"
    probe = f"""
import importlib.util
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

backend_root = Path({str(backend_root)!r})
owned_root = Path({str(tmp_path / "bootstrap")!r})
def reject_shared_root(event, args):
    if event in {{"open", "os.mkdir", "os.remove", "os.rmdir", "os.rename"}}:
        assert not any(isinstance(value, str) and value.startswith("/tmp/test_data") for value in args), (event, args)
sys.addaudithook(reject_shared_root)
conftest_path = backend_root / "tests" / "conftest.py"
spec = importlib.util.spec_from_file_location("bootstrap_reconciliation_probe", conftest_path)
assert spec is not None
assert spec.loader is not None
bootstrap = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bootstrap
spec.loader.exec_module(bootstrap)

from app.mission import storage
from app.mission.models import Mission, MissionLeg, TransportConfig

with tempfile.TemporaryDirectory(dir={str(tmp_path)!r}) as directory:
    storage.MISSIONS_DIR = Path(directory)
    storage.save_mission_v2(Mission(
        id="persisted-active",
        name="Persisted active",
        legs=[MissionLeg(
            id="leg-1",
            name="Leg 1",
            route_id="route-1",
            is_active=True,
            transports=TransportConfig(initial_x_satellite_id="X-1"),
        )],
    ))
    with TestClient(bootstrap.app) as client:
        persisted = storage.load_mission_v2("persisted-active")
        assert persisted is not None
        assert not persisted.legs[0].is_active
        assert client.app.state.route_manager.get_active_route() is None
"""

    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=tmp_path,
        env={
            **os.environ,
            "STARLINK_TEST_DATA_DIR": str(owned_root),
            "PYTHONPATH": str(backend_root),
        },
        timeout=60,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
