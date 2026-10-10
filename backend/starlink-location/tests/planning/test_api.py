"""Planning and legacy public responses never reveal owned source paths."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from .test_store import create
from .test_store import service as service_fixture

service = service_fixture


def test_read_and_stale_draft_api(service):
    from app.mission.planning.routes import router
    from app.mission.routes_v2 import router as legacy_router

    app = FastAPI()
    app.state.planning_service = service
    app.include_router(router)
    app.include_router(legacy_router)
    view, _ = create(service)
    with TestClient(app) as client:
        path = f"/api/v2/missions/planning/missions/{view.mission.id}"
        response = client.get(path)
        assert response.status_code == 200
        assert "owned_relative_path" not in response.text
        response = client.put(
            path + "/legs/card-1/draft", json={"expected_revision": 1, "draft": {}}
        )
        assert response.status_code == 200
        before = service.store.read(view.mission.id)
        stale = client.put(
            path + "/legs/card-1/draft", json={"expected_revision": 1, "draft": {}}
        )
        assert stale.status_code == 409
        assert service.store.read(view.mission.id) == before
        response = client.get(f"/api/v2/missions/{view.mission.id}")
        assert response.status_code == 200
        assert "owned_relative_path" not in response.text
        listed = client.get("/api/v2/missions")
        assert listed.status_code == 200 and "owned_relative_path" not in listed.text
        patched = client.patch(
            f"/api/v2/missions/{view.mission.id}", json={"name": "Renamed"}
        )
        assert patched.status_code == 200 and "owned_relative_path" not in patched.text
        assert service.store.read(view.mission.id).revision == before.revision


def test_real_lifespan_recovers_before_reconciliation_and_runtime_readers(
    service, tmp_path, monkeypatch
):
    import base64
    import json

    import main
    from app.mission import storage

    view, _ = create(service)
    mission_file = storage.get_mission_file_path(view.mission.id)
    original = mission_file.read_bytes()
    journal_path = service.store.journal.directory / "interrupted.json"
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text(
        json.dumps(
            {
                "version": 1,
                "state": "prepared",
                "files": [
                    {
                        "path": str(mission_file),
                        "before": base64.b64encode(original).decode(),
                    }
                ],
            }
        )
    )
    mission_file.write_text("{broken")
    events = []
    real_reconcile = main.reconcile_active_legs_on_startup

    def reconcile():
        assert mission_file.read_bytes() == original
        events.append("reconciled")
        return real_reconcile()

    class StartupObserved(Exception):
        pass

    def config_reader():
        assert events == ["reconciled"]
        assert not journal_path.exists()
        assert service.store.read(view.mission.id) == view
        raise StartupObserved()

    monkeypatch.setattr(main, "reconcile_active_legs_on_startup", reconcile)
    monkeypatch.setattr(main, "ConfigManager", config_reader)
    with pytest.raises(StartupObserved), TestClient(main.app):
        pytest.fail(
            "Intentional startup observation should stop before starting runtime resources"
        )


def test_unrecoverable_journal_blocks_actual_app_readiness(service, monkeypatch):
    import main

    path = service.store.journal.directory / "broken.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"version":999}')

    def unexpected():
        pytest.fail("Runtime reader started before recovery")

    monkeypatch.setattr(main, "ConfigManager", unexpected)
    with pytest.raises(ValueError), TestClient(main.app):
        pytest.fail("Unrecoverable storage exposed readiness")
    path.unlink()


@pytest.mark.parametrize(
    "kind,status,code,retryable",
    [
        ("deadline", 503, "planning_deadline_exceeded", True),
        ("worker", 503, "planning_worker_failed", True),
        ("invalid", 422, "invalid_itinerary_pdf", False),
    ],
)
def test_parser_errors_have_typed_status_and_retryability(
    service, monkeypatch, kind, status, code, retryable
):
    from app.mission.planning.deadlines import (
        PlanningDeadlineError,
        PlanningWorkerError,
    )
    from app.mission.planning.extract import ItineraryExtractionError
    from app.mission.planning.routes import router

    failures = {
        "deadline": PlanningDeadlineError,
        "worker": PlanningWorkerError,
        "invalid": ItineraryExtractionError,
    }

    def fail(*args):
        raise failures[kind]("synthetic failure")

    monkeypatch.setattr(service, "preview_itinerary", fail)
    app = FastAPI()
    app.state.planning_service = service
    app.include_router(router)
    with TestClient(app) as client:
        response = client.post(
            "/api/v2/missions/planning/itinerary-previews",
            files={"file": ("synthetic.pdf", b"synthetic")},
        )
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    assert response.json()["detail"]["retryable"] is retryable


@pytest.mark.asyncio
async def test_pdf_upload_bound_precedes_parse_and_kml_preserves_unbounded_read():
    from app.mission.planning.routes import upload_bytes
    from fastapi import HTTPException

    class Upload:
        def __init__(self, data):
            self.data = data
            self.read_sizes = []

        async def read(self, size=-1):
            self.read_sizes.append(size)
            return self.data if size < 0 else self.data[:size]

    pdf = Upload(b"x" * (10 * 1024 * 1024 + 1))
    with pytest.raises(HTTPException) as caught:
        await upload_bytes(pdf, pdf=True)
    assert caught.value.status_code == 422
    assert pdf.read_sizes == [10 * 1024 * 1024 + 1]
    kml = Upload(b"synthetic KML")
    assert await upload_bytes(kml) == b"synthetic KML"
    assert kml.read_sizes == [-1]
