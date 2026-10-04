import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import overview_adsb
from app.services.adsb_lol import AdsbLolProvider
from app.services.overview_adsb_settings import AdsbSettingsStore
from app.services.overview_adsb_traffic import AdsbTrafficService


async def test_traffic_api_filters_immediately_and_keeps_source_errors(tmp_path):
    now = 1791028800.0
    payload = {
        "now": now * 1000,
        "ac": [{"hex": "00ab12", "lat": 40, "lon": -75, "seen_pos": 0}],
    }
    upstream = httpx.AsyncClient(
        base_url="https://api.adsb.lol",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
    )
    store = AdsbSettingsStore(tmp_path / "adsb.json")
    service = AdsbTrafficService(
        store, AdsbLolProvider(upstream, lambda: now), lambda: now, lambda: now
    )
    overview_adsb.set_overview_adsb_runtime(store, service)
    app = FastAPI()
    app.include_router(overview_adsb.router)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            assert (await client.get("/api/overview-adsb/traffic")).json()[
                "contacts"
            ] == []
            await client.put("/api/overview-adsb/settings", json={"enabled": True})
            await service.refresh_once()
            assert (await client.get("/api/overview-adsb/traffic")).json()["contacts"][
                0
            ]["hex"] == "00AB12"
            await client.put(
                "/api/overview-adsb/settings", json={"exclude_hexes": ["00AB12"]}
            )
            assert (await client.get("/api/overview-adsb/traffic")).json()[
                "contacts"
            ] == []
            store._path.write_text("{bad")
            assert (await client.get("/api/overview-adsb/traffic")).status_code == 503
    finally:
        overview_adsb.set_overview_adsb_runtime(None, None)
        await service.aclose()
        await upstream.aclose()


def test_uninitialized_traffic_returns_503():
    app = FastAPI()
    app.include_router(overview_adsb.router)
    overview_adsb.set_overview_adsb_runtime(None, None)
    with TestClient(app) as client:
        assert client.get("/api/overview-adsb/traffic").status_code == 503


async def test_source_failure_returns_200_with_status(tmp_path):
    now = 1791028800.0
    async with httpx.AsyncClient(
        base_url="https://api.adsb.lol",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(503, content="private upstream body")
        ),
    ) as upstream:
        store = AdsbSettingsStore(tmp_path / "a.json")
        store.update({"enabled": True})
        service = AdsbTrafficService(
            store, AdsbLolProvider(upstream, lambda: now), lambda: now, lambda: now
        )
        overview_adsb.set_overview_adsb_runtime(store, service)
        app = FastAPI()
        app.include_router(overview_adsb.router)
        try:
            await service.refresh_once()
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/overview-adsb/traffic")
                assert response.status_code == 200
                assert response.json()["sources"][0]["error"]
                assert "private" not in response.text
        finally:
            overview_adsb.set_overview_adsb_runtime(None, None)
            await service.aclose()
