"""Previously uncovered public typed removal/restoration and immutable history."""

from copy import deepcopy

import pytest
from tests.operator.api_helpers import BASE, create, headers
from tests.operator.test_capability_api import assessment
from tests.operator.test_conference_api import conference_data
from tests.operator.test_transport_contract import decision, row


@pytest.mark.parametrize(
    "kind",
    [
        "conference",
        "participation",
        "capability_assessment",
        "transport_decision",
        "call_observation",
    ],
)
def test_typed_correction_remove_restore_keeps_original_history(api, record_data, kind):
    parent = None
    if kind == "conference":
        data = conference_data(record_data, coordinator="Fictional coordinator")
    elif kind == "capability_assessment":
        data = assessment(record_data)
    elif kind == "transport_decision":
        data = decision(record_data, row(applied={"transport": "Ka"}))
    elif kind == "participation":
        response = create(api, conference_data(record_data))
        assert response.status_code == 201, response.text
        parent = response.json()["saved_records"][0]
        data = deepcopy(record_data)
        data.update(record_type="participation", time={})
        data["payload"] = {
            "entry_type": "participation",
            "title": "Fictional interval",
            "state": "connected",
            "conference_id": parent["record_id"],
        }
    else:
        data = deepcopy(record_data)
        data["payload"]["entry_type"] = "call_observation"
    first = create(api, data)
    assert first.status_code == 201, first.text
    original = first.json()["saved_records"][0]
    path = BASE + "/records/" + original["record_id"]
    changed = deepcopy(data)
    changed["payload"]["title"] = "Fictional corrected title"
    update = api.put(path, json=dict(changed, expected_version=1), headers=headers(api))
    assert update.status_code == 200, update.text
    replacement = update.json()["saved_records"][0]
    results = [original, replacement]
    for action, version in [("remove", 2), ("restore", 3)]:
        response = api.post(
            path + "/" + action,
            json={"expected_version": version},
            headers=headers(api),
        )
        assert response.status_code == 200, response.text
        saved = response.json()["saved_records"][0]
        assert saved["deleted"] == (action == "remove")
        assert saved["payload"] == replacement["payload"]
        assert saved["time"] == replacement["time"]
        results.append(saved)
    history = api.get(path + "/history").json()
    assert [item["record"] for item in history["items"]] == results
    assert [item["record"]["version"] for item in history["items"]] == [1, 2, 3, 4]
    assert api.get(path).json()["record"] == results[-1]
    if parent:
        assert (
            api.get(BASE + "/records/" + parent["record_id"]).json()["record"] == parent
        )


def test_cancel_call_preserves_established_conference_and_connected_customer(
    api, record_data
):
    from tests.operator.test_call_api import call_data

    response = create(api, conference_data(record_data, status="established"))
    assert response.status_code == 201, response.text
    conference = response.json()["saved_records"][0]
    data = call_data(record_data, conference_id=conference["record_id"])
    response = create(api, data)
    assert response.status_code == 201, response.text
    call = response.json()["saved_records"][0]
    interval = deepcopy(record_data)
    interval.update(record_type="participation", time={})
    interval["payload"] = {
        "entry_type": "participation",
        "title": "Fictional connected customer",
        "state": "connected",
        "call_id": call["record_id"],
        "conference_id": conference["record_id"],
    }
    response = create(api, interval)
    assert response.status_code == 201, response.text
    customer = response.json()["saved_records"][0]
    data["payload"].update(status="cancelled", prep_lead_minutes=None)
    response = api.put(
        BASE + "/records/" + call["record_id"],
        json=dict(data, expected_version=1),
        headers=headers(api),
    )
    assert response.status_code == 200, response.text
    assert response.json()["saved_records"][0]["payload"]["status"] == "cancelled"
    for original in (conference, customer):
        assert (
            api.get(BASE + "/records/" + original["record_id"]).json()["record"]
            == original
        )
