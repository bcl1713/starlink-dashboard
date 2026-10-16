"""Advisory partitions preserve canonical availability and UTC evidence."""

import json
from dataclasses import replace
from datetime import timedelta

from app.mission.exporter.customer_document import build_customer_document
from app.mission.exporter.customer_evidence import _leg_records
from app.mission.exporter.customer_projection import project_briefing_leg
from app.mission.exporter.customer_view import project_customer_leg
from app.mission.exporter.snapshot_inputs import canonical_json
from tests.unit.customer_briefing_fixtures import fixture, snapshot, utc
from tests.unit.test_customer_document import inputs

EVENT = "Starshield Transition Window"


def forecast(centers):
    return {
        "revision": "captured-planning",
        "catalog_fingerprint": "captured-catalog",
        "status": "ready",
        "transitions": [
            {
                "crossing": {
                    "id": identity,
                    "from_pop_id": "a",
                    "to_pop_id": "b",
                    "segment_index": 0,
                    "fraction": 0.5,
                    "latitude": 0,
                    "longitude": 1,
                    "distance_meters": 10,
                },
                "crossing_utc": center.isoformat(),
                "window_start_utc": (center - timedelta(minutes=5)).isoformat(),
                "window_end_utc": (center + timedelta(minutes=5)).isoformat(),
            }
            for identity, center in centers
        ],
    }


def with_forecast(captured, centers):
    leg = captured.legs[0]
    timeline = json.loads(leg.timeline_json)
    timeline["pop_forecast"] = forecast(centers)
    # Unrelated aircraft state must never be presented in this planning document.
    timeline["pop_advisories"] = [{"kind": "mismatch", "observed_pop_id": "live"}]
    leg = replace(leg, timeline_json=canonical_json(timeline))
    captured = replace(captured, legs=(leg,))
    projection = project_briefing_leg(leg)
    view = project_customer_leg(leg, projection, leg_number=1, leg_count=1)
    return captured, projection, view


def test_missing_continuity_partitions_simultaneous_occurrences_without_inventing_nominal():
    data = fixture("f01")
    captured, _, _ = inputs()
    leg = snapshot(data)
    captured = replace(captured, legs=(leg,))
    start, end = leg.utc_bounds
    captured, projection, view = with_forecast(
        captured,
        [
            ("one", start + timedelta(minutes=30)),
            ("two", start + timedelta(minutes=35)),
            ("three", start + timedelta(minutes=35)),
        ],
    )
    pop = [i for i in projection.intervals if i.pop_transition_ids]
    assert [i.pop_transition_ids for i in pop] == [
        ("one",),
        ("one", "two", "three"),
        ("two", "three"),
    ]
    assert all(
        i.posture == "Posture uncertain" and i.decisions[1].value == "Up" for i in pop
    )
    assert projection.intervals[0].start_time == start
    assert projection.intervals[-1].end_time == end
    assert all(
        a.end_time == b.start_time
        for a, b in zip(projection.intervals, projection.intervals[1:])
    )
    rows = [r for r in view.rows if r.pop_transition_ids]
    assert len(rows) == 3
    assert all(
        r.impact == EVENT
        and r.remaining == "Call continuity unresolved"
        and r.posture == "Assessment incomplete"
        for r in rows
    )
    assert len({i.id for i in projection.intervals}) == len(projection.intervals)


def test_advisory_overlap_retains_outage_sof_and_full_unclipped_evidence():
    captured, _, _ = inputs()
    start, end = captured.legs[0].utc_bounds
    captured, projection, view = with_forecast(
        captured,
        [
            ("departure", start),
            ("outage", utc("2026-10-25T16:27:00Z")),
            ("arrival", end),
        ],
    )
    payload = build_customer_document(captured, view, projection)
    transitions = payload["popTransitions"]
    assert transitions[0]["windowStartUtc"] == "2026-10-25T13:55:00Z"
    assert transitions[-1]["windowEndUtc"] == "2026-10-25T22:05:00Z"
    both = [r for r in payload["rows"] if "outage" in r["popTransitionIds"]]
    assert any("unavailable" in r["impact"] and EVENT in r["impact"] for r in both)
    assert any("SOF" in r["impact"] and EVENT in r["impact"] for r in payload["rows"])
    evidence = _leg_records(captured.legs[0], projection, view)
    assert (
        evidence["canonical"]["popForecast"]["catalog_fingerprint"]
        == "captured-catalog"
    )
    assert "mismatch" not in json.dumps(payload)
    assert all(start <= i.start_time < i.end_time <= end for i in projection.intervals)


def test_old_customer_payload_is_empty_and_dst_display_keeps_clock_identity():
    from app.mission.exporter.customer_display import display_row

    captured, projection, view = inputs()
    assert build_customer_document(captured, view, projection)["popTransitions"] == []
    cells = display_row(
        {
            "et": "01:55 EDT–01:05 EST",
            "impact": EVENT,
            "remaining": "Starshield",
            "posture": "Nominal",
        }
    )
    assert cells[0] == "01:55 - 01:05"
    from app.mission.exporter.briefing_clocks import format_clocks
    from app.mission.exporter.customer_clocks import format_customer_range

    a, b = utc("2026-11-01T05:55:00Z"), utc("2026-11-01T06:05:00Z")
    clock = format_customer_range(a, b, a)
    assert clock.start == "01:55 EDT" and clock.end == "01:05 EST"
    assert format_clocks(a, a).et.endswith("01:55 EDT")
    assert format_clocks(b, a).et.endswith("01:05 EST")


def test_sanitized_dst_fixture_retains_both_impacts_and_canonical_bounds():
    data = fixture("pop-coordination")
    captured, _, _ = inputs()
    leg = snapshot(data)
    captured = replace(captured, legs=(leg,))
    projection = project_briefing_leg(leg)
    view = project_customer_leg(leg, projection, leg_number=1, leg_count=1)
    payload = build_customer_document(captured, view, projection)
    evidence = _leg_records(leg, projection, view)
    both = [
        r for r in payload["rows"] if r["popTransitionIds"] == ["fold-one", "fold-two"]
    ]
    assert len(both) == 3
    overlap = both[1]
    assert "Takeoff SOF" in overlap["impact"]
    assert "Commercial Ka unavailable" in overlap["impact"]
    assert EVENT in overlap["impact"]
    assert overlap["posture"] == "Assessment incomplete"
    assert overlap["remaining"] == "Call continuity unresolved"
    assert overlap["et"] == "01:58 EDT–01:02 EST"
    assert overlap["displayCells"][0] == "01:58 - 01:02"
    record = next(r for r in evidence["customerRows"] if r["id"] == overlap["id"])
    assert record["startUtc"] == "2026-11-01T05:58:00Z"
    assert record["endUtc"] == "2026-11-01T06:02:00Z"
    assert record["clock"]["start"].endswith("EDT")
    assert record["clock"]["end"].endswith("EST")
    assert payload["popTransitions"][0]["windowStartUtc"] == "2026-11-01T04:55:00Z"
    assert payload["popTransitions"][-1]["windowEndUtc"] == "2026-11-01T11:05:00Z"
