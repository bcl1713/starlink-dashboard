"""HTTP publication honesty and dependency-free exposition."""

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from prometheus_client import CollectorRegistry

from app.api import health, metrics_export
from app.api import metrics as http_metrics
from app.core.metrics import prometheus_metrics as metrics
from app.core.metrics.frames import FrameGaugeView, FrameStore, TelemetryFrameCollector
from app.mission.dependencies import get_poi_manager, get_route_manager
from tests.unit.test_metrics_frames import prepared


@pytest.fixture
def publication_http(monkeypatch):
    store = FrameStore(metrics.COUPLED_SCHEMA)
    registry = CollectorRegistry()
    registry.register(TelemetryFrameCollector(store, store.schema))
    monkeypatch.setattr(metrics, "FRAME_STORE", store)
    for definition in store.schema:
        monkeypatch.setattr(metrics, definition.name, FrameGaugeView(store, definition))
    monkeypatch.setattr(metrics_export, "REGISTRY", registry)
    monkeypatch.setattr(http_metrics, "_last_scrape_time", None)
    monkeypatch.setattr(metrics_export, "_exposition_error", None)
    monkeypatch.setattr(
        health,
        "_coordinator",
        SimpleNamespace(
            get_uptime_seconds=lambda: 10,
            mode="live",
            is_connected=lambda: False,
        ),
    )
    app = FastAPI()
    app.include_router(http_metrics.router)
    app.include_router(health.router)

    def forbidden():
        raise AssertionError("scrape resolved a source manager")

    app.dependency_overrides[get_route_manager] = forbidden
    app.dependency_overrides[get_poi_manager] = forbidden
    return app, store, registry


@pytest.mark.asyncio
async def test_http_never_resolves_manager_dependencies(publication_http):
    app, store, _ = publication_http
    store.publish(store.read(), prepared(store, 7))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        for _ in range(100):
            response = await client.get("/metrics")
            assert response.status_code == 200
            assert response.text.count("# EOF\n") == 1
        responses = await asyncio.gather(*(client.get("/metrics") for _ in range(100)))
    assert all(r.status_code == 200 for r in responses)
    assert all(r.text.endswith("# EOF\n") for r in responses)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state,want",
    [
        ("ready", "ok"),
        ("pending", "degraded"),
        ("failed", "degraded"),
        ("uninitialized", "degraded"),
    ],
)
async def test_publication_state_controls_health(publication_http, state, want):
    app, store, _ = publication_http
    if state != "uninitialized":
        store.publish(store.read(), prepared(store, 7))
    if state == "pending":
        store.invalidate("source change")
    elif state == "failed":
        store.fail(store.read(), "preparation failed")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/metrics")
        assert response.status_code == 200
        data = (await client.get("/health")).json()
    assert data["status"] == want
    assert data["metrics_publication"]["state"] == state
    if state != "ready":
        assert "starlink_dish_latitude_degrees NaN" in response.text


@pytest.mark.asyncio
async def test_export_failure_is_503_until_successful_exposition(publication_http):
    app, store, registry = publication_http
    store.publish(store.read(), prepared(store, 7))

    class BrokenCollector:
        def collect(self):
            raise ValueError("broken collector")

    broken = BrokenCollector()
    registry.register(broken)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/metrics")
        assert response.status_code == 503
        data = (await client.get("/health")).json()
        assert data["status"] == "degraded"
        assert data["prometheus_last_scrape"] is not None
        registry.unregister(broken)
        assert (await client.get("/health")).json()["status"] == "degraded"
        assert (await client.get("/metrics")).status_code == 200
        assert (await client.get("/health")).json()["status"] == "ok"


@pytest.mark.asyncio
async def test_unavailable_source_is_ready_and_preserves_last_observation(
    publication_http,
):
    from app.core.metrics.frame_builder import FrameInputs, prepare_unavailable_frame

    app, store, _ = publication_http
    store.publish(store.read(), prepared(store, 7))
    head = store.invalidate("disconnect")
    frame = prepare_unavailable_frame(FrameInputs(head))
    assert store.publish(head, frame)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/metrics")
        data = (await client.get("/health")).json()
    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/openmetrics-text; version=1.0.0; charset=utf-8"
    )
    assert "starlink_dish_latitude_degrees NaN" in response.text
    assert data["status"] == "ok"
    assert data["dish_connected"] is False
    assert store.read().frame.last_observation_publication_time == 123


@pytest.mark.asyncio
async def test_first_startup_health_retains_503(publication_http, monkeypatch):
    app, _, _ = publication_http
    monkeypatch.setattr(health, "_coordinator", None)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/metrics")).status_code == 200
        assert (await client.get("/health")).status_code == 503


@pytest.mark.asyncio
async def test_helper_failure_is_not_hidden_by_registry_fallback(
    publication_http, monkeypatch
):
    app, store, _ = publication_http
    store.publish(store.read(), prepared(store, 7))

    def broken(*args):
        raise RuntimeError("threadpool failed")

    monkeypatch.setattr(metrics_export, "run_in_threadpool", broken)
    before = metrics.REGISTRY.get_sample_value(
        "starlink_metrics_generation_errors_total"
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/metrics")
        assert response.status_code == 503
        assert (await client.get("/health")).json()["status"] == "degraded"
    assert (
        metrics.REGISTRY.get_sample_value("starlink_metrics_generation_errors_total")
        == before + 1
    )


@pytest.mark.asyncio
async def test_position_and_dynamic_labels_stay_in_one_generation(publication_http):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from prometheus_client import Counter, Histogram
    from prometheus_client.parser import text_string_to_metric_families

    app, store, registry = publication_http
    count = Counter(
        "independent_updates", "Independent observations", registry=registry
    )
    duration = Histogram(
        "independent_duration", "Independent durations", registry=registry
    )
    store.publish(store.read(), prepared(store, 1, "generation-1"))
    stop = Event()

    def produce():
        generation = 1
        while not stop.is_set():
            generation += 1
            frame = prepared(store, generation, f"generation-{generation}")
            assert store.publish(store.read(), frame)
            count.inc()
            duration.observe(0.1)

    with ThreadPoolExecutor(1) as pool:
        worker = pool.submit(produce)
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                responses = await asyncio.wait_for(
                    asyncio.gather(*(client.get("/metrics") for _ in range(100))), 15
                )
                positions = await asyncio.gather(
                    *(client.get("/position-table") for _ in range(100))
                )
            for response in responses:
                assert response.status_code == 200
                samples = [
                    s
                    for f in text_string_to_metric_families(response.text)
                    for s in f.samples
                    if s.name.startswith("starlink_")
                ]
                assert len({s.value for s in samples}) == 1
                labels = {
                    v for s in samples for k, v in s.labels.items() if k != "dimension"
                }
                assert len(labels) == 1
                assert "independent_updates_total" in response.text
                assert "independent_duration_bucket" in response.text
            for position in positions:
                assert position.status_code == 200
                assert len(set(position.json()["rows"][0][1:])) == 1
        finally:
            stop.set()
            worker.result(timeout=5)


@pytest.mark.asyncio
async def test_direct_helpers_use_custom_registry_without_managers(publication_http):
    _, store, _ = publication_http
    store.publish(store.read(), prepared(store, 5, "custom"))

    class ForbiddenManager:
        def __getattribute__(self, key):
            raise AssertionError(key)

    output = metrics_export._prepare_metrics(ForbiddenManager(), ForbiddenManager())
    assert "starlink_dish_latitude_degrees 5.0" in output
    assert output.count("# EOF\n") == 1
    assert (
        await metrics_export.get_metrics(ForbiddenManager(), ForbiddenManager())
        == output
    )


@pytest.mark.asyncio
async def test_concurrent_source_invalidation_never_exposes_stale_values(
    publication_http,
):
    import math
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from prometheus_client.parser import text_string_to_metric_families

    app, store, _ = publication_http
    store.publish(store.read(), prepared(store, 1, "old-source"))
    stop = Event()

    def transition():
        generation = 1
        while not stop.is_set():
            pending = store.invalidate("source transition")
            store.fail(pending, "preparation failed")
            generation += 1
            assert store.publish(
                store.read(), prepared(store, generation, f"source-{generation}")
            )

    with ThreadPoolExecutor(1) as pool:
        worker = pool.submit(transition)
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                responses = await asyncio.wait_for(
                    asyncio.gather(*(client.get("/metrics") for _ in range(100))), 15
                )
            for response in responses:
                assert response.status_code == 200
                samples = [
                    s
                    for f in text_string_to_metric_families(response.text)
                    for s in f.samples
                    if s.name != "starlink_metrics_last_update_timestamp_seconds"
                ]
                finite = {s.value for s in samples if not math.isnan(s.value)}
                if finite:
                    assert len(finite) == 1
                    assert all(not math.isnan(s.value) for s in samples)
                else:
                    assert all(math.isnan(s.value) for s in samples)
        finally:
            stop.set()
            worker.result(timeout=5)


@pytest.mark.asyncio
async def test_http_bookkeeping_does_not_renew_publication(publication_http):
    app, store, _ = publication_http
    store.publish(store.read(), prepared(store, 3))
    head = store.read()
    before = metrics.REGISTRY.get_sample_value(
        "starlink_metrics_scrape_duration_seconds_count"
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/metrics")).status_code == 200
    assert (
        metrics.REGISTRY.get_sample_value(
            "starlink_metrics_scrape_duration_seconds_count"
        )
        == before + 1
    )
    assert store.read() is head


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [RuntimeError, AssertionError])
async def test_health_detects_registry_failure_after_recent_success(
    publication_http, error
):
    app, store, _ = publication_http
    store.publish(store.read(), prepared(store, 3))

    class BrokenCollector:
        def collect(self):
            raise error("registry unavailable")

    broken = BrokenCollector()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/metrics")).status_code == 200
        metrics.REGISTRY.register(broken)
        try:
            data = (await client.get("/health")).json()
            assert data["status"] == "degraded"
            assert data["metrics_publication"]["exposition_error"] == error.__name__
        finally:
            metrics.REGISTRY.unregister(broken)
        assert (await client.get("/health")).json()["status"] == "degraded"
        assert (await client.get("/metrics")).status_code == 200
        assert (await client.get("/health")).json()["status"] == "ok"
