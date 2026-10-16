"""Captured continuity drives call posture without changing physical lanes."""

import json
from dataclasses import replace
from datetime import timedelta

import pytest

from app.mission.exporter.customer_document import build_customer_document
from app.mission.exporter.customer_evidence import _leg_records
from app.mission.exporter.customer_projection import project_briefing_leg
from app.mission.exporter.customer_view import project_customer_leg
from app.mission.exporter.snapshot_inputs import canonical_json
from app.services.pop.continuity import project_call_continuity
from app.services.pop.continuity_models import CapabilitySpan
from app.services.pop.models import PopForecast
from tests.unit.customer_briefing_fixtures import fixture, snapshot
from tests.unit.test_customer_document import inputs
from tests.unit.test_customer_pop import forecast


def captured_projection(
    ka="unavailable", x="unavailable", fallback=False, partial=False
):
    captured, _, _ = inputs()
    leg = snapshot(fixture("f01"))
    start, end = leg.utc_bounds
    raw = json.loads(leg.timeline_json)
    raw["pop_forecast"] = forecast(
        [("one", start + timedelta(minutes=30)), ("two", start + timedelta(minutes=30))]
    )
    edge = start + timedelta(minutes=30) if partial else end
    spans = [
        CapabilitySpan(
            start_utc=start,
            end_utc=edge,
            ka=ka,
            x=x,
            starshield="available",
            x_concurrency_only=fallback,
            source_ids=("captured-source",),
        )
    ]
    if partial:
        spans.append(
            CapabilitySpan(
                start_utc=edge, end_utc=end, ka="available", x=x, starshield="available"
            )
        )
    continuity = project_call_continuity(
        PopForecast.model_validate(raw["pop_forecast"]),
        spans,
        start_utc=start,
        end_utc=end,
    )
    raw["call_continuity"] = continuity.model_dump(mode="json")
    raw["pop_advisories"] = [{"kind": "mismatch"}]
    leg = replace(leg, timeline_json=canonical_json(raw))
    captured = replace(captured, legs=(leg,))
    projection = project_briefing_leg(leg)
    view = project_customer_leg(leg, projection, leg_number=1, leg_count=1)
    return captured, projection, view, continuity


@pytest.mark.parametrize(
    "ka,x,fallback,classification",
    [
        ("unavailable", "unavailable", False, "planned_outage"),
        ("available", "unavailable", False, "advisory"),
        ("unavailable", "available", False, "advisory"),
        ("unavailable", "unavailable", True, "x_fallback"),
        ("unknown", "unknown", False, "unknown"),
    ],
)
def test_customer_consumes_shared_classification(ka, x, fallback, classification):
    captured, projection, view, continuity = captured_projection(ka, x, fallback)
    active = [i for i in projection.intervals if i.pop_transition_ids]
    assert all(i.call_classification == classification for i in active)
    assert all(i.decisions[1].value == "Up" for i in active)
    assert projection.call_continuity == continuity
    payload = build_customer_document(captured, view, projection)
    assert payload["callContinuity"] == continuity.model_dump(mode="json")
    rows = [r for r in payload["rows"] if r["popTransitionIds"]]
    if classification == "planned_outage":
        assert all(
            r["posture"] == "Communications unavailable"
            and r["remaining"] == "No secure-call transport"
            for r in rows
        )
    elif classification == "x_fallback":
        assert all(r["remaining"] == "Planned X-Band fallback" for r in rows)
        assert all(r["impact"] == "Starshield Transition Window" for r in rows)
    elif classification == "unknown":
        assert all(
            r["posture"] == "Assessment incomplete"
            and r["remaining"] == "Call continuity unresolved"
            for r in rows
        )
    evidence = _leg_records(captured.legs[0], projection, view)
    assert evidence["canonical"]["callContinuity"] == payload["callContinuity"]
    assert all(
        i["callClassification"] == classification
        for i in evidence["canonical"]["intervals"]
        if i["popTransitionIds"]
    )
    assert "mismatch" not in json.dumps(payload)


def test_partial_alternative_return_splits_rows_with_unchanged_full_marker_and_totals():
    captured, projection, view, continuity = captured_projection(partial=True)
    rows = [r for r in view.rows if r.pop_transition_ids]
    assert len(rows) == 2
    assert rows[0].posture == "Communications unavailable"
    assert rows[1].posture != "Communications unavailable"
    assert rows[0].end_time == rows[1].start_time
    assert continuity.pop_call_outage_seconds == 300
    assert continuity.planned_communications_outage_seconds == 300
    assert rows[0].pop_transition_ids == rows[1].pop_transition_ids == ("one", "two")
    assert build_customer_document(captured, view, projection)["popTransitions"][0][
        "windowEndUtc"
    ].endswith("08:35:00Z")


def test_csv_uses_captured_call_intervals_without_mutating_physical_states():
    import csv
    import io

    from app.mission.exporter.__main__ import generate_csv_export
    from app.mission.exporter.snapshot_views import SnapshotViews

    captured, _, _, continuity = captured_projection(partial=True)
    from app.mission.exporter.snapshot_inputs import SourcePayload

    captured = replace(
        captured, source_payloads=(SourcePayload("ground_entry", b"null"),)
    )
    timeline = SnapshotViews(captured).timeline(captured.legs[0].leg_id)
    original = timeline.model_dump_json()
    rows = list(
        csv.DictReader(
            io.StringIO(
                generate_csv_export(
                    timeline,
                    SnapshotViews(captured).leg(captured.legs[0].leg_id),
                    export_snapshot=captured,
                ).decode()
            )
        )
    )
    active = [r for r in rows if r["Call Continuity"] == "planned_outage"]
    assert active[0]["Call Interval Start UTC"] == "2026-10-07T08:25:00Z"
    assert active[0]["Call Interval End UTC"] == "2026-10-07T08:30:00Z"
    assert active and all(
        r["Call Posture"] == "Communications unavailable" for r in active
    )
    assert all(r["StarShield"] == "AVAILABLE" for r in active)
    assert all(r["Planned Communications Outage Seconds"] == "300.0" for r in rows)
    assert timeline.model_dump_json() == original
    assert continuity.pop_call_outage_seconds == 300


@pytest.mark.parametrize("change", ["missing", "revision", "gapped"])
def test_unaligned_captured_continuity_never_claims_nominal(change):
    captured, _, _, _ = captured_projection()
    leg = captured.legs[0]
    raw = json.loads(leg.timeline_json)
    if change == "missing":
        raw.pop("call_continuity")
    elif change == "revision":
        raw["call_continuity"]["revision"] = "obsolete"
    else:
        raw["call_continuity"]["intervals"].pop(0)
    leg = replace(leg, timeline_json=canonical_json(raw))
    projection = project_briefing_leg(leg)
    view = project_customer_leg(leg, projection, leg_number=1, leg_count=1)
    assert projection.call_continuity is None
    assert all(
        r.posture == "Assessment incomplete" for r in view.rows if r.pop_transition_ids
    )


def test_immutable_capture_reuses_continuity_for_document_csv_and_evidence():
    captured, projection, view, _ = captured_projection()
    before = captured.legs[0].timeline_json
    payload = build_customer_document(captured, view, projection)
    payload["callContinuity"]["intervals"][0]["source_ids"].append("mutated")
    assert captured.legs[0].timeline_json == before
    assert "mutated" not in json.dumps(
        build_customer_document(captured, view, projection)
    )


@pytest.mark.parametrize("hard", [None, "x_ar_cone", "x_elevation", "manual:1"])
def test_customer_consumes_real_policy_extractor_without_releasing_hard_blocks(hard):
    from app.mission.models import MissionLegTimeline
    from app.mission.pop_continuity import attach_call_continuity

    captured, _, _, _ = captured_projection()
    leg = captured.legs[0]
    raw = json.loads(leg.timeline_json)
    segment = raw["segments"][0]
    constraints = ["x_aft_cone"] + ([hard] if hard else [])
    segment.update(ka_state="offline", x_state="offline", ku_state="available")
    segment["metadata"] = {
        "planning_policy": "prefer_starshield_v1",
        "transport_constraints": {"X": constraints},
        "planning_interval": {
            "start_time": segment["start_time"],
            "end_time": segment["end_time"],
            "physical_x_state": "degraded" if hard else "available",
            "physical_ka_state": "offline",
            "physical_ku_state": "available",
            "policy_x_state": "offline",
            "policy_ku_state": "available",
            "policy_ka_state": "offline",
            "raw_constraints": constraints,
            "physical_reasons": [],
            "policy_reasons": [],
        },
    }
    timeline = MissionLegTimeline.model_validate(raw)
    original = timeline.segments[0].model_dump_json()
    attach_call_continuity(timeline)
    leg = replace(leg, timeline_json=canonical_json(timeline.model_dump(mode="json")))
    projection = project_briefing_leg(leg)
    view = project_customer_leg(leg, projection, leg_number=1, leg_count=1)
    rows = [r for r in view.rows if r.pop_transition_ids]
    assert all(
        r.call_classification == ("planned_outage" if hard else "x_fallback")
        for r in rows
    )
    assert timeline.segments[0].model_dump_json() == original
    assert projection.call_continuity.pop_call_outage_seconds == (600 if hard else 0)


def test_csv_absent_projection_reports_unresolved_instead_of_zero():
    from app.mission.exporter.csv_continuity import apply_csv_continuity
    from app.mission.models import MissionLegTimeline

    captured, _, _, _ = captured_projection()
    raw = json.loads(captured.legs[0].timeline_json)
    raw.pop("call_continuity")
    timeline = MissionLegTimeline.model_validate(raw)
    apply_csv_continuity(timeline)
    for segment in timeline.segments:
        assert segment.metadata["call_posture"] == "Call continuity unresolved"
        assert (
            segment.metadata["call_continuity_csv"][
                "Planned Communications Outage Seconds"
            ]
            == "Unresolved"
        )


def test_unavailable_forecast_cannot_leave_a_nominal_call_hero():
    captured, _, _, _ = captured_projection()
    leg = captured.legs[0]
    raw = json.loads(leg.timeline_json)
    raw["pop_forecast"].update(
        status="unavailable", reason="Captured timing unavailable", transitions=[]
    )
    raw["call_continuity"] = None
    projection = project_briefing_leg(replace(leg, timeline_json=canonical_json(raw)))
    assert all(i.posture == "Posture uncertain" for i in projection.intervals)
