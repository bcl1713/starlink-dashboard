"""Owned Uvicorn fixture: real endpoints, telemetry, capture and ZIP assembly.

Local PDF executables are container-installed, so rendering is covered by the
exact-image private acceptance runner. This socket control isolates API
responsiveness during representative normalization and package CPU work.
"""

import asyncio
import socket
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import main
from app.api import health, status
from app.core.eta_service import initialize_eta_service, shutdown_eta_service
from app.mission import storage
from app.mission.models import Mission, MissionLeg, TransportConfig
from app.mission.package.customer_artifacts import build_mission_package_download
from app.mission.package.preparation import ExportPreparationService
from app.mission.slide_cache.coordinator import reconcile
from app.mission.slide_cache.identity import renderer_revision
from app.mission.slide_cache.store import default_store
from app.models.config import SimulationConfig
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from app.simulation.coordinator import SimulationCoordinator

root, fd, mode = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
storage.MISSIONS_DIR = root / "missions"
routes = RouteManager(root / "routes")
pois = POIManager(root / "pois.json")
base = datetime(2026, 1, 1, tzinfo=timezone.utc)
for route_id in ("r", "s", "t"):
    routes.add_route(
        route_id,
        ParsedRoute(
            metadata=RouteMetadata(
                name=route_id, file_path=route_id + ".kml", point_count=500
            ),
            points=[
                RoutePoint(
                    latitude=10 + i / 500,
                    longitude=20 + i / 500,
                    sequence=i,
                    expected_arrival_time=base + timedelta(seconds=i * 60),
                )
                for i in range(500)
            ],
        ),
    )
    points = routes.get_route(route_id).points
    times = "".join(
        f"<when>{point.expected_arrival_time.isoformat()}</when>" for point in points
    )
    coords = "".join(
        f"<gx:coord>{point.longitude} {point.latitude} 0</gx:coord>" for point in points
    )
    (routes.routes_dir / (route_id + ".kml")).write_text(
        f'<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2"><Document><Placemark><gx:Track>{times}{coords}</gx:Track></Placemark></Document></kml>'
    )
storage.save_mission_v2(
    Mission(
        id="m",
        name="Socket control",
        metadata={"normalization_load": list(range(100000))},
        legs=[
            MissionLeg(
                id=leg,
                name=leg,
                route_id=route,
                transports=TransportConfig(initial_x_satellite_id=""),
            )
            for leg, route in zip(("a", "b", "c"), ("r", "s", "t"))
        ],
    )
)
initialize_eta_service(pois)
routes.activate_route("r")
config = SimulationConfig(update_interval_seconds=0.1)
coordinator = SimulationCoordinator(config)
coordinator.set_route_manager(routes)
coordinator.update()
health.set_coordinator(coordinator)
status.set_coordinator(coordinator)
main._coordinator, main._route_manager, main._simulation_config = (
    coordinator,
    routes,
    config,
)
main.app.state.route_manager, main.app.state.poi_manager = routes, pois
main.app.state.simulation_run_service = None
main.app.state.blocked = False
main.app.state.fail_next = False


def build(mission, route_manager, poi_manager, *, enabled, cancel, on_stage):
    if main.app.state.fail_next:
        main.app.state.fail_next = False
        raise RuntimeError("Controlled assembly worker failure")
    # Production normalization runs off-loop without the global gate.
    reconcile(mission, route_manager, poi_manager, default_store(), renderer_revision())
    cancel.wait(0.5)
    return build_mission_package_download(
        mission,
        route_manager,
        poi_manager,
        enabled=enabled,
        cancel=cancel,
        on_stage=on_stage,
    )


@asynccontextmanager
async def lifespan(app):
    service = ExportPreparationService(routes, pois, enabled=False, builder=build)
    app.state.export_preparation_service = service
    telemetry = asyncio.create_task(main._background_update_loop(pois))
    app.state.saturation_tasks = []
    try:
        yield
    finally:
        await asyncio.to_thread(service.close)
        telemetry.cancel()
        await asyncio.gather(telemetry, return_exceptions=True)
        await asyncio.gather(*app.state.saturation_tasks, return_exceptions=True)
        shutdown_eta_service()


main.app.router.lifespan_context = lifespan


@main.app.middleware("http")
async def blocking_control(request, call_next):
    if main.app.state.blocked:
        # Intentional blocked event-loop negative control.
        time.sleep(3)  # noqa: ASYNC251
    return await call_next(request)


@main.app.get("/block")
async def block():
    main.app.state.blocked = mode == "blocking"
    time.sleep(3)  # noqa: ASYNC251
    return {"blocked": True}


@main.app.post("/control/fail-next")
def fail_next():
    main.app.state.fail_next = True
    return {"armed": True}


@main.app.post("/control/saturate")
async def saturate():
    loop = asyncio.get_running_loop()
    ready = asyncio.Event()
    guard = threading.Lock()
    entered = [0]
    await asyncio.to_thread(lambda: None)
    worker_count = loop._default_executor._max_workers

    def occupy():
        with guard:
            entered[0] += 1
            if entered[0] == worker_count:
                loop.call_soon_threadsafe(ready.set)
        time.sleep(3)

    main.app.state.saturation_tasks = [
        asyncio.create_task(asyncio.to_thread(occupy)) for _ in range(worker_count)
    ]
    await ready.wait()
    return {"occupied": worker_count}


if mode == "serialization":
    from types import SimpleNamespace

    from pydantic import BaseModel, model_serializer

    from app.mission import routes_v2
    from app.mission.planning.models import PlanningView

    class SlowMetadata(BaseModel):
        @model_serializer(mode="plain")
        def serialize(self):
            time.sleep(3)
            return "serialized"

    delayed = Mission(id="m", name="Heavy response", metadata={"slow": SlowMetadata()})
    routes_v2.load_mission_v2 = lambda _: delayed
    main.app.state.planning_service = SimpleNamespace(
        store=SimpleNamespace(
            read=lambda _: PlanningView(mission=delayed, revision=1, expected_legs=[])
        )
    )


@main.app.post("/control/hold-mission-gate")
def hold_mission_gate():
    entered = threading.Event()

    def hold():
        with storage.get_active_leg_lock():
            entered.set()
            time.sleep(3)

    worker = threading.Thread(target=hold, name="owned-gate-control", daemon=True)
    worker.start()
    assert entered.wait(2)
    return {"holding": True}


listener = socket.socket(fileno=fd)
server = uvicorn.Server(
    uvicorn.Config(main.app, log_level="warning", timeout_graceful_shutdown=5)
)
asyncio.run(server.serve(sockets=[listener]))
