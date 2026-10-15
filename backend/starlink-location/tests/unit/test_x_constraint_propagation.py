"""Invented geometry regressions for independently changing X constraints."""

from datetime import datetime, timedelta, timezone

import pytest

from app.mission.call_availability import normalize_call_availability_timeline
from app.mission.models import (
    MissionLeg,
    MissionLegTimeline,
    TimelineSegment,
    TimelineStatus,
    Transport,
    TransportConfig,
    TransportState,
)
from app.mission.state import generate_transport_intervals
from app.mission.timeline import assemble_mission_timeline
from app.mission.timeline_builder.aar import ResolvedAARWindow
from app.mission.timeline_builder.coverage import RouteSample
from app.mission.timeline_builder.events import apply_x_azimuth_events
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
from app.satellites.catalog import Satellite, SatelliteCatalog
from app.satellites.rules import RuleEngine

START = datetime(2035, 1, 1, tzinfo=timezone.utc)


def at(minute):
    return START + timedelta(minutes=minute)


def segment_at(timeline, minute):
    return next(s for s in timeline.segments if s.start_time <= at(minute) < s.end_time)


@pytest.mark.parametrize(
    "angles,ar_window,expected",
    [
        (
            [(90, 20), (180, 20), (180, 5), (180, 5), (180, 20), (90, 20)],
            None,
            [
                "available",
                "available",
                "degraded",
                "degraded",
                "available",
                "available",
            ],
        ),
        (
            [(90, 20), (180, 20), (0, 20), (0, 20), (180, 20), (90, 20)],
            (20, 40),
            [
                "available",
                "available",
                "degraded",
                "degraded",
                "available",
                "available",
            ],
        ),
        (
            [(180, 5), (90, 5), (0, 5), (0, 20), (90, 20), (180, 20)],
            (20, 35),
            ["degraded", "degraded", "degraded", "degraded", "available", "available"],
        ),
        (
            [(180, 5), (180, 20), (90, 20), (90, 20), (90, 20), (90, 20)],
            None,
            [
                "degraded",
                "available",
                "available",
                "available",
                "available",
                "available",
            ],
        ),
    ],
    ids=[
        "advisory-elevation-advisory",
        "advisory-ar-advisory",
        "independent-clears",
        "elevation-clears-first",
    ],
)
def test_constraint_changes_survive_active_violation_union(
    monkeypatch, angles, ar_window, expected
):
    timeline, _ = build_constraint_timeline(monkeypatch, angles, ar_window)
    assert [
        segment_at(timeline, i * 10 + 1).x_state.value for i in range(6)
    ] == expected
    for i, (_, elevation) in enumerate(angles):
        if elevation < 10:
            assert any(
                "line-of-sight blocked" in reason
                for reason in segment_at(timeline, i * 10 + 1).metadata[
                    "source_reasons"
                ]
            )


def build_constraint_timeline(
    monkeypatch, angles, ar_window=None, configure=None, assignments=None
):
    catalog = SatelliteCatalog()
    catalog.add_satellite(Satellite("X-invented", "X", longitude=0))
    catalog.add_satellite(Satellite("X-other-invented", "X", longitude=1))
    monkeypatch.setattr("app.satellites.catalog._catalog", catalog)
    # Replace only look-angle geometry; event generation, reducer and normalization are real.
    monkeypatch.setattr(
        "app.satellites.rules.look_angles", lambda lat, lon, alt, sat: angles[int(lon)]
    )
    samples = [RouteSample(i * 1000, at(i * 10), 0, i, 10000, 0) for i in range(6)]
    route = ParsedRoute(
        metadata=RouteMetadata(
            name="Invented", file_path="invented.kml", point_count=2
        ),
        points=[RoutePoint(latitude=0, longitude=i, sequence=i) for i in (0, 1)],
    )
    leg = MissionLeg(
        id="invented",
        name="Invented",
        route_id="invented-route",
        transports=TransportConfig(initial_x_satellite_id="X-invented"),
    )
    windows = (
        [ResolvedAARWindow("Invented AR", at(ar_window[0]), at(ar_window[1]))]
        if ar_window
        else []
    )
    engine = RuleEngine()
    if configure:
        configure(engine)
    apply_x_azimuth_events(
        engine, leg, route, samples, windows, assignments or [], None, START, at(60)
    )
    timeline = assemble_mission_timeline(
        "invented",
        START,
        at(60),
        generate_transport_intervals(engine.events, START, at(60)),
    )
    normalize_call_availability_timeline(timeline)
    return timeline, engine


@pytest.mark.parametrize(
    "reason,ka_state,want_x",
    [
        (
            "X line-of-sight blocked (Invented, elevation 5° < min 10°)",
            "available",
            "degraded",
        ),
        ("Manual AR Track: Invented", "available", "degraded"),
        ("X-AAR Conflict az=0° el=20°", "available", "degraded"),
        ("X Transition to Invented", "available", "degraded"),
        ("Ka coverage lost (Invented)", "degraded", "available"),
        ("Ka transition Invented-A → Invented-B", "degraded", "available"),
    ],
)
def test_legacy_mixed_reasons_preserve_only_actual_x_restrictions(
    reason, ka_state, want_x
):
    segment = TimelineSegment(
        id="invented",
        start_time=START,
        end_time=at(10),
        status=TimelineStatus.DEGRADED,
        x_state=TransportState.DEGRADED,
        ka_state=TransportState(ka_state),
        ku_state=TransportState.AVAILABLE,
        reasons=["X-Ku Conflict az=180° el=20°", reason],
    )
    timeline = MissionLegTimeline(mission_leg_id="invented", segments=[segment])
    normalize_call_availability_timeline(timeline)
    assert timeline.segments[0].x_state.value == want_x
    if reason.startswith("Ka coverage"):
        assert "Satellite swap" not in timeline.segments[0].metadata["primary_reason"]


def test_typed_constraints_override_advisory_wording_and_survive_renormalization():
    segment = TimelineSegment(
        id="invented",
        start_time=START,
        end_time=at(10),
        status=TimelineStatus.DEGRADED,
        x_state=TransportState.DEGRADED,
        ka_state=TransportState.AVAILABLE,
        ku_state=TransportState.AVAILABLE,
        reasons=["X-Ku Conflict", "Restriction with renamed display text"],
        metadata={"transport_constraints": {"X": ["x_aft_cone", "x_elevation"]}},
    )
    timeline = MissionLegTimeline(mission_leg_id="invented", segments=[segment])
    normalize_call_availability_timeline(timeline)
    normalize_call_availability_timeline(timeline)
    assert timeline.segments[0].x_state == TransportState.DEGRADED
    assert timeline.segments[0].metadata["transport_constraints"]["X"] == [
        "x_aft_cone",
        "x_elevation",
    ]


def test_manual_track_clears_without_erasing_remaining_elevation(monkeypatch):
    timeline, _ = build_constraint_timeline(
        monkeypatch,
        [(180, 20), (180, 20), (180, 5), (180, 5), (180, 20), (90, 20)],
        configure=lambda engine: engine.add_manual_aar_track_events(
            at(15), at(25), "invented-track", "Invented"
        ),
    )
    assert [
        segment_at(timeline, minute).x_state.value for minute in [11, 16, 21, 26, 41]
    ] == ["available", "degraded", "degraded", "degraded", "available"]
    assert any(
        "Manual AR Track" in r
        for r in segment_at(timeline, 16).metadata["source_reasons"]
    )
    assert all(
        "Manual AR Track" not in r
        for r in segment_at(timeline, 26).metadata["source_reasons"]
    )


def test_satellite_change_refreshes_restriction_without_clearing_handover(monkeypatch):
    timeline, engine = build_constraint_timeline(
        monkeypatch,
        [(180, 20), (180, 20), (180, 5), (180, 5), (180, 20), (180, 20)],
        configure=lambda engine: engine.add_x_transition_events(
            at(30), "X-other-invented"
        ),
        assignments=[(START, "X-invented", None), (at(30), "X-other-invented", None)],
    )
    assert [
        segment_at(timeline, minute).x_state.value
        for minute in [11, 16, 21, 31, 41, 46]
    ] == ["available", "degraded", "degraded", "degraded", "degraded", "available"]
    reasons = segment_at(timeline, 31).metadata["source_reasons"]
    assert any("X-other-invented, elevation" in r for r in reasons)
    assert all("X-invented, elevation" not in r for r in reasons)
    assert any(
        e.timestamp == at(30)
        and e.metadata.get("constraint") == "x_elevation"
        and e.satellite_id == "X-other-invented"
        for e in engine.events
    )


def test_mixed_typed_and_legacy_segments_do_not_lose_hard_constraint_on_second_pass():
    advisory = TimelineSegment(
        id="advisory",
        start_time=START,
        end_time=at(10),
        status=TimelineStatus.DEGRADED,
        x_state=TransportState.DEGRADED,
        ka_state=TransportState.AVAILABLE,
        ku_state=TransportState.AVAILABLE,
        reasons=["X-Ku Conflict"],
        metadata={"transport_constraints": {"X": ["x_aft_cone"]}},
    )
    hard = advisory.model_copy(
        update={"id": "hard", "reasons": ["X line-of-sight blocked"], "metadata": {}}
    )
    timeline = MissionLegTimeline(mission_leg_id="invented", segments=[advisory, hard])
    normalize_call_availability_timeline(timeline)
    normalize_call_availability_timeline(timeline)
    assert timeline.segments[0].x_state == TransportState.DEGRADED


def test_elevation_clears_without_erasing_remaining_manual_track(monkeypatch):
    timeline, _ = build_constraint_timeline(
        monkeypatch,
        [(180, 20), (180, 20), (180, 5), (180, 20), (180, 20), (90, 20)],
        configure=lambda engine: engine.add_manual_aar_track_events(
            at(15), at(35), "invented-track", "Invented"
        ),
    )
    assert [
        segment_at(timeline, minute).x_state.value for minute in [11, 16, 21, 31, 36]
    ] == ["available", "degraded", "degraded", "degraded", "available"]
    assert all(
        "line-of-sight blocked" not in r
        for r in segment_at(timeline, 31).metadata["source_reasons"]
    )


def test_legacy_azimuth_events_retain_ordinary_advisory_policy():
    from app.satellites.rules import EventType, MissionEvent

    events = [
        MissionEvent(
            START, EventType.X_AZIMUTH_VIOLATION, Transport.X, reason="X-Ku Conflict"
        )
    ]
    timeline = assemble_mission_timeline(
        "invented", START, at(10), generate_transport_intervals(events, START, at(10))
    )
    normalize_call_availability_timeline(timeline)
    assert timeline.segments[0].x_state == TransportState.AVAILABLE


def test_legacy_advisory_cannot_erase_renamed_typed_hard_constraint_on_second_pass():
    hard = TimelineSegment(
        id="hard",
        start_time=START,
        end_time=at(10),
        status=TimelineStatus.DEGRADED,
        x_state=TransportState.DEGRADED,
        ka_state=TransportState.AVAILABLE,
        ku_state=TransportState.AVAILABLE,
        reasons=["Renamed display text"],
        metadata={"transport_constraints": {"X": ["x_elevation"]}},
    )
    advisory = hard.model_copy(
        update={"id": "advisory", "reasons": ["X-Ku Conflict"], "metadata": {}}
    )
    timeline = MissionLegTimeline(mission_leg_id="invented", segments=[advisory, hard])
    normalize_call_availability_timeline(timeline)
    normalize_call_availability_timeline(timeline)
    assert timeline.segments[0].x_state == TransportState.DEGRADED


def test_ka_only_loss_with_x_advisory_is_single_transport_degradation(monkeypatch):
    from app.mission.timeline_builder.stats import attach_statistics
    from app.satellites.rules import EventType, MissionEvent

    def ka_loss(engine):
        engine.events.extend(
            [
                MissionEvent(
                    at(15),
                    EventType.KA_COVERAGE_EXIT,
                    Transport.KA,
                    reason="Ka coverage lost (Invented)",
                ),
                MissionEvent(
                    at(35),
                    EventType.KA_COVERAGE_ENTRY,
                    Transport.KA,
                    severity="info",
                    reason="Ka coverage restored (Invented)",
                ),
            ]
        )

    timeline, _ = build_constraint_timeline(
        monkeypatch, [(180, 20)] * 6, configure=ka_loss
    )
    attach_statistics(timeline, START, at(60))
    assert all(s.x_state == TransportState.AVAILABLE for s in timeline.segments)
    assert segment_at(timeline, 21).status == TimelineStatus.DEGRADED
    assert timeline.statistics["critical_seconds"] == 0
    assert timeline.statistics["degraded_seconds"] == 1200
