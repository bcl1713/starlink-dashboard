"""Actual ASGI receive events release production transport subscriber leases."""

import asyncio

from tests.fixtures.weather_streams import WeatherStreams
from tests.unit.test_overview_weather_api import weather_app
from tests.unit.test_overview_weather_service import service_for


async def start_request(app, path):
    receive_queue = asyncio.Queue()
    await receive_queue.put({"type": "http.request", "body": b"", "more_body": False})
    messages = []

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "scheme": "http",
        "server": ("test", 80),
        "client": ("127.0.0.1", 1234),
    }
    task = asyncio.create_task(app(scope, receive_queue.get, send))
    return task, receive_queue, messages


async def test_actual_disconnect_preserves_sibling_disable_shutdown_close_once(
    tmp_path,
):
    streams = WeatherStreams()
    service, store = service_for(tmp_path, streams)
    store.update({"enabled": True})
    app = weather_app(service, store)
    first, queue, _ = await start_request(app, "/api/overview-weather/frame")
    await streams.opened.wait()
    second, _, _ = await start_request(app, "/api/overview-weather/frame")
    for _ in range(10):
        await asyncio.sleep(0)
    await queue.put({"type": "http.disconnect"})
    await first
    assert not second.done()
    assert streams.writers[0].close_calls == 0
    await service.settings_changed(store.update({"enabled": False}))
    await second
    await asyncio.gather(service.aclose(), service.aclose())
    assert streams.writers[0].close_calls == 1
    assert streams.writers[0].wait_closed_calls == 1
    assert len(streams.dials) == 1
