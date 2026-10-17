"""Freshness uses source time and a known producer policy, never acceptance."""

from datetime import timedelta
from uuid import uuid4

import pytest

from app.operator.models import CreateRecord
from app.operator.provenance import SourceProvenance, SourceReference
from app.operator.read_metadata import freshness


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
