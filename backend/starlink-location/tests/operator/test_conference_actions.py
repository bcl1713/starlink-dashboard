"""Independent lifecycle, predecessor integrity and immutable retry outcomes."""

from copy import deepcopy
from uuid import uuid4

import pytest

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


def test_combined_establishment_is_atomic_and_retryable(api, record_data):
    data = conference_data(record_data, status="preparing", configured_transport="Ka")
    first = saved(create(api, data))
    data["time"] = {
        "occurred_at": "2026-10-17T16:00:00Z",
        "precision": "exact",
        "end_state": "instant",
    }
    data["payload"].update(status="established", verified_at="2026-10-17T16:00:00Z")
    key = str(uuid4())
    body = dict(data, expected_version=1, establish_session=True)
    response = api.put(
        BASE + "/records/" + first["record_id"], json=body, headers=headers(api, key)
    )
    established = saved(response)
    assert established["payload"]["verified_at"] == "2026-10-17T16:00:00.000000Z"
    assert established["version"] == 2
    assert (
        api.put(
            BASE + "/records/" + first["record_id"],
            json=body,
            headers=headers(api, key),
        ).json()
        == response.json()
    )
    assert (
        len(
            api.get(BASE + "/records/" + first["record_id"] + "/history").json()[
                "items"
            ]
        )
        == 2
    )


@pytest.mark.parametrize(
    "activity",
    [
        "active_call",
        "connected",
        "unknown",
        "interrupted_unknown",
        "indirect_connected",
    ],
)
def test_close_rejects_authoritative_activity_without_a_revision(
    api, record_data, activity
):
    data = conference_data(record_data, status="established")
    conference = saved(create(api, data))
    if activity in ("active_call", "indirect_connected"):
        call = call_data(record_data, conference_id=conference["record_id"])
        if activity == "active_call":
            call["time"].update(
                occurred_at="2026-10-17T15:30:00Z",
                precision="exact",
                end_state="ongoing",
            )
        linked = saved(create(api, call))
    if activity != "active_call":
        state = {
            "connected": "connected",
            "unknown": "unknown",
            "interrupted_unknown": "interrupted",
            "indirect_connected": "connected",
        }[activity]
        customer = participation(record_data, conference["record_id"], state=state)
        if activity == "indirect_connected":
            customer["payload"].update(conference_id=None, call_id=linked["record_id"])
        saved(create(api, customer))
    data["payload"]["status"] = "closed"
    denied = replace(api, conference, data)
    assert denied.status_code == 409, denied.text
    assert (
        api.get(BASE + "/records/" + conference["record_id"]).json()["record"][
            "version"
        ]
        == 1
    )


def test_future_requirement_alone_does_not_block_close(api, record_data):
    data = conference_data(record_data, status="established")
    conference = saved(create(api, data))
    saved(create(api, call_data(record_data, conference_id=conference["record_id"])))
    data["payload"]["status"] = "closed"
    assert saved(replace(api, conference, data))["payload"]["status"] == "closed"


def test_direct_call_establishment_and_ad_hoc_transport_roundtrip(api, record_data):
    data = call_data(
        record_data,
        direct_transport="ad-hoc:backup",
        established_at="2026-10-17T15:30:00Z",
    )
    data["time"].update(
        occurred_at="2026-10-17T15:30:00Z", precision="exact", end_state="ongoing"
    )
    direct = saved(create(api, data))
    assert direct["payload"]["direct_transport"] == "ad-hoc:backup"
    assert direct["payload"]["established_at"] == "2026-10-17T15:30:00.000000Z"
    assert direct["payload"]["conference_id"] is None
    assert (
        saved(
            create(
                api, conference_data(record_data, configured_transport="ad-hoc:backup")
            )
        )["payload"]["configured_transport"]
        == "ad-hoc:backup"
    )


def test_direct_check_cannot_report_future_evidence(api, record_data):
    assert (
        create(
            api, call_data(record_data, established_at="2026-10-17T16:02:00Z")
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "target_state",
    ["closed", "preparing", "interrupted", "legacy_unchecked", "direct_unchecked"],
)
def test_connect_intent_transactionally_rejects_unready_target(
    api, record_data, target_state
):
    if target_state == "direct_unchecked":
        call = saved(create(api, call_data(record_data)))
        data = participation(
            record_data, None, state="connected", call_id=call["record_id"]
        )
    else:
        state = "established" if target_state == "legacy_unchecked" else target_state
        bridge = saved(create(api, conference_data(record_data, status=state)))
        data = participation(record_data, bridge["record_id"], state="connected")
    data.update(connect_customer=True)
    data["time"] = {
        "occurred_at": "2026-10-17T16:00:00Z",
        "precision": "exact",
        "end_state": "ongoing",
    }
    response = create(api, data)
    assert response.status_code == 409, response.text


def test_explicit_connect_accepts_checked_bridge_then_close_rejects(api, record_data):
    bridge_data = conference_data(
        record_data, status="established", verified_at="2026-10-17T16:00:00Z"
    )
    bridge = saved(create(api, bridge_data))
    data = participation(record_data, bridge["record_id"], state="connected")
    data.update(connect_customer=True)
    data["time"] = {
        "occurred_at": "2026-10-17T16:00:00Z",
        "precision": "exact",
        "end_state": "ongoing",
    }
    assert saved(create(api, data))["payload"]["state"] == "connected"
    bridge_data["payload"].update(status="closed", verified_at=None)
    assert replace(api, bridge, bridge_data).status_code == 409


def test_pre_upgrade_direct_call_retry_keeps_original_receipt_hash(
    service, record_data
):
    import hashlib
    import json

    from app.operator.commands import execute_in_transaction
    from app.operator.models import CreateRecord
    from tests.operator.service_helpers import submit

    command = CreateRecord(**call_data(record_data))
    body = command.model_dump(mode="json", exclude={"connect_customer"})
    body["payload"].pop("direct_transport", None)
    body["payload"].pop("established_at", None)
    legacy_hash = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    key = str(uuid4())
    with service.store.connect(write=True) as connection:
        original = execute_in_transaction(
            connection,
            command,
            key=key,
            request_hash=legacy_hash,
            clock=service.clock,
            actor=service.actor,
        )
    assert submit(service, command, key=key) == original


def test_direct_establishment_updates_existing_actual_start_without_losing_transport(
    api, record_data
):
    data = call_data(record_data, direct_transport="Ka")
    first = saved(create(api, data))
    data["payload"].update(prep_lead_minutes=10, established_at="2026-10-17T16:00:00Z")
    data["time"].update(
        occurred_at="2026-10-17T15:30:00Z", precision="exact", end_state="ongoing"
    )
    response = api.put(
        BASE + "/records/" + first["record_id"],
        json=dict(data, expected_version=1, establish_session=True),
        headers=headers(api),
    )
    established = saved(response)
    assert established["time"]["occurred_at"] == "2026-10-17T15:30:00.000000Z"
    assert established["payload"]["established_at"] == "2026-10-17T16:00:00.000000Z"
    customer = participation(
        record_data, None, state="connected", call_id=first["record_id"]
    )
    customer.update(connect_customer=True)
    customer["time"] = {
        "occurred_at": "2026-10-17T16:00:00Z",
        "precision": "exact",
        "end_state": "ongoing",
    }
    assert saved(create(api, customer))["payload"]["call_id"] == first["record_id"]


def test_changing_direct_transport_clears_check_before_reuse(api, record_data):
    data = call_data(
        record_data, direct_transport="Ka", established_at="2026-10-17T15:30:00Z"
    )
    first = saved(create(api, data))
    data["payload"].update(prep_lead_minutes=10, direct_transport="X")
    response = replace(api, first, data)
    assert response.status_code == 422, response.text
    data["payload"]["established_at"] = None
    assert saved(replace(api, first, data))["payload"]["established_at"] is None


def test_connect_start_intent_rejects_closed_bridge_before_actual_activity(
    api, record_data
):
    conference = saved(create(api, conference_data(record_data, status="closed")))
    data = call_data(record_data, conference_id=conference["record_id"])
    first = saved(create(api, data))
    data["payload"]["prep_lead_minutes"] = 10
    data["time"].update(
        occurred_at="2026-10-17T16:00:00Z", precision="exact", end_state="ongoing"
    )
    response = api.put(
        BASE + "/records/" + first["record_id"],
        json=dict(data, expected_version=1, begin_customer_connect=True),
        headers=headers(api),
    )
    assert response.status_code == 409, response.text
    assert (
        api.get(BASE + "/records/" + first["record_id"]).json()["record"]["time"][
            "occurred_at"
        ]
        is None
    )


def test_connect_start_intent_protects_bridge_until_customer_capture(api, record_data):
    conference_data_ = conference_data(
        record_data, status="established", verified_at="2026-10-17T16:00:00Z"
    )
    conference = saved(create(api, conference_data_))
    data = call_data(record_data, conference_id=conference["record_id"])
    first = saved(create(api, data))
    data["payload"]["prep_lead_minutes"] = 10
    data["time"].update(
        occurred_at="2026-10-17T16:00:00Z", precision="exact", end_state="ongoing"
    )
    response = api.put(
        BASE + "/records/" + first["record_id"],
        json=dict(data, expected_version=1, begin_customer_connect=True),
        headers=headers(api),
    )
    assert saved(response)["time"]["occurred_at"] == "2026-10-17T16:00:00.000000Z"
    conference_data_["payload"].update(status="closed", verified_at=None)
    assert replace(api, conference, conference_data_).status_code == 409


def test_live_customer_connection_requires_actual_call_start(api, record_data):
    bridge = saved(
        create(
            api,
            conference_data(
                record_data, status="established", verified_at="2026-10-17T16:00:00Z"
            ),
        )
    )
    call = saved(create(api, call_data(record_data, conference_id=bridge["record_id"])))
    data = participation(
        record_data, bridge["record_id"], state="connected", call_id=call["record_id"]
    )
    data.update(connect_customer=True)
    data["time"] = {
        "occurred_at": "2026-10-17T16:00:00Z",
        "precision": "exact",
        "end_state": "ongoing",
    }
    assert create(api, data).status_code == 409
