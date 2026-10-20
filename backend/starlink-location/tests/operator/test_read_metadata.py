"""Freshness uses source time and a known producer policy, never acceptance."""

from datetime import timedelta
from uuid import uuid4

import pytest

from app.operator.models import CreateRecord
from app.operator.provenance import SourceProvenance, SourceReference
from app.operator.read_metadata import freshness
from tests.operator.api_helpers import BASE, create, headers


@pytest.mark.parametrize(
    "kind,age,policy,want,threshold",
    [
        ("observed", 9, {"fixture": 10}, "fresh", 10),
        ("observed", 10, {"fixture": 10}, "stale", 10),
        ("modeled", 90, {"fixture": 60}, "stale", 60),
        ("observed", 90, {}, "unknown", None),
        ("operator_reported", 0, {"fixture": 10}, "unknown", None),
        ("observed", None, {"fixture": 10}, "unknown", None),
    ],
)
def test_source_age_and_unknown_policy(
    service, record_data, clock, kind, age, policy, want, threshold
):
    saved = service.execute(
        CreateRecord(**record_data),
        key=str(uuid4()),
        epoch=str(service.store.health().api_epoch),
    ).saved_records[0]
    source_time = None if age is None else clock.now() - timedelta(seconds=age)
    provenance = SourceProvenance(
        kind=kind,
        source_mode="live",
        observed_at=source_time if kind == "observed" else None,
        predicted_at=source_time if kind == "modeled" else None,
        source_ref=SourceReference(producer_id="fixture"),
    )
    derived = saved.model_copy(update={"provenance": provenance})
    result = freshness(derived, as_of=clock.now(), policies=policy)
    assert result == {
        "status": want,
        "threshold_seconds": threshold,
        "as_of": "2026-10-17T16:00:00.000000Z",
    }
    assert saved.provenance.observed_at is None


@pytest.mark.parametrize("metadata", ["[]", "null", "17", '"malformed"'])
def test_non_object_planning_metadata_preserves_saved_current_and_history(
    api, record_data, metadata
):
    from app.mission import storage

    key = str(uuid4())
    created = create(api, record_data, key)
    first = created.json()["saved_records"][0]
    path = BASE + "/records/" + first["record_id"]
    edited = api.put(
        path, json=dict(record_data, expected_version=1), headers=headers(api)
    )
    second = edited.json()["saved_records"][0]
    service = api.app.state.operator_runtime.service
    stored_history = service.history(first["record_id"]).items
    storage.get_mission_file_path("demo-mission").write_text(metadata)

    for read_path, expected_records in (
        (path, [second]),
        (BASE + "/records?mission_id=demo-mission", [second]),
        (path + "/history", [first, second]),
        (BASE + "/journal?mission_id=demo-mission", [first, second]),
    ):
        result = api.get(read_path)
        assert result.status_code == 200
        body = result.json()
        envelopes = body.get("items", [body])
        assert [item["record"] for item in envelopes] == expected_records
        assert all(
            item["association"]
            == {
                "status": "unknown",
                "unresolved_fields": [],
                "error_code": "planning_unavailable",
            }
            for item in envelopes
        )
        assert result.headers["Cache-Control"] == "no-store"

    assert service.get(first["record_id"]).model_dump(mode="json") == second
    assert service.history(first["record_id"]).items == stored_history
    replay = create(api, record_data, key)
    assert replay.json() == created.json()
    assert replay.headers["Idempotency-Replayed"] == "true"
