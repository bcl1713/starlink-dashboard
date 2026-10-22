"""Private-store candidate component diagnostic; no application lifespan."""

import cProfile
import importlib.metadata
import os
import sys

from perf391_independent import measure, profile_rows


def component(root, output, timing=False):
    import logging
    import threading
    from copy import deepcopy
    from datetime import UTC, datetime

    sys.path.insert(0, str(root / "backend/starlink-location"))
    os.environ["STARLINK_DISABLE_BACKGROUND_TASKS"] = "1"
    os.environ["LOG_LEVEL"] = "ERROR"
    # Every implicit relative application path resolves inside task-owned storage.
    scratch = output / "storage"
    scratch.mkdir(parents=True, exist_ok=True)
    os.chdir(scratch)
    os.environ["MPLCONFIGDIR"] = str(scratch / "matplotlib")
    import main
    from app.api import metrics_export
    from app.core import eta_service
    from app.core.metrics import prometheus_metrics as metrics
    from app.core.metrics.frame_builder import FrameInputs, prepare_frame
    from app.core.metrics.frames import GaugeFrame
    from app.core.metrics.source_admission import model_identity, poi_identity
    from app.mission import storage
    from app.models.config import SimulationConfig
    from app.models.poi import POI
    from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
    from app.services.flight_state import get_flight_state_manager
    from app.services.poi_manager import POIManager
    from app.services.route_manager import RouteManager
    from app.simulation.coordinator import SimulationCoordinator

    logging.getLogger().setLevel(logging.ERROR)
    storage.MISSIONS_DIR = scratch / "missions"
    manager = POIManager(scratch / "pois.json")
    routes = RouteManager(scratch / "routes")
    config = SimulationConfig()
    coordinator = SimulationCoordinator(config)
    coordinator.route_manager = routes
    main._coordinator, main._simulation_config, main._route_manager = (
        coordinator,
        config,
        routes,
    )
    main.app.state.poi_manager = manager
    eta_service.initialize_eta_service(manager)
    route = ParsedRoute(
        metadata=RouteMetadata(
            name="Synthetic diagnostic route", file_path="synthetic.kml", point_count=5
        ),
        points=[
            RoutePoint(latitude=0, longitude=-10 + i * 5, sequence=i) for i in range(5)
        ],
    )
    routes._routes["synthetic-route"] = route
    routes._active_route_id = "synthetic-route"
    get_flight_state_manager().update_route_context(route)
    if timing:
        import asyncio

        from perf391_independent_timing import http_timing

        return asyncio.run(http_timing(root, output, main, manager, coordinator))
    result = {
        "python": sys.version,
        "packages": {
            name: importlib.metadata.version(name)
            for name in ["pydantic", "prometheus-client", "filelock", "fastapi"]
        },
        "rows": [],
    }
    tick_count = 1
    for count in [0, 2, 10, 100, 1100]:
        manager._pois = {
            str(i): POI(
                id=str(i), name=f"POI {i}", latitude=0.1, longitude=-9 + i / 2000
            )
            for i in range(count)
        }

        # Prepare via the real producer and real admission gates; no lifespan or I/O services.
        def tick():
            nonlocal tick_count
            tick_count = main._background_update_tick(manager, 1, tick_count, 0)

        tick()
        telemetry = coordinator.get_current_telemetry()
        pois = manager.list_pois()
        flight = get_flight_state_manager().get_status()

        def capture(telemetry=telemetry, pois=pois, flight=flight):
            return FrameInputs(
                metrics.FRAME_STORE.read(),
                telemetry=telemetry,
                config=config,
                active_route=route,
                pois=pois,
                flight_status=flight,
                now=datetime.now(UTC),
            )

        inputs = capture()
        frame = prepare_frame(inputs, admit_observation=False)
        n = 100 if count < 100 else 30
        operations = {
            "tick": tick,
            "list_pois_copy": manager.list_pois,
            "frame_inputs_copy": capture,
            "eta_second_poi_copy": lambda inputs=inputs: tuple(
                deepcopy(p) for p in inputs.pois
            ),
            "poi_identity": lambda inputs=inputs: poi_identity(inputs.pois),
            "route_identity": lambda: model_identity(route),
            "repository_gate_lookup": storage.get_active_leg_lock,
            "eta_calculation_only": lambda telemetry=telemetry, inputs=inputs, flight=flight: eta_service.get_eta_calculator().calculate_poi_metrics(
                telemetry.position.latitude,
                telemetry.position.longitude,
                inputs.pois,
                telemetry.position.speed,
                active_route=route,
                eta_mode=flight.eta_mode,
                flight_phase=flight.phase,
                track_passage=False,
            ),
            "prepare_derived_frame": lambda inputs=inputs: prepare_frame(
                inputs, admit_observation=False
            ),
            "frame_validation": lambda frame=frame: metrics.FRAME_STORE._validate(
                frame
            ),
            "immutable_sample_freeze": lambda frame=frame: GaugeFrame(
                frame.identity, frame.families, frame.last_observation_publication_time
            ),
            "scrape_serialization": metrics_export._prepare_metrics,
        }
        row = {
            "pois": count,
            "route_points": 5,
            "timings": {name: measure(op, n) for name, op in operations.items()},
        }
        # Wall profiles are separate from uninstrumented thread-CPU timings above.
        # Never interpret instrumented cumulative times as uninstrumented CPU costs.
        profile = cProfile.Profile()
        profile.enable()
        for _ in range(20):
            tick()
        profile.disable()
        path = output / f"cpu-{count}.prof"
        profile.dump_stats(str(path))
        row["profile"] = profile_rows(path)
        assert metrics.FRAME_STORE.read().status == "ready"
        result["rows"].append(row)
    result["remaining_threads"] = [
        t.name for t in threading.enumerate() if t is not threading.main_thread()
    ]
    return result
