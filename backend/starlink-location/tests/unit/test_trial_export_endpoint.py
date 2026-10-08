"""The normal ZIP endpoint surfaces trial outcomes across the CORS boundary."""

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.mission import routes_v2
from app.mission.exporter import trial_projection
from main import app
from tests.unit import test_trial_package
from tests.unit.test_trial_package import TRIAL, flag

package_inputs = test_trial_package.package_inputs


@pytest.mark.parametrize("status", ["disabled", "included", "failed"])
def test_trial_warning_download_result(package_inputs, monkeypatch, status):
    frozen, _ = package_inputs
    flag(status != "disabled")
    if status == "failed":

        def fail(*a):
            raise RuntimeError("secret\r\n/private/customer" * 1000)

        monkeypatch.setattr(trial_projection, "project_trial_leg", fail)
    monkeypatch.setattr(routes_v2.limiter, "enabled", False)
    old = app.dependency_overrides.copy()
    app.dependency_overrides[routes_v2.get_route_manager] = lambda: None
    app.dependency_overrides[routes_v2.get_poi_manager] = lambda: None
    try:
        # No application lifespan: these checks own no server/background coordinator.
        response = TestClient(app).post(
            f"/api/v2/missions/{frozen.mission_id}/export",
            headers={"Origin": "http://customer.example"},
        )
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["x-mission-export-trial-status"] == status
    raw = response.headers["x-mission-export-warnings"]
    warnings = json.loads(raw)
    assert isinstance(warnings, list) and all(isinstance(w, str) for w in warnings)
    assert len(raw) < 2048 and "secret" not in raw and "/private" not in raw
    exposed = response.headers["access-control-expose-headers"].lower()
    assert "x-mission-export-trial-status" in exposed
    assert "x-mission-export-warnings" in exposed and "x-total-count" in exposed
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.testzip() is None
        assert (TRIAL in archive.namelist()) == (status == "included")
        manifest = json.loads(archive.read("manifest.json"))
        if status == "disabled":
            assert "trial_status" not in manifest and warnings == []
        else:
            assert manifest["trial_status"] == status
            assert manifest["warnings"] == warnings
            if status == "failed":
                assert warnings


def test_export_endpoint_closes_the_owned_zip_stream(package_inputs, monkeypatch):
    from app.mission.package import export_mission_package_result

    frozen, _ = package_inputs
    flag(False)
    owned = []

    def export(*a, **kw):
        result = export_mission_package_result(*a, **kw)
        owned.append(result.stream)
        return result

    monkeypatch.setattr(routes_v2, "export_mission_package_result", export)
    monkeypatch.setattr(routes_v2.limiter, "enabled", False)
    old = app.dependency_overrides.copy()
    app.dependency_overrides[routes_v2.get_route_manager] = lambda: None
    app.dependency_overrides[routes_v2.get_poi_manager] = lambda: None
    try:
        response = TestClient(app).post(f"/api/v2/missions/{frozen.mission_id}/export")
        assert response.status_code == 200
        assert owned[0].closed
    finally:
        for stream in owned:
            stream.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old)
