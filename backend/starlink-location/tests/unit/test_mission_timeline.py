"""Tests for mission timeline segment assembly."""

# FR-004: The shared segment and timing fixtures make this contract suite cohesive
# despite its size; the sampler concurrency regression belongs with them.

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from app.mission import timeline_service
from app.mission.call_availability import normalize_call_availability_timeline
from app.mission.models import (
    AARWindow,
    MissionLeg,
    MissionLegTimeline,
    TimelineSegment,
    TimelineStatus,
    Transport,
    TransportConfig,
    TransportState,
)
from app.mission.state import TransportInterval
from app.mission.timeline import build_timeline_segments
from app.mission.timeline_builder.aar import parse_elapsed_offset, resolve_aar_windows
from app.mission.timeline_builder.stats import annotate_aar_markers
from app.satellites.rules import EventType, MissionEvent

BASE = datetime(2025, 10, 27, 12, 0, tzinfo=timezone.utc)


def _interval(transport, start_offset, end_offset, state, reasons=None):
    start = BASE + timedelta(minutes=start_offset)
    end = BASE + timedelta(minutes=end_offset) if end_offset is not None else None
    return TransportInterval(
        transport=transport,
        state=state,
        start=start,
        end=end,
        reasons=reasons or [],
    )


def test_nominal_segment_generation():
    """Single nominal interval should produce one nominal segment."""
    intervals = {
        Transport.X: [_interval(Transport.X, 0, 60, TransportState.AVAILABLE)],
        Transport.KA: [_interval(Transport.KA, 0, 60, TransportState.AVAILABLE)],
        Transport.KU: [_interval(Transport.KU, 0, 60, TransportState.AVAILABLE)],
    }

    segments = build_timeline_segments(
        mission_id="mission-1",
        mission_start=BASE,
        mission_end=BASE + timedelta(minutes=60),
        intervals=intervals,
    )

    assert len(segments) == 1
    assert segments[0].status == TimelineStatus.NOMINAL
    assert segments[0].reasons == []
    assert segments[0].impacted_transports == []


def test_degraded_and_critical_segments():
    """Mixed transport states should create degraded and critical segments."""
    intervals = {
        Transport.X: [
            _interval(Transport.X, 0, 20, TransportState.AVAILABLE),
            _interval(
                Transport.X,
                20,
                40,
                TransportState.DEGRADED,
                reasons=["X transition"],
            ),
            _interval(Transport.X, 40, 60, TransportState.AVAILABLE),
        ],
        Transport.KA: [
            _interval(Transport.KA, 0, 30, TransportState.AVAILABLE),
            _interval(
                Transport.KA,
                30,
                60,
                TransportState.OFFLINE,
                reasons=["Ka outage"],
            ),
        ],
        Transport.KU: [
            _interval(Transport.KU, 0, 60, TransportState.AVAILABLE),
        ],
    }

    segments = build_timeline_segments(
        mission_id="mission-1",
        mission_start=BASE,
        mission_end=BASE + timedelta(minutes=60),
        intervals=intervals,
    )

    statuses = [segment.status for segment in segments]
    assert statuses == [
        TimelineStatus.NOMINAL,
        TimelineStatus.DEGRADED,
        TimelineStatus.CRITICAL,
        TimelineStatus.DEGRADED,
    ]

    degraded_segment = segments[1]
    assert Transport.X in degraded_segment.impacted_transports
    assert degraded_segment.reasons == ["X transition"]

    critical_segment = segments[2]
    assert set(critical_segment.impacted_transports) == {Transport.X, Transport.KA}
    assert "Ka outage" in critical_segment.reasons


def test_segment_boundaries_clamped():
    """Segment boundaries should honor mission start/end range."""
    intervals = {
        Transport.X: [
            _interval(
                Transport.X,
                -10,
                10,
                TransportState.DEGRADED,
                reasons=["Pre-start transition"],
            ),
            _interval(Transport.X, 10, 70, TransportState.AVAILABLE),
        ],
    }

    mission_start = BASE
    mission_end = BASE + timedelta(minutes=60)
    segments = build_timeline_segments(
        mission_id="mission-1",
        mission_start=mission_start,
        mission_end=mission_end,
        intervals=intervals,
    )

    assert segments[0].start_time == mission_start
    assert segments[-1].end_time == mission_end
    assert segments[0].status == TimelineStatus.DEGRADED


def test_annotate_aar_markers_appends_reasons():
    """AAR start/end markers should show up in timeline segment reasons."""
    segments = [
        TimelineSegment(
            id="seg-1",
            start_time=BASE,
            end_time=BASE + timedelta(minutes=30),
            status=TimelineStatus.NOMINAL,
            x_state=TransportState.AVAILABLE,
            ka_state=TransportState.AVAILABLE,
            ku_state=TransportState.AVAILABLE,
            reasons=[],
            impacted_transports=[],
            metadata={},
        ),
        TimelineSegment(
            id="seg-2",
            start_time=BASE + timedelta(minutes=30),
            end_time=BASE + timedelta(minutes=60),
            status=TimelineStatus.NOMINAL,
            x_state=TransportState.AVAILABLE,
            ka_state=TransportState.AVAILABLE,
            ku_state=TransportState.AVAILABLE,
            reasons=[],
            impacted_transports=[],
            metadata={},
        ),
    ]
    timeline = MissionLegTimeline(
        mission_leg_id="mission-1",
        segments=segments,
        advisories=[],
        statistics={},
    )
    events = [
        MissionEvent(
            timestamp=BASE + timedelta(minutes=10),
            event_type=EventType.AAR_WINDOW,
            transport=Transport.X,
            affected_transport=Transport.X,
            severity="warning",
            reason="AAR Start",
        ),
        MissionEvent(
            timestamp=BASE + timedelta(minutes=45),
            event_type=EventType.AAR_WINDOW,
            transport=Transport.X,
            affected_transport=Transport.X,
            severity="info",
            reason="AAR End",
        ),
    ]

    annotate_aar_markers(timeline, events)

    blocks = timeline.statistics.get("_aar_blocks")
    assert blocks is not None
    assert len(blocks) == 1
    block = blocks[0]
    expected_start = (BASE + timedelta(minutes=10)).isoformat()
    expected_end = (BASE + timedelta(minutes=45)).isoformat()
    assert block["start"] == expected_start
    assert block["end"] == expected_end


def _timeline_from_segments(segments, statistics=None):
    return MissionLegTimeline(
        mission_leg_id="mission-1",
        segments=segments,
        advisories=[],
        statistics=statistics or {},
    )


def _segment(seg_id, start_offset, end_offset, status, reasons=None, metadata=None):
    return TimelineSegment(
        id=seg_id,
        start_time=BASE + timedelta(minutes=start_offset),
        end_time=BASE + timedelta(minutes=end_offset),
        status=status,
        x_state=TransportState.AVAILABLE,
        ka_state=TransportState.AVAILABLE,
        ku_state=TransportState.AVAILABLE,
        reasons=reasons or [],
        impacted_transports=[],
        metadata=metadata or {},
    )


def test_call_availability_aar_advisory_carves_hole_without_degrading():
    timeline = _timeline_from_segments(
        [_segment("seg-1", 0, 60, TimelineStatus.NOMINAL)],
        statistics={
            "_aar_blocks": [
                {
                    "start": (BASE + timedelta(minutes=20)).isoformat(),
                    "end": (BASE + timedelta(minutes=40)).isoformat(),
                }
            ]
        },
    )

    normalize_call_availability_timeline(timeline)

    assert [(s.start_time, s.end_time) for s in timeline.segments] == [
        (BASE, BASE + timedelta(minutes=20)),
        (BASE + timedelta(minutes=20), BASE + timedelta(minutes=40)),
        (BASE + timedelta(minutes=40), BASE + timedelta(minutes=60)),
    ]
    assert [s.metadata["call_posture"] for s in timeline.segments] == [
        "Nominal calls",
        "Safety-of-flight advised",
        "Nominal calls",
    ]
    assert timeline.segments[1].status == TimelineStatus.SOF
    assert timeline.segments[1].metadata["primary_reason"] == "AAR window"
    assert timeline.segments[1].reasons == [
        "Safety-of-flight advised — AAR window; AAR Start"
    ]


def test_default_coverage_sampler_constructor_is_synchronized(monkeypatch, tmp_path):
    """Concurrent lazy sampler lookups should construct the sampler once."""
    coverage_path = tmp_path / "data" / "sat_coverage" / "commka.geojson"
    coverage_path.parent.mkdir(parents=True)
    coverage_path.write_text('{"type": "FeatureCollection", "features": []}')
    constructed = 0

    class FakeSampler:
        def __init__(self, path):
            nonlocal constructed
            constructed += 1
            self.path = path

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(timeline_service, "_COVERAGE_SAMPLER", None)
    monkeypatch.setattr(timeline_service, "CoverageSampler", FakeSampler)

    with ThreadPoolExecutor(max_workers=10) as executor:
        samplers = list(
            executor.map(
                lambda _: timeline_service._get_default_coverage_sampler(), range(10)
            )
        )

    assert constructed == 1
    assert len({id(sampler) for sampler in samplers}) == 1


def test_call_availability_priority_aar_advisory_not_outage():
    outage = _segment(
        "seg-outage",
        10,
        20,
        TimelineStatus.DEGRADED,
        reasons=["Ka outage"],
    )
    outage.ka_state = TransportState.OFFLINE
    outage.impacted_transports = [Transport.KA]
    timeline = _timeline_from_segments(
        [
            _segment("seg-nominal-a", 0, 10, TimelineStatus.NOMINAL),
            outage,
            _segment("seg-nominal-b", 20, 30, TimelineStatus.NOMINAL),
        ],
        statistics={
            "_aar_blocks": [
                {
                    "start": (BASE + timedelta(minutes=5)).isoformat(),
                    "end": (BASE + timedelta(minutes=25)).isoformat(),
                }
            ]
        },
    )

    normalize_call_availability_timeline(timeline)

    labels = [s.metadata["availability_label"] for s in timeline.segments]
    assert labels == [
        "Nominal calls",
        "Safety-of-flight advised — AAR window; AAR Start",
        "Unavailable — Ka outage; AAR window",
        "Safety-of-flight advised — AAR window",
        "Nominal calls; AAR End",
    ]


def test_call_availability_ku_x_conflict_is_advisory_not_degraded():
    conflict = _segment(
        "seg-conflict",
        15,
        25,
        TimelineStatus.DEGRADED,
        reasons=["X-Ku Conflict az=180° el=20°"],
    )
    conflict.x_state = TransportState.DEGRADED
    conflict.impacted_transports = [Transport.X]
    timeline = _timeline_from_segments(
        [
            _segment("seg-a", 0, 15, TimelineStatus.NOMINAL),
            conflict,
            _segment("seg-b", 25, 40, TimelineStatus.NOMINAL),
        ]
    )

    normalize_call_availability_timeline(timeline)

    advisory = timeline.segments[1]
    assert advisory.status == TimelineStatus.SOF
    assert advisory.x_state == TransportState.AVAILABLE
    assert advisory.ku_state == TransportState.AVAILABLE
    assert advisory.impacted_transports == []
    assert advisory.metadata["call_posture"] == "Transport concurrency advisory"
    assert advisory.metadata["primary_reason"] == "X Band / Ku conflict"
    assert (
        advisory.metadata["availability_label"]
        == "X Band / Ku conflict — choose one transport"
    )
    assert "PACE" not in advisory.metadata["availability_label"]


def test_call_availability_ku_x_conflict_preserves_separate_degradation():
    conflict_with_outage = _segment(
        "seg-conflict-outage",
        15,
        25,
        TimelineStatus.DEGRADED,
        reasons=["X-Ku Conflict az=180° el=20°", "Ka coverage gap"],
    )
    conflict_with_outage.x_state = TransportState.DEGRADED
    conflict_with_outage.ka_state = TransportState.DEGRADED
    conflict_with_outage.impacted_transports = [Transport.X, Transport.KA]
    timeline = _timeline_from_segments([conflict_with_outage])

    normalize_call_availability_timeline(timeline)

    assert timeline.segments[0].status == TimelineStatus.DEGRADED
    assert timeline.segments[0].metadata["call_posture"] == "Degraded"
    assert timeline.segments[0].metadata["primary_reason"] == "Ka coverage gap"
    assert timeline.segments[0].impacted_transports == [Transport.KA]
    assert timeline.segments[0].x_state == TransportState.AVAILABLE
    assert timeline.segments[0].ka_state == TransportState.DEGRADED


def test_call_availability_satellite_swap_reason_is_specific():
    swap = _segment(
        "seg-swap",
        10,
        20,
        TimelineStatus.DEGRADED,
        reasons=["X Transition to X-2"],
    )
    swap.x_state = TransportState.DEGRADED
    swap.impacted_transports = [Transport.X]
    timeline = _timeline_from_segments(
        [
            _segment("seg-a", 0, 10, TimelineStatus.NOMINAL),
            swap,
            _segment("seg-b", 20, 30, TimelineStatus.NOMINAL),
        ]
    )

    normalize_call_availability_timeline(timeline)

    assert timeline.segments[1].metadata["call_posture"] == "Degraded"
    assert timeline.segments[1].metadata["primary_reason"] == (
        "Satellite swap: X Transition to X-2"
    )


def test_call_availability_x_aar_conflict_is_specific_degrade():
    conflict = _segment(
        "seg-conflict",
        10,
        20,
        TimelineStatus.DEGRADED,
        reasons=["X-Band azimuth conflict during AAR window"],
    )
    conflict.x_state = TransportState.DEGRADED
    conflict.impacted_transports = [Transport.X]
    timeline = _timeline_from_segments(
        [
            _segment("seg-a", 0, 10, TimelineStatus.NOMINAL),
            conflict,
            _segment("seg-b", 20, 30, TimelineStatus.NOMINAL),
        ],
        statistics={
            "_aar_blocks": [
                {
                    "start": (BASE + timedelta(minutes=5)).isoformat(),
                    "end": (BASE + timedelta(minutes=25)).isoformat(),
                }
            ]
        },
    )

    normalize_call_availability_timeline(timeline)

    degraded = [
        segment
        for segment in timeline.segments
        if segment.metadata["primary_reason"] == "X Band / AAR conflict"
    ]
    assert degraded
    assert degraded[0].metadata["call_posture"] == "Degraded"


def test_call_availability_aar_reason_with_unrelated_x_is_not_x_aar_conflict():
    aar_exercise = _segment(
        "seg-aar-exercise",
        10,
        20,
        TimelineStatus.NOMINAL,
        reasons=["AAR exercise window"],
    )
    timeline = _timeline_from_segments([aar_exercise])

    normalize_call_availability_timeline(timeline)

    assert timeline.segments[0].metadata["call_posture"] == "Nominal calls"
    assert timeline.segments[0].metadata["primary_reason"] == "nominal window"


def test_call_availability_takeoff_landing_sof_periods_are_distinct():
    timeline = _timeline_from_segments(
        [
            _segment(
                "seg-takeoff",
                0,
                15,
                TimelineStatus.NOMINAL,
                reasons=["Safety-of-Flight (takeoff)"],
            ),
            _segment("seg-cruise", 15, 45, TimelineStatus.NOMINAL),
            _segment(
                "seg-landing",
                45,
                60,
                TimelineStatus.NOMINAL,
                reasons=["Safety-of-Flight (landing)"],
            ),
        ]
    )

    normalize_call_availability_timeline(timeline)

    assert [s.metadata["availability_label"] for s in timeline.segments] == [
        "Avoid calls — Safety-of-Flight (takeoff); Takeoff safety window",
        "Nominal calls",
        "Avoid calls — Safety-of-Flight (landing); Landing safety window",
    ]
    assert [s.status for s in timeline.segments] == [
        TimelineStatus.SOF,
        TimelineStatus.NOMINAL,
        TimelineStatus.SOF,
    ]


def test_call_availability_priority_degraded_over_sof():
    degraded_sof = _segment(
        "seg-degraded-sof",
        0,
        15,
        TimelineStatus.NOMINAL,
        reasons=["Safety-of-Flight (takeoff)", "X transition to X-2"],
    )
    degraded_sof.x_state = TransportState.DEGRADED
    degraded_sof.impacted_transports = [Transport.X]
    timeline = _timeline_from_segments([degraded_sof])

    normalize_call_availability_timeline(timeline)

    assert timeline.segments[0].status == TimelineStatus.DEGRADED
    assert timeline.segments[0].metadata["call_posture"] == "Degraded"
    assert timeline.segments[0].metadata["primary_reason"] == (
        "Satellite swap: X transition to X-2"
    )


def test_call_availability_priority_critical_over_sof():
    critical_sof = _segment(
        "seg-critical-sof",
        45,
        60,
        TimelineStatus.NOMINAL,
        reasons=["Safety-of-Flight (landing)", "Ka outage", "Ku outage"],
    )
    critical_sof.ka_state = TransportState.OFFLINE
    critical_sof.ku_state = TransportState.OFFLINE
    critical_sof.impacted_transports = [Transport.KA, Transport.KU]
    timeline = _timeline_from_segments([critical_sof])

    normalize_call_availability_timeline(timeline)

    assert timeline.segments[0].status == TimelineStatus.CRITICAL
    assert timeline.segments[0].metadata["call_posture"] == "Unavailable"
    assert timeline.segments[0].metadata["primary_reason"] == "Ka outage; Ku outage"


def test_call_availability_source_status_priority_order_is_explicit():
    timeline = _timeline_from_segments(
        [
            _segment("seg-sof", 0, 10, TimelineStatus.SOF),
            _segment("seg-degraded", 0, 10, TimelineStatus.DEGRADED),
        ]
    )

    normalize_call_availability_timeline(timeline)

    assert timeline.segments[0].status == TimelineStatus.DEGRADED

    timeline = _timeline_from_segments(
        [
            _segment("seg-nominal", 0, 10, TimelineStatus.NOMINAL),
            _segment("seg-sof", 0, 10, TimelineStatus.SOF),
            _segment("seg-degraded", 0, 10, TimelineStatus.DEGRADED),
            _segment("seg-critical", 0, 10, TimelineStatus.CRITICAL),
        ]
    )

    normalize_call_availability_timeline(timeline)

    assert timeline.segments[0].status == TimelineStatus.CRITICAL


def test_call_availability_merges_adjacent_only_when_labels_match():
    timeline = _timeline_from_segments(
        [
            _segment("seg-a", 0, 10, TimelineStatus.NOMINAL),
            _segment("seg-b", 10, 20, TimelineStatus.NOMINAL),
            _segment(
                "seg-c", 20, 30, TimelineStatus.NOMINAL, metadata={"note": "handoff"}
            ),
        ]
    )

    normalize_call_availability_timeline(timeline)

    assert [(s.start_time, s.end_time) for s in timeline.segments] == [
        (BASE, BASE + timedelta(minutes=20)),
        (BASE + timedelta(minutes=20), BASE + timedelta(minutes=30)),
    ]
    assert timeline.segments[0].metadata["source_segment_ids"] == ["seg-a", "seg-b"]
    assert timeline.segments[1].metadata["notes"] == ["handoff"]


def test_call_availability_normalization_is_idempotent_for_labels():
    swap = _segment(
        "seg-swap",
        0,
        10,
        TimelineStatus.DEGRADED,
        reasons=["Ka transition IOR → POR"],
    )
    swap.ka_state = TransportState.DEGRADED
    swap.impacted_transports = [Transport.KA]
    timeline = _timeline_from_segments(
        [
            _segment(
                "seg-sof",
                10,
                20,
                TimelineStatus.SOF,
                reasons=["Safety-of-Flight (landing)"],
            ),
            swap,
        ]
    )

    normalize_call_availability_timeline(timeline)
    normalize_call_availability_timeline(timeline)

    assert [s.metadata["availability_label"] for s in timeline.segments] == [
        "Degraded — Satellite swap: Ka transition IOR → POR",
        "Avoid calls — Safety-of-Flight (landing); Landing safety window",
    ]
    assert [s.reasons for s in timeline.segments] == [
        ["Degraded — Satellite swap: Ka transition IOR → POR"],
        ["Avoid calls — Safety-of-Flight (landing); Landing safety window"],
    ]


def test_call_availability_rows_are_sorted_and_non_overlapping():
    conflict = _segment(
        "seg-conflict",
        5,
        20,
        TimelineStatus.DEGRADED,
        reasons=["Other activity conflict"],
    )
    conflict.x_state = TransportState.DEGRADED
    conflict.impacted_transports = [Transport.X]
    timeline = _timeline_from_segments(
        [
            conflict,
            _segment("seg-nominal", 0, 5, TimelineStatus.NOMINAL),
            _segment("seg-tail", 20, 30, TimelineStatus.NOMINAL),
        ],
        statistics={
            "_aar_blocks": [
                {
                    "start": (BASE + timedelta(minutes=10)).isoformat(),
                    "end": (BASE + timedelta(minutes=15)).isoformat(),
                }
            ]
        },
    )

    normalize_call_availability_timeline(timeline)

    starts = [s.start_time for s in timeline.segments]
    assert starts == sorted(starts)
    for prev, nxt in zip(timeline.segments, timeline.segments[1:]):
        assert prev.end_time <= nxt.start_time
    assert [s.metadata["availability_label"] for s in timeline.segments] == [
        "Nominal calls",
        "Other activity conflict",
        "Degraded — X Band / AAR conflict; AAR Start; AAR window",
        "Other activity conflict; AAR End",
        "Nominal calls",
    ]
    assert [s.metadata.get("operational_markers") for s in timeline.segments] == [
        [],
        [],
        ["AAR Start", "AAR window"],
        ["AAR End"],
        [],
    ]


def test_call_availability_keeps_aar_start_boundary_during_existing_degrade():
    degraded = _segment(
        "seg-ka-gap",
        0,
        30,
        TimelineStatus.DEGRADED,
        reasons=["Ka coverage gap"],
    )
    degraded.ka_state = TransportState.DEGRADED
    degraded.impacted_transports = [Transport.KA]
    timeline = _timeline_from_segments(
        [degraded],
        statistics={
            "_aar_blocks": [
                {
                    "start": (BASE + timedelta(minutes=10)).isoformat(),
                    "end": (BASE + timedelta(minutes=20)).isoformat(),
                }
            ]
        },
    )

    normalize_call_availability_timeline(timeline)

    assert [(s.start_time, s.end_time) for s in timeline.segments] == [
        (BASE, BASE + timedelta(minutes=10)),
        (BASE + timedelta(minutes=10), BASE + timedelta(minutes=20)),
        (BASE + timedelta(minutes=20), BASE + timedelta(minutes=30)),
    ]
    assert timeline.segments[1].status == TimelineStatus.DEGRADED
    assert timeline.segments[1].metadata["boundary_markers"] == ["AAR Start"]
    assert timeline.segments[1].metadata["operational_markers"] == [
        "AAR Start",
        "AAR window",
    ]
    assert "AAR Start" in timeline.segments[1].metadata["availability_label"]
    assert "AAR Start" in timeline.segments[1].reasons[0]


def test_call_availability_exposes_aar_start_inline_in_reason_text():
    conflict = _segment(
        "seg-x-ku",
        0,
        20,
        TimelineStatus.DEGRADED,
        reasons=["X Band / Ku conflict"],
    )
    conflict.x_state = TransportState.DEGRADED
    conflict.impacted_transports = [Transport.X]
    timeline = _timeline_from_segments(
        [conflict],
        statistics={
            "_aar_blocks": [
                {
                    "start": (BASE + timedelta(minutes=10)).isoformat(),
                    "end": (BASE + timedelta(minutes=20)).isoformat(),
                }
            ]
        },
    )

    normalize_call_availability_timeline(timeline)

    aar_start_segment = timeline.segments[1]
    assert aar_start_segment.status == TimelineStatus.SOF
    assert aar_start_segment.metadata["availability_label"] == (
        "X Band / Ku conflict — choose one transport; AAR Start; AAR window"
    )
    assert aar_start_segment.metadata["operational_markers"] == [
        "AAR Start",
        "AAR window",
    ]
    assert aar_start_segment.reasons[0] == (
        "X Band / Ku conflict — choose one transport; AAR Start; AAR window"
    )


def test_call_availability_lists_multiple_critical_degrade_causes():
    critical = _segment(
        "seg-critical",
        0,
        10,
        TimelineStatus.CRITICAL,
        reasons=["Ka transition AOR → POR", "Ku outage"],
    )
    critical.ka_state = TransportState.OFFLINE
    critical.ku_state = TransportState.OFFLINE
    critical.impacted_transports = [Transport.KA, Transport.KU]
    timeline = _timeline_from_segments([critical])

    normalize_call_availability_timeline(timeline)

    label = timeline.segments[0].metadata["availability_label"]
    assert timeline.segments[0].status == TimelineStatus.CRITICAL
    assert "Ka transition AOR → POR" in label
    assert "Ku outage" in label


def test_call_availability_coalesces_adjacent_same_reason_degraded_blocks():
    segments = []
    for idx, (start, end) in enumerate(((0, 10), (10, 20), (20, 30)), start=1):
        segment = _segment(
            f"seg-swap-{idx}",
            start,
            end,
            TimelineStatus.DEGRADED,
            reasons=["X Transition to X-6"],
        )
        segment.x_state = TransportState.DEGRADED
        segment.impacted_transports = [Transport.X]
        segments.append(segment)
    timeline = _timeline_from_segments(segments)

    normalize_call_availability_timeline(timeline)

    assert len(timeline.segments) == 1
    assert timeline.segments[0].start_time == BASE
    assert timeline.segments[0].end_time == BASE + timedelta(minutes=30)
    assert timeline.segments[0].metadata["source_segment_ids"] == [
        "seg-swap-1",
        "seg-swap-2",
        "seg-swap-3",
    ]


def test_call_availability_landing_marker_survives_x_ku_advisory_overlap():
    x_ku = _segment(
        "seg-x-ku-landing",
        0,
        15,
        TimelineStatus.DEGRADED,
        reasons=["X Band / Ku conflict", "Safety-of-Flight (landing)"],
    )
    x_ku.x_state = TransportState.DEGRADED
    x_ku.impacted_transports = [Transport.X]
    timeline = _timeline_from_segments([x_ku])

    normalize_call_availability_timeline(timeline)

    assert len(timeline.segments) == 1
    assert timeline.segments[0].status == TimelineStatus.SOF
    assert timeline.segments[0].metadata["availability_label"] == (
        "X Band / Ku conflict — choose one transport; Landing safety window"
    )
    assert timeline.segments[0].metadata["operational_markers"] == [
        "Landing safety window"
    ]


def test_resolve_aar_windows_uses_manual_time_overrides_without_route_waypoints():
    override_start = BASE + timedelta(minutes=12)
    override_end = BASE + timedelta(minutes=42)
    mission = MissionLeg(
        id="mission-override",
        name="Mission override",
        route_id="route-1",
        transports=TransportConfig(
            initial_x_satellite_id="X-1",
            aar_windows=[
                AARWindow(
                    id="aar-1",
                    start_waypoint_name="ARIP",
                    end_waypoint_name="AREX",
                    override_start_time=override_start,
                    override_end_time=override_end,
                )
            ],
        ),
    )

    windows = resolve_aar_windows(
        mission,
        route=type("Route", (), {"waypoints": []})(),
        projector=object(),
    )

    assert len(windows) == 1
    assert windows[0].start_time == override_start
    assert windows[0].end_time == override_end


def test_elapsed_aar_override_preserves_route_duration_and_shifts_end_time():
    original_start = BASE + timedelta(minutes=15)
    original_end = BASE + timedelta(minutes=75)
    mission = MissionLeg(
        id="mission-elapsed-override",
        name="Mission elapsed override",
        route_id="route-1",
        transports=TransportConfig(
            initial_x_satellite_id="X-1",
            aar_windows=[
                AARWindow(
                    id="aar-1",
                    start_waypoint_name="ARIP",
                    end_waypoint_name="AREX",
                    override_start_elapsed="T+00:30",
                )
            ],
        ),
    )
    waypoint_type = type("Waypoint", (), {})
    arip = waypoint_type()
    arip.name = "ARIP"
    arip.expected_arrival_time = original_start
    arip.latitude = 0.0
    arip.longitude = 0.0
    arex = waypoint_type()
    arex.name = "AREX"
    arex.expected_arrival_time = original_end
    arex.latitude = 0.0
    arex.longitude = 0.0
    projector = type(
        "Projector",
        (),
        {
            "start_time": BASE,
            "shift_route_timestamp": lambda self, timestamp: timestamp,
        },
    )()

    windows = resolve_aar_windows(
        mission,
        route=type("Route", (), {"waypoints": [arip, arex]})(),
        projector=projector,
    )

    assert parse_elapsed_offset("T+00:30") == timedelta(minutes=30)
    assert len(windows) == 1
    assert windows[0].start_time == BASE + timedelta(minutes=30)
    assert windows[0].end_time == BASE + timedelta(minutes=90)
