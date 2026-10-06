import json
import struct

import pytest

from app.services.overview_weather.clock import WeatherClock
from app.services.overview_weather.service import (
    WeatherService,
    WeatherTileError,
    validate_png,
)
from app.services.overview_weather.settings import WeatherSettingsStore
from tests.fixtures.weather_streams import WeatherStreams, http_response
from tests.unit.test_overview_weather_acquisitions import pool_for

NOW = 1791244800000


def metadata(time_seconds=1791244200, path=None):
    return json.dumps(
        {
            "host": "https://tilecache.rainviewer.com",
            "radar": {
                "past": [
                    {"time": time_seconds, "path": path or f"/v2/radar/{time_seconds}"}
                ],
                "nowcast": [{"time": 1791244800, "path": "/v2/radar/1791244800"}],
            },
        }
    ).encode()


def service_for(tmp_path, streams, now=None):
    now = now or [NOW]
    clock = WeatherClock(utc_ms=lambda: now[0], monotonic=lambda: now[0] / 1000)
    store = WeatherSettingsStore(tmp_path / "weather.json")
    return WeatherService(store, pool_for(streams, clock), clock), store


async def test_default_off_and_disable_never_read_provider_or_cached_tile(tmp_path):
    streams = WeatherStreams(http_response(metadata()))
    service, store = service_for(tmp_path, streams)
    assert (await service.read_frame()).state == "off"
    assert streams.dials == []
    store.update({"enabled": True})
    ready = await service.read_frame()
    assert ready.frame_time_ms == 1791244200000
    assert (
        ready.radar_tile_template
        == "/api/overview-weather/radar/1791244200/{z}/{x}/{y}.png"
    )
    assert ready.coverage_token == 20732
    assert ready.coverage_expires_at_ms == 1791331200000
    await service.settings_changed(store.update({"enabled": False}))
    with pytest.raises(WeatherTileError) as caught:
        await service.radar_tile(1791244200, 2, 0, 0)
    assert caught.value.status_code == 409
    assert len(streams.dials) == 1
    await service.aclose()


async def test_expired_cached_metadata_and_midnight_mask_are_not_reused(tmp_path):
    now = [NOW + 86300000]
    frame = now[0] // 1000 - 600
    streams = WeatherStreams(http_response(metadata(frame)))
    service, store = service_for(tmp_path, streams, now)
    store.update({"enabled": True})
    ready = await service.read_frame()
    now[0] += 100000
    with pytest.raises(WeatherTileError) as caught:
        await service.coverage_tile(ready.coverage_token, 2, 0, 0)
    assert caught.value.status_code == 404
    now[0] += 3600000
    assert (await service.read_frame()).state == "unavailable"
    await service.aclose()


@pytest.mark.parametrize("frame", [True, -1, 1791244861, 1791241200])
async def test_ineligible_times_cannot_admit_frame(tmp_path, frame):
    streams = WeatherStreams(http_response(metadata(frame)))
    service, store = service_for(tmp_path, streams)
    store.update({"enabled": True})
    assert (await service.read_frame()).state == "unavailable"
    await service.aclose()


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(host="https://localhost"),
        lambda p: p["radar"]["past"][0].update(path="/v2/radar/../private"),
        lambda p: p["radar"].update(past=[p["radar"]["past"][0]] * 33),
    ],
)
async def test_invalid_metadata_is_not_admitted(tmp_path, change):
    payload = json.loads(metadata())
    change(payload)
    streams = WeatherStreams(http_response(json.dumps(payload).encode()))
    service, store = service_for(tmp_path, streams)
    store.update({"enabled": True})
    assert (await service.read_frame()).state == "unavailable"
    await service.aclose()


def test_png_requires_signature_and_512_square_ihdr():
    prefix = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
    validate_png(
        prefix + struct.pack(">II", 512, 512) + b"\x08\x06\x00\x00\x00" + b"\x00" * 4
    )
    for body in [b"not-png", prefix + struct.pack(">II", 256, 512) + b"\x00" * 9]:
        with pytest.raises(ValueError):
            validate_png(body)


async def test_retains_two_frames_without_regressing_and_accepts_future_tolerance(
    tmp_path,
):
    now = [NOW]
    streams = WeatherStreams(http_response(metadata(1791244860)))
    service, store = service_for(tmp_path, streams, now)
    store.update({"enabled": True})
    assert (await service.read_frame()).frame_time_ms == 1791244860000
    for seconds in [300, 600]:
        now[0] = NOW + seconds * 1000
        streams.wire = http_response(metadata(now[0] // 1000))
        assert (await service.read_frame()).frame_time_ms == now[0]
    with pytest.raises(WeatherTileError) as old:
        await service.radar_tile(1791244860, 2, 0, 0)
    assert old.value.status_code == 404
    now[0] += 300000
    streams.wire = http_response(metadata(1791244800))
    assert (await service.read_frame()).frame_time_ms == 1791245400000
    await service.aclose()


async def test_disable_during_generation_pruning_does_not_start_exchange(
    tmp_path, monkeypatch
):
    streams = WeatherStreams(http_response(metadata()))
    service, store = service_for(tmp_path, streams)
    store.update({"enabled": True})
    original = service.pool.prune

    async def disable_after_pruning(allowed):
        await original(allowed)
        await service.settings_changed(store.update({"enabled": False}))

    monkeypatch.setattr(service.pool, "prune", disable_after_pruning)
    assert (await service.read_frame()).state == "off"
    assert streams.dials == []
    await service.aclose()


@pytest.mark.parametrize("bad_frame", [NOW // 1000 - 3600, NOW // 1000 + 10000])
async def test_ineligible_metadata_recovers_after_failure_cooldown(tmp_path, bad_frame):
    now = [NOW]
    streams = WeatherStreams(http_response(metadata(bad_frame)))
    service, store = service_for(tmp_path, streams, now)
    store.update({"enabled": True})
    assert (await service.read_frame()).state == "unavailable"
    streams.wire = http_response(metadata(NOW // 1000))
    now[0] += 31000
    recovered = await service.read_frame()
    assert recovered.state == "ready"
    assert recovered.frame_time_ms == NOW
    assert len(streams.dials) == 2
    await service.aclose()


@pytest.mark.parametrize("path", ["/v2/radar/f1fa64870793", "/v2/radar/frame_ID-2"])
async def test_observed_opaque_path_serves_radar_under_local_timestamp(tmp_path, path):
    streams = WeatherStreams(http_response(metadata(path=path)))
    service, store = service_for(tmp_path, streams)
    store.update({"enabled": True})
    try:
        ready = await service.read_frame()
        assert ready.state == "ready"
        assert ready.frame_time_ms == 1791244200000
        assert ready.radar_tile_template == (
            "/api/overview-weather/radar/1791244200/{z}/{x}/{y}.png"
        )
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR"
            + struct.pack(">II", 512, 512)
            + b"\x08\x06\x00\x00\x00\x00\x00\x00\x00"
        )
        streams.wire = http_response(png, "image/png")
        assert (await service.radar_tile(1791244200, 2, 1, 1)).body == png
        assert f"GET {path}/512/2/1/1/2/1_1.png HTTP/1.1".encode() in (
            streams.writers[-1].written
        )
    finally:
        await service.aclose()


@pytest.mark.parametrize(
    "path",
    [
        "/v2/radar/../private",
        "/v2/radar/%2e%2e",
        "/v2/radar/id/extra",
        "/v2/radar/id?url=http://localhost",
        "/v2/radar/id#fragment",
        "/v2/radar/",
        "/v2/radar/" + "a" * 129,
        "https://evil.example/v2/radar/id",
    ],
)
async def test_unsafe_provider_frame_paths_are_not_admitted(tmp_path, path):
    streams = WeatherStreams(http_response(metadata(path=path)))
    service, store = service_for(tmp_path, streams)
    store.update({"enabled": True})
    try:
        assert (await service.read_frame()).state == "unavailable"
        with pytest.raises(WeatherTileError) as caught:
            await service.radar_tile(1791244200, 2, 1, 1)
        assert caught.value.status_code == 404
        assert len(streams.dials) == 1
    finally:
        await service.aclose()
