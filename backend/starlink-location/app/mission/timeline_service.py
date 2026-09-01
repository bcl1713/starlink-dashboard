"""Mission timeline computation utilities."""

# FR-004: File exceeds 300 lines (305 lines) because timeline generation
# coordinates route projection, transport rules, POI replacement, sampler
# initialization, statistics, and compatibility exports. Deferred to v0.4.0.

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from app.mission.call_availability import normalize_call_availability_timeline
from app.mission.derived_route import (
    build_derived_route_estimate,
    derived_route_for_estimate,
)
from app.mission.models import MissionLeg, MissionLegTimeline, Transport
from app.mission.state import generate_transport_intervals
from app.mission.timeline import assemble_mission_timeline
from app.mission.timeline_builder.aar import (
    apply_manual_aar_tracks,
    apply_x_transitions,
    resolve_aar_windows,
)
from app.mission.timeline_builder.calculator import (
    TIMELINE_SAMPLE_INTERVAL_SECONDS,
    RouteTemporalProjector,
    TimelineComputationError,
    derive_mission_window,
    generate_timeline_samples,
    route_takeoff_delta,
    route_with_adjusted_departure,
)
from app.mission.timeline_builder.coverage import analyze_ka_coverage
from app.mission.timeline_builder.events import (
    apply_ka_events,
    apply_manual_outages,
    apply_x_azimuth_events,
)
from app.mission.timeline_builder.pois import collect_ka_pois, collect_x_aar_pois
from app.mission.timeline_builder.stats import (
    TimelineSummary,
    annotate_aar_markers,
    attach_statistics,
    summarize_timeline,
)
from app.satellites.catalog import get_satellite_catalog
from app.satellites.coverage import CoverageSampler
from app.satellites.kmz_importer import load_commka_coverage
from app.satellites.rules import RuleEngine
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager

logger = logging.getLogger(__name__)

try:
    APP_DIR = Path(__file__).resolve().parents[1]
except IndexError:
    APP_DIR = Path(__file__).resolve().parent
try:
    REPO_ROOT = Path(__file__).resolve().parents[4]
except IndexError:
    REPO_ROOT = Path.cwd()

_COVERAGE_SAMPLER: CoverageSampler | None = None
_COVERAGE_SAMPLER_LOCK = threading.Lock()


def build_mission_timeline(
    mission: MissionLeg,
    route_manager: RouteManager,
    poi_manager: POIManager | None = None,
    coverage_sampler: CoverageSampler | None = None,
    parent_mission_id: str | None = None,
    include_samples: bool = False,
) -> tuple[MissionLegTimeline, TimelineSummary]:
    """Compute the mission communication timeline and derived summary.

    Args:
        mission: Mission leg configuration
        route_manager: Route manager for loading route data
        poi_manager: Optional POI manager for satellite POI sync
        coverage_sampler: Optional coverage sampler for Ka coverage analysis
        parent_mission_id: Optional parent mission ID for POI scoping
        include_samples: If True, include route samples in timeline for preview rendering

    Returns:
        Tuple of (MissionLegTimeline, TimelineSummary)
    """

    if not mission.route_id:
        raise TimelineComputationError("Mission is missing route_id")

    route = route_manager.get_route(mission.route_id)
    if not route:
        raise TimelineComputationError(f"Route {mission.route_id} not loaded")

    route = route_with_adjusted_departure(route, mission.adjusted_departure_time)
    splice = mission.transports.manual_route_splice
    selected_track = None
    splice_available = False
    if splice:
        selected_track = next(
            (
                track
                for track in mission.transports.manual_aar_tracks
                if track.id == splice.enabled_track_id
            ),
            None,
        )
        if selected_track:
            estimate = build_derived_route_estimate(route, selected_track, splice)
            splice_available = estimate.available
            route = derived_route_for_estimate(route, estimate)
    mission_start, mission_end = derive_mission_window(route)
    projector = RouteTemporalProjector(route, mission_start, mission_end)

    resolved_sampler = coverage_sampler or _get_default_coverage_sampler()
    catalog = get_satellite_catalog()
    if poi_manager:
        satellite_names = {sat.satellite_id for sat in catalog.list_all()}
        removed = poi_manager.delete_scoped_pois_by_names(satellite_names)
        if removed:
            logger.info(
                "Removed %d scoped satellite POIs to enforce global definitions",
                removed,
            )

    build_start = time.perf_counter()
    sample_start = build_start
    samples = generate_timeline_samples(
        projector,
        coverage_sampler=resolved_sampler,
        interval_seconds=TIMELINE_SAMPLE_INTERVAL_SECONDS,
    )
    sampling_runtime_ms = (time.perf_counter() - sample_start) * 1000.0
    logger.debug(
        "Generated %d timeline samples (interval=%ds) for mission %s in %.1f ms",
        len(samples),
        TIMELINE_SAMPLE_INTERVAL_SECONDS,
        mission.id,
        sampling_runtime_ms,
    )
    if len(samples) > 2000:
        logger.info(
            "Mission %s uses high sample count (%d) — consider increasing interval",
            mission.id,
            len(samples),
        )

    rule_engine = RuleEngine()
    rule_engine.add_takeoff_landing_buffers(mission_start, mission_end)

    aar_windows = resolve_aar_windows(mission, route, projector)
    for window in aar_windows:
        rule_engine.add_aar_window_events(
            window.start_time, window.end_time, window.name
        )
    # The selected replacement track is an estimated route basis only when its
    # splice is feasible.  Other saved Manual AR tracks remain independent X
    # overlays; an unavailable selected splice leaves planned output unchanged.
    manual_tracks = [
        track
        for track in mission.transports.manual_aar_tracks
        if not splice or track.id != splice.enabled_track_id
    ]
    if selected_track and splice_available:
        manual_tracks.append(selected_track)
    apply_manual_aar_tracks(rule_engine, manual_tracks, projector)

    transition_schedule = apply_x_transitions(
        rule_engine, mission, projector, aar_windows
    )

    coverage_result = analyze_ka_coverage(
        samples,
        projector,
        coverage_enabled=resolved_sampler is not None,
    )
    apply_ka_events(rule_engine, coverage_result)
    apply_x_azimuth_events(
        rule_engine,
        mission,
        route,
        samples,
        aar_windows,
        transition_schedule,
        poi_manager,
        mission_start,
        mission_end,
    )

    if poi_manager:
        effective_mission_id = parent_mission_id or mission.id
        generated_pois = [
            *collect_ka_pois(mission, route, coverage_result, parent_mission_id),
            *collect_x_aar_pois(mission, route, parent_mission_id),
        ]
        poi_manager.replace_timeline_event_pois(
            route_id=mission.route_id,
            mission_id=effective_mission_id,
            generated_pois=generated_pois,
            route=route,
        )

    apply_manual_outages(rule_engine, mission.transports.ka_outages, Transport.KA)
    apply_manual_outages(rule_engine, mission.transports.ku_overrides, Transport.KU)

    events = rule_engine.get_sorted_events()
    intervals = generate_transport_intervals(
        events,
        mission_start,
        mission_end,
        transports=[Transport.X, Transport.KA, Transport.KU],
    )

    timeline = assemble_mission_timeline(
        mission_id=mission.id,
        mission_start=mission_start,
        mission_end=mission_end,
        intervals=intervals,
    )
    annotate_aar_markers(timeline, events)
    normalize_call_availability_timeline(timeline)
    attach_statistics(timeline, mission_start, mission_end)

    # Attach route samples if requested (for preview rendering)
    if include_samples:
        from app.mission.models import RouteSampleData

        timeline.samples = [
            RouteSampleData(
                timestamp=sample.timestamp,
                latitude=sample.latitude,
                longitude=sample.longitude,
                altitude=sample.altitude,
                coverage=list(sample.coverage),
            )
            for sample in samples
        ]

    total_runtime_ms = (time.perf_counter() - build_start) * 1000.0
    if total_runtime_ms > 1000:
        logger.warning(
            "Mission timeline generation for %s took %.1f ms (samples=%d)",
            mission.id,
            total_runtime_ms,
            len(samples),
        )
    else:
        logger.debug(
            "Mission timeline generation for %s completed in %.1f ms",
            mission.id,
            total_runtime_ms,
        )
    summary = summarize_timeline(
        timeline,
        mission_start,
        mission_end,
        sample_count=len(samples),
        sample_interval_seconds=TIMELINE_SAMPLE_INTERVAL_SECONDS,
        generation_runtime_ms=total_runtime_ms,
    )

    return timeline, summary


def _get_default_coverage_sampler() -> CoverageSampler | None:
    global _COVERAGE_SAMPLER
    if _COVERAGE_SAMPLER is not None:
        return _COVERAGE_SAMPLER

    with _COVERAGE_SAMPLER_LOCK:
        if _COVERAGE_SAMPLER is not None:
            return _COVERAGE_SAMPLER

        coverage_path = Path("data/sat_coverage/commka.geojson")
        if not coverage_path.exists():
            kmz_candidates = [
                Path("data/sat_coverage/CommKa.kmz"),
                APP_DIR / "satellites" / "assets" / "CommKa.kmz",
            ]
            for kmz_path in kmz_candidates:
                if kmz_path.exists():
                    coverage_path.parent.mkdir(parents=True, exist_ok=True)
                    load_commka_coverage(kmz_path, coverage_path.parent)
                    break

        if coverage_path.exists():
            _COVERAGE_SAMPLER = CoverageSampler(coverage_path)
        else:
            _COVERAGE_SAMPLER = None
    return _COVERAGE_SAMPLER


__all__ = [
    "RouteTemporalProjector",
    "TimelineComputationError",
    "TimelineSummary",
    "build_mission_timeline",
    "route_takeoff_delta",
    "route_with_adjusted_departure",
]
