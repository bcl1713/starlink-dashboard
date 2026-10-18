"""Synthetic issue workflows and immutable historical correction guards."""

from copy import deepcopy
from uuid import uuid4

import pytest

from tests.operator.api_helpers import BASE, create, headers


def issue_data(record_data, **payload):
    data = deepcopy(record_data)
    data.update(record_type="issue", time={})
    data["payload"] = {
        "entry_type": "issue",
        "title": "Synthetic backup problem",
        **payload,
    }
    return data


def saved(response, status=201):
    assert response.status_code == status, response.text
    return response.json()["saved_records"][0]


def replace(api, data, record, **payload):
    data = deepcopy(data)
    data["payload"].update(payload)
    return api.put(
        BASE + "/records/" + record["record_id"],
        json=dict(data, expected_version=record["version"]),
        headers=headers(api),
    )


def test_description_only_issue(api, record_data):
    record = saved(create(api, issue_data(record_data)))
    assert record["payload"]["status"] == "open"
    assert record["payload"]["priority"] is None
    assert record["payload"]["responsible_party"] is None
    assert record["payload"]["follow_up_at"] is None


def test_monitoring_workaround_is_not_resolved(api, record_data):
    data = issue_data(record_data)
    record = saved(create(api, data))
    updated = saved(
        replace(
            api,
            data,
            record,
            status="monitoring",
            mitigation="workaround",
            update_text="Synthetic alternate path",
        ),
        200,
    )
    assert updated["payload"]["status"] == "monitoring"
    assert updated["payload"]["mitigation"] == "workaround"
    assert updated["reason_origin"] == "automatic"


def resolved_issue(api, record_data):
    data = issue_data(record_data, update_text="Synthetic initial update")
    record = saved(create(api, data))
    data["payload"].update(status="resolved", update_text="")
    return data, saved(replace(api, data, record), 200)


def test_correct_after_resolve_preserves_current_fields(api, record_data):
    data, resolved = resolved_issue(api, record_data)
    corrected = saved(
        replace(
            api,
            data,
            resolved,
            corrects_version=1,
            corrected_update_at="2026-10-17T15:00:00Z",
            update_text="Synthetic corrected update",
        ),
        200,
    )
    assert corrected["payload"]["status"] == "resolved"
    assert corrected["time"] == resolved["time"]
    assert corrected["payload"]["follow_up_at"] is None
    assert corrected["reason"] == "Issue update corrected"
    history = api.get(BASE + "/records/" + corrected["record_id"] + "/history").json()
    assert any(
        item["record"]["payload"].get("update_text") == "Synthetic initial update"
        for item in history["items"]
    )


def test_mixed_correction_and_status_edit_rejected(api, record_data):
    data, resolved = resolved_issue(api, record_data)
    assert (
        replace(
            api,
            data,
            resolved,
            corrects_version=1,
            update_text="Synthetic correction",
            status="reopened",
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"title": " "},
        {"priority": "critical"},
        {"status": "done"},
        {"follow_up_at": "2026-10-17T16:00:00"},
        {"status": "resolved", "follow_up_at": "2026-10-17T15:00:00Z"},
        {"corrects_version": 1, "update_text": "Synthetic invalid create correction"},
        {"corrected_update_at": "2026-10-17T15:00:00Z"},
    ],
)
def test_invalid_issue_fields(api, record_data, payload):
    assert create(api, issue_data(record_data, **payload)).status_code == 422


@pytest.mark.parametrize(
    "target,text", [(99, "Synthetic update"), (2, "Synthetic update"), (1, " ")]
)
def test_invalid_correction_targets(api, record_data, target, text):
    data, resolved = resolved_issue(api, record_data)
    assert (
        replace(
            api, data, resolved, corrects_version=target, update_text=text
        ).status_code
        == 422
    )


def test_issue_replay_conflict_remove_restore(api, record_data):
    data = issue_data(
        record_data,
        follow_up_at="2026-10-17T15:00:00Z",
        priority="urgent",
        responsible_party="  ",
    )
    key = str(uuid4())
    first = create(api, data, key)
    record = saved(first)
    assert create(api, data, key).json() == first.json()
    assert record["payload"]["responsible_party"] is None
    updated = saved(replace(api, data, record, status="reopened"), 200)
    assert replace(api, data, record).status_code == 409
    removed = saved(
        api.post(
            BASE + "/records/" + record["record_id"] + "/remove",
            json={"expected_version": updated["version"]},
            headers=headers(api),
        ),
        200,
    )
    restored = saved(
        api.post(
            BASE + "/records/" + record["record_id"] + "/restore",
            json={"expected_version": removed["version"]},
            headers=headers(api),
        ),
        200,
    )
    assert not restored["deleted"]


def test_issue_call_link_guards_both_directions(api, record_data):
    call = deepcopy(record_data)
    call.update(record_type="call", time={})
    call["payload"] = {
        "entry_type": "call",
        "title": "Synthetic call",
        "status": "tentative",
    }
    target = saved(create(api, call))
    saved(create(api, issue_data(record_data, call_id=target["record_id"])))
    removal = api.post(
        BASE + "/records/" + target["record_id"] + "/remove",
        json={"expected_version": 1},
        headers=headers(api),
    )
    assert removal.status_code == 409
    data = issue_data(record_data, call_id=target["record_id"])
    data["mission_id"] = "other-mission"
    assert create(api, data).status_code == 409
