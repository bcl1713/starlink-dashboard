"""Real same-origin routes admit only current enabled scientific artifacts."""

import asyncio
import hashlib
import json
import uuid

import httpx
import pytest

from app.services.aviation_weather.runtime import AviationWeatherService
from app.services.aviation_weather.settings import AviationSettingsStore
from tests.fixtures.gfs_fields import RUN
from tests.unit.test_aviation_weather_runtime import Source, app_for
from tests.unit.test_gfs_grid import candidate
from tests.unit.test_gfs_ipc import other_owner
from tests.unit.test_gfs_worker import alive, worker_process


def runtime(root, *, publish=True):
    from app.services.aviation_weather.gfs.bridge import GfsBridge
    from app.services.aviation_weather.gfs.store import GfsProductStore

    settings = AviationSettingsStore(root / "settings.json")
    enabled = settings.update({"winds": True, "temperature": True})
    now = [RUN]
    source = Source()
    service = AviationWeatherService(settings, source, utc_ms=lambda: now[0])
    products = GfsProductStore(
        root / "artifacts", root / "mailbox", settings, clock=lambda: RUN / 1000
    )
    if publish:
        products.publish(candidate(root / "work"), enabled.revision)
    bridge = GfsBridge(
        settings, products.root, products.mailbox, clock=lambda: now[0] / 1000
    )
    app = app_for(service)
    app.state.aviation_gfs_bridge = bridge
    return app, service, bridge, products, enabled, now, source


async def test_same_origin_descriptor_binary_hashes_and_private_revalidation(tmp_path):
    app, service, bridge, _products, enabled, now, source = runtime(tmp_path)
    with other_owner(bridge.mailbox.root / "worker.lock"):
        bridge.mailbox.heartbeat(enabled.revision, uuid.uuid4().hex, now[0])
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            catalog = await client.get("/api/aviation-weather/v1/catalog")
            assert catalog.status_code == 200
            entry = next(
                item
                for item in catalog.json()["products"]
                if item["product_type"] == "winds"
            )
            assert entry["state"] == "ready"
            descriptor = await client.get(entry["payload"]["path"])
            assert descriptor.status_code == 200
            assert (
                hashlib.sha256(descriptor.content).hexdigest()
                == entry["payload"]["sha256"]
            )
            assert descriptor.headers["cache-control"] == "private, no-cache"
            for buffer in descriptor.json()["buffers"].values():
                payload = await client.get(buffer["path"])
                assert payload.status_code == 200
                assert payload.headers["content-type"] == "application/octet-stream"
                assert len(payload.content) == buffer["byte_length"]
                assert hashlib.sha256(payload.content).hexdigest() == buffer["sha256"]
                assert payload.headers["etag"] == f'"{buffer["sha256"]}"'
                assert (
                    await client.get(
                        buffer["path"],
                        headers={"If-None-Match": payload.headers["etag"]},
                    )
                ).status_code == 304
            assert source.calls == []
    await bridge.aclose()
    await service.aclose()


async def test_missing_or_stale_worker_denies_models_without_awaiting_ingest(tmp_path):
    app, service, bridge, _products, enabled, now, source = runtime(tmp_path)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        async with asyncio.timeout(1):
            result = await client.get("/api/aviation-weather/v1/catalog")
        models = result.json()["products"][-2:]
        assert [item["state"] for item in models] == ["unavailable", "unavailable"]
        assert (
            await client.get("/api/aviation-weather/v1/settings")
        ).status_code == 200
        assert source.calls == []
        with other_owner(bridge.mailbox.root / "worker.lock"):
            bridge.mailbox.heartbeat(enabled.revision, uuid.uuid4().hex, now[0] - 15001)
            result = await client.get("/api/aviation-weather/v1/catalog")
            assert all(
                item["state"] == "unavailable"
                for item in result.json()["products"][-2:]
            )
    await bridge.aclose()
    await service.aclose()


async def test_original_freshness_and_expiry_are_not_renewed(tmp_path):
    app, service, bridge, _products, enabled, now, _source = runtime(tmp_path)
    with other_owner(bridge.mailbox.root / "worker.lock"):
        owner = uuid.uuid4().hex
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            for hours, state in ((0, "ready"), (9, "stale"), (18, "unavailable")):
                now[0] = RUN + hours * 3600000
                bridge.mailbox.heartbeat(enabled.revision, owner, now[0])
                result = await client.get("/api/aviation-weather/v1/catalog")
                model = result.json()["products"][-2]
                assert model["state"] == state
                if state != "unavailable":
                    assert model["retrieved_at_ms"] == RUN
                    assert model["expires_at_ms"] == RUN + 18 * 3600000
                    assert model["valid_at_ms"] == RUN + 6 * 3600000
                    path = model["payload"]["path"]
            assert (await client.get(path)).status_code == 404
    await bridge.aclose()
    await service.aclose()


async def test_disabled_obsolete_and_unknown_paths_have_no_payload(tmp_path):
    app, service, bridge, _products, enabled, now, _source = runtime(tmp_path)
    with other_owner(bridge.mailbox.root / "worker.lock"):
        bridge.mailbox.heartbeat(enabled.revision, uuid.uuid4().hex, now[0])
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            catalog = (await client.get("/api/aviation-weather/v1/catalog")).json()
            path = catalog["products"][-2]["payload"]["path"]
            service.store.update({"winds": False})
            assert (await client.get(path)).status_code == 404
            assert (
                await client.get(path.replace("grid.json", "lineage.json"))
            ).status_code == 404
            assert (
                await client.get(path.replace("grid.json", ".."))
            ).status_code == 404
    await bridge.aclose()
    await service.aclose()


async def test_disable_waits_for_real_owned_child_exit(tmp_path):
    app, service, bridge, products, enabled, _now, _source = runtime(
        tmp_path, publish=False
    )
    (tmp_path / "clock.json").write_text(json.dumps(RUN))
    bridge.mailbox.renew(bridge.owner, enabled, RUN)
    with worker_process(tmp_path, "blocked"):
        ready = tmp_path / "decoder-ready.json"
        async with asyncio.timeout(5):
            while not ready.exists():
                await asyncio.sleep(0.02)
        child = json.loads(ready.read_text())["pid"]
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.put(
                "/api/aviation-weather/v1/settings",
                json={"winds": False, "temperature": False},
            )
            assert response.status_code == 200
            assert response.json()["revision"] == enabled.revision + 1
            assert not alive(child)
            assert not list((products.root / "staging").iterdir())
    await bridge.aclose()
    await service.aclose()


async def test_missing_ack_returns_sanitized_503_but_disabled_save_stays_committed(
    tmp_path, monkeypatch
):
    import app.services.aviation_weather.gfs.bridge as module

    app, service, bridge, _products, enabled, now, _source = runtime(tmp_path)
    monkeypatch.setattr(module, "ACK_SECONDS", 0.05)
    with other_owner(bridge.mailbox.root / "worker.lock"):
        bridge.mailbox.heartbeat(enabled.revision, uuid.uuid4().hex, now[0])
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.put(
                "/api/aviation-weather/v1/settings",
                json={"winds": False, "temperature": False},
            )
            assert response.status_code == 503
            assert response.json() == {"detail": "Aviation weather unavailable"}
            assert not service.store.get().winds
            assert not service.store.get().temperature
    await bridge.aclose()
    await service.aclose()


async def test_disconnect_releases_lease_and_unstarted_response_owns_none(tmp_path):
    _app, service, bridge, products, enabled, _now, _source = runtime(tmp_path)
    with other_owner(bridge.mailbox.root / "worker.lock"):
        bridge.mailbox.heartbeat(enabled.revision, uuid.uuid4().hex, RUN)
        descriptor = products.read_current(enabled.gfs_selection, RUN)[0]
        response = await bridge.response(descriptor.instance_id, "u.bin", enabled, RUN)
        path = products.root / "products" / descriptor.instance_id
        scope = {
            "type": "http",
            "method": "GET",
            "headers": [],
            "path": "/",
            "http_version": "1.1",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
        }

        async def receive():
            return {"type": "http.disconnect"}

        async def send(message):
            if message["type"] == "http.response.body":
                products.prune(RUN + 18 * 3600000)
                assert path.exists()
                raise OSError("fixture socket disconnect")

        with pytest.raises(OSError):
            await response(scope, receive, send)
        products.prune(RUN + 18 * 3600000)
        assert not path.exists()
        # Preparing a replacement response does not hold a lease before ASGI
        # starts it; the route disconnect watcher may discard this response.
        products.publish(candidate(tmp_path / "replacement"), enabled.revision)
        descriptor = products.read_current(enabled.gfs_selection, RUN)[0]
        abandoned = await bridge.response(descriptor.instance_id, "u.bin", enabled, RUN)
        assert abandoned is not None
        products.prune(RUN + 18 * 3600000)
        assert not (products.root / "products" / descriptor.instance_id).exists()
    await bridge.aclose()
    await service.aclose()


async def test_corrupted_binary_is_denied_and_clock_rollback_withdraws_demand(tmp_path):
    _app, service, bridge, products, enabled, _now, _source = runtime(tmp_path)
    with other_owner(bridge.mailbox.root / "worker.lock"):
        bridge.mailbox.heartbeat(enabled.revision, uuid.uuid4().hex, RUN)
        model = (await bridge.products(enabled, RUN))[0]
        path = products.root / "products" / model.instance_id / "u.bin"
        body = path.read_bytes()
        path.write_bytes(b"x" + body[1:])
        assert await bridge.response(model.instance_id, "u.bin", enabled, RUN) is None
        assert all(
            product.state == "unavailable"
            for product in await bridge.products(enabled, RUN - 1)
        )
        assert bridge.mailbox.current(RUN) is None
    await bridge.aclose()
    await service.aclose()


def test_two_process_save_publish_race_rejects_obsolete_pointer(tmp_path):
    import subprocess
    import sys
    import time
    from pathlib import Path

    from app.services.aviation_weather.gfs.store import control_lock

    _app, service, bridge, products, enabled, _now, _source = runtime(
        tmp_path, publish=False
    )
    new = candidate(tmp_path / "work")
    command = [
        sys.executable,
        "-m",
        "tests.fixtures.gfs_publish_process",
        str(tmp_path),
        str(new.directory),
        str(enabled.revision),
    ]
    (tmp_path / "publisher-owner.json").write_text(
        json.dumps({"command": command, "state": "starting"})
    )
    process = None
    try:
        with control_lock(bridge.mailbox.root):
            process = subprocess.Popen(
                command, cwd=Path(__file__).parents[2], start_new_session=True
            )
            (tmp_path / "publisher-owner.json").write_text(
                json.dumps(
                    {"command": command, "pid": process.pid, "pgid": process.pid}
                )
            )
            deadline = time.monotonic() + 5
            while (
                not (tmp_path / "publisher-ready").exists()
                and time.monotonic() < deadline
            ):
                time.sleep(0.02)
            assert (tmp_path / "publisher-ready").exists()
            changed = service.store.update({"winds": False, "temperature": False})
            bridge.mailbox.invalidate_locked(changed.revision)
        assert process.wait(timeout=5) == 20
        assert not (products.root / "current.json").exists()
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


async def test_oversized_damaged_binary_is_rejected_before_allocation(tmp_path):
    import tracemalloc

    _app, service, bridge, products, enabled, _now, _source = runtime(tmp_path)
    with other_owner(bridge.mailbox.root / "worker.lock"):
        bridge.mailbox.heartbeat(enabled.revision, uuid.uuid4().hex, RUN)
        descriptor = products.read_current(enabled.gfs_selection, RUN)[0]
        with (products.root / "products" / descriptor.instance_id / "u.bin").open(
            "r+b"
        ) as stream:
            stream.truncate(32 * 1024**2)
        tracemalloc.start()
        try:
            assert (
                await bridge.response(descriptor.instance_id, "u.bin", enabled, RUN)
                is None
            )
            _current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert peak < 2 * 1024**2
    await bridge.aclose()
    await service.aclose()
