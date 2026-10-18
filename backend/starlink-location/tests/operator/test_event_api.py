"""Public feed snapshots remain useful without notification delivery."""

from tests.operator.api_helpers import BASE, create
from tests.operator.test_call_api import call_data


def test_feed_uses_utc_clock_and_prep_default(api, record_data, clock):
    assert create(api, call_data(record_data)).status_code == 201
    response = api.get(BASE + "/events", params={"mission_id": "demo-mission"})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["as_of"] == "2026-10-17T16:00:00.000000Z"
    assert [event["kind"] for event in body["events"]] == ["call_prep", "call_start"]
    assert body["events"][0]["due_at"] == "2026-10-17T16:50:00.000000Z"
    assert not any(e["notification"]["eligible"] for e in body["events"])
    clock.advance(50 * 60)
    assert api.get(BASE + "/events", params={"mission_id": "demo-mission"}).json()[
        "events"
    ][0]["notification"]["eligible"]


def test_feed_requires_mission_and_invalid_cursor_is_explicit(api):
    assert api.get(BASE + "/events").status_code == 422
    response = api.get(
        BASE + "/events", params={"mission_id": "demo-mission", "cursor": "invented"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "event_snapshot_changed"


def test_feed_pagination_is_pinned_during_new_writes(api, record_data):
    for index in range(3):
        data = call_data(record_data)
        data["payload"]["title"] = "Synthetic " + str(index)
        assert create(api, data).status_code == 201
    first = api.get(
        BASE + "/events", params={"mission_id": "demo-mission", "limit": 2}
    ).json()
    assert len(first["events"]) == 2
    assert first["cursor"]
    assert create(api, call_data(record_data)).status_code == 201
    second = api.get(
        BASE + "/events",
        params={"mission_id": "demo-mission", "limit": 2, "cursor": first["cursor"]},
    ).json()
    assert second["H"] == first["H"] == 3
    assert not set(e["event_id"] for e in first["events"]) & set(
        e["event_id"] for e in second["events"]
    )


def test_unknown_call_time_stays_visible_without_eligible_alert(api, record_data):
    data = call_data(record_data, status="tentative")
    data["time"] = {}
    assert create(api, data).status_code == 201
    body = api.get(BASE + "/events", params={"mission_id": "demo-mission"}).json()
    assert len(body["events"]) == 1
    assert body["events"][0]["due_at"] is None
    assert body["events"][0]["state"] == "unknown"
    assert body["events"][0]["notification"]["eligible"] is False


def test_rescheduled_history_cannot_resurrect_old_pending_occurrences(api, record_data):
    from tests.operator.api_helpers import headers

    data = call_data(record_data)
    record = create(api, data).json()["saved_records"][0]
    before = api.get(BASE + "/events", params={"mission_id": "demo-mission"}).json()
    old_ids = {e["notification"]["generation"] for e in before["events"]}
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
    current = api.get(BASE + "/events", params={"mission_id": "demo-mission"}).json()
    assert not old_ids & {e["notification"]["generation"] for e in current["events"]}
    history = api.get(
        BASE + "/events", params={"mission_id": "demo-mission", "include_history": True}
    ).json()
    obsolete = [
        e for e in history["events"] if e["notification"]["generation"] in old_ids
    ]
    assert len(obsolete) == 2
    assert all(e["notification"]["retired"] and not e["active"] for e in obsolete)
