"""Independent fixture expectations and customer meaning, without source leakage."""

import importlib

from app.mission.exporter.trial_projection import project_trial_leg
from tests.unit.customer_briefing_fixtures import fixture, snapshot, utc


def view(captured, trial=None):
    name = "app.mission.exporter.customer_view"
    assert importlib.util.find_spec(name), "customer presentation contract is absent"
    return importlib.import_module(name).project_customer_leg(
        captured, trial or project_trial_leg(captured), leg_number=1, leg_count=1
    )


def test_checkpoint_pair_has_independent_assessment_and_known_risks():
    for name in ("composition-assessed", "composition-incomplete-x"):
        captured = snapshot(fixture(name))
        leg = project_trial_leg(captured)
        result = view(captured, leg)
        assert result.intervals is leg.intervals
        assert leg.utc_bounds == (
            utc("2026-10-25T14:00:00Z"),
            utc("2026-10-25T22:00:00Z"),
        )
        assert {
            (r.start_time, r.end_time) for i in leg.intervals for r in i.restrictions
        } == {
            (utc("2026-10-25T14:00:00Z"), utc("2026-10-25T14:15:00Z")),
            (utc("2026-10-25T21:45:00Z"), utc("2026-10-25T22:00:00Z")),
        }
        if name.endswith("assessed"):
            assert not any(d.value == "?" for i in leg.intervals for d in i.decisions)
            assert {i.posture for i in leg.intervals} == {
                "Nominal",
                "Degraded",
                "Limited / elevated risk",
                "Communications unavailable",
            }
            outage = [
                i for i in leg.intervals if i.posture == "Communications unavailable"
            ]
            assert len(outage) == 1
            assert (outage[0].start_time, outage[0].end_time) == (
                utc("2026-10-25T16:25:00Z"),
                utc("2026-10-25T16:30:00Z"),
            )
        else:
            assert all(i.decisions[2].value == "?" for i in leg.intervals)
            assert all(i.posture == "Posture uncertain" for i in leg.intervals)
            assert any(
                i.decisions[0].value == i.decisions[1].value == "Down"
                for i in leg.intervals
            )


def test_customer_view_groups_equivalent_adjacent_sources():
    data = fixture("composition-assessed")
    risk = next(r for r in data["source_records"] if r["source_id"] == "risk-Ka")
    risk["end_time"] = "2026-10-25T16:10:00Z"
    data["source_records"].append(
        {
            **risk,
            "source_id": "risk-Ka-other",
            "start_time": "2026-10-25T16:10:00Z",
            "end_time": "2026-10-25T17:00:00Z",
        }
    )
    captured = snapshot(data)
    trial = project_trial_leg(captured)
    result = view(captured, trial)
    row = next(r for r in result.rows if r.start_time == utc("2026-10-25T16:00:00Z"))
    assert row.end_time == utc("2026-10-25T16:15:00Z")
    assert len(row.interval_ids) == 2
    assert {"risk-Ka", "risk-Ka-other"} <= set(row.source_ids)
    assert not any(r.start_time == utc("2026-10-25T14:15:00Z") for r in result.rows)
    assert "Commercial Ka unavailable" in row.impact
    assert not any(
        token in repr(result.rows)
        for token in ("PRIVATE", "abcdef123", "rule-17", "Window ")
    )


def test_unknown_x_has_one_notice_and_keeps_known_outages():
    captured = snapshot(fixture("composition-incomplete-x"))
    result = view(captured)
    assert (
        result.notice
        == "X-Band planning incomplete — confirmed transport capability shown below."
    )
    assert len(result.rows) == 5  # SOF twice; Ka, overlap, Ka recovery.
    assert all(r.posture == "Assessment incomplete" for r in result.rows)
    assert any(r.remaining == "Starshield confirmed" for r in result.rows)
    assert any(r.remaining == "No transport confirmed available" for r in result.rows)
    assert not any("Communications unavailable" in r.posture for r in result.rows)


def test_endpoint_pair_and_single_name_fallback():
    data = fixture("composition-assessed")
    captured = snapshot(data)
    result = view(captured)
    assert result.title == "LEG 1 OF 1 — KADW → PAED"
    assert result.subtitle == "Washington, DC → Anchorage, AK"
    assert result.timing_label == "DEP 10:00 ET | ARR 18:00 ET | 8h 00m"
    assert result.date_label == "25 Oct 2026"
    leg = data["mission"]["legs"][0]
    leg.pop("departure_airport")
    leg.pop("arrival_airport")
    data["route"]["points"][0].pop("name")
    data["route"]["points"][-1].pop("name")
    result = view(snapshot(data))
    assert result.title == "LEG 1 OF 1 — Northern mission"
    assert "→" not in result.title
    leg["name"] = ""
    assert view(snapshot(data)).title == "LEG 1 OF 1 — Leg 1"


def test_checkpoint_oct25_eight_hours_and_nested_outages():
    data = fixture("composition-assessed")
    assert data["utc_bounds"] == ["2026-10-25T14:00:00Z", "2026-10-25T22:00:00Z"]
    result = view(snapshot(data))
    assert result.title == "LEG 1 OF 1 — KADW → PAED"
    assert result.date_label == "25 Oct 2026"
    assert result.timing_label == "DEP 10:00 ET | ARR 18:00 ET | 8h 00m"
    outage = [i for i in result.intervals if i.posture == "Communications unavailable"]
    assert len(outage) == 1
    assert (outage[0].start_time, outage[0].end_time) == (
        utc("2026-10-25T16:25:00Z"),
        utc("2026-10-25T16:30:00Z"),
    )


def test_checkpoint_incomplete_x_keeps_confirmed_risks():
    result = view(snapshot(fixture("composition-incomplete-x")))
    assert all(i.decisions[2].value == "?" for i in result.intervals)
    assert any(r.remaining == "Starshield confirmed" for r in result.rows)
    assert any(r.remaining == "No transport confirmed available" for r in result.rows)


def test_customer_grouping_ignores_internal_rule_identity():
    from dataclasses import replace

    captured = snapshot(fixture("composition-assessed"))
    trial = project_trial_leg(captured)
    first = next(
        i for i in trial.intervals if i.start_time == utc("2026-10-25T16:00:00Z")
    )
    left = replace(first, end_time=utc("2026-10-25T16:10:00Z"))
    right = replace(
        first,
        id="internal-new",
        start_time=left.end_time,
        decisions=tuple(replace(d, rule_id="internal-churn") for d in first.decisions),
    )
    split = replace(
        trial,
        intervals=tuple(
            sorted(
                tuple(i for i in trial.intervals if i is not first) + (left, right),
                key=lambda i: i.start_time,
            )
        ),
    )
    row = next(r for r in view(captured, split).rows if r.start_time == left.start_time)
    assert row.end_time == first.end_time
    assert len(row.interval_ids) == 2


def test_customer_uncertainty_change_without_outage_is_material():
    from dataclasses import replace

    captured = snapshot(fixture("composition-assessed"))
    trial = project_trial_leg(captured)
    nominal = next(
        i for i in trial.intervals if not i.restrictions and i.posture == "Nominal"
    )
    changed = replace(
        nominal,
        decisions=tuple(
            (
                replace(d, value="?", limitation="Prerequisites unavailable")
                if n == 2
                else d
            )
            for n, d in enumerate(nominal.decisions)
        ),
        posture="Posture uncertain",
    )
    trial = replace(
        trial, intervals=tuple(changed if i is nominal else i for i in trial.intervals)
    )
    row = next(
        r for r in view(captured, trial).rows if r.start_time == changed.start_time
    )
    assert row.posture == "Assessment incomplete"
    assert row.remaining == "Ka + Starshield confirmed"
    assert row.end_time == changed.end_time
