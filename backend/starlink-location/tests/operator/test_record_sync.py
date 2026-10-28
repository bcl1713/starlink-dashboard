"""Cross-client reads bind baselines and incremental checkpoints to their source."""

import json
from base64 import urlsafe_b64decode, urlsafe_b64encode

import pytest
from tests.operator.api_helpers import BASE, create, headers


def source_key(health):
    return json.dumps(
        [health["store_id"], health["api_epoch"], health["source_mode"], None],
        separators=(",", ":"),
    )


def changes(api, after=0, **params):
    return api.get(
        BASE + "/record-changes",
        params={"mission_id": "demo-mission", "after_seq": after, **params},
    )


def test_empty_baseline_and_changes_capture_identity(api):
    health = api.get(BASE + "/health").json()
    baseline = api.get(
        BASE + "/records",
        params={"mission_id": "demo-mission", "source_identity": source_key(health)},
    ).json()
    assert baseline["items"] == []
    assert baseline["H"] == 0
    assert baseline["source"] == {**health, "mission_id": "demo-mission"}
    delta = changes(api).json()
    assert delta["items"] == []
    assert delta["H"] == 0
    assert delta["source"] == baseline["source"]


def test_delta_latest_versions_tombstones_and_mission_isolation(api, record_data):
    first = create(api, record_data).json()["saved_records"][0]
    second = create(api, record_data).json()["saved_records"][0]
    create(api, dict(record_data, mission_id="other-mission"))
    path = BASE + "/records/" + first["record_id"]
    edited = api.put(
        path, json=dict(record_data, expected_version=1), headers=headers(api)
    )
    assert edited.status_code == 200
    removed = api.post(
        path + "/remove", json={"expected_version": 2}, headers=headers(api)
    )
    assert removed.status_code == 200
    page = changes(api).json()
    assert [
        (r["record"]["record_id"], r["record"]["version"]) for r in page["items"]
    ] == [(second["record_id"], 1), (first["record_id"], 3)]
    assert page["items"][1]["record"]["deleted"] is True
    assert changes(api, page["H"]).json()["items"] == []
    restored = api.post(
        path + "/restore", json={"expected_version": 3}, headers=headers(api)
    )
    assert restored.status_code == 200
    delta = changes(api, page["H"]).json()
    assert len(delta["items"]) == 1
    assert delta["items"][0]["record"]["version"] == 4
    assert delta["items"][0]["record"]["deleted"] is False


def test_changes_batch_freezes_upper_boundary_during_writes(api, record_data):
    rows = [create(api, record_data).json()["saved_records"][0] for _ in range(3)]
    page = changes(api, limit=1).json()
    assert len(page["items"]) == 1
    assert page["cursor"]
    path = BASE + "/records/" + rows[1]["record_id"]
    assert (
        api.put(
            path, json=dict(record_data, expected_version=1), headers=headers(api)
        ).status_code
        == 200
    )
    new = create(api, record_data).json()["saved_records"][0]
    all_rows = list(page["items"])
    cursor = page["cursor"]
    while cursor:
        following = changes(api, limit=1, cursor=cursor).json()
        assert following["H"] == page["H"]
        assert following["as_of"] == page["as_of"]
        all_rows.extend(following["items"])
        cursor = following["cursor"]
    assert [r["record"]["record_id"] for r in all_rows] == [
        r["record_id"] for r in rows
    ]
    assert [r["record"]["version"] for r in all_rows] == [1, 1, 1]
    tail = changes(api, page["H"]).json()
    assert [r["record"]["record_id"] for r in tail["items"]] == [
        rows[1]["record_id"],
        new["record_id"],
    ]


@pytest.mark.parametrize(
    "params",
    [{"after_seq": -1}, {"after_seq": 1}, {"cursor": "invalid"}, {"limit": 201}],
)
def test_invalid_checkpoints_are_distinguishable_from_transient_failures(api, params):
    response = api.get(
        BASE + "/record-changes",
        params={"mission_id": "demo-mission", "after_seq": 0, **params},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] in ("invalid_cursor", "validation_error")


def test_source_change_rejects_old_baseline_and_delta_cursor(api, record_data):
    health = api.get(BASE + "/health").json()
    for _ in range(2):
        create(api, record_data)
    cursor = changes(api, limit=1).json()["cursor"]
    foreign = json.loads(urlsafe_b64decode(cursor))
    foreign["source"] = "foreign-context"
    forged = urlsafe_b64encode(json.dumps(foreign).encode()).decode()
    assert changes(api, cursor=forged).status_code == 422
    assert changes(api, source_identity="obsolete-source").status_code == 409
    response = api.get(
        BASE + "/records",
        params={"mission_id": "demo-mission", "source_identity": "obsolete-source"},
    )
    assert response.status_code == 409
    # A cursor for one mission can never be used for another, even in one store.
    assert (
        api.get(
            BASE + "/record-changes",
            params={"mission_id": "other-mission", "after_seq": 0, "cursor": cursor},
        ).status_code
        == 422
    )
    assert changes(api, source_identity=source_key(health)).status_code == 200


def test_replay_replacement_rejects_checkpoint_even_when_operating_context_is_unchanged(
    api, service, clock, record_data, monkeypatch
):
    from app.operator.models import CreateRecord
    from app.operator.runtime import OperatorRuntimeBinding
    from tests.operator.service_helpers import submit

    monkeypatch.setenv("OPERATOR_ROOT", str(service.store.settings.root))
    replay = ["replay-a"]
    binding = OperatorRuntimeBinding(
        clock=clock,
        context=lambda: ("simulation", replay[0]),
        mission_journals=True,
        operating_context=lambda: "context-a",
    )
    api.app.state.operator_binding = binding
    try:
        with binding.access() as runtime:
            runtime.provision(
                expected_mode="simulation",
                expected_run=runtime.health().simulation_run_id,
            )
            for _ in range(2):
                submit(runtime.service, CreateRecord.model_validate(record_data))
        health = api.get(BASE + "/health").json()
        identity = json.dumps(
            [health["store_id"], health["api_epoch"], "simulation", "context-a"],
            separators=(",", ":"),
        )
        baseline = api.get(
            BASE + "/records",
            params={
                "mission_id": "demo-mission",
                "source_identity": identity,
                "limit": 1,
            },
        ).json()
        delta = changes(api, limit=1).json()
        assert baseline["source"]["replay_run_id"] == "replay-a"
        replay[0] = "replay-b"
        assert changes(api, cursor=delta["cursor"]).status_code == 422
        continuation = api.get(
            BASE + "/records",
            params={
                "mission_id": "demo-mission",
                "source_identity": identity,
                "cursor": baseline["cursor"],
            },
        )
        assert continuation.status_code == 422
        fresh = api.get(
            BASE + "/records",
            params={"mission_id": "demo-mission", "source_identity": identity},
        ).json()
        assert fresh["source"]["replay_run_id"] == "replay-b"
        assert fresh["source"]["store_id"] == health["store_id"]
    finally:
        del api.app.state.operator_binding
        binding.close()
