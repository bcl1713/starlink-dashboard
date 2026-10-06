"""Fallback telemetry stays usable by Overview through the real status API."""

from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from app.api import status as status_api
from app.models.config import PositionConfig, RouteConfig, SimulationConfig
from app.simulation import position as position_module
from app.simulation.coordinator import SimulationCoordinator


@pytest.mark.asyncio
@pytest.mark.parametrize("longitude", [179.95, -179.95])
async def test_no_mission_status_moves_continuously_across_dateline(
    monkeypatch, longitude
):
    clock = [1000.0]
    monkeypatch.setattr(position_module, "time", SimpleNamespace(time=lambda: clock[0]))
    coordinator = SimulationCoordinator(
        SimulationConfig(
            route=RouteConfig(
                latitude_start=70, longitude_start=longitude, radius_km=100
            ),
            position=PositionConfig(speed_min_knots=400, speed_max_knots=400),
        )
    )
    monkeypatch.setattr(status_api, "_coordinator", coordinator)
    app = FastAPI()
    app.include_router(status_api.router)
    longitudes = []
    previous = None
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        for _ in range(360):
            response = await client.get("/api/status")
            assert response.status_code == 200
            position = response.json()["position"]
            lat, lon = position["latitude"], position["longitude"]
            assert 69 <= lat <= 71
            assert -180 <= lon <= 180
            assert abs(lon) > 177
            if previous is not None:
                old_lat, old_lon = previous
                assert (lat, lon) != previous
                assert abs(lat - old_lat) < 0.03
                assert abs((lon - old_lon + 180) % 360 - 180) < 0.1
            previous = lat, lon
            longitudes.append(lon)
            clock[0] += 10
            coordinator.update()
    assert any(lon < -177 for lon in longitudes)
    assert any(lon > 177 for lon in longitudes)
