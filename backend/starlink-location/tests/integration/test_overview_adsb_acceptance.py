"""Owned-service acceptance with a controlled provider, never live ADS-B calls."""

import asyncio
import time

import httpx
import main
from app.api import overview_adsb
from app.services.adsb_lol import AdsbLolProvider
from app.services.overview_adsb_settings import AdsbSettingsStore
from app.services.overview_adsb_traffic import AdsbTrafficService
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_normal_lifespan_persists_settings_but_not_contacts(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "OVERVIEW_ADSB_SETTINGS_PATH", tmp_path / "adsb.json")
    original = httpx.AsyncClient
    fail = False

    def provider(request):
        assert request.url.host == "api.adsb.lol"
        if fail:
            return httpx.Response(503)
        return httpx.Response(
            200,
            json={
                "now": time.time() * 1000,
                "ac": [{"hex": "00ab12", "lat": 38, "lon": -90, "seen_pos": 0}],
            },
        )

    def client_factory(*args, **kwargs):
        if kwargs.get("base_url") == "https://api.adsb.lol":
            kwargs["transport"] = httpx.MockTransport(provider)
        return original(*args, **kwargs)

    monkeypatch.setattr(main.httpx, "AsyncClient", client_factory)
    with TestClient(main.app) as client:
        saved = client.put(
            "/api/overview-adsb/settings",
            json={"enabled": True, "include_hexes": ["00AB12"]},
        ).json()
        client.portal.call(main.app.state.overview_adsb_service.refresh_once)
        assert len(client.get("/api/overview-adsb/traffic").json()["contacts"]) == 1
    fail = True
    with TestClient(main.app) as client:
        assert client.get("/api/overview-adsb/settings").json() == saved
        assert client.get("/api/overview-adsb/traffic").json()["contacts"] == []
    assert overview_adsb._service is None


async def test_global_workload_and_many_clients_share_one_acquisition(tmp_path):
    now = 1791028800.0
    records = [
        {
            "hex": f"{i:06x}",
            "lat": -80 + i % 161,
            "lon": -179 + i % 359,
            "seen_pos": 40 if i % 3 == 0 else 0,
            "flight": f"RCH-{i}",
        }
        for i in range(2000)
    ]
    requests = []

    async def provider(request):
        requests.append(request.url.path)
        await asyncio.sleep(0)
        if request.url.path.endswith("/mil"):
            return httpx.Response(
                200, json={"now": now * 1000, "ac": records + records[:3]}
            )
        return httpx.Response(503)

    async with httpx.AsyncClient(
        base_url="https://api.adsb.lol", transport=httpx.MockTransport(provider)
    ) as upstream:
        store = AdsbSettingsStore(tmp_path / "adsb.json")
        store.update(
            {
                "enabled": True,
                "include_hexes": [f"{i:06X}" for i in range(50)] + ["ABCDEF"],
            }
        )
        service = AdsbTrafficService(
            store, AdsbLolProvider(upstream, lambda: now), lambda: now, lambda: now
        )
        overview_adsb.set_overview_adsb_runtime(store, service)
        app = FastAPI()
        app.include_router(overview_adsb.router)
        try:
            await asyncio.gather(*(service.refresh_once() for _ in range(20)))
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                replies = await asyncio.gather(
                    *(client.get("/api/overview-adsb/traffic") for _ in range(30))
                )
            assert all(len(r.json()["contacts"]) == 2000 for r in replies)
            assert len({c["hex"] for c in replies[0].json()["contacts"]}) == 2000
            assert requests == [
                "/v2/mil",
                "/v2/hex/"
                + ",".join([f"{i:06X}" for i in range(0, 50, 3)] + ["ABCDEF"]),
            ]
            sources = {s["key"]: s for s in replies[0].json()["sources"]}
            assert sources["military"]["error"] is None
            assert sources["hex:ABCDEF"]["error"]
        finally:
            await service.aclose()
            overview_adsb.set_overview_adsb_runtime(None, None)


async def test_router_expiry_is_original_observation_age_even_after_repeat(tmp_path):
    start = 1791028800.0
    clock = [start]
    payload = {
        "now": start * 1000,
        "ac": [{"hex": "000001", "lat": 38, "lon": -90, "seen_pos": 0, "dbFlags": 0}],
    }
    async with httpx.AsyncClient(
        base_url="https://api.adsb.lol",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
    ) as upstream:
        store = AdsbSettingsStore(tmp_path / "adsb.json")
        store.update(
            {"enabled": True, "mode": "included_only", "include_hexes": ["000001"]}
        )
        service = AdsbTrafficService(
            store,
            AdsbLolProvider(upstream, lambda: clock[0]),
            lambda: clock[0],
            lambda: clock[0],
        )
        overview_adsb.set_overview_adsb_runtime(store, service)
        app = FastAPI()
        app.include_router(overview_adsb.router)
        try:
            await service.refresh_once()
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                for age in (29.999, 30, 119.999):
                    clock[0] = start + age
                    await service.refresh_once()
                    contacts = (await client.get("/api/overview-adsb/traffic")).json()[
                        "contacts"
                    ]
                    assert len(contacts) == 1
                    assert contacts[0]["position_observed_at_ms"] == start * 1000
                clock[0] = start + 120
                assert (await client.get("/api/overview-adsb/traffic")).json()[
                    "contacts"
                ] == []
                clock[0] = start + 130
                await service.refresh_once()
                assert (await client.get("/api/overview-adsb/traffic")).json()[
                    "contacts"
                ] == []
                assert store.get().include_hexes == ["000001"]
        finally:
            await service.aclose()
            overview_adsb.set_overview_adsb_runtime(None, None)
