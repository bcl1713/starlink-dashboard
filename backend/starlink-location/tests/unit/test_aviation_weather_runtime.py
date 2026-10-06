"""Real runtime behavior with only upstream I/O and worker boundary substituted."""

import asyncio
import json

import httpx
from fastapi import FastAPI

from app.api import aviation_weather
from app.models.aviation_weather import AviationCatalog
from app.services.aviation_weather.runtime import AviationWeatherService
from app.services.aviation_weather.settings import AviationSettingsStore
from app.services.overview_weather.protocol import WeatherUnavailable
from tests.fixtures.weather_streams import WeatherStreams, http_response
from tests.unit.test_overview_weather_service import NOW, metadata, service_for


def snapshot(layer, now):
    return {
        "type": "FeatureCollection",
        "source_id": "awc",
        "retrieved_at_ms": now,
        "feed_completeness": "unknown",
        "omitted_features": 0,
        "features": [
            {
                "type": "Feature",
                "id": "KJFK",
                "geometry": {"type": "Point", "coordinates": [-73.78, 40.64]},
                "properties": {
                    "observed_at_ms": now - 600000,
                    "expires_at_ms": now + 6600000,
                    "fresh_until_ms": now + 3900000,
                },
            }
        ],
    }


class Source:
    def __init__(self):
        self.calls = []
        self.closed = 0
        self.gate = None
        self.fail = False

    async def fetch(self, layer, before_attempt):
        before_attempt()
        self.calls.append(layer)
        if self.gate is not None:
            await self.gate.wait()
        if self.fail:
            raise WeatherUnavailable()
        return b"source"

    async def aclose(self):
        self.closed += 1


def runtime(tmp_path, now=None):
    now = now or [NOW]
    store = AviationSettingsStore(tmp_path / "aviation.json")
    source = Source()

    async def decode(layer, body, instant):
        return snapshot(layer, instant)

    service = AviationWeatherService(
        store,
        source,
        utc_ms=lambda: now[0],
        monotonic=lambda: now[0] / 1000,
        normalize=decode,
    )
    return service, store, source, now


def app_for(service, radar=None):
    app = FastAPI()
    app.state.aviation_weather_service = service
    app.state.aviation_weather_settings_store = service.store
    if radar:
        app.state.overview_weather_service = radar
    app.include_router(aviation_weather.router)
    return app


async def test_settings_default_off_and_invalid_updates_do_not_acquire(tmp_path):
    service, _store, source, _now = runtime(tmp_path)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app_for(service)), base_url="http://test"
    ) as client:
        settings = await client.get("/api/aviation-weather/v1/settings")
        assert settings.json() == {
            "metar": False,
            "taf": False,
            "sigmet": False,
            "winds": False,
            "temperature": False,
            "gfs_selection": {"pressure_pa": 50000, "horizon_hours": 0},
            "revision": 0,
        }
        for invalid in [
            {"metar": 1},
            {"revision": 2},
            {"metar": True, "unknown": False},
        ]:
            assert (
                await client.put("/api/aviation-weather/v1/settings", json=invalid)
            ).status_code == 422
        catalog = await client.get("/api/aviation-weather/v1/catalog")
        assert catalog.status_code == 200
        assert catalog.headers["cache-control"] == "no-store"
        assert [item["state"] for item in catalog.json()["products"]] == [
            "unavailable",
            "off",
            "off",
            "off",
        ]
        assert source.calls == []
    await service.aclose()
    assert source.closed == 1


async def test_admitted_immutable_snapshot_and_disable_invalidate_payload(tmp_path):
    service, _store, source, _now = runtime(tmp_path)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app_for(service)), base_url="http://test"
    ) as client:
        response = await client.put(
            "/api/aviation-weather/v1/settings", json={"metar": True}
        )
        assert response.json() == {
            "metar": True,
            "taf": False,
            "sigmet": False,
            "winds": False,
            "temperature": False,
            "gfs_selection": {"pressure_pa": 50000, "horizon_hours": 0},
            "revision": 1,
        }
        assert source.calls == []
        catalog = (await client.get("/api/aviation-weather/v1/catalog")).json()
        AviationCatalog.model_validate(catalog)
        entry = catalog["products"][1]
        assert entry["state"] == "ready"
        assert entry["time_kind"] == "observation"
        payload = await client.get(entry["payload"]["path"])
        assert payload.status_code == 200
        assert payload.json()["features"][0]["geometry"]["coordinates"] == [
            -73.78,
            40.64,
        ]
        assert payload.headers["cache-control"] == "private, no-cache"
        assert (await client.get("/api/aviation-weather/v1/catalog")).json()[
            "products"
        ][1]["instance_id"] == entry["instance_id"]
        assert source.calls == ["metar"]
        await client.put("/api/aviation-weather/v1/settings", json={"metar": False})
        assert (await client.get(entry["payload"]["path"])).status_code == 404
        assert service.pending_count == 0
    await service.aclose()


async def test_concurrent_readers_share_acquisition_and_cancel_only_last_lease(
    tmp_path,
):
    service, store, source, now = runtime(tmp_path)
    await service.settings_changed(store.update({"metar": True}))
    source.gate = asyncio.Event()
    first = asyncio.create_task(service.products())
    second = asyncio.create_task(service.products())
    for _ in range(20):
        await asyncio.sleep(0)
        if source.calls:
            break
    assert source.calls == ["metar"]
    first.cancel()
    await asyncio.gather(first, return_exceptions=True)
    source.gate.set()
    assert (await second)[0].state == "ready"
    assert source.calls == ["metar"]
    source.gate.clear()
    now[0] += 300000
    pending = asyncio.create_task(service.products())
    for _ in range(20):
        await asyncio.sleep(0)
        if len(source.calls) == 2:
            break
    pending.cancel()
    await asyncio.gather(pending, return_exceptions=True)
    assert service.pending_count == 0
    await service.aclose()


async def test_failure_preserves_original_deadlines_then_removes_expired_snapshot(
    tmp_path,
):
    service, store, source, now = runtime(tmp_path)
    await service.settings_changed(store.update({"metar": True}))
    first = (await service.products())[0]
    source.fail = True
    now[0] += 600000
    stale = (await service.products())[0]
    assert stale.state == "stale"
    assert stale.fresh_until_ms == first.fresh_until_ms
    assert stale.expires_at_ms == first.expires_at_ms
    assert stale.instance_id == first.instance_id
    now[0] = first.expires_at_ms
    assert (await service.products())[0].state == "unavailable"
    assert service.payload(first.instance_id, "metar.json") is None
    await asyncio.gather(service.aclose(), service.aclose())
    assert source.closed == 1


async def test_disable_during_acquisition_never_publishes(tmp_path):
    service, store, source, _now = runtime(tmp_path)
    await service.settings_changed(store.update({"metar": True}))
    source.gate = asyncio.Event()
    pending = asyncio.create_task(service.products())
    for _ in range(20):
        await asyncio.sleep(0)
        if source.calls:
            break
    await service.settings_changed(store.update({"metar": False}))
    assert (await pending)[0].state == "off"
    assert service.pending_count == 0
    await service.aclose()


async def test_radar_catalog_reuses_existing_pool_and_keeps_capability(tmp_path):
    service, _store, _source, now = runtime(tmp_path)
    streams = WeatherStreams(http_response(metadata()))
    radar, radar_store = service_for(tmp_path, streams, now)
    radar_store.update({"enabled": True})
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app_for(service, radar)), base_url="http://test"
    ) as client:
        result = await client.get("/api/aviation-weather/v1/catalog")
        assert result.status_code == 200
        entry = result.json()["products"][0]
        assert entry["state"] == "ready"
        assert entry["radar"]["product_id"] == entry["product_id"]
        assert entry["coverage"]["missing_meaning"] == "unknown-not-clear"
        first = entry["instance_id"]
        assert len(streams.dials) == 1
        assert (await radar.read_frame()).product_id == entry["product_id"]
        assert len(streams.dials) == 1
        now[0] = 1791244200000 + 1200000
        stale = (await client.get("/api/aviation-weather/v1/catalog")).json()[
            "products"
        ][0]
        assert stale["state"] == "stale"
        assert stale["instance_id"] == first
        now[0] = 1791244200000 + 3600000
        assert (await client.get("/api/aviation-weather/v1/catalog")).json()[
            "products"
        ][0]["state"] == "unavailable"
    await radar.aclose()
    await service.aclose()


async def test_missing_optional_runtime_is_sanitized_and_health_remains_usable():
    app = FastAPI()
    app.include_router(aviation_weather.router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        response = await client.get("/api/aviation-weather/v1/catalog")
        assert response.status_code == 503
        assert response.json() == {"detail": "Aviation weather unavailable"}


async def test_superseded_snapshot_never_resurrects_after_empty_generation_expires(
    tmp_path,
):
    service, store, source, now = runtime(tmp_path)

    async def decode(layer, body, instant):
        return (
            snapshot(layer, instant)
            if len(source.calls) == 1
            else {
                "type": "FeatureCollection",
                "features": [],
                "source_id": "awc",
                "feed_completeness": "unknown",
                "omitted_features": 0,
                "retrieved_at_ms": instant,
            }
        )

    service.normalize = decode
    await service.settings_changed(store.update({"sigmet": True}))
    original = (await service.products())[2]
    now[0] += 300000
    empty = (await service.products())[2]
    assert empty.instance_id != original.instance_id
    source.fail = True
    now[0] = empty.expires_at_ms
    assert (await service.products())[2].state == "unavailable"
    assert service.payload(original.instance_id, "sigmet.json") is None
    await service.aclose()


async def test_station_byte_cap_preserves_geographic_regions(tmp_path):
    service, store, _source, _now = runtime(tmp_path)

    async def decode(layer, body, instant):
        collection = snapshot(layer, instant)
        features = []
        for region, lon in [("AAAA", -100), ("BBBB", 0), ("CCCC", 100)]:
            for number in range(30):
                feature = json.loads(json.dumps(collection["features"][0]))
                feature["id"] = f"{region}{number:02d}"
                feature["geometry"]["coordinates"] = [lon, 40]
                feature["properties"]["raw_text"] = "x" * 20000
                features.append(feature)
        collection["features"] = features
        return collection

    service.normalize = decode
    await service.settings_changed(store.update({"metar": True}))
    entry = (await service.products())[0]
    body = service.payload(entry.instance_id, "metar.json")
    data = json.loads(body)
    assert len(body) <= 1024**2
    assert data["feed_completeness"] == "partial"
    assert data["omitted_features"] == 90 - len(data["features"])
    assert {f["geometry"]["coordinates"][0] for f in data["features"]} == {-100, 0, 100}
    await service.aclose()


async def test_cancellation_lineage_suppresses_replayed_original_without_cancelling_new_series_use(
    tmp_path,
):
    service, store, source, now = runtime(tmp_path)

    async def decode(layer, body, instant):
        result = snapshot(layer, instant)
        original = {
            "issuer": "KZNY",
            "fir": "KZNY",
            "series": "A1",
            "bulletin_series": "A1",
            "issued_at_ms": NOW - 600000,
            "cancellation_target": None,
            "revision": None,
            "valid_from_ms": NOW - 600000,
            "valid_to_ms": NOW + 7200000,
            "expires_at_ms": NOW + 7200000,
            "cancelled": False,
            "amends": None,
        }
        result["features"][0]["properties"].update(original)
        if len(source.calls) == 2:
            result["features"][0]["properties"].update(
                cancelled=True,
                amends="KZNY/KZNY/A1",
                valid_from_ms=instant,
                issued_at_ms=instant,
                cancellation_target={
                    "series": "A1",
                    "valid_from_ms": NOW - 600000,
                    "valid_to_ms": NOW + 7200000,
                },
            )
            result["features"][0]["geometry"] = None
        elif len(source.calls) >= 4:
            result["features"][0]["properties"].update(
                valid_from_ms=NOW + 900000,
                valid_to_ms=NOW + 10800000,
                expires_at_ms=NOW + 10800000,
            )
        return result

    service.normalize = decode
    await service.settings_changed(store.update({"sigmet": True}))
    assert (await service.products())[2].state == "ready"
    now[0] += 300000
    await service.products()
    now[0] += 300000
    third = (await service.products())[2]
    replay = json.loads(service.payload(third.instance_id, "sigmet.json"))["features"][
        0
    ]
    assert replay["properties"]["cancelled"] is True
    assert replay["geometry"] is None
    now[0] += 300000
    fourth = (await service.products())[2]
    newer = json.loads(service.payload(fourth.instance_id, "sigmet.json"))["features"][
        0
    ]
    assert newer["properties"]["cancelled"] is False
    assert newer["geometry"] is not None
    await service.aclose()


async def test_future_cancellation_lineage_waits_for_effective_utc_and_preserves_later_revision(
    tmp_path,
):
    service, _, _, _ = runtime(tmp_path)
    target = {
        "series": "OSCAR 55",
        "valid_from_ms": NOW - 600000,
        "valid_to_ms": NOW + 7200000,
    }
    cancellation = {
        "issuer": "KZNY",
        "fir": "KZNY",
        "bulletin_series": "OSCAR 56",
        "cancellation_target": target,
        "cancelled": True,
        "revision": None,
        "valid_from_ms": NOW + 300000,
        "valid_to_ms": NOW + 7200000,
        "issued_at_ms": NOW,
    }
    original = {
        **cancellation,
        "cancelled": False,
        "cancellation_target": None,
        "bulletin_series": "OSCAR 55",
        "valid_from_ms": NOW - 600000,
        "issued_at_ms": NOW - 600000,
    }
    service._advisory_history(
        {"features": [{"id": "cancel", "properties": cancellation}]}, NOW
    )

    def replay(issued):
        return {
            "features": [
                {
                    "id": "OSCAR55F",
                    "properties": {**original, "issued_at_ms": issued},
                    "geometry": {"type": "Polygon"},
                }
            ]
        }

    before = service._advisory_history(replay(NOW - 600000), NOW)
    assert before["features"][0]["properties"]["cancelled"] is False
    effective = service._advisory_history(replay(NOW - 600000), NOW + 300000)
    assert effective["features"][0]["geometry"] is None
    newer = service._advisory_history(replay(NOW + 1), NOW + 300000)
    assert newer["features"][0]["properties"]["cancelled"] is False
    await service.aclose()


async def test_future_cancellation_cutoff_removes_retained_geometry_when_refresh_fails(
    tmp_path,
):
    service, store, source, now = runtime(tmp_path)

    async def decode(layer, body, instant):
        collection = snapshot(layer, instant)
        original = collection["features"][0]
        original["properties"].update(
            issuer="KZNY",
            fir="KZNY",
            series="A1",
            bulletin_series="A1",
            issued_at_ms=NOW - 600000,
            valid_from_ms=NOW - 600000,
            valid_to_ms=NOW + 7200000,
            cancelled=False,
            revision=None,
            cancellation_target=None,
        )
        cancellation = json.loads(json.dumps(original))
        cancellation["id"] = "cancel"
        cancellation["geometry"] = None
        cancellation["properties"].update(
            cancelled=True,
            issued_at_ms=NOW,
            valid_from_ms=NOW + 300000,
            cancellation_target={
                "series": "A1",
                "valid_from_ms": NOW - 600000,
                "valid_to_ms": NOW + 7200000,
            },
        )
        collection["features"].append(cancellation)
        return collection

    service.normalize = decode
    await service.settings_changed(store.update({"sigmet": True}))
    first = (await service.products())[2]
    assert first.expires_at_ms == NOW + 300000
    source.fail = True
    now[0] += 300000
    assert (await service.products())[2].state == "unavailable"
    assert service.payload(first.instance_id, "sigmet.json") is None
    await service.aclose()
