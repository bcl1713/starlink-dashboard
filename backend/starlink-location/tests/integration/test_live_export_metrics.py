"""Exports must leave real live metric publication and scrapes available."""

import asyncio
from datetime import timedelta
from threading import Event

import httpx
import pytest

import main
from app.core.metrics.prometheus_metrics import FRAME_STORE
from app.mission import storage
from app.mission.models import Mission, MissionLeg, TransportConfig
from app.mission.package.customer_artifacts import build_mission_package_download
from app.mission.package.preparation import ExportPreparationService
from app.mission.slide_cache.store import SlideStore
from tests.integration.test_live_background_route import background_runtime

__all__ = ["background_runtime"]


@pytest.mark.parametrize("background_runtime", ["live"], indirect=True)
async def test_export_keeps_live_publications_and_scrapes_ready(
    background_runtime, tmp_path
):
    runtime = background_runtime
    storage.save_mission_v2(
        Mission(
            id="export-metrics",
            name="Two live legs",
            legs=[
                MissionLeg(
                    id=name,
                    name=name,
                    route_id=name,
                    transports=TransportConfig(initial_x_satellite_id=""),
                )
                for name in ("first", "second")
            ],
        )
    )
    assert runtime.route_manager.activate_route("first")
    main._background_update_tick(main.app.state.poi_manager, 1, 0, 0)
    assert FRAME_STORE.read().status == "ready"
    entered, release = Event(), Event()

    def build(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return build_mission_package_download(*args, **kwargs)

    service = ExportPreparationService(
        runtime.route_manager,
        main.app.state.poi_manager,
        enabled=False,
        cache=SlideStore(tmp_path / "exports/slides.sqlite3"),
        builder=build,
    )
    try:
        job = await asyncio.to_thread(service.start, "export-metrics")
        assert await asyncio.to_thread(entered.wait, 3)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        ) as client:
            for index in range(5):
                runtime.clock[0] += timedelta(seconds=1)
                await asyncio.to_thread(
                    main._background_update_tick,
                    main.app.state.poi_manager,
                    1,
                    index + 1,
                    0,
                )
                assert FRAME_STORE.read().status == "ready"
                responses = await asyncio.wait_for(
                    asyncio.gather(*(client.get("/metrics") for _ in range(5))), 2
                )
                assert all(response.status_code == 200 for response in responses)
                assert all(
                    "starlink_dish_latitude_degrees 1.0" in response.text
                    for response in responses
                )
            release.set()
            deadline = asyncio.get_running_loop().time() + 5
            while asyncio.get_running_loop().time() < deadline:
                current = service.status("export-metrics", job.id)
                assert FRAME_STORE.read().status == "ready"
                if current.state in {"ready", "failed", "superseded"}:
                    break
                await asyncio.sleep(0.01)
            assert current.state == "ready"
            assert FRAME_STORE.read().status == "ready"
    finally:
        release.set()
        await asyncio.to_thread(service.close)
