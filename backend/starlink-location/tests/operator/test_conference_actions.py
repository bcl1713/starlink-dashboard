"""Independent lifecycle, predecessor integrity and immutable retry outcomes."""

from copy import deepcopy
from uuid import uuid4

from tests.operator.api_helpers import BASE, create, headers
from tests.operator.test_call_api import call_data
from tests.operator.test_conference_api import conference_data


def saved(response):
    assert response.status_code in (200, 201), response.text
    return response.json()["saved_records"][0]


def replace(api, record, data):
    return api.put(
        BASE + "/records/" + record["record_id"],
        json=dict(data, expected_version=record["version"]),
        headers=headers(api),
    )


def participation(record_data, target, **payload):
    data = deepcopy(record_data)
    data.update(record_type="participation", time={})
    data["payload"] = dict(
        entry_type="participation",
        title="Synthetic customer",
        conference_id=target,
        **payload
    )
    return data


def test_verification_requires_established_conference(api, record_data):
    assert (
        create(
            api,
            conference_data(
                record_data, status="interrupted", verified_at="2026-10-17T15:00:00Z"
            ),
        ).status_code
        == 422
    )


def test_configuration_change_clears_verification(api, record_data):
    data = conference_data(
        record_data,
        status="established",
        configured_transport="Ka",
        verified_at="2026-10-17T15:00:00Z",
    )
    first = saved(create(api, data))
    data["payload"]["configured_transport"] = "X"
    assert replace(api, first, data).status_code == 422
    data["payload"]["verified_at"] = None
    assert saved(replace(api, first, data))["payload"]["verified_at"] is None


def test_resume_link_rejects_cycles_and_wrong_targets(api, record_data):
    conference = saved(create(api, conference_data(record_data)))
    data = participation(record_data, conference["record_id"], state="interrupted")
    predecessor = saved(create(api, data))
    data["payload"].update(
        state="connected", resumes_participation_id=predecessor["record_id"]
    )
    resumed = saved(create(api, data))
    assert resumed["reason"] == "Customer connection restored"
    predecessor_data = participation(
        record_data, conference["record_id"], state="connected"
    )
    assert replace(api, predecessor, predecessor_data).status_code == 409
    predecessor_data["payload"].update(
        state="interrupted", resumes_participation_id=resumed["record_id"]
    )
    assert replace(api, predecessor, predecessor_data).status_code == 409
    assert (
        api.post(
            BASE + "/records/" + predecessor["record_id"] + "/remove",
            json={"expected_version": 1},
            headers=headers(api),
        ).status_code
        == 409
    )


def test_call_completion_does_not_mutate_conference(api, record_data):
    conference = saved(create(api, conference_data(record_data, status="established")))
    data = call_data(record_data, conference_id=conference["record_id"])
    call = saved(create(api, data))
    data["payload"].update(status="completed", prep_lead_minutes=None)
    saved(replace(api, call, data))
    assert (
        api.get(BASE + "/records/" + conference["record_id"]).json()["record"]
        == conference
    )


def test_retry_after_remote_edit_replays_original_receipt(api, record_data):
    conference = saved(create(api, conference_data(record_data)))
    data = participation(record_data, conference["record_id"], state="connected")
    key = str(uuid4())
    response = create(api, data, key)
    first = saved(response)
    updated = deepcopy(data)
    updated["payload"]["state"] = "left"
    saved(replace(api, first, updated))
    assert create(api, data, key).json() == response.json()
    assert (
        api.get(BASE + "/records/" + first["record_id"]).json()["record"]["payload"][
            "state"
        ]
        == "left"
    )
