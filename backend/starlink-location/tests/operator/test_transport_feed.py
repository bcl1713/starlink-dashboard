"""Review is pinned to the very same capture/H as the existing event feed."""

from tests.operator.api_helpers import BASE, create
from tests.operator.test_call_api import call_data
from tests.operator.test_transport_contract import decision, row


def test_transport_review_pinned_during_pagination(api, record_data):
    for _ in range(3):
        assert create(api, call_data(record_data)).status_code == 201
    assert (
        create(api, decision(record_data, row(applied={"transport": "Ka"}))).status_code
        == 201
    )
    first = api.get(
        BASE + "/events", params={"mission_id": "demo-mission", "limit": 1}
    ).json()
    assert first["transport_review"]["H"] == first["H"] == 4
    assert first["transport_review"]["actual_routing"] == "unknown"
    assert (
        create(
            api, decision(record_data, row(requested={"transport": "X"}))
        ).status_code
        == 201
    )
    second = api.get(
        BASE + "/events",
        params={"mission_id": "demo-mission", "limit": 1, "cursor": first["cursor"]},
    ).json()
    assert second["transport_review"] == first["transport_review"]


def test_review_capture_called_once_and_no_decision_writes(
    production, clock, monkeypatch
):
    from app.operator.event_feed import build_snapshot
    from tests.operator.test_production_live_timing import runtime_for

    runtime, adapter = runtime_for(production, clock)
    calls = []
    capture = adapter.capture

    def wrapped(*args, **kwargs):
        calls.append(1)
        return capture(*args, **kwargs)

    monkeypatch.setattr(adapter, "capture", wrapped)
    with adapter.service.store.connect() as db:
        before = db.execute("SELECT count(*) FROM revisions").fetchone()[0]
    snapshot = build_snapshot(runtime, "demo-mission", adapter)
    assert len(calls) == 1
    assert snapshot.transport_review.H == snapshot.H
    with adapter.service.store.connect() as db:
        assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == before
