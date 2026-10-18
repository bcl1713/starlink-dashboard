"""External publication replacement must not be acknowledged as an obsolete model."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from threading import Event
from concurrent.futures import ThreadPoolExecutor

from app.operator.event_models import SourceCapture
from app.operator.event_sources import EventSourceAdapter
from tests.operator.api_helpers import BASE, headers


def model_feed(api, service, clock, *, guardable=True):
    runtime = api.app.state.operator_runtime
    source = SourceCapture(
        source="model:leg-a",
        revision="one",
        generation="one",
        input_identity="route",
        captured_at=clock.now(),
        freshness="fresh",
        aligned=True,
        guardable=guardable,
    )
    runtime.event_publication.publish(source)

    class Adapter:
        def capture(self, mission_id, *, as_of):
            inputs = EventSourceAdapter(service).capture(mission_id, as_of=as_of)
            return replace(
                inputs,
                sources=[source],
                models={
                    "leg-a": {
                        "segments": [
                            {
                                "id": "synthetic",
                                "start_time": clock.now().isoformat(),
                                "end_time": (
                                    clock.now() + timedelta(minutes=10)
                                ).isoformat(),
                                "ka_state": "offline",
                            }
                        ]
                    }
                },
            )

    runtime.event_source_adapter = Adapter()
    feed = api.get(BASE + "/events", params={"mission_id": "demo-mission"}).json()
    event = feed["events"][0]
    return (
        runtime,
        source,
        dict(
            schema_version=1,
            occurrence_id=event["notification"]["generation"],
            severity_generation=event["notification"]["severity_generation"],
            snapshot_token=feed["snapshot_token"],
        ),
    )


def test_forecast_change_during_acknowledgment(api, service, clock):
    runtime, source, body = model_feed(api, service, clock)
    ready, replaced = Event(), Event()
    original_guard = runtime.event_publication.guard

    @contextmanager
    def guarded(expected):
        ready.set()
        assert replaced.wait(2)
        with original_guard(expected):
            yield

    runtime.event_publication.guard = guarded

    def publish():
        assert ready.wait(2)
        runtime.event_publication.publish(
            source.model_copy(update={"generation": "two", "revision": "two"})
        )
        replaced.set()

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            worker = pool.submit(publish)
            response = api.post(
                BASE + "/events/acknowledge", json=body, headers=headers(api)
            )
            worker.result(timeout=3)
        assert response.status_code == 409, response.text
        with service.store.connect() as db:
            assert db.execute(
                "SELECT count(*) FROM event_acknowledgments"
            ).fetchone() == (0,)
    finally:
        replaced.set()
        runtime.event_publication.guard = original_guard


def test_unguardable_prediction_is_readable_but_acknowledgment_fails_closed(
    api, service, clock
):
    _, _, body = model_feed(api, service, clock, guardable=False)
    response = api.post(BASE + "/events/acknowledge", json=body, headers=headers(api))
    assert response.status_code == 503
    with service.store.connect() as db:
        assert db.execute("SELECT count(*) FROM event_acknowledgments").fetchone() == (
            0,
        )


def test_call_canceled_between_evaluation_and_transaction_never_acknowledges(
    api, service, record_data
):
    from tests.operator.test_event_ack import pending

    data, record, body = pending(api, record_data)
    runtime = api.app.state.operator_runtime
    guard = runtime.event_publication.guard

    @contextmanager
    def cancel_first(expected):
        replacement = dict(data, expected_version=1)
        replacement["payload"] = dict(
            data["payload"], status="cancelled", prep_lead_minutes=10
        )
        assert (
            api.put(
                BASE + "/records/" + record["record_id"],
                json=replacement,
                headers=headers(api),
            ).status_code
            == 200
        )
        with guard(expected):
            yield

    runtime.event_publication.guard = cancel_first
    try:
        response = api.post(
            BASE + "/events/acknowledge", json=body, headers=headers(api)
        )
        assert response.status_code == 409
        with service.store.connect() as db:
            assert db.execute(
                "SELECT count(*) FROM event_acknowledgments"
            ).fetchone() == (0,)
    finally:
        runtime.event_publication.guard = guard
