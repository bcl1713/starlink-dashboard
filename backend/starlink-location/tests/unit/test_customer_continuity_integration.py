"""Call projection preserves proven outages and stable customer row boundaries."""

import json
from dataclasses import replace
from datetime import timedelta

import pytest

from app.mission.exporter.customer_projection import project_briefing_leg
from app.mission.exporter.customer_view import project_customer_leg
from app.mission.exporter.snapshot_inputs import canonical_json
from app.services.pop.continuity import project_call_continuity
from app.services.pop.continuity_models import CapabilitySpan
from app.services.pop.models import PopForecast
from tests.unit.customer_briefing_fixtures import fixture, snapshot
from tests.unit.test_customer_continuity import captured_projection


def test_customer_rows_union_continuity_source_churn_without_splitting_outage():
    captured, _, _, _ = captured_projection()
    leg = captured.legs[0]
    start, end = leg.utc_bounds
    cut = start + timedelta(minutes=30)
    raw = json.loads(leg.timeline_json)
    continuity = project_call_continuity(
        PopForecast.model_validate(raw["pop_forecast"]),
        tuple(
            CapabilitySpan(
                start_utc=a,
                end_utc=b,
                ka="unavailable",
                x="unavailable",
                starshield="available",
                source_ids=(identity,),
            )
            for a, b, identity in [(start, cut, "call-a"), (cut, end, "call-b")]
        ),
        start_utc=start,
        end_utc=end,
    )
    raw["call_continuity"] = continuity.model_dump(mode="json")
    leg = replace(leg, timeline_json=canonical_json(raw))
    projection = project_briefing_leg(leg)
    view = project_customer_leg(leg, projection, leg_number=1, leg_count=1)
    rows = [r for r in view.rows if r.pop_transition_ids]
    assert [(r.start_time, r.end_time) for r in rows] == [
        (start + timedelta(minutes=25), start + timedelta(minutes=35))
    ]
    assert rows[0].call_classification == "planned_outage"
    assert rows[0].pop_transition_ids == ("one", "two")
    assert {"call-a", "call-b"} <= set(rows[0].source_ids)
    assert len(rows[0].interval_ids) == 2


@pytest.mark.parametrize(
    "scenario,expected",
    [("composition-assessed", True), ("composition-incomplete-x", False)],
)
def test_missing_continuity_keeps_only_independently_proven_outages(scenario, expected):
    leg = snapshot(fixture(scenario))
    projection = project_briefing_leg(leg)
    existing = [
        i for i in projection.intervals if i.call_classification == "existing_outage"
    ]
    assert bool(existing) is expected
    assert all(
        i.posture == "Communications unavailable" and not i.remaining_transports
        for i in existing
    )
    assert all(all(d.value == "Down" for d in i.decisions) for i in existing)
    assert all(
        i.call_classification == "unknown" and i.posture == "Posture uncertain"
        for i in projection.intervals
        if i not in existing
    )


@pytest.mark.parametrize("ka", ["unknown", "available"])
def test_confirmed_outage_survives_unknown_captured_call_evidence(ka):
    captured, _, _, _ = captured_projection(ka=ka, x="unknown")
    leg = captured.legs[0]
    start, _ = leg.utc_bounds
    a, b = start + timedelta(minutes=27), start + timedelta(minutes=32)
    sources = tuple(
        canonical_json(
            {
                "source_id": f"hard-{t}",
                "source_type": "configured_outage",
                "transport": t,
                "state": "offline",
                "start_time": a.isoformat(),
                "end_time": b.isoformat(),
                "reason": "Known independent outage",
            }
        )
        for t in ("Ka", "Ku", "X")
    )
    leg = replace(leg, source_records=leg.source_records + sources)
    projection = project_briefing_leg(leg)
    existing = next(i for i in projection.intervals if i.start_time == a)
    assert existing.call_classification == "existing_outage"
    assert existing.posture == "Communications unavailable"
    assert existing.call_alternatives == ()
    assert {"hard-Ka", "hard-Ku", "hard-X"} <= set(existing.call_source_ids)


def test_equal_advisory_classifications_keep_different_usable_alternative_boundaries():
    captured, _, _, _ = captured_projection()
    leg = captured.legs[0]
    start, end = leg.utc_bounds
    cut = start + timedelta(minutes=30)
    raw = json.loads(leg.timeline_json)
    continuity = project_call_continuity(
        PopForecast.model_validate(raw["pop_forecast"]),
        (
            CapabilitySpan(
                start_utc=start,
                end_utc=cut,
                ka="available",
                x="unavailable",
                starshield="available",
                source_ids=("ka-source",),
            ),
            CapabilitySpan(
                start_utc=cut,
                end_utc=end,
                ka="unavailable",
                x="available",
                starshield="available",
                source_ids=("x-source",),
            ),
        ),
        start_utc=start,
        end_utc=end,
    )
    raw["call_continuity"] = continuity.model_dump(mode="json")
    leg = replace(leg, timeline_json=canonical_json(raw))
    projection = project_briefing_leg(leg)
    view = project_customer_leg(leg, projection, leg_number=1, leg_count=1)
    rows = [r for r in view.rows if r.pop_transition_ids]
    assert [(r.start_time, r.end_time) for r in rows] == [
        (start + timedelta(minutes=25), cut),
        (cut, start + timedelta(minutes=35)),
    ]
    assert {r.call_classification for r in rows} == {"advisory"}
    assert "ka-source" in rows[0].source_ids
    assert "x-source" in rows[1].source_ids
