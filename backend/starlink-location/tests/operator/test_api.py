"""HTTP contracts exercise the real journal, receipts and planning references."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, local
from uuid import uuid4

import pytest

from tests.operator.api_helpers import BASE, create, headers


def test_saved_then_replayed(api, record_data):
    key = str(uuid4())
    first = create(api, record_data, key)
    assert first.status_code == 201
    saved = first.json()["saved_records"][0]
    assert saved["version"] == 1
    assert saved["author"]["backend"] == "restricted-access operator"
    path = BASE + "/records/" + saved["record_id"]
    body = dict(record_data, expected_version=1)
    edited = api.put(path, json=body, headers=headers(api))
    assert edited.status_code == 200
    assert edited.json()["saved_records"][0]["version"] == 2
    retry = create(api, record_data, key)
    assert retry.json() == first.json()
    assert retry.headers["Idempotency-Replayed"] == "true"
    assert first.headers["Idempotency-Replayed"] == "false"
    conflict = api.put(path, json=body, headers=headers(api))
    assert conflict.status_code == 409
    assert conflict.json()["error"]["current_version"] == 2
    assert create(api, dict(record_data, scope="postflight"), key).status_code == 409
    assert api.get(path).headers["Cache-Control"] == "no-store"


def test_required_preconditions_size_absence_and_cursor_bounds(api, record_data):
    assert api.post(BASE + "/records", json=record_data).status_code == 422
    assert (
        api.post(
            BASE + "/records",
            json=record_data,
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 422
    )
    saved = create(api, record_data).json()["saved_records"][0]
    path = BASE + "/records/" + saved["record_id"]
    assert api.put(path, json=record_data, headers=headers(api)).status_code == 422
    assert api.get(BASE + "/records/" + str(uuid4())).status_code == 404
    result = api.post(BASE + "/records", content=b" " * 65537, headers=headers(api))
    assert result.status_code == 422
    for query in ("limit=0", "limit=201", "cursor=invalid"):
        assert (
            api.get(BASE + "/records?mission_id=demo-mission&" + query).status_code
            == 422
        )


@pytest.mark.parametrize(
    "note,reason,origin",
    [
        (None, "Operator correction", "automatic"),
        ("  ", "Operator correction", "automatic"),
        ("typo fixed", "typo fixed", "operator"),
    ],
)
def test_optional_audit_reason_and_ordered_history(
    api, record_data, note, reason, origin
):
    saved = create(api, record_data).json()["saved_records"][0]
    path = BASE + "/records/" + saved["record_id"]
    body = dict(record_data, expected_version=1)
    if note is not None:
        body["audit_note"] = note
    edited = api.put(path, json=body, headers=headers(api))
    revision = edited.json()["saved_records"][0]
    assert (revision["reason"], revision["reason_origin"]) == (reason, origin)
    for action, version, expected in (
        ("remove", 2, "Operator removal"),
        ("restore", 3, "Operator restoration"),
    ):
        result = api.post(
            path + "/" + action,
            json={"expected_version": version},
            headers=headers(api),
        )
        assert result.json()["saved_records"][0]["reason"] == expected
    history = api.get(path + "/history").json()
    assert [item["record"]["version"] for item in history["items"]] == [1, 2, 3, 4]
    assert [
        item["record"]["version"]
        for item in api.get(BASE + "/journal?mission_id=demo-mission").json()["items"]
    ] == [1, 2, 3, 4]


def test_read_metadata_preserves_missing_unknown_and_saved_receipt(
    api, record_data, monkeypatch
):
    from app.mission import storage

    saved = create(api, record_data).json()["saved_records"][0]
    path = BASE + "/records/" + saved["record_id"]
    monkeypatch.setattr(storage, "load_mission_v2", lambda _: None)
    read = api.get(path).json()
    assert read["record"] == saved
    assert read["association"]["status"] == "missing"
    assert read["association"]["unresolved_fields"] == ["mission_id"]
    assert read["freshness"] == {
        "status": "unknown",
        "threshold_seconds": None,
        "as_of": "2026-10-17T16:00:00.000000Z",
    }
    assert (
        api.get(path + "/history").json()["items"][0]["association"]["status"]
        == "missing"
    )

    def unavailable(_):
        raise OSError("private fixture path")

    monkeypatch.setattr(storage, "load_mission_v2", unavailable)
    assert api.get(path).json()["association"]["status"] == "unknown"


def test_simultaneous_duplicate_headers_match_actual_write(
    api, record_data, monkeypatch
):
    from app.operator import commands

    receipt_for_key = commands.receipt_for_key
    barrier, state = Barrier(2), local()

    def synchronized_read(*args):
        receipt = receipt_for_key(*args)
        if not getattr(state, "checked", False):
            state.checked = True
            assert receipt is None
            barrier.wait(timeout=5)
        return receipt

    monkeypatch.setattr(commands, "receipt_for_key", synchronized_read)
    key = str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: create(api, record_data, key), range(2)))
    assert [result.status_code for result in results] == [201, 201]
    assert results[0].json() == results[1].json()
    assert sorted(result.headers["Idempotency-Replayed"] for result in results) == [
        "false",
        "true",
    ]
    assert len(api.get(BASE + "/journal?mission_id=demo-mission").json()["items"]) == 1
