"""Acceptance-only startup injection. Production main/default factories are intact."""

import importlib
import os
from datetime import datetime
from pathlib import Path

from scenario import ScenarioClock
from seed import seed_demo

from app.mission import storage
from app.services import ground_entry_point
from app.services.position_freshness import OBSERVATION_FRESHNESS_SECONDS

if os.getenv("OPERATOR_ACCEPTANCE_FIXTURE") != "synthetic-local-only":
    raise RuntimeError("Explicit synthetic acceptance configuration required")
if os.getenv("STARLINK_MODE") != "simulation":
    raise RuntimeError("This acceptance fixture requires simulation mode")

root = Path(os.environ["OPERATOR_ACCEPTANCE_ROOT"])


class ControlledClock(ScenarioClock):
    def now(self):
        path = root / "synthetic-issue-clock.txt"
        return (
            datetime.fromisoformat(path.read_text().strip())
            if path.exists()
            else super().now()
        )


models_enabled = os.getenv("OPERATOR_MODEL_ALERTS_ACCEPTANCE") == "true"
events_enabled = os.getenv("OPERATOR_EVENTS_ACCEPTANCE") == "true"
if models_enabled:
    from model_inputs_fixture import ModelClock

    scenario_clock = ModelClock(root)
elif events_enabled:
    from events_fixture import EventsClock

    scenario_clock = EventsClock(root)
else:
    scenario_clock = ControlledClock()
seed = seed_demo(
    root,
    clock=scenario_clock,
    mode="simulation",
    include_shell=True,
    include_timelines=not models_enabled,
)
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
        if models_enabled and runtime.service is not None:
            from model_inputs_fixture import ModelInputsFixture

            main.app.state.synthetic_models = ModelInputsFixture(
                main, runtime, root, scenario_clock
            )
        if events_enabled and runtime.service is not None:
            from events_fixture import EventsFixture

            main.app.state.synthetic_events = EventsFixture(
                runtime, root, scenario_clock
            )
    return binding


# Only this uvicorn module replaces the constructor argument for the real app.
main.OperatorRuntimeBinding = fixture_binding
app = main.app


if events_enabled:
    from fastapi import HTTPException

    @app.post("/api/_synthetic/operator-events")
    def synthetic_events_control(body: dict):
        try:
            return app.state.synthetic_events.update(body)
        except (ValueError, TypeError, KeyError):
            raise HTTPException(422, "Invalid synthetic input") from None


if models_enabled:
    from fastapi import HTTPException

    @app.post("/api/_synthetic/operator-model-inputs")
    def synthetic_models_control(body: dict):
        try:
            return app.state.synthetic_models.update(body)
        except (ValueError, TypeError, KeyError):
            raise HTTPException(422, "Invalid synthetic raw input") from None


if models_enabled:

    @app.get("/api/_synthetic/operator-model-acknowledgments")
    def synthetic_model_acknowledgments():
        with app.state.synthetic_models.runtime.service.store.connect() as db:
            count = db.execute(
                "SELECT count(*) FROM event_acknowledgments a JOIN event_occurrences o USING (occurrence_id) WHERE json_extract(o.event_json, '$.provenance')='modeled'"
            ).fetchone()[0]
        return {"synthetic": True, "modeledAcknowledgments": count}
