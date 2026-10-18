"""Exact UTC thresholds and bounded current actionability use server time only."""

from datetime import timedelta

import pytest


@pytest.mark.parametrize(
    "kind,offset,want",
    [
        ("call_start", 121, False),
        ("call_start", 120, True),
        ("call_prep", 1, False),
        ("call_prep", 0, True),
        ("issue_followup", 1, False),
        ("issue_followup", 0, True),
        ("issue_followup", -900, True),
        ("issue_followup", -901, False),
        ("restriction", 301, False),
        ("restriction", 300, True),
        ("pop_advisory", 0, False),
    ],
)
def test_server_eligibility_thresholds(clock, kind, offset, want):
    from app.operator.event_models import OperationalEvent, EventNotification
    from app.operator.event_eligibility import select_eligible

    event = OperationalEvent(
        event_id="event",
        mission_id="demo-mission",
        kind=kind,
        title="Synthetic",
        state="upcoming",
        due_at=clock.now() + timedelta(seconds=offset),
        end_at=clock.now() + timedelta(minutes=10),
        significance="unavailable" if kind == "restriction" else "routine",
        notification=EventNotification(generation="one"),
    )
    assert bool(select_eligible([event], as_of=clock.now())) == want


@pytest.mark.parametrize(
    "field,value",
    [
        ("freshness", "stale"),
        ("freshness", "unknown"),
        ("active", False),
        ("state", "unknown"),
    ],
)
def test_uncertain_or_inactive_events_never_cue(clock, field, value):
    from app.operator.event_models import OperationalEvent, EventNotification
    from app.operator.event_eligibility import select_eligible

    event = OperationalEvent(
        event_id="event",
        mission_id="demo-mission",
        kind="call_start",
        title="Synthetic",
        due_at=clock.now(),
        state="active",
        notification=EventNotification(generation="one"),
    )
    setattr(event, field, value)
    assert select_eligible([event], as_of=clock.now()) == []
