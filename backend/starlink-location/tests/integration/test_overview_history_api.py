from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import overview_history


def test_overview_history_returns_503_until_its_runtime_reader_is_initialized():
    overview_history.set_overview_history_reader(None)
    app = FastAPI()
    app.include_router(overview_history.router)
    response = TestClient(app).get("/api/overview-history")
    assert response.status_code == 503
    assert response.json() == {
        "detail": "Overview history is not yet initialized",
    }
