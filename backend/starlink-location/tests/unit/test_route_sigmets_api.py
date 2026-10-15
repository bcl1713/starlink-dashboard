"""Authoritative API conflicts, sanitized failures and settings isolation."""

import httpx
from fastapi import FastAPI

from app.api import aviation_weather
from tests.unit.test_route_sigmets_runtime import close, mutation, setup_service


def app_for(service, weather):
    from app.api import route_sigmets

    app = FastAPI()
    app.state.route_sigmet_service = service
    app.state.aviation_weather_service = weather
    app.state.aviation_weather_settings_store = weather.store
    app.include_router(route_sigmets.router)
    app.include_router(aviation_weather.router)
    return app


async def test_old_revision_clear_returns_conflict(tmp_path):
    service, weather, store, _, now, mono, reports, _ = setup_service(tmp_path)
    try:
        store.update({"sigmet": True})
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app_for(service, weather)),
            base_url="http://test",
        ) as client:
            first = await client.get("/api/aviation-weather/v1/route-sigmets")
            assert (
                first.status_code == 200
                and first.headers["cache-control"] == "no-store"
            )
            entry = first.json()["entries"][0]
            change = {
                "context_key": first.json()["context"]["context_key"],
                "notice_key": entry["notice_key"],
                "semantic_digest": entry["semantic_digest"],
                "acknowledged": True,
            }
            accepted = await client.put(
                "/api/aviation-weather/v1/route-sigmets/acknowledgement", json=change
            )
            assert (
                accepted.status_code == 200
                and accepted.headers["cache-control"] == "no-store"
            )
            reports[0]["properties"].update(revision="AMD", issued_at_ms=150)
            now[0], mono[0] = 1100, 301
            obsolete = await client.put(
                "/api/aviation-weather/v1/route-sigmets/acknowledgement", json=change
            )
            assert (
                obsolete.status_code == 409
                and obsolete.headers["cache-control"] == "no-store"
            )
            replacement = (
                await client.get("/api/aviation-weather/v1/route-sigmets")
            ).json()
            assert not replacement["entries"][0]["acknowledged"]
            for invalid in [{**change, "acknowledged": 1}, {**change, "extra": True}]:
                assert (
                    await client.put(
                        "/api/aviation-weather/v1/route-sigmets/acknowledgement",
                        json=invalid,
                    )
                ).status_code == 422
    finally:
        await close(service, weather)


async def test_storage_failure_is_sanitized_and_does_not_change_weather_settings(
    tmp_path,
):
    service, weather, store, source, _, _, _, _ = setup_service(tmp_path)
    try:
        store.update({"sigmet": True})
        first = await service.read()
        settings = store.path.read_bytes()
        service.store.path.write_text("private corrupt fixture")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app_for(service, weather)),
            base_url="http://test",
        ) as client:
            failed = await client.put(
                "/api/aviation-weather/v1/route-sigmets/acknowledgement",
                json=mutation(first).model_dump(),
            )
            assert failed.status_code == 503
            assert (
                "private" not in failed.text
                and failed.headers["cache-control"] == "no-store"
            )
            assert (
                await client.get("/api/aviation-weather/v1/settings")
            ).status_code == 200
        assert store.path.read_bytes() == settings and source.calls == ["sigmet"]
    finally:
        await close(service, weather)


async def test_clear_does_not_invalidate_gfs_demand_or_settings(tmp_path):
    import uuid

    from app.services.aviation_weather.gfs.bridge import GfsBridge

    service, weather, store, source, _, _, _, _ = setup_service(tmp_path)
    bridge = GfsBridge(store, tmp_path / "gfs", tmp_path / "mailbox")
    try:
        settings = store.update({"sigmet": True, "winds": True})
        bridge.mailbox.renew(uuid.uuid4().hex, settings, 1000)
        demand = (bridge.mailbox.root / "demand.json").read_bytes()
        preferences = store.path.read_bytes()
        first = await service.read()
        app = app_for(service, weather)
        app.state.aviation_gfs_bridge = bridge
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.put(
                "/api/aviation-weather/v1/route-sigmets/acknowledgement",
                json=mutation(first).model_dump(),
            )
            assert response.status_code == 200
        assert (bridge.mailbox.root / "demand.json").read_bytes() == demand
        assert store.path.read_bytes() == preferences and source.calls == ["sigmet"]
    finally:
        await bridge.aclose()
        await close(service, weather)


async def test_deadline_cancels_source_lease_and_validation_errors_are_no_store(
    tmp_path, monkeypatch
):
    import asyncio

    from app.api import route_sigmets

    monkeypatch.setattr(route_sigmets, "REQUEST_SECONDS", 0.03)
    service, weather, store, source, _, _, _, _ = setup_service(tmp_path)
    try:
        store.update({"sigmet": True})
        source.gate = asyncio.Event()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app_for(service, weather)),
            base_url="http://test",
        ) as client:
            result = await client.get("/api/aviation-weather/v1/route-sigmets")
            assert (
                result.status_code == 503
                and result.headers["cache-control"] == "no-store"
            )
            assert weather.pending_count == 0
            bad = await client.put(
                "/api/aviation-weather/v1/route-sigmets/acknowledgement", json={}
            )
            assert bad.status_code == 422 and bad.headers["cache-control"] == "no-store"
    finally:
        await close(service, weather)


async def test_real_settings_lock_contention_finishes_request_and_keeps_health_responsive(
    tmp_path, monkeypatch
):
    import asyncio
    import threading
    from types import SimpleNamespace

    from app.api import health, route_sigmets

    service, weather, store, _, _, _, _, _ = setup_service(tmp_path)
    entered, release = threading.Event(), threading.Event()

    def hold():
        with store.lock:
            entered.set()
            release.wait(3)

    holder = threading.Thread(target=hold)
    holder.start()
    monkeypatch.setattr(route_sigmets, "REQUEST_SECONDS", 0.05)
    monkeypatch.setattr(
        health,
        "_coordinator",
        SimpleNamespace(mode="simulation", get_uptime_seconds=lambda: 1),
    )
    try:
        assert await asyncio.to_thread(entered.wait, 1)
        app = app_for(service, weather)
        app.include_router(health.router)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            started = asyncio.get_running_loop().time()
            pending = asyncio.create_task(
                client.get("/api/aviation-weather/v1/route-sigmets")
            )
            await asyncio.sleep(0.02)
            healthy = await client.get("/health")
            assert healthy.status_code == 200
            assert asyncio.get_running_loop().time() - started < 0.3
            response = await pending
            assert response.status_code == 503
            assert asyncio.get_running_loop().time() - started < 1.6
    finally:
        release.set()
        await asyncio.to_thread(holder.join, 1)
        await close(service, weather)
