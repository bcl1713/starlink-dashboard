"""Mission timeline computation utilities."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
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
    route_with_adjusted_departure,
)
from app.mission.timeline_builder.coverage import analyze_ka_coverage
from app.mission.timeline_builder.events import (
    apply_ka_events,
    apply_manual_outages,
    apply_x_azimuth_events,
)
from app.mission.timeline_builder.pois import MISSION_POI_KINDS, construct_mission_pois
from app.mission.timeline_builder.stats import (
    TimelineSummary,
    annotate_aar_markers,
    attach_statistics,
    summarize_timeline,
)
from app.models.poi import POICreate
from app.models.route import ParsedRoute
from app.satellites.catalog import SatelliteCatalog, get_satellite_catalog
from app.satellites.coverage import CoverageSampler
from app.satellites.rules import ConstraintConfig, MissionEvent, RuleEngine
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from app.simulation.run_route import normalize_timed_route

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TimelineArtifacts:
    route: ParsedRoute
    projector: RouteTemporalProjector
    events: tuple[MissionEvent, ...]
    timeline: MissionLegTimeline
    summary: TimelineSummary
    generated_pois: tuple[POICreate, ...]
    x_assignments: tuple[tuple[datetime, str, str | None], ...] = ()
    export_x_conditions: tuple[MissionEvent, ...] | None = None


def prepare_mission_timeline(
    mission: MissionLeg,
    route_manager: RouteManager,
    poi_manager: POIManager | None = None,
    coverage_sampler: CoverageSampler | None = None,
    parent_mission_id: str | None = None,
    include_samples: bool = False,
    *,
    capture_x_conditions: bool = False,
    normalize_for_simulation: bool = False,
    discover_coverage: bool = True,
    satellite_catalog: SatelliteCatalog | None = None,
    constraint_config: ConstraintConfig | None = None,
) -> TimelineArtifacts:
    """Prepare effective geometry, canonical events and POIs without publishing."""

    if not mission.route_id:
        raise TimelineComputationError("Mission is missing route_id")

    route = route_manager.get_route(mission.route_id)
    if not route:
        raise TimelineComputationError(f"Route {mission.route_id} not loaded")

    if normalize_for_simulation:
        route = normalize_timed_route(route)
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
            if normalize_for_simulation and not estimate.available:
                raise TimelineComputationError(
                    f"Selected diversion is unavailable: {estimate.unavailable_reason}"
                )
            splice_available = estimate.available
            route = derived_route_for_estimate(route, estimate)
            if normalize_for_simulation and splice_available:
                for point in route.points:
                    point.expected_segment_speed_knots = None
        elif normalize_for_simulation:
            raise TimelineComputationError("Selected diversion track is missing")
    if normalize_for_simulation:
        route = normalize_timed_route(route)
    else:
        route = route.model_copy(deep=True)
    mission_start, mission_end = derive_mission_window(route)
    projector = RouteTemporalProjector(route, mission_start, mission_end)

    coverage_path = Path("data/sat_coverage/commka.geojson")
    resolved_sampler = coverage_sampler or (
        CoverageSampler(coverage_path)
        if discover_coverage and coverage_path.exists()
        else None
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

    rule_engine = RuleEngine(constraint_config)
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
    export_x_conditions = [] if capture_x_conditions else None
    warning_boundaries = apply_x_azimuth_events(
        rule_engine,
        mission,
        route,
        samples,
        aar_windows,
        transition_schedule,
        poi_manager,
        mission_start,
        mission_end,
        satellite_catalog=satellite_catalog,
        condition_events=export_x_conditions,
    )

    generated_pois = construct_mission_pois(
        mission,
        route,
        mission_start=mission_start,
        mission_end=mission_end,
        aar_windows=aar_windows,
        transition_schedule=transition_schedule,
        coverage=coverage_result,
        parent_mission_id=parent_mission_id,
        warning_boundaries=warning_boundaries,
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
    timeline.coverage_events = coverage_result.coverage_events
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

    return TimelineArtifacts(
        route,
        projector,
        tuple(events),
        timeline,
        summary,
        generated_pois,
        tuple(transition_schedule),
        tuple(export_x_conditions) if export_x_conditions is not None else None,
    )


def publish_mission_pois(
    artifacts: TimelineArtifacts,
    poi_manager: POIManager,
    mission_id: str,
    route_id: str,
) -> None:
    """Publish prepared POIs only after a mutation path accepts the plan."""
    catalog = get_satellite_catalog()
    poi_manager.delete_scoped_pois_by_names(
        {sat.satellite_id for sat in catalog.list_all()}
    )
    poi_manager.delete_leg_pois(
        route_id=route_id,
        mission_id=mission_id,
        kinds=MISSION_POI_KINDS,
        generated_source="mission-timeline",
    )
    for poi in artifacts.generated_pois:
        poi_manager.create_poi(
            poi,
            active_route=artifacts.route,
            generated_source="mission-timeline",
            route_segment_index=poi._route_segment_index,
        )
