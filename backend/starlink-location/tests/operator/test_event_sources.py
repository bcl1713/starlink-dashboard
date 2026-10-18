"""Existing PoP publications feed Operator without advancing the predictor."""

from app.mission.pop_status import PopStatusService
from tests.operator.fixtures import pop_inputs


def test_source_capture_reuses_actual_predictor_publication(service, clock):
    from app.operator.event_sources import EventSourceAdapter

    inputs = pop_inputs(clock)
    inputs["mode"] = "live"
    inputs.pop("timeline")
    sample = inputs.pop("telemetry")
    observation = inputs.pop("observation")
    pop = PopStatusService(observation_provider=lambda *args: observation)
    expected = pop.snapshot(sample, **inputs)
    before = pop.state
    adapter = EventSourceAdapter(
        service, live_provider=lambda mission: ("demo-leg", pop.read_publication())
    )
    captured = adapter.capture("demo-mission", as_of=clock.now())
    assert captured.models["demo-leg"]["pop_forecast"] == expected["pop_forecast"]
    assert pop.state == before
    assert captured.sources[-1].guardable is False
    assert captured.sources[-1].aligned is False  # no asserted mission association


def test_missing_saved_source_is_unknown_not_all_clear(service, clock):
    from app.operator.event_sources import EventSourceAdapter

    captured = EventSourceAdapter(service).capture("demo-mission", as_of=clock.now())
    assert captured.sources
    assert any(source.freshness == "unknown" for source in captured.sources)


def test_changed_store_epoch_cannot_reuse_capture(service, clock):
    from app.operator.event_sources import EventSourceAdapter

    adapter = EventSourceAdapter(service)
    captured = adapter.capture("demo-mission", as_of=clock.now())
    assert captured.store_id == str(service.store.health().store_id)
    assert captured.H == 0
    assert captured.records == []


def test_matching_mission_scope_alone_cannot_certify_current_input_alignment(
    service, clock
):
    from app.operator.event_sources import EventSourceAdapter

    inputs = pop_inputs(clock)
    inputs["mode"] = "live"
    inputs.pop("timeline")
    sample = inputs.pop("telemetry")
    observation = inputs.pop("observation")
    pop = PopStatusService(observation_provider=lambda *args: observation)
    pop.snapshot(sample, **inputs)
    publication = pop.read_publication()
    publication.update(
        mission_id="demo-mission", leg_id="leg-a", simulation_run_id=None
    )
    captured = EventSourceAdapter(
        service, live_provider=lambda mission: ("leg-a", publication)
    ).capture("demo-mission", as_of=clock.now())
    assert (
        next(s for s in captured.sources if s.source == "model:leg-a").aligned is False
    )
