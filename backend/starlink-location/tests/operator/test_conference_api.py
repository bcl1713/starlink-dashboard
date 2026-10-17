"""Conference contracts preserve unknowns and independent customer state."""
from copy import deepcopy
from tests.operator.api_helpers import BASE, create, headers


def conference_data(record_data, **payload):
    data = deepcopy(record_data)
    data.update(record_type="conference", time={})
    data["payload"] = dict(entry_type="conference", title="Synthetic conference", **payload)
    return data


def test_public_conference_and_participation_roundtrip(api, record_data):
    data = conference_data(record_data, status="established")
    response = create(api, data)
    assert response.status_code == 201, response.text
    record = response.json()["saved_records"][0]
    assert record["payload"]["verified_at"] is None
    assert record["payload"]["configured_transport"] is None
    participation = deepcopy(record_data)
    participation.update(record_type="participation", time={})
    participation["payload"] = dict(entry_type="participation", title="Unknown customer", state="connected", conference_id=record["record_id"])
    joined = create(api, participation)
    assert joined.status_code == 201, joined.text
    saved = joined.json()["saved_records"][0]
    assert saved["time"]["occurred_at"] is None
    assert saved["payload"]["participant"] is None
    participation["payload"]["state"] = "left"
    left = api.put(BASE + "/records/" + saved["record_id"], json=dict(participation, expected_version=1), headers=headers(api))
    assert left.status_code == 200, left.text
    assert left.json()["saved_records"][0]["time"]["occurred_at"] is None
    assert api.get(BASE + "/records/" + record["record_id"]).json()["record"]["version"] == 1


def test_conference_unknown_defaults(api, record_data):
    response = create(api, conference_data(record_data))
    assert response.status_code == 201, response.text
    assert response.json()["saved_records"][0]["payload"]["status"] is None


def test_conference_actual_payload_times_use_acceptance_clock(api, record_data):
    response = create(api, conference_data(record_data, status="established", verified_at="2026-10-17T16:02:00Z"))
    assert response.status_code == 422, response.text
