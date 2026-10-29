"""Both mission preparation entrypoints expose real capacity failures safely."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.mark.parametrize("suffix", ["export", "export-preparations"])
def test_capacity_failure_is_actionable_on_both_entrypoints(suffix):
    from app.mission.package.archive_errors import ArchiveCapacityError
    from app.mission.package.preparation_routes import router
    from app.mission.routes_v2 import router as legacy

    class Service:
        def start(self, mission_id, **kwargs):
            raise ArchiveCapacityError("supplementary-members", 256 * 1024 * 1024)

    app = FastAPI()
    app.state.export_preparation_service = Service()
    app.include_router(router)
    app.include_router(legacy)
    with TestClient(app) as client:
        response = client.post(f"/api/v2/missions/m/{suffix}?telemetry_format=compact")
        assert response.status_code == 413
        assert response.json()["detail"]["code"] == "mission_archive_capacity"
        assert response.json()["detail"]["layer"] == "supplementary-members"


@pytest.mark.parametrize("suffix", ["export", "export-preparations"])
def test_unknown_telemetry_format_is_rejected_before_capture(suffix):
    from app.mission.package.preparation_routes import router
    from app.mission.routes_v2 import router as legacy

    app = FastAPI()
    app.include_router(router)
    app.include_router(legacy)
    with TestClient(app) as client:
        assert (
            client.post(
                f"/api/v2/missions/m/{suffix}?telemetry_format=discard-everything"
            ).status_code
            == 422
        )
