"""Timeline separates source facts from notification delivery and protection."""

from dataclasses import replace
from datetime import timedelta

import pytest

from tests.operator.api_helpers import create as api_create
from tests.operator.service_helpers import create
from tests.operator.test_call_api import call_data
from tests.operator.test_conference_api import conference_data
from tests.operator.test_issue_api import issue_data


def derive(service, clock, **updates):
    from app.operator.event_policy import EventPolicy
    from app.operator.event_projection import derive_events
    from app.operator.event_sources import EventSourceAdapter

    inputs = EventSourceAdapter(service).capture("demo-mission", as_of=clock.now())
    return derive_events(
        replace(inputs, **updates), as_of=clock.now(), policy=EventPolicy()
    )


@pytest.mark.parametrize(
    "status,active",
    [
        ("scheduled", True),
        ("delayed", True),
        ("tentative", True),
        ("cancelled", False),
        ("completed", False),
    ],
)
def test_call_milestones_use_saved_ten_minute_preparation(
    api, service, record_data, clock, status, active
):
    response = api_create(api, call_data(record_data, status))
    assert response.status_code == 201
    events = derive(service, clock)
    assert {e.kind for e in events} == (
        {"call_start", "call_prep"} if active else {"call_start"}
    )
    start = next(e for e in events if e.kind == "call_start")
    assert start.active == active
    if active:
        prep = next(e for e in events if e.kind == "call_prep")
        assert (start.due_at - prep.due_at).total_seconds() == 600


def test_unknown_prep_and_resolved_followup_are_not_invented(
    api, service, record_data, clock
):
    api_create(api, call_data(record_data, prep_lead_minutes=None))
    api_create(api, issue_data(record_data, follow_up_at="2026-10-17T15:59:00Z"))
    api_create(
        api,
        issue_data(record_data, status="resolved", follow_up_at="2026-10-17T16:00:00Z"),
    )
    events = derive(service, clock)
    assert sum(e.kind == "call_prep" for e in events) == 0
    issues = [e for e in events if e.kind == "issue_followup"]
    assert sum(e.active for e in issues) == 1
    assert next(e for e in issues if e.active).state == "overdue"


@pytest.mark.parametrize(
    "conference_state", ["closed", "interrupted", None, "missing", "established"]
)
def test_connected_customer_survives_conference_discrepancy(
    service, record_data, clock, conference_state
):
    conference = create(
        service,
        conference_data(
            record_data,
            status=conference_state if conference_state != "missing" else "closed",
            configured_transport="Ka",
        ),
    )
    participation = create(
        service,
        dict(
            record_data,
            record_type="participation",
            time={},
            payload={
                "entry_type": "participation",
                "title": "Synthetic customer",
                "state": "connected",
                "conference_id": str(conference.record_id),
            },
        ),
    )
    from app.operator.event_policy import EventPolicy
    from app.operator.event_projection import derive_events
    from app.operator.event_sources import EventSourceAdapter

    inputs = EventSourceAdapter(service).capture("demo-mission", as_of=clock.now())
    if conference_state == "missing":
        inputs = replace(
            inputs,
            records=[r for r in inputs.records if r.record_id != conference.record_id],
        )
    models = {
        "leg-a": {
            "segments": [
                {
                    "id": "restriction-a",
                    "start_time": clock.now().isoformat(),
                    "end_time": (clock.now() + timedelta(minutes=10)).isoformat(),
                    "ka_state": "offline",
                }
            ]
        }
    }
    events = derive_events(
        replace(inputs, models=models), as_of=clock.now(), policy=EventPolicy()
    )
    event = next(e for e in events if e.kind == "restriction")
    assert event.protected_participation_ids == [str(participation.record_id)]
    assert event.transport_relevance == (
        "configured" if conference_state == "established" else "unknown"
    )
    if conference_state != "established":
        assert event.continuity_status == "unknown"
        assert event.discrepancies


@pytest.mark.parametrize("fallback,outage", [(None, True), ("Ka", False), ("X", False)])
def test_real_pop_windows_remain_advisory_and_fallback_protects_plan(
    service, clock, fallback, outage
):
    from app.mission.pop_continuity import attach_call_continuity
    from tests.operator.fixtures import pop_inputs

    inputs = pop_inputs(clock, fallback=fallback)
    timeline = inputs["timeline"]
    attach_call_continuity(timeline)
    events = derive(service, clock, models={"leg-a": timeline.model_dump(mode="json")})
    pop = [e for e in events if e.kind == "pop_advisory"]
    assert len(pop) == 1
    assert pop[0].significance == "advisory"
    assert (pop[0].end_at - pop[0].due_at).total_seconds() == 600
    assert any(e.significance == "call_outage" for e in events) == outage


def test_forecast_revision_does_not_change_crossing_event_identity(service, clock):
    from copy import deepcopy

    from tests.operator.fixtures import pop_inputs

    model = pop_inputs(clock)["timeline"].model_dump(mode="json")
    first = [
        e
        for e in derive(service, clock, models={"leg-a": model})
        if e.kind == "pop_advisory"
    ]
    changed = deepcopy(model)
    changed["pop_forecast"]["revision"] = "new-revision"
    crossing = changed["pop_forecast"]["transitions"][0]["crossing"]
    crossing["id"] = "new-producer-id"
    second = [
        e
        for e in derive(service, clock, models={"leg-a": changed})
        if e.kind == "pop_advisory"
    ]
    assert first[0].event_id == second[0].event_id
    repeated = deepcopy(changed["pop_forecast"]["transitions"][0])
    repeated["crossing"]["segment_index"] += 1
    changed["pop_forecast"]["transitions"].append(repeated)
    assert (
        len(
            {
                e.event_id
                for e in derive(service, clock, models={"leg-a": changed})
                if e.kind == "pop_advisory"
            }
        )
        == 2
    )


def test_actual_pop_advisories_survive_without_future_forecast_windows(service, clock):
    events = derive(
        service,
        clock,
        models={
            "leg-a": {
                "pop_forecast": {"status": "ready", "transitions": []},
                "pop_advisories": [
                    {"kind": "observation_unknown"},
                    {"kind": "overdue", "transition_id": "synthetic-crossing"},
                ],
            }
        },
    )
    assert len(events) == 2
    assert {event.provenance for event in events} == {"observed", "modeled"}
    assert all(
        event.kind == "pop_advisory" and event.significance == "advisory"
        for event in events
    )
    assert all(not event.notification.available for event in events)
    assert any("not confirmed" in event.title for event in events)


def test_model_identity_is_scoped_to_mission_even_when_leg_ids_are_reused(
    service, clock
):
    from app.operator.event_policy import EventPolicy
    from app.operator.event_projection import derive_events
    from app.operator.event_sources import EventSourceAdapter
    from tests.operator.fixtures import pop_inputs

    model = pop_inputs(clock)["timeline"].model_dump(mode="json")
    original = EventSourceAdapter(service).capture("demo-mission", as_of=clock.now())
    a = derive_events(
        replace(original, models={"leg-a": model}),
        as_of=clock.now(),
        policy=EventPolicy(),
    )
    b = derive_events(
        replace(original, mission_id="other-mission", models={"leg-a": model}),
        as_of=clock.now(),
        policy=EventPolicy(),
    )
    assert not {event.event_id for event in a} & {event.event_id for event in b}


def test_fresh_source_without_continuity_evidence_stays_unknown(service, clock):
    from app.operator.event_models import SourceCapture
    from app.operator.event_policy import EventPolicy
    from app.operator.event_projection import derive_events
    from app.operator.event_sources import EventSourceAdapter

    original = EventSourceAdapter(service).capture("demo-mission", as_of=clock.now())
    inputs = replace(
        original,
        sources=[SourceCapture(source="model:leg-a", freshness="fresh", aligned=True)],
        models={
            "leg-a": {
                "segments": [
                    {
                        "start_time": "2026-10-17T16:00:00Z",
                        "end_time": "2026-10-17T16:10:00Z",
                        "ka_state": "offline",
                    }
                ]
            }
        },
    )
    assert (
        derive_events(inputs, as_of=clock.now(), policy=EventPolicy())[
            0
        ].continuity_status
        == "unknown"
    )
