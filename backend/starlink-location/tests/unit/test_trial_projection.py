"""Trial interpretation stays independent of legacy call-posture normalization."""

import json
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta

import pytest

from app.mission.models import Transport, TransportState
from tests.unit.customer_briefing_fixtures import fixture, snapshot, utc


def evidence(kind, transport="X", reason="", **metadata):
    from app.mission.exporter.trial_projection import SourceRecord

    return SourceRecord(
        source_id=kind,
        leg_id="leg",
        transport=Transport(transport),
        source_type=kind,
        reason=reason,
        metadata_json=json.dumps(metadata, sort_keys=True).encode(),
    )


@pytest.mark.parametrize(
    "state, sources, expected",
    [
        ("available", [], "Up"),
        ("offline", [], "Down"),
        (None, [], "?"),
        ("degraded", [], "?"),
        ("degraded", [("ka_coverage_exit", "Ka", "Ka coverage lost", {})], "Down"),
        ("degraded", [("condition", "Ka", "ka_no_coverage", {})], "Down"),
        (
            "degraded",
            [("x_azimuth_violation", "X", "blocked", {"line_of_sight_blocked": True})],
            "Down",
        ),
        (
            "available",
            [("x_azimuth_violation", "X", "blocked", {"elevation_below_min": True})],
            "Down",
        ),
        (
            "degraded",
            [("x_azimuth_violation", "X", "X-Ku Conflict az=180° el=35°", {})],
            "Up",
        ),
        (
            "available",
            [("x_azimuth_violation", "X", "X-Ku Conflict az=180° el=35°", {})],
            "Up",
        ),
        ("degraded", [("x_transition_start", "X", "transition", {})], "?"),
        ("degraded", [("manual_aar_track_start", "X", "Manual AR Track", {})], "?"),
        ("degraded", [("x_azimuth_violation", "X", "X-AAR Conflict", {})], "?"),
        ("degraded", [("x_azimuth_violation", "X", "X azimuth conflict", {})], "?"),
        ("degraded", [("ka_transition", "Ka", "Ka transition", {})], "?"),
        (
            "available",
            [("availability_basis", "Ka", "", {"prerequisites_available": False})],
            "?",
        ),
        (
            "available",
            [("availability_basis", "X", "", {"prerequisites_available": False})],
            "?",
        ),
        ("available", [("unrecognized", "X", "new warning", {})], "?"),
        (
            "available",
            [
                ("x_azimuth_violation", "X", "X-Ku Conflict", {}),
                ("x_transition_start", "X", "transition", {}),
            ],
            "?",
        ),
        (
            "degraded",
            [
                ("x_azimuth_violation", "X", "X-Ku Conflict", {}),
                (
                    "x_azimuth_violation",
                    "X",
                    "blocked",
                    {"line_of_sight_blocked": True},
                ),
            ],
            "Down",
        ),
        ("offline", [("x_transition_start", "X", "transition", {})], "Down"),
        (
            "degraded",
            [
                ("ka_transition", "Ka", "transition", {}),
                (
                    "transport_state",
                    "Ka",
                    "verified usable",
                    {"independent_usability": "Up"},
                ),
            ],
            "Up",
        ),
    ],
)
def test_reason_specific_usability(state, sources, expected):
    from app.mission.exporter.trial_projection import classify_transport

    records = tuple(
        evidence(kind, transport, reason, **meta)
        for kind, transport, reason, meta in sources
    )
    decision = classify_transport(TransportState(state) if state else None, records)
    assert decision.value == expected
    assert decision.rule_id
    assert set(decision.source_ids) == {s.source_id for s in records}
    if any("X-Ku" in s.reason for s in records):
        assert decision.limitation  # Text is preserved even when lane is plain Up.


def contiguous(leg):
    start, end = leg.utc_bounds
    assert leg.intervals[0].start_time == start
    assert leg.intervals[-1].end_time == end
    assert all(i.start_time < i.end_time for i in leg.intervals)
    assert all(
        a.end_time == b.start_time for a, b in zip(leg.intervals, leg.intervals[1:])
    )
    assert [i.window_number for i in leg.intervals] == list(
        range(1, len(leg.intervals) + 1)
    )
    for row in leg.coordination_rows:
        assert row is leg.intervals[row.window_number - 1]


def test_quiet_nominal_only_standard_sof():
    from app.mission.exporter.trial_projection import project_trial_leg

    data = fixture("f01")
    leg = project_trial_leg(snapshot(data))
    contiguous(leg)
    assert all(i.posture == "Nominal" for i in leg.intervals)
    assert [
        (
            i.start_time.strftime("%H:%M:%S"),
            i.end_time.strftime("%H:%M:%S"),
            i.window_number,
        )
        for i in leg.coordination_rows
    ] == [tuple(r) for r in data["expected"]["rows"]]
    assert (
        leg.quiet_summary
        == "No communications degradation or coordination windows beyond standard SOF restrictions identified for this leg."
    )
    assert "re-export" in leg.planned_departure_basis.lower()
    assert "prediction" in leg.prediction_caveat.lower()


def test_nested_outages_partition_and_filtered_ids():
    from app.mission.exporter.trial_projection import project_trial_leg

    data = fixture("f02")
    leg = project_trial_leg(snapshot(data))
    contiguous(leg)
    rows = [
        (
            i.start_time.strftime("%H:%M:%S"),
            i.end_time.strftime("%H:%M:%S"),
            i.window_number,
        )
        for i in leg.coordination_rows
    ]
    assert rows == [tuple(r) for r in data["expected"]["rows"]]
    assert [i.id for i in leg.coordination_rows] == [
        f"f02-window-{n:03d}" for n in (1, 2, 3, 4, 5, 7)
    ]
    for t, seconds in data["expected"]["down_seconds"].items():
        lane = ("Ka", "Ku", "X").index(t)
        assert (
            sum(
                (i.end_time - i.start_time).total_seconds()
                for i in leg.intervals
                if i.decisions[lane].value == "Down"
            )
            == seconds
        )
    overlap = leg.intervals[3]
    assert overlap.posture == "Limited / elevated risk"
    assert overlap.remaining_transports == ("Starshield",)
    assert "ka-long" in overlap.active_source_ids
    assert any("line-of-sight" in c for c in overlap.causes)
    assert "sof-takeoff" in leg.intervals[1].active_source_ids
    source = next(s for s in leg.sources if s.source_id == "ka-long")
    assert (source.start_time, source.end_time) == (
        utc("2026-10-07T08:10:00Z"),
        utc("2026-10-07T12:15:00Z"),
    )
    assert source.source_digest and source.source_revision
    nested = project_trial_leg(snapshot(fixture("f02_ar")))
    contiguous(nested)
    ar = next(i for i in nested.intervals if "ar-nested" in i.active_source_ids)
    assert (ar.start_time, ar.end_time) == (
        utc("2026-10-07T10:00:00Z"),
        utc("2026-10-07T10:30:00Z"),
    )
    assert "ka-long" in ar.active_source_ids and len(ar.causes) >= 3
    assert ar.posture == "Limited / elevated risk"


def test_half_open_brief_outage_and_short_sof():
    from app.mission.exporter.trial_projection import project_trial_leg

    leg = project_trial_leg(snapshot(fixture("f03")))
    contiguous(leg)
    red = [i for i in leg.intervals if i.posture == "Communications unavailable"]
    assert len(red) == 1
    assert (red[0].start_time, red[0].end_time) == (
        utc("2026-10-07T09:00:00Z"),
        utc("2026-10-07T09:00:30Z"),
    )
    assert "ka-b" in red[0].active_source_ids and "ka-a" not in red[0].active_source_ids
    assert red[0] in leg.coordination_rows
    assert red[0].remaining_transports == ()
    after = next(i for i in leg.intervals if i.start_time == red[0].end_time)
    assert after.posture == "Degraded" and after.remaining_transports == (
        "Starshield",
        "X-Band MILSATCOM",
    )
    short = project_trial_leg(snapshot(fixture("f04")))
    contiguous(short)
    assert all(i.posture == "Nominal" for i in short.intervals)
    assert (
        sum(
            (i.end_time - i.start_time).total_seconds()
            for i in short.intervals
            if i.restrictions
        )
        == 1200
    )
    overlap = next(
        i for i in short.intervals if i.start_time == utc("2026-10-07T08:08:00Z")
    )
    assert {r.source_id for r in overlap.restrictions} == {
        "sof-takeoff",
        "sof-landing",
        "ar-short",
    }
    assert {r.label for r in overlap.restrictions} >= {
        "Safety-of-Flight (takeoff)",
        "Safety-of-Flight (landing)",
    }


def test_resolved_ar_and_missing_timing_note():
    from app.mission.exporter.trial_projection import project_trial_leg
    from app.mission.models import MissionLeg
    from app.mission.timeline_builder.aar import resolve_aar_windows
    from app.mission.timeline_builder.calculator import RouteTemporalProjector
    from app.models.route import ParsedRoute

    data = fixture("f05")
    route = ParsedRoute.model_validate(data["route"])
    bounds = [utc(v) for v in data["utc_bounds"]]
    resolved = resolve_aar_windows(
        MissionLeg.model_validate(data["mission"]["legs"][0]),
        route,
        RouteTemporalProjector(route, *bounds),
    )
    assert {
        w.name: [w.start_time.strftime("%H:%M:%S"), w.end_time.strftime("%H:%M:%S")]
        for w in resolved
    } == data["expected"]
    leg = project_trial_leg(snapshot(data))
    contiguous(leg)
    assert all(i.posture == "Nominal" for i in leg.intervals)
    assert any(
        "ar-unresolved" in note and "timing" in note.lower() for note in leg.notes
    )
    assert all("ar-unresolved" not in i.active_source_ids for i in leg.intervals)
    for identity, times in data["expected"].items():
        rows = [i for i in leg.coordination_rows if identity in i.active_source_ids]
        assert rows[0].start_time.strftime("%H:%M:%S") == times[0]
        assert rows[-1].end_time.strftime("%H:%M:%S") == times[1]
    assert any(s.source_id == "ar-unresolved" for s in leg.sources)


def test_two_down_plus_unknown_and_concurrency_materiality():
    from app.mission.exporter.trial_projection import project_trial_leg

    leg = project_trial_leg(snapshot(fixture("f06")))
    contiguous(leg)
    pure = next(i for i in leg.intervals if i.start_time == utc("2026-10-07T08:20:00Z"))
    assert pure.decisions[2].value == "Up" and pure.posture == "Nominal"
    assert pure.limitations and pure in leg.coordination_rows
    mixed = next(
        i for i in leg.intervals if i.start_time == utc("2026-10-07T08:40:00Z")
    )
    assert [d.value for d in mixed.decisions] == ["Down", "Down", "?"]
    assert mixed.posture == "Posture uncertain" and mixed.remaining_transports == ()
    assert any(s.source_id == "transition-saved" for s in leg.sources)
    assert leg.quiet_summary is None


def test_missing_stale_and_uncovered_evidence_never_verified_nominal():
    from app.mission.exporter.trial_projection import project_trial_leg

    data = fixture("f10")
    leg = project_trial_leg(snapshot(data))
    assert all(i.posture == "Posture uncertain" for i in leg.intervals)
    assert leg.quiet_summary is None
    assert any(s.source_type == "cached_segment" for s in leg.sources)
    # Shift current departure but retain all original cached timestamps.
    data["utc_bounds"] = ["2026-10-07T10:00:00Z", "2026-10-07T16:00:00Z"]
    shifted = project_trial_leg(snapshot(data))
    contiguous(shifted)
    assert all(i.posture == "Posture uncertain" for i in shifted.intervals)
    source = next(s for s in shifted.sources if s.source_type == "cached_segment")
    assert source.start_time == utc("2026-10-07T08:00:00Z")
    assert any("cached" in n.lower() for n in shifted.notes)
    missing = replace(
        snapshot(data), utc_bounds=None, effective_route_json=None, timeline_json=None
    )
    incomplete = project_trial_leg(missing)
    assert incomplete.utc_bounds is None and incomplete.intervals == ()
    assert incomplete.quiet_summary is None
    assert any("timing" in n.lower() for n in incomplete.notes)
    data = fixture("f01")
    data["source_records"][0]["end_time"] = "2026-10-07T10:00:00Z"
    data["timeline"]["segments"][0]["end_time"] = "2026-10-07T10:00:00Z"
    partial = project_trial_leg(snapshot(data))
    contiguous(partial)
    assert all(
        i.posture == "Posture uncertain"
        for i in partial.intervals
        if i.start_time >= utc("2026-10-07T10:00:00Z")
    )


def test_unsplit_outside_flight_source_and_immutable_result():
    from app.mission.exporter.trial_projection import project_trial_leg

    data = fixture("f02")
    data["mission"]["legs"][0]["transports"]["ka_outages"][0].update(
        start_time="2026-10-07T07:00:00Z", duration_seconds=8 * 3600
    )
    original = snapshot(data)
    leg = project_trial_leg(original)
    source = next(s for s in leg.sources if s.source_id == "ka-long")
    assert (source.start_time, source.end_time) == (
        utc("2026-10-07T07:00:00Z"),
        utc("2026-10-07T15:00:00Z"),
    )
    assert project_trial_leg(original) == leg
    with pytest.raises(FrozenInstanceError):
        leg.intervals[0].posture = "Nominal"
    assert all(isinstance(s.metadata_json, bytes) for s in leg.sources)


def test_internal_informational_events_do_not_fragment_primary_windows():
    from app.mission.exporter.trial_projection import project_trial_leg

    data = fixture("f01")
    data["source_records"].append(
        {
            "timestamp": "2026-10-07T10:00:00Z",
            "event_type": "minor_telemetry",
            "transport": "Ka",
            "severity": "info",
            "reason": "Minor detail",
            "metadata": {},
        }
    )
    leg = project_trial_leg(snapshot(data))
    assert len(leg.intervals) == 3
    assert any(s.reason == "Minor detail" for s in leg.sources)


@pytest.mark.parametrize("available", [True, False])
def test_manual_ar_selected_splice_applicability(export_inputs, available):
    from app.mission import storage
    from app.mission.exporter.snapshot import capture_export_snapshot
    from app.mission.exporter.trial_projection import project_trial_leg
    from app.mission.models import (
        ManualAARTrack,
        ManualAARTrackPoint,
        ManualRouteSplice,
    )

    mission, routes, pois, _ = export_inputs
    leg = mission.legs[0]
    leg.transports.manual_aar_tracks = [
        ManualAARTrack(
            id="track-saved",
            name="Saved track",
            points=[
                ManualAARTrackPoint(latitude=0.3 if available else 70, longitude=0.01),
                ManualAARTrackPoint(latitude=0.7 if available else 71, longitude=0.01),
            ],
        )
    ]
    leg.transports.manual_route_splice = ManualRouteSplice(
        enabled_track_id="track-saved", speed_knots=100
    )
    storage.save_mission_v2(mission)
    captured = capture_export_snapshot("m", routes, pois).legs[0]
    trial = project_trial_leg(captured)
    assert (
        any("track-saved" in i.active_source_ids for i in trial.intervals) is available
    )
    assert any(s.source_id == "track-saved" for s in trial.sources)
    if not available:
        assert any(
            "track-saved" in n and "unavailable" in n.lower() for n in trial.notes
        )


@pytest.mark.parametrize("missing", ["coverage", "geometry"])
def test_capture_records_missing_transport_prerequisites(
    export_inputs, monkeypatch, missing
):
    from app.mission.exporter import snapshot as module
    from app.mission.exporter.trial_projection import project_trial_leg

    _, routes, pois, catalog = export_inputs
    if missing == "coverage":
        monkeypatch.setattr(module, "captured_coverage", lambda _: None)
    else:
        catalog.satellites.clear()
    captured = module.capture_export_snapshot("m", routes, pois).legs[0]
    assert captured.preparation_origin == "rebuilt"
    trial = project_trial_leg(captured)
    lane = 0 if missing == "coverage" else 2
    assert all(i.decisions[lane].value == "?" for i in trial.intervals)
    assert all(i.posture == "Posture uncertain" for i in trial.intervals)


def test_configured_sof_reuses_captured_buffers(export_inputs, monkeypatch):
    from app.mission.exporter import snapshot as module
    from app.mission.exporter.trial_projection import project_trial_leg
    from app.satellites.rules import ConstraintConfig

    monkeypatch.setattr(
        "app.mission.exporter.snapshot_inputs.ConstraintConfig",
        lambda: ConstraintConfig(takeoff_buffer_minutes=7, landing_buffer_minutes=9),
    )
    _, routes, pois, _ = export_inputs
    trial = project_trial_leg(module.capture_export_snapshot("m", routes, pois).legs[0])
    takeoff = [
        i
        for i in trial.intervals
        if any(r.source_id == "sof-takeoff" for r in i.restrictions)
    ]
    landing = [
        i
        for i in trial.intervals
        if any(r.source_id == "sof-landing" for r in i.restrictions)
    ]
    assert takeoff[-1].end_time - takeoff[0].start_time == timedelta(minutes=7)
    assert landing[-1].end_time - landing[0].start_time == timedelta(minutes=9)


def test_cached_unambiguous_sources_and_stale_basis():
    from app.mission.exporter.trial_projection import project_trial_leg

    data = fixture("f10")
    segment = data["timeline"]["segments"][0]
    segment["metadata"]["source_reasons"] = [
        "Ka coverage lost (AOR)",
        "X line-of-sight blocked (X-fixture, elevation 0.0° < min 10.0°)",
    ]
    leg = project_trial_leg(snapshot(data))
    assert all(
        [d.value for d in i.decisions] == ["Down", "?", "Down"] for i in leg.intervals
    )
    assert all(i.posture == "Posture uncertain" for i in leg.intervals)
    # Even overlapping stale sources must not be asserted as current outage.
    data["utc_bounds"] = ["2026-10-07T10:00:00Z", "2026-10-07T16:00:00Z"]
    stale = project_trial_leg(snapshot(data))
    assert all(
        [d.value for d in i.decisions] == ["?", "?", "?"] for i in stale.intervals
    )
    assert any(
        s.source_type == "cached_segment"
        and s.start_time == utc("2026-10-07T08:00:00Z")
        for s in stale.sources
    )
    data["utc_bounds"] = ["2026-10-07T08:00:00Z", "2026-10-07T14:00:00Z"]
    data["mission"]["legs"][0]["updated_at"] = "2026-10-07T15:00:00Z"
    stale_revision = project_trial_leg(snapshot(data))
    assert all(
        [d.value for d in i.decisions] == ["?", "?", "?"]
        for i in stale_revision.intervals
    )


def test_saved_transition_id_and_zero_duration_events(export_inputs, monkeypatch):
    from app.mission import storage
    from app.mission.exporter.snapshot import capture_export_snapshot
    from app.mission.exporter.trial_projection import project_trial_leg
    from app.mission.models import XTransition
    from app.satellites.rules import ConstraintConfig

    mission, routes, pois, _ = export_inputs
    mission.legs[0].transports.x_transitions = [
        XTransition(
            id="transition-live-id",
            latitude=0.5,
            longitude=0,
            target_satellite_id="X-test",
        )
    ]
    storage.save_mission_v2(mission)
    leg = project_trial_leg(capture_export_snapshot("m", routes, pois).legs[0])
    active = [i for i in leg.intervals if "transition-live-id" in i.active_source_ids]
    assert active and any("Transition" in c for i in active for c in i.causes)
    monkeypatch.setattr(
        "app.mission.exporter.snapshot_inputs.ConstraintConfig",
        lambda: ConstraintConfig(transition_buffer_minutes=0),
    )
    zero = project_trial_leg(capture_export_snapshot("m", routes, pois).legs[0])
    assert all("transition-live-id" not in i.active_source_ids for i in zero.intervals)


def test_nested_same_transport_outages_keep_union_and_ids():
    from app.mission.exporter.trial_projection import project_trial_leg

    data = fixture("f02")
    data["mission"]["legs"][0]["transports"]["ka_outages"].append(
        {
            "id": "nested-ka",
            "start_time": "2026-10-07T10:00:00Z",
            "duration_seconds": 600,
        }
    )
    leg = project_trial_leg(snapshot(data))
    nested = next(
        i for i in leg.intervals if i.start_time == utc("2026-10-07T10:00:00Z")
    )
    assert {"ka-long", "nested-ka"}.issubset(nested.active_source_ids)
    assert (
        sum(
            (i.end_time - i.start_time).total_seconds()
            for i in leg.intervals
            if i.decisions[0].value == "Down"
        )
        == 14700
    )


def test_uncovered_predictions_cannot_prove_geometry_outage():
    from app.mission.exporter.trial_projection import project_trial_leg

    data = fixture("f02")
    data["timeline"]["segments"][0]["end_time"] = "2026-10-07T10:00:00Z"
    leg = project_trial_leg(snapshot(data))
    interval = next(
        i for i in leg.intervals if i.start_time == utc("2026-10-07T10:00:00Z")
    )
    assert [d.value for d in interval.decisions] == ["Down", "?", "?"]
    assert interval.posture == "Posture uncertain"


@pytest.mark.parametrize("normalized_state", ["available", "degraded"])
def test_cached_concurrency_requires_no_conflicting_x_reason(normalized_state):
    from app.mission.exporter.trial_projection import project_trial_leg

    data = fixture("f10")
    segment = data["timeline"]["segments"][0]
    segment["x_state"] = "available"  # Normalizer's usable X-Ku semantics.
    segment["metadata"]["source_reasons"] = ["X-Ku Conflict az=180° el=35°"]
    leg = project_trial_leg(snapshot(data))
    assert all(i.decisions[2].value == "Up" and i.limitations for i in leg.intervals)
    assert all(i.posture == "Posture uncertain" for i in leg.intervals)
    segment["x_state"] = normalized_state
    segment["metadata"]["source_reasons"].append("Unexpected X warning")
    ambiguous = project_trial_leg(snapshot(data))
    assert all(i.decisions[2].value == "?" for i in ambiguous.intervals)


@pytest.mark.parametrize("state", ["available", "offline"])
def test_stale_evidence_cannot_verify_transport(state):
    from app.mission.exporter.trial_projection import classify_transport

    decision = classify_transport(
        TransportState(state),
        (evidence("transport_state", "X", "Old prediction", stale=True),),
    )
    assert decision.value == "?"


def test_cached_fallback_retains_current_configured_sof(export_inputs, monkeypatch):
    from app.mission import storage, timeline_preparation
    from app.mission.exporter.snapshot import capture_export_snapshot
    from app.mission.exporter.trial_projection import project_trial_leg

    mission, routes, pois, _ = export_inputs
    old = timeline_preparation.prepare_mission_timeline(
        mission.legs[0], routes, pois
    ).timeline
    storage.save_mission_timeline("l", old, "m")
    mission.legs[0].adjusted_departure_time = utc("2026-10-07T10:00:00Z")
    storage.save_mission_v2(mission)

    def failed(*args, **kwargs):
        raise RuntimeError("Rebuild unavailable")

    monkeypatch.setattr(
        "app.mission.exporter.snapshot.prepare_mission_timeline", failed
    )
    trial = project_trial_leg(capture_export_snapshot("m", routes, pois).legs[0])
    sof = {
        r.source_id: (r.start_time, r.end_time)
        for i in trial.intervals
        for r in i.restrictions
    }
    assert sof == {
        "sof-takeoff": (utc("2026-10-07T10:00:00Z"), utc("2026-10-07T10:15:00Z")),
        "sof-landing": (utc("2026-10-07T10:45:00Z"), utc("2026-10-07T11:00:00Z")),
    }
    assert all(i.posture == "Posture uncertain" for i in trial.intervals)
    assert any("ar" in n and "timing" in n.lower() for n in trial.notes)


# Register an existing real capture fixture under a local name.
@pytest.fixture
def export_inputs(request):
    from tests.unit.test_export_snapshot import export_inputs as capture_fixture

    return capture_fixture.__wrapped__(
        request.getfixturevalue("tmp_path"), request.getfixturevalue("monkeypatch")
    )


def test_independent_x_clear_keeps_other_constraint_active():
    """dev's aft clear must not clear an independently active elevation outage."""
    from app.mission.exporter.trial_projection import project_trial_leg

    data = fixture("composition-assessed")
    data["source_records"] = [
        r for r in data["source_records"] if r["source_type"] == "availability_basis"
    ]
    for identity, minute, constraint, active in (
        ("aft-start", "16:00", "x_aft_cone", True),
        ("elevation-start", "16:15", "x_elevation", True),
        ("aft-clear", "16:30", "x_aft_cone", False),
        ("elevation-clear", "16:45", "x_elevation", False),
    ):
        data["source_records"].append(
            {
                "source_id": identity,
                "source_type": "x_azimuth_violation",
                "transport": "X",
                "timestamp": "2026-10-25T" + minute + ":00Z",
                "severity": "warning" if active else "info",
                "reason": (
                    "X-Ku Conflict"
                    if constraint == "x_aft_cone" and active
                    else "Geometry condition"
                ),
                "metadata": {
                    "constraint": constraint,
                    "line_of_sight_blocked": constraint == "x_elevation" and active,
                },
            }
        )
    leg = project_trial_leg(snapshot(data))
    middle = next(
        i
        for i in leg.intervals
        if i.start_time <= utc("2026-10-25T16:35:00Z") < i.end_time
    )
    assert middle.decisions[2].value == "Down"
    assert "elevation-start" in middle.active_source_ids
    assert "aft-start" not in middle.active_source_ids
    restored = next(
        i
        for i in leg.intervals
        if i.start_time <= utc("2026-10-25T16:50:00Z") < i.end_time
    )
    assert restored.decisions[2].value == "Up"
