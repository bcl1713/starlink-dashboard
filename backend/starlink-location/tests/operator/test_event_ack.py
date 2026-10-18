"""Acknowledgment changes notification disposition, never operational events."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from tests.operator.api_helpers import BASE, create, headers
from tests.operator.test_call_api import call_data


def pending(api, record_data):
    data = call_data(record_data)
    record = create(api, data).json()["saved_records"][0]
    feed = api.get(BASE + "/events", params={"mission_id": "demo-mission"}).json()
    event = feed["events"][0]
    return (
        data,
        record,
        {
            "schema_version": 1,
            "occurrence_id": event["notification"]["generation"],
            "severity_generation": event["notification"]["severity_generation"],
            "snapshot_token": feed["snapshot_token"],
        },
    )


def test_acknowledgment_is_shared_without_mutating_call(
    api, service, record_data, clock
):
    from app.operator.recovery import verify_store

    _data, _record, body = pending(api, record_data)
    key = str(uuid4())
    first = api.post(BASE + "/events/acknowledge", json=body, headers=headers(api, key))
    assert first.status_code == 200, first.text
    assert "saved_records" not in first.json()
    assert (
        api.post(
            BASE + "/events/acknowledge", json=body, headers=headers(api, key)
        ).json()
        == first.json()
    )
    again = api.post(BASE + "/events/acknowledge", json=body, headers=headers(api))
    assert again.status_code == 200
    assert again.json()["acknowledgment_id"] == first.json()["acknowledgment_id"]
    feed = api.get(BASE + "/events", params={"mission_id": "demo-mission"}).json()
    assert len(feed["events"]) == 2
    assert feed["events"][0]["notification"]["acknowledged"]
    with service.store.connect() as db:
        assert db.execute("SELECT count(*) FROM event_acknowledgments").fetchone() == (
            1,
        )
        assert db.execute("SELECT count(*) FROM revisions").fetchone() == (1,)
    assert verify_store(service.store).ready


def test_obsolete_schedule_rejected_but_committed_receipt_replays(api, record_data):
    data, record, body = pending(api, record_data)
    key = str(uuid4())
    committed = api.post(
        BASE + "/events/acknowledge", json=body, headers=headers(api, key)
    )
    assert committed.status_code == 200
    data["time"]["planned_start_at"] = "2026-10-17T18:00:00Z"
    data["payload"]["prep_lead_minutes"] = 10
    assert (
        api.put(
            BASE + "/records/" + record["record_id"],
            json=dict(data, expected_version=1),
            headers=headers(api),
        ).status_code
        == 200
    )
    assert (
        api.post(
            BASE + "/events/acknowledge", json=body, headers=headers(api)
        ).status_code
        == 409
    )
    assert (
        api.post(
            BASE + "/events/acknowledge", json=body, headers=headers(api, key)
        ).json()
        == committed.json()
    )
    current = api.get(BASE + "/events", params={"mission_id": "demo-mission"}).json()
    assert not any(e["notification"]["acknowledged"] for e in current["events"])


def test_expired_token_and_wrong_epoch_do_not_ack(api, service, record_data, clock):
    _, _, body = pending(api, record_data)
    wrong = headers(api)
    wrong["X-Operator-Store-Epoch"] = str(uuid4())
    assert (
        api.post(BASE + "/events/acknowledge", json=body, headers=wrong).status_code
        == 409
    )
    clock.advance(120)
    assert (
        api.post(
            BASE + "/events/acknowledge", json=body, headers=headers(api)
        ).status_code
        == 409
    )
    with service.store.connect() as db:
        assert db.execute("SELECT count(*) FROM event_acknowledgments").fetchone() == (
            0,
        )


def test_distinct_clients_create_one_durable_acknowledgment(api, service, record_data):
    _, _, body = pending(api, record_data)
    first_headers, second_headers = headers(api), headers(api)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                api.post, BASE + "/events/acknowledge", json=body, headers=value
            )
            for value in (first_headers, second_headers)
        ]
        responses = [future.result(timeout=5) for future in futures]
    assert [r.status_code for r in responses] == [200, 200]
    assert (
        responses[0].json()["acknowledgment_id"]
        == responses[1].json()["acknowledgment_id"]
    )
    with service.store.connect() as db:
        assert db.execute("SELECT count(*) FROM event_acknowledgments").fetchone() == (
            1,
        )


def test_acknowledgment_preserves_operational_exports_and_survives_restart(
    api, service, record_data, clock
):
    from app.operator.projections import capture_projection
    from app.operator.runtime import OperatorRuntime

    _, _, body = pending(api, record_data)
    before = dict(
        capture_projection(
            service.store, mission_id="demo-mission", include_audit=True
        ).files
    )
    key = str(uuid4())
    response = api.post(
        BASE + "/events/acknowledge", json=body, headers=headers(api, key)
    )
    assert response.status_code == 200
    assert (
        dict(
            capture_projection(
                service.store, mission_id="demo-mission", include_audit=True
            ).files
        )
        == before
    )
    api.app.state.operator_runtime.close()
    api.app.state.operator_runtime = OperatorRuntime.start(
        service.store.settings, clock=clock
    )
    replay = api.post(
        BASE + "/events/acknowledge", json=body, headers=headers(api, key)
    )
    assert replay.status_code == 200
    assert replay.json() == response.json()
    assert (
        api.post(
            BASE + "/events/acknowledge", json=body, headers=headers(api)
        ).status_code
        == 409
    )
    assert api.get(BASE + "/events", params={"mission_id": "demo-mission"}).json()[
        "events"
    ][0]["notification"]["acknowledged"]
