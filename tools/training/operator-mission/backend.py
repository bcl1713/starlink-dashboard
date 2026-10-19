"""Explicit training entrypoint using production replay, sources and journal services."""

import asyncio
import importlib
import importlib.util
import os
from contextlib import asynccontextmanager
from pathlib import Path

if (
    os.getenv("OPERATOR_TRAINING_FIXTURE") != "explicit-private-training-v1"
    or os.getenv("STARLINK_MODE") != "simulation"
):
    raise RuntimeError("Explicit private simulation training configuration required")

spec = importlib.util.spec_from_file_location(
    "operator_training_scenario", Path(__file__).with_name("scenario.py")
)
scenario = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scenario)
root = Path(os.environ["OPERATOR_TRAINING_ROOT"])
namespace = scenario.training_namespace(root, mode="simulation")
seeded = scenario.seed_prerequisites(root, routes_dir=Path("/data/routes"))
clock = scenario.training_clock(root)
os.environ["OPERATOR_ROOT"] = str(root / "operator")
os.environ["OPERATOR_SIMULATION_RUN_ID"] = namespace
os.environ["STARLINK_DISABLE_BACKGROUND_TASKS"] = "1"

from app.mission import storage
from app.services import ground_entry_point

storage.MISSIONS_DIR = root / "missions"
ground_entry_point._resolver = ground_entry_point.GroundEntryPointResolver(
    ip_resolver=lambda: None, geolocator=lambda _ip: None
)
main = importlib.import_module("main")
original_context = main._operator_context
main._operator_context = scenario.stable_context(root, original_context)
main.SystemClock = lambda: clock
original_replay_runtime = main.SimulationRunRuntime
main.SimulationRunRuntime = lambda _monotonic, _utc, mode: original_replay_runtime(
    clock.monotonic, clock.now, mode
)
original_pop_context = main._simulation_pop_context


def pop_context():
    value = original_pop_context()
    value["observed_now"] = clock.now()
    value["simulation_run_id"] = namespace
    return value


main._simulation_pop_context = pop_context
app = main.app
original_lifespan = app.router.lifespan_context


@asynccontextmanager
async def training_lifespan(application):
    async with original_lifespan(application):
        from app.mission.slide_cache.coordinator import start_runtime
        from app.services.flight_events.live_adapter import FlightEventRuntime

        # This archive has only explicitly supplied synthetic operational-format
        # inputs. Simulation replay is never admitted as live measurements.
        app.state.flight_event_runtime = FlightEventRuntime(
            root / "synthetic-operational-archive"
        )

        # The normal background polling loop remains disabled. Own only the
        # existing PDF worker, whose normal application shutdown closes it.
        app.state.customer_pdf_coordinator = await asyncio.to_thread(
            start_runtime, main._route_manager, app.state.poi_manager
        )
        yield


app.router.lifespan_context = training_lifespan
applied_checkpoint = None
raw_helper = None
checkpoint_lock = asyncio.Lock()


@app.middleware("http")
async def apply_raw_checkpoint(request, call_next):
    global applied_checkpoint, raw_helper
    async with checkpoint_lock:
        inputs = scenario.checkpoint_inputs(root)
        token = (inputs["checkpoint_id"], inputs["now"])
        if token != applied_checkpoint:
            if raw_helper is None:
                from model_inputs_fixture import ModelInputsFixture

                with app.state.operator_binding.access() as runtime:
                    raw_helper = ModelInputsFixture(
                        main,
                        runtime,
                        root,
                        clock,
                        seed=False,
                        manage_route=False,
                        restore_phase=False,
                        ka_east_longitude=0,
                        initial_inputs={
                            key: inputs[key]
                            for key in (
                                "now",
                                "latitude",
                                "longitude",
                                "speed",
                                "heading",
                                "stale",
                                "invalid_ka",
                                "missing_pop",
                            )
                        },
                    )
            # The normal replay engine owns actual phase, route activation and timing.
            app.state.simulation_run_service.collect(
                main._coordinator, main._publish_replay_telemetry
            )
            raw_helper.update(
                {
                    key: inputs[key]
                    for key in (
                        "now",
                        "latitude",
                        "longitude",
                        "speed",
                        "heading",
                        "stale",
                        "invalid_ka",
                        "missing_pop",
                    )
                }
            )
            applied_checkpoint = token
    return await call_next(request)
