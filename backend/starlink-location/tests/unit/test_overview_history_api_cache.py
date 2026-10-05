"""API cache invalidation and failure controls without a threaded TestClient."""

import copy
import json

import fastapi.routing
import httpx
from fastapi import FastAPI

from app.api import overview_history
from app.services.overview_history_prometheus import (
    OverviewHistoryPrometheusResponseError,
)
from app.services.overview_history_settings import OverviewHistorySettingsStore


async def test_settings_invalidate_after_persistence_even_when_duration_is_unchanged(
    tmp_path,
):
    store = OverviewHistorySettingsStore(
        tmp_path / "history.json", default_window_seconds=1800
    )
    calls = []

    def invalidate():
        calls.append(store.get_window_seconds())

    async def read():
        return {"window_seconds": store.get_window_seconds()}

    overview_history.set_overview_history_reader(read, invalidate)
    overview_history.set_overview_history_settings_store(store)
    app = FastAPI()
    app.include_router(overview_history.router)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for window in (900, 900, 1800):
                response = await client.put(
                    "/api/overview-history/settings", json={"window_seconds": window}
                )
                assert response.status_code == 200
                assert calls[-1] == window
                assert (await client.get("/api/overview-history")).json() == {
                    "window_seconds": window
                }
            assert len(calls) == 3
            response = await client.put(
                "/api/overview-history/settings", json={"window_seconds": 0}
            )
            assert response.status_code == 422
            assert len(calls) == 3
    finally:
        overview_history.set_overview_history_reader(None)
        overview_history.set_overview_history_settings_store(None)


async def test_raw_refresh_failure_returns_503_without_a_new_bundle():
    async def read():
        raise OverviewHistoryPrometheusResponseError("upstream unavailable")

    overview_history.set_overview_history_reader(read)
    app = FastAPI()
    app.include_router(overview_history.router)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/overview-history")
            assert response.status_code == 503
            assert response.json() == {
                "detail": "Overview history is temporarily unavailable"
            }
    finally:
        overview_history.set_overview_history_reader(None)


async def test_primitive_shared_bundle_uses_identical_json_without_generic_conversion(
    monkeypatch,
):
    bundle = {
        "window_seconds": 300,
        "start_timestamp_seconds": 100,
        "end_timestamp_seconds": 400,
        "step_seconds": 1,
        "series": {"latency": [(100, 0.0), (101, 180.0), (103, 20.5)]},
        "rolling_5m": {
            "latency": {
                "state": "available",
                "min": [(100, 0.0)],
                "avg": [(100, 20.5)],
                "max": [(100, 180.0)],
            },
            "downlink": {"state": "unavailable", "min": [], "avg": [], "max": []},
        },
    }
    original = copy.deepcopy(bundle)
    converted = []
    encoder = fastapi.routing.jsonable_encoder

    def observe(value, *args, **kwargs):
        if value is bundle:
            converted.append(value)
        return encoder(value, *args, **kwargs)

    monkeypatch.setattr(fastapi.routing, "jsonable_encoder", observe)

    async def read():
        return bundle

    overview_history.set_overview_history_reader(read)
    app = FastAPI()
    app.include_router(overview_history.router)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for _ in range(2):
                response = await client.get("/api/overview-history")
                assert response.status_code == 200
                assert response.headers["content-type"] == "application/json"
                assert (
                    response.content
                    == json.dumps(
                        original,
                        ensure_ascii=False,
                        allow_nan=False,
                        separators=(",", ":"),
                    ).encode()
                )
                assert bundle == original
        assert converted == []
    finally:
        overview_history.set_overview_history_reader(None)
