from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import overview_history
from app.services.overview_history_prometheus import (
    OverviewHistoryPrometheusResponseError,
)


def test_overview_history_returns_503_until_its_runtime_reader_is_initialized():
    overview_history.set_overview_history_reader(None)
    app = FastAPI()
    app.include_router(overview_history.router)
    response = TestClient(app).get("/api/overview-history")
    assert response.status_code == 503
    assert response.json() == {
        "detail": "Overview history is not yet initialized",
    }


def test_overview_history_returns_the_initialized_reader_bundle():
    async def read_history() -> dict:
        return {
            "window_seconds": 1800,
            "start_timestamp_seconds": 1_781_998_200,
            "end_timestamp_seconds": 1_782_000_000,
            "step_seconds": 1,
            "series": {
                "starlink_dish_latitude_degrees": [
                    [1_782_000_000.0, 41.2566],
                ],
            },
        }

    overview_history.set_overview_history_reader(read_history)
    try:
        app = FastAPI()
        app.include_router(overview_history.router)
        response = TestClient(app).get("/api/overview-history")
    finally:
        overview_history.set_overview_history_reader(None)
    assert response.status_code == 200
    assert response.json() == {
        "window_seconds": 1800,
        "start_timestamp_seconds": 1_781_998_200,
        "end_timestamp_seconds": 1_782_000_000,
        "step_seconds": 1,
        "series": {
            "starlink_dish_latitude_degrees": [
                [1_782_000_000.0, 41.2566],
            ],
        },
    }


def test_overview_history_returns_503_when_its_prometheus_reader_fails():
    async def read_history() -> dict:
        raise OverviewHistoryPrometheusResponseError(
            "Prometheus history query failed: query timed out"
        )

    overview_history.set_overview_history_reader(read_history)
    try:
        app = FastAPI()
        app.include_router(overview_history.router)
        response = TestClient(
            app,
            raise_server_exceptions=False,
        ).get("/api/overview-history")
    finally:
        overview_history.set_overview_history_reader(None)
    assert response.status_code == 503
    assert response.json() == {
        "detail": "Overview history is temporarily unavailable",
    }
