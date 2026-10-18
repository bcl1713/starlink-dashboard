"""Aircraft-free feed capture uses real #348 timing/geometry and source status."""

import pytest

from app.mission import storage
from app.mission.pop_status import PopStatusService
from app.operator.runtime import OperatorRuntime
from app.operator.settings import OperatorSettings
from tests.operator.fixtures import ScenarioClock, pop_inputs, seed_demo


@pytest.mark.parametrize(
    "state,want",
    [("ready", "fresh"), ("disabled", "disabled"), ("unavailable", "unknown")],
)
def test_real_model_status_survives_capture(tmp_path, monkeypatch, state, want):
    from app.operator.event_sources import EventSourceAdapter

    clock = ScenarioClock()
    seeded = seed_demo(tmp_path, clock=clock, mode="simulation")
    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    runtime = OperatorRuntime.start(
        OperatorSettings(
            enabled=True,
            root=tmp_path / "operator",
            source_mode="simulation",
            simulation_run_id=seeded["run_id"],
        ),
        clock=clock,
    )
    try:
        inputs = pop_inputs(clock)
        inputs.pop("timeline")
        sample = inputs.pop("telemetry")
        observation = inputs.pop("observation")
        if state == "disabled":
            inputs["enabled"] = False
        if state == "unavailable":
            inputs.pop("projector")
            sample.position.observed_at = None
        pop = PopStatusService(observation_provider=lambda *args: observation)
        pop.snapshot(sample, **inputs)
        published = pop.read_publication()
        published.update(
            mission_id="synthetic-mission-a",
            leg_id="synthetic-leg-1",
            simulation_run_id=seeded["run_id"],
        )
        adapter = EventSourceAdapter(
            runtime.service,
            live_provider=lambda mission: ("synthetic-leg-1", published),
        )
        captured = adapter.capture("synthetic-mission-a", as_of=clock.now())
        source = next(
            s for s in captured.sources if s.source == "model:synthetic-leg-1"
        )
        assert source.freshness == want
        assert source.aligned
        assert source.guardable is False
        model = captured.models["synthetic-leg-1"]
        assert model["pop_forecast"]["status"] == state
        if state == "ready":
            assert model["pop_forecast"]["transitions"]
    finally:
        runtime.close()
