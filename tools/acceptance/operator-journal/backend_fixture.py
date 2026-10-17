"""Acceptance-only startup injection. Production main/default factories are intact."""

import importlib
import os
from pathlib import Path

from app.mission import storage
from app.services import ground_entry_point
from app.services.position_freshness import OBSERVATION_FRESHNESS_SECONDS
from scenario import ScenarioClock
from seed import seed_demo

if os.getenv("OPERATOR_ACCEPTANCE_FIXTURE") != "synthetic-local-only":
    raise RuntimeError("Explicit synthetic acceptance configuration required")
if os.getenv("STARLINK_MODE") != "simulation":
    raise RuntimeError("This acceptance fixture requires simulation mode")

scenario_clock = ScenarioClock()
root = Path(os.environ["OPERATOR_ACCEPTANCE_ROOT"])
seed = seed_demo(root, clock=scenario_clock, mode="simulation", include_shell=True)
storage.MISSIONS_DIR = root / "missions"
os.environ["OPERATOR_ROOT"] = seed["roots"]["operator"]
os.environ["OPERATOR_SIMULATION_RUN_ID"] = seed["run_id"]
os.environ["STARLINK_DISABLE_BACKGROUND_TASKS"] = "1"
ground_entry_point._resolver = ground_entry_point.GroundEntryPointResolver(
    ip_resolver=lambda: None, geolocator=lambda ip: None
)
main = importlib.import_module("main")
original_binding = main.OperatorRuntimeBinding


def fixture_binding(*, clock, context):
    binding = original_binding(clock=scenario_clock, context=context)
    with binding.access() as runtime:
        runtime.freshness_policies["accepted_position"] = OBSERVATION_FRESHNESS_SECONDS
    return binding


# Only this uvicorn module replaces the constructor argument for the real app.
main.OperatorRuntimeBinding = fixture_binding
app = main.app
