"""Durable manual and inferred event delivery, revision and ownership checks."""

from datetime import timedelta

import pytest

from app.services.flight_events.store import FlightEventStore
from tests.unit.test_flight_events import START, observation


def test_manual_events_survive_restart_and_deliver_until_acknowledged(tmp_path):
    store = FlightEventStore(tmp_path / "events.db")
    event = store.record_manual_event(
        "m", "l", "off_blocks", START, "observed", "operator"
    )
    reopened = FlightEventStore(tmp_path / "events.db")
    assert reopened.pending_events()[0].event_id == event.event_id
    assert reopened.pending_events()[0].event_id == event.event_id
    reopened.acknowledge(event.event_id, 1)
    assert not reopened.pending_events()


def test_multisegment_correction_and_revision_conflict(tmp_path):
    store = FlightEventStore(tmp_path / "events.db")
    events = []
    for second, kind in enumerate(
        [
            "off_blocks",
            "takeoff",
            "landed",
            "on_blocks",
            "off_blocks",
            "takeoff",
            "landed",
        ]
    ):
        events.append(
            store.record_manual_event(
                "m",
                "l",
                kind,
                START + timedelta(seconds=second * 100),
                "observed",
                "operator",
            )
        )
    revised = store.correct_event(
        events[-1].event_id,
        START + timedelta(seconds=610),
        "adjusted",
        "operator",
        1,
        "m",
        "l",
    )
    assert revised.revision == 2
    assert store.events("m", "l")[2].occurred_at == events[2].occurred_at
    with pytest.raises(ValueError, match="revision"):
        store.correct_event(
            revised.event_id, START, "adjusted", "operator", 1, "m", "l"
        )
    with pytest.raises(ValueError, match="ownership"):
        store.correct_event(
            revised.event_id, START, "adjusted", "operator", 2, "m", "other"
        )


def test_candidate_pin_survives_restart(tmp_path):
    store = FlightEventStore(tmp_path / "events.db")
    for second in range(301):
        store.apply_observation(observation(second))
    store.apply_observation(observation(301, speed=10))
    reopened = FlightEventStore(tmp_path / "events.db")
    assert reopened.pin_start("m", "l") == START + timedelta(seconds=301 - 1800)
    assert reopened.state("m", "l").movement == "parked"


def test_order_and_unknown_startup(tmp_path):
    store = FlightEventStore(tmp_path / "events.db")
    with pytest.raises(ValueError, match="preceding"):
        store.record_manual_event("m", "l", "on_blocks", START, "observed", "operator")
    result = store.apply_observation(observation(100, speed=150, altitude=5000))
    assert not result.emitted_events
    assert result.state.uncertain


def test_operator_can_reopen_misclassified_destination_stop(tmp_path):
    store = FlightEventStore(tmp_path / "events.db")
    for second, kind in enumerate(["off_blocks", "takeoff", "landed", "on_blocks"]):
        park = store.record_manual_event(
            "m", "l", kind, START + timedelta(seconds=second), "observed", "operator"
        )
    store.classify_stop(
        "m", "l", park.event_id, "destination_complete", "arrived", "operator"
    )
    assert store.state("m", "l").destination_complete
    store.classify_stop(
        "m", "l", park.event_id, "intermediate", "corrected stop", "operator"
    )
    assert not store.state("m", "l").destination_complete


def test_operator_can_override_inferred_destination_stop(tmp_path):
    store = FlightEventStore(tmp_path / "events.db")
    for begin, end, speed, altitude in [
        (0, 300, 0, 100),
        (301, 320, 10, 100),
        (321, 350, 120, 500),
        (351, 360, 200, 10000),
        (361, 400, 25, 100),
        (401, 710, 0, 100),
    ]:
        for second in range(begin, end + 1):
            store.apply_observation(observation(second, speed=speed, altitude=altitude))
    park = store.events("m", "l")[-1]
    assert store.state("m", "l").destination_complete
    store.classify_stop(
        "m", "l", park.event_id, "intermediate", "fuel stop", "operator"
    )
    assert not store.state("m", "l").destination_complete
