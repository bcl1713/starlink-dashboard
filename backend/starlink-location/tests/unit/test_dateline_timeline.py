"""Issue #271 regressions using entirely fabricated routes and coverage."""

from datetime import timedelta
from itertools import pairwise
from pathlib import Path

import pytest

from app.mission.models import MissionLeg, Transport, TransportConfig, TransportState
from app.mission.state import generate_transport_intervals
from app.mission.timeline_builder.calculator import (
    RouteTemporalProjector,
    derive_mission_window,
    generate_timeline_samples,
    route_with_adjusted_departure,
)
from app.mission.timeline_builder.coverage import analyze_ka_coverage
from app.mission.timeline_builder.events import apply_ka_events
from app.mission.timeline_service import build_mission_timeline
from app.satellites.rules import RuleEngine
from app.services.kml.parser import parse_kml_file
from app.services.route_manager import RouteManager
from tests.fixtures.synthetic_coverage import SyntheticCoverage


@pytest.fixture
def route():
    return parse_kml_file(
        Path(__file__).parents[1] / "fixtures/synthetic-dateline-timeline.kml"
    )


@pytest.fixture
def projector(route):
    return RouteTemporalProjector(route, *derive_mission_window(route))


def test_untimed_dateline_vertex_has_monotonic_progress_and_inverse_times(projector):
    samples = generate_timeline_samples(projector, SyntheticCoverage())
    assert all(a.distance_meters <= b.distance_meters for a, b in pairwise(samples))
    for sample in samples:
        assert (
            abs(
                (
                    projector.timestamp_for_distance(sample.distance_meters)
                    - sample.timestamp
                ).total_seconds()
            )
            < 1e-5
        )
    # Interior vertex follows distance between WEST and EAST, not whole-leg speed.
    seam = projector.sample_at_distance(projector.cumulative_distances[2])
    assert (
        projector.start_time + timedelta(hours=3)
        < seam.timestamp
        < projector.start_time + timedelta(hours=3, minutes=35)
    )
    assert abs(abs(seam.longitude) - 180) < 1e-5


def test_synthetic_gaps_are_ordered_and_ka_recovers_at_landing(projector):
    samples = generate_timeline_samples(projector, SyntheticCoverage())
    coverage = analyze_ka_coverage(samples, projector, True)
    assert coverage.gaps
    assert all(
        gap.end
        and projector.start_time
        <= gap.start.timestamp
        < gap.end.timestamp
        <= projector.end_time
        for gap in coverage.gaps
    )
    engine = RuleEngine()
    apply_ka_events(engine, coverage)
    intervals = generate_transport_intervals(
        engine.get_sorted_events(), projector.start_time, projector.end_time
    )[Transport.KA]
    assert samples[-1].coverage == {"IOR"}
    assert intervals[-1].state == TransportState.AVAILABLE


def test_coverage_recovery_preserves_independent_outage_and_transition(projector):
    coverage = analyze_ka_coverage(
        generate_timeline_samples(projector, SyntheticCoverage()), projector, True
    )
    engine = RuleEngine()
    apply_ka_events(engine, coverage)
    recovery = coverage.gaps[-1].end.timestamp
    engine.add_manual_outage_events(
        recovery - timedelta(minutes=1),
        recovery + timedelta(minutes=2),
        Transport.KA,
        "Manual maintenance",
    )
    intervals = generate_transport_intervals(
        engine.get_sorted_events(), projector.start_time, projector.end_time
    )[Transport.KA]
    at_recovery = next(span for span in intervals if span.start <= recovery < span.end)
    assert at_recovery.state == TransportState.OFFLINE
    assert "Manual maintenance" in at_recovery.reasons
    assert not any("coverage lost" in reason for reason in at_recovery.reasons)
    swap = coverage.swaps[0]
    at_handoff = next(
        span for span in intervals if span.start <= swap.midpoint.timestamp < span.end
    )
    assert at_handoff.state == TransportState.DEGRADED
    assert any("transition" in reason for reason in at_handoff.reasons)
    assert intervals[-1].state == TransportState.AVAILABLE


def test_adjusted_departure_shifts_projection_without_mutating_cached_route(route):
    original = route.model_dump()
    start, _end = derive_mission_window(route)
    shifted = route_with_adjusted_departure(route, start + timedelta(hours=23))
    projector = RouteTemporalProjector(shifted, *derive_mission_window(shifted))
    assert projector.timestamp_for_distance(
        projector.cumulative_distances[3]
    ) == start + timedelta(hours=26, minutes=35)
    assert route.model_dump() == original


def test_timeline_exposes_start_entry_handoff_exit_without_overlap_outage(route):
    manager = RouteManager()
    manager._routes["synthetic-route"] = route
    leg = MissionLeg(
        id="synthetic-271",
        name="Fabricated regression",
        route_id="synthetic-route",
        transports=TransportConfig(initial_x_satellite_id="X-1"),
    )
    timeline, _ = build_mission_timeline(
        leg, manager, coverage_sampler=SyntheticCoverage()
    )
    events = timeline.coverage_events
    assert events[0].event_type == "starting"
    assert events[0].coverage == ["POR"]
    entry = next(
        e for e in events if e.event_type == "entry" and e.satellite_id == "IOR"
    )
    handoff = next(e for e in events if e.event_type == "handoff")
    exit_event = next(
        e
        for e in events
        if e.event_type == "exit"
        and e.satellite_id == "POR"
        and e.timestamp > entry.timestamp
    )
    assert entry.timestamp < handoff.timestamp < exit_event.timestamp
    assert entry.coverage == ["IOR", "POR"]
    assert exit_event.coverage == ["IOR"]
    assert not any(
        e.event_type == "lost"
        and entry.timestamp <= e.timestamp <= exit_event.timestamp
        for e in events
    )
    assert events == sorted(events, key=lambda e: e.timestamp)
    assert timeline.segments[-1].ka_state == TransportState.AVAILABLE


def test_modeled_same_satellite_gap_crossing_dateline_is_not_suppressed(projector):
    samples = [
        projector.sample_at_distance(projector.cumulative_distances[i])
        for i in (1, 2, 3)
    ]
    samples[0].coverage = {"POR"}
    samples[2].coverage = {"POR"}
    coverage = analyze_ka_coverage(samples, projector, True)
    assert len(coverage.gaps) == 1
    assert coverage.gaps[0].start.timestamp < coverage.gaps[0].end.timestamp


def test_recovery_during_transition_clears_only_coverage_loss(projector):
    from app.satellites.rules import EventType, MissionEvent

    coverage = analyze_ka_coverage(
        generate_timeline_samples(projector, SyntheticCoverage()), projector, True
    )
    recovery = coverage.gaps[-1].end.timestamp
    engine = RuleEngine()
    apply_ka_events(engine, coverage)
    for minutes, severity in [(-1, "warning"), (2, "info")]:
        engine.events.append(
            MissionEvent(
                timestamp=recovery + timedelta(minutes=minutes),
                event_type=EventType.KA_TRANSITION,
                transport=Transport.KA,
                severity=severity,
                reason="Independent transition",
                metadata={"transition_id": "synthetic-transition"},
            )
        )
    intervals = generate_transport_intervals(
        engine.get_sorted_events(), projector.start_time, projector.end_time
    )[Transport.KA]
    at_recovery = next(span for span in intervals if span.start <= recovery < span.end)
    assert at_recovery.state == TransportState.DEGRADED
    assert at_recovery.reasons == ["Independent transition"]
    after_transition = next(
        span
        for span in intervals
        if span.start <= recovery + timedelta(minutes=3) < span.end
    )
    assert after_transition.state == TransportState.AVAILABLE
