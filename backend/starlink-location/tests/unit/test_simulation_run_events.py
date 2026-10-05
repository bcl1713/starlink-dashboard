"""Behavioral clock, event cursor, endpoint, and publication contracts."""

import random
from dataclasses import replace
from datetime import timedelta

import pytest

from app.mission.models import Transport, TransportState
from app.satellites.rules import EventType, MissionEvent
from app.simulation.run_plan import prepare_mission_run
from app.simulation.run_runtime import SimulationRunRuntime
from tests.unit.simulation_run_fixtures import Clocks, timed_plan_sources
from tests.unit.test_simulation_run_plan import multiplier_input
from tests.unit.test_simulation_run_runtime import tick


@pytest.fixture
def setup(tmp_path):
    clocks = Clocks()
    leg, routes, pois = timed_plan_sources(tmp_path)
    plan = prepare_mission_run("mission-1", leg, multiplier_input(10), routes, pois)
    return (
        SimulationRunRuntime(clocks.monotonic, clocks.utc_now, "simulation"),
        clocks,
        plan,
    )


def test_simultaneous_events_keep_canonical_order(setup, monkeypatch):
    runtime, clocks, plan = setup
    from app.simulation import run_replay

    observed = []
    original = run_replay.apply_transport_event

    def observe(state, event):
        observed.append(event.reason)
        return original(state, event)

    monkeypatch.setattr(run_replay, "apply_transport_event", observe)
    start = plan.preview.planned_departure
    events = tuple(
        MissionEvent(
            start + timedelta(seconds=second),
            kind,
            Transport.KA,
            reason=name,
            metadata={"id": identity},
        )
        for second, kind, name, identity in [
            (-5, EventType.KA_OUTAGE_START, "pre", "a"),
            (0, EventType.KA_OUTAGE_END, "zero", "a"),
            (50, EventType.KA_OUTAGE_START, "one", "a"),
            (50, EventType.KA_OUTAGE_START, "two", "b"),
            (50, EventType.KA_OUTAGE_END, "three", "a"),
            (1200, EventType.KA_OUTAGE_END, "end", "b"),
        ]
    )
    plan = replace(plan, replay_events=events)
    runtime.commit_tick(runtime.prepare_start(plan))
    assert observed == ["pre", "zero"]
    clocks.advance(5)
    tick(runtime)
    assert observed == ["pre", "zero", "one", "two", "three"]
    assert runtime.frame().transport_states[Transport.KA] == TransportState.OFFLINE
    tick(runtime)
    assert len(observed) == 5
    clocks.advance(115)
    tick(runtime)
    assert observed[-1] == "end" and len(observed) == 6
    assert runtime.frame().transport_states[Transport.KA] == TransportState.AVAILABLE


def test_all_crossed_events_are_processed_once(setup):
    runtime, clocks, plan = setup
    from app.mission.replay_state import TransportReplayState, apply_transport_event

    runtime.commit_tick(runtime.prepare_start(plan))
    randomizer = random.Random(262)
    while runtime.status().state == "running":
        clocks.advance(randomizer.uniform(0.1, 20))
        tick(runtime)
        reference = TransportReplayState()
        eligible = [
            e
            for e in plan.replay_events
            if e.timestamp <= runtime.frame().simulation_time
        ]
        for event in eligible:
            reference = apply_transport_event(reference, event)
        assert runtime.frame().processed_event_count == len(eligible)
        assert runtime.frame().transport_states == reference.states()
