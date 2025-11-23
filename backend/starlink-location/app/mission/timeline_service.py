"""Mission timeline computation utilities."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Sequence

from app.mission.models import (
    Mission,
    MissionTimeline,
    TimelineStatus,
    Transport,
    TransportState,
)
from app.mission.state import generate_transport_intervals
from app.mission.timeline import assemble_mission_timeline
from app.models.route import ParsedRoute, RouteWaypoint
from app.services.poi_manager import POIManager, POICreate
from app.services.route_manager import RouteManager
from app.services.route_eta_calculator import RouteETACalculator
from app.simulation.route import calculate_bearing
from app.satellites.coverage import CoverageSampler
from app.satellites.kmz_importer import load_commka_coverage
from app.satellites.rules import EventType, MissionEvent, RuleEngine
from app.satellites.catalog import get_satellite_catalog
from app.mission.models import KaOutage, KuOutageOverride

logger = logging.getLogger(__name__)

MISSION_EVENT_CATEGORY = "mission-event"
KA_POI_CATEGORIES = {
    "mission-ka-transition",
    "mission-ka-gap-exit",
    "mission-ka-gap-entry",
}
KA_POI_NAME_PREFIXES = (
    "Ka Coverage Exit",
    "Ka Coverage Entry",
    "Ka Transition",
    "Ka Swap",
    "CommKa",
)
X_AAR_POI_PREFIXES = (
    "X-Band",
    "AAR",
)


_COVERAGE_SAMPLER: CoverageSampler | None = None
try:
    APP_DIR = Path(__file__).resolve().parents[1]
except IndexError:
    APP_DIR = Path(__file__).resolve().parent
try:
    REPO_ROOT = Path(__file__).resolve().parents[4]
except IndexError:
    REPO_ROOT = Path.cwd()
DEFAULT_CRUISE_ALTITUDE_M = 10668.0  # ~35,000 ft
TIMELINE_SAMPLE_INTERVAL_SECONDS = 60  # Minute-level sampling cadence


class TimelineComputationError(RuntimeError):
    """Raised when mission timeline generation fails."""


@dataclass
class RouteProjection:
    """Projection of an arbitrary coordinate onto the route timeline."""

    progress: float
    distance_meters: float
    timestamp: datetime
    latitude: float
    longitude: float


@dataclass
class RouteSample:
    """Sampled point along the route with timing, altitude, and coverage metadata."""

    distance_meters: float
    timestamp: datetime
    latitude: float
    longitude: float
    altitude: float | None = None
    heading: float | None = None
    coverage: set[str] = field(default_factory=set)


@dataclass
class KaCoverageGap:
    """Represents a Ka coverage outage interval."""

    start: RouteSample
    end: RouteSample | None
    lost_satellite: str | None
    regained_satellite: str | None


@dataclass
class KaCoverageSwap:
    """Represents a Ka swap opportunity inside an overlap window."""

    midpoint: RouteSample
    from_satellite: str
    to_satellite: str


@dataclass
class CoverageAnalysisResult:
    """Container for Ka coverage derived events."""

    gaps: list[KaCoverageGap]
    swaps: list[KaCoverageSwap]


@dataclass
class ResolvedAARWindow:
    """AAR window with route-aligned timestamps."""

    name: str
    start_time: datetime
    end_time: datetime


@dataclass
class TimelineSummary:
    """Lightweight summary derived from the computed timeline."""

    mission_start: datetime
    mission_end: datetime
    degraded_seconds: float
    critical_seconds: float
    next_conflict_seconds: float
    transport_states: dict[Transport, TransportState]
    sample_count: int
    sample_interval_seconds: int
    generation_runtime_ms: float


def build_mission_timeline(
    mission: Mission,
    route_manager: RouteManager,
    poi_manager: POIManager | None = None,
    coverage_sampler: CoverageSampler | None = None,
) -> tuple[MissionTimeline, TimelineSummary]:
    """Compute the mission communication timeline and derived summary."""

    if not mission.route_id:
        raise TimelineComputationError("Mission is missing route_id")

    route = route_manager.get_route(mission.route_id)
    if not route:
        raise TimelineComputationError(f"Route {mission.route_id} not loaded")

    mission_start, mission_end = _derive_mission_window(route)
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
    samples = _generate_timeline_samples(
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

    aar_windows = _resolve_aar_windows(mission, route, projector)
    for window in aar_windows:
        rule_engine.add_aar_window_events(
            window.start_time, window.end_time, window.name
        )

    transition_schedule = _apply_x_transitions(
        rule_engine, mission, projector, aar_windows
    )

    coverage_result = _analyze_ka_coverage(
        samples,
        projector,
        coverage_enabled=resolved_sampler is not None,
    )
    _apply_ka_events(rule_engine, coverage_result)
    _apply_x_azimuth_events(
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

    if poi_manager and (coverage_result.gaps or coverage_result.swaps):
        _sync_ka_pois(mission, route, poi_manager, coverage_result)
    if poi_manager:
        _sync_x_aar_pois(mission, route, poi_manager)

    _apply_manual_outages(rule_engine, mission.transports.ka_outages, Transport.KA)
    _apply_manual_outages(rule_engine, mission.transports.ku_overrides, Transport.KU)

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
    _annotate_aar_markers(timeline, events)
    _attach_statistics(timeline, mission_start, mission_end)
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
    summary = _summarize_timeline(
        timeline,
        mission_start,
        mission_end,
        sample_count=len(samples),
        sample_interval_seconds=TIMELINE_SAMPLE_INTERVAL_SECONDS,
        generation_runtime_ms=total_runtime_ms,
    )

    return timeline, summary


def _annotate_aar_markers(
    timeline: MissionTimeline,
    events: Sequence[MissionEvent],
) -> None:
    """Persist AAR window intervals for export consumers."""
    if not timeline.segments:
        return
    blocks: list[dict[str, str]] = []
    pending_start: datetime | None = None
    for event in events:
        if event.event_type != EventType.AAR_WINDOW:
            continue
        ts = _ensure_datetime(event.timestamp)
        if event.severity in ("warning", "critical", "safety"):
            pending_start = ts
        elif pending_start:
            blocks.append(
                {
                    "start": pending_start.isoformat(),
                    "end": ts.isoformat(),
                }
            )
            pending_start = None
    if pending_start:
        blocks.append(
            {
                "start": pending_start.isoformat(),
                "end": _ensure_datetime(timeline.segments[-1].end_time or pending_start).isoformat(),
            }
        )
    if blocks:
        stats = dict(timeline.statistics or {})
        stats["_aar_blocks"] = blocks
        timeline.statistics = stats


def _ensure_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _derive_mission_window(route: ParsedRoute) -> tuple[datetime, datetime]:
    """Infer mission start/end timestamps from the parsed route."""

    start_candidates: list[datetime] = []
    end_candidates: list[datetime] = []

    if route.timing_profile:
        if route.timing_profile.departure_time:
            start_candidates.append(route.timing_profile.departure_time)
        if route.timing_profile.arrival_time:
            end_candidates.append(route.timing_profile.arrival_time)

    for point in route.points:
        if point.expected_arrival_time:
            start_candidates.append(point.expected_arrival_time)
            end_candidates.append(point.expected_arrival_time)

    if not start_candidates or not end_candidates:
        raise TimelineComputationError(
            "Route timing data missing departure/arrival timestamps"
        )

    mission_start = min(start_candidates)
    mission_end = max(end_candidates)

    if mission_end <= mission_start:
        raise TimelineComputationError("Mission end must be after mission start")

    return mission_start, mission_end


class RouteTemporalProjector:
    """Utility for mapping arbitrary coordinates onto the timed route."""

    def __init__(self, route: ParsedRoute, start_time: datetime, end_time: datetime):
        self.route = route
        self.start_time = start_time
        self.end_time = end_time
        self.duration_seconds = max((end_time - start_time).total_seconds(), 1.0)
        self.calculator = RouteETACalculator(route)
        self.cumulative_distances = self._build_cumulative_distances()
        self.total_distance = max(self.cumulative_distances[-1], 1.0)

    def _build_cumulative_distances(self) -> list[float]:
        distances = [0.0]
        for idx in range(1, len(self.route.points)):
            prev = self.route.points[idx - 1]
            curr = self.route.points[idx]
            segment = self.calculator._haversine_distance(  # type: ignore[attr-defined]
                prev.latitude,
                prev.longitude,
                curr.latitude,
                curr.longitude,
            )
            distances.append(distances[-1] + segment)
        if not distances:
            distances = [0.0]
        return distances

    def project(self, latitude: float, longitude: float) -> RouteProjection:
        projection = self.calculator.project_poi_to_route(latitude, longitude)
        progress = (projection["projected_route_progress"] or 0.0) / 100.0
        distance = self.total_distance * progress
        timestamp = self.timestamp_for_distance(distance)
        return RouteProjection(
            progress=progress,
            distance_meters=distance,
            timestamp=timestamp,
            latitude=projection["projected_lat"],
            longitude=projection["projected_lon"],
        )

    def timestamp_for_distance(self, distance: float) -> datetime:
        if self.total_distance <= 0:
            return self.start_time
        ratio = max(0.0, min(1.0, distance / self.total_distance))
        return self.start_time + timedelta(seconds=ratio * self.duration_seconds)

    def sample_at_distance(self, distance: float) -> RouteSample:
        distance = max(0.0, min(distance, self.total_distance))
        if len(self.route.points) == 1:
            point = self.route.points[0]
            return RouteSample(
                distance_meters=0.0,
                timestamp=self.start_time,
                latitude=point.latitude,
                longitude=point.longitude,
                altitude=point.altitude if point.altitude is not None else DEFAULT_CRUISE_ALTITUDE_M,
                heading=None,
            )

        for idx in range(1, len(self.cumulative_distances)):
            prev_dist = self.cumulative_distances[idx - 1]
            next_dist = self.cumulative_distances[idx]
            if distance <= next_dist or idx == len(self.cumulative_distances) - 1:
                segment_span = max(next_dist - prev_dist, 1e-6)
                ratio = max(0.0, min(1.0, (distance - prev_dist) / segment_span))
                prev_point = self.route.points[idx - 1]
                next_point = self.route.points[idx]
                lat = prev_point.latitude + ratio * (
                    next_point.latitude - prev_point.latitude
                )
                lon = _interpolate_longitude(
                    prev_point.longitude, next_point.longitude, ratio
                )
                altitude = _interpolate_altitude(
                    prev_point.altitude, next_point.altitude, ratio
                )
                timestamp = self.timestamp_for_distance(distance)
                heading = None
                if not (
                    prev_point.latitude == next_point.latitude
                    and prev_point.longitude == next_point.longitude
                ):
                    heading = calculate_bearing(
                        prev_point.latitude,
                        prev_point.longitude,
                        next_point.latitude,
                        next_point.longitude,
                    )
                return RouteSample(
                    distance_meters=distance,
                    timestamp=timestamp,
                    latitude=lat,
                    longitude=lon,
                    altitude=altitude,
                    heading=heading,
                )

        return self.sample_at_distance(self.total_distance)


def _resolve_aar_windows(
    mission: Mission,
    route: ParsedRoute,
    projector: RouteTemporalProjector,
) -> list[ResolvedAARWindow]:
    windows: list[ResolvedAARWindow] = []
    if not mission.transports.aar_windows:
        return windows

    waypoint_lookup = {wp.name: wp for wp in route.waypoints if wp.name}

    for idx, window in enumerate(mission.transports.aar_windows or []):
        start_wp = waypoint_lookup.get(window.start_waypoint_name)
        end_wp = waypoint_lookup.get(window.end_waypoint_name)
        start_time = _timestamp_for_waypoint(start_wp, projector)
        end_time = _timestamp_for_waypoint(end_wp, projector)
        if not start_time or not end_time or end_time <= start_time:
            continue
        windows.append(
            ResolvedAARWindow(
                name=window.id or f"AAR-{idx + 1}",
                start_time=start_time,
                end_time=end_time,
            )
        )

    return windows


def _timestamp_for_waypoint(
    waypoint: RouteWaypoint | None, projector: RouteTemporalProjector
) -> datetime | None:
    if not waypoint:
        return None
    if waypoint.expected_arrival_time:
        return waypoint.expected_arrival_time
    projection = projector.project(waypoint.latitude, waypoint.longitude)
    return projection.timestamp


def _apply_x_transitions(
    rule_engine: RuleEngine,
    mission: Mission,
    projector: RouteTemporalProjector,
    aar_windows: list[ResolvedAARWindow],
) -> list[tuple[datetime, str]]:
    schedule: list[tuple[datetime, str]] = []
    initial_sat = mission.transports.initial_x_satellite_id
    if initial_sat:
        schedule.append((projector.start_time, initial_sat))

    if not mission.transports.x_transitions:
        return schedule

    for transition in mission.transports.x_transitions:
        projection = projector.project(transition.latitude, transition.longitude)
        timestamp = projection.timestamp
        if _falls_within_window(timestamp, aar_windows):
            rule_engine.add_x_transition_events(
                timestamp,
                transition.target_satellite_id,
                is_aar_mode=True,
            )
        else:
            rule_engine.add_x_transition_events(
                timestamp,
                transition.target_satellite_id,
                is_aar_mode=False,
            )
        schedule.append((timestamp, transition.target_satellite_id))

    return sorted(schedule, key=lambda item: item[0])


def _falls_within_window(
    timestamp: datetime, windows: Sequence[ResolvedAARWindow]
) -> bool:
    for window in windows:
        if window.start_time <= timestamp <= window.end_time:
            return True
    return False


def _analyze_ka_coverage(
    samples: Sequence[RouteSample],
    projector: RouteTemporalProjector,
    coverage_enabled: bool,
) -> CoverageAnalysisResult:
    if not coverage_enabled or not samples:
        return CoverageAnalysisResult(gaps=[], swaps=[])

    gaps: list[KaCoverageGap] = []
    swaps: list[KaCoverageSwap] = []

    gap_state: KaCoverageGap | None = None
    overlap_state: dict | None = None

    if not samples[0].coverage:
        gap_state = KaCoverageGap(
            start=samples[0],
            end=None,
            lost_satellite=None,
            regained_satellite=None,
        )

    for idx in range(1, len(samples)):
        prev_sample = samples[idx - 1]
        curr_sample = samples[idx]
        prev_set = prev_sample.coverage
        curr_set = curr_sample.coverage

        if prev_set == curr_set:
            continue

        # Gap start
        if not curr_set and prev_set and gap_state is None:
            boundary = _interpolate_sample(projector, prev_sample, curr_sample)
            gap_state = KaCoverageGap(
                start=boundary,
                end=None,
                lost_satellite=_pick_satellite(prev_set),
                regained_satellite=None,
            )
            continue

        # Gap end
        if gap_state and curr_set:
            boundary = _interpolate_sample(projector, prev_sample, curr_sample)
            gap_state.end = boundary
            gap_state.regained_satellite = _pick_satellite(curr_set)
            is_same_satellite = (
                gap_state.lost_satellite
                and gap_state.lost_satellite == gap_state.regained_satellite
            )
            if (
                is_same_satellite
                and _looks_like_idl_gap(gap_state.start, gap_state.end)
            ):
                gap_state = None
                continue
            gaps.append(gap_state)
            gap_state = None

        # Overlap detection
        if len(curr_set) >= 2:
            if len(prev_set) == 1 and prev_set.issubset(curr_set):
                overlap_state = {
                    "from": _pick_satellite(prev_set),
                    "to": _pick_satellite(curr_set - prev_set),
                    "start": _interpolate_sample(projector, prev_sample, curr_sample),
                }
                continue
            elif overlap_state:
                overlap_state["last"] = curr_sample
                continue

        if overlap_state and len(curr_set) == 1 and curr_set == {overlap_state["to"]}:
            end_boundary = _interpolate_sample(
                projector, prev_sample, curr_sample
            )
            start_boundary = overlap_state.get("start", prev_sample)
            midpoint_distance = (
                start_boundary.distance_meters + end_boundary.distance_meters
            ) / 2.0
            midpoint = projector.sample_at_distance(midpoint_distance)
            swaps.append(
                KaCoverageSwap(
                    midpoint=midpoint,
                    from_satellite=overlap_state["from"],
                    to_satellite=overlap_state["to"],
                )
            )
            overlap_state = None

    if gap_state:
        gaps.append(gap_state)

    return CoverageAnalysisResult(gaps=gaps, swaps=swaps)


def _generate_timeline_samples(
    projector: RouteTemporalProjector,
    coverage_sampler: CoverageSampler | None,
    interval_seconds: int = TIMELINE_SAMPLE_INTERVAL_SECONDS,
) -> list[RouteSample]:
    """Generate minute-level samples along the mission timeline."""

    if interval_seconds <= 0:
        interval_seconds = TIMELINE_SAMPLE_INTERVAL_SECONDS

    samples: list[RouteSample] = []
    total_duration = max(projector.duration_seconds, 0.0)
    total_distance = projector.total_distance

    step = 0
    while True:
        elapsed = min(step * interval_seconds, total_duration)
        timestamp = projector.start_time + timedelta(seconds=elapsed)
        ratio = (elapsed / total_duration) if total_duration > 0 else 0.0
        distance = total_distance * ratio

        sample = projector.sample_at_distance(distance)
        # Ensure timestamp aligns with the simulation clock
        sample.timestamp = timestamp

        if coverage_sampler:
            sample.coverage = set(
                coverage_sampler.check_coverage_at_point(
                    sample.latitude, sample.longitude
                )
            )

        samples.append(sample)

        if elapsed >= total_duration:
            break

        step += 1

    _backfill_sample_headings(samples)
    return samples


def _backfill_sample_headings(samples: Sequence[RouteSample]) -> None:
    """Ensure every sample has a heading by propagating nearest known values."""

    last_heading: float | None = None
    for sample in samples:
        if sample.heading is None and last_heading is not None:
            sample.heading = last_heading
        if sample.heading is not None:
            last_heading = sample.heading

    last_heading = None
    for sample in reversed(samples):
        if sample.heading is None and last_heading is not None:
            sample.heading = last_heading
        if sample.heading is not None:
            last_heading = sample.heading

    if samples:
        samples[0].heading = None


def _interpolate_sample(
    projector: RouteTemporalProjector,
    prev_sample: RouteSample,
    next_sample: RouteSample,
) -> RouteSample:
    mid = (prev_sample.distance_meters + next_sample.distance_meters) / 2.0
    sample = projector.sample_at_distance(mid)
    sample.coverage = set()
    return sample


def _interpolate_altitude(
    prev_altitude: float | None,
    next_altitude: float | None,
    ratio: float,
) -> float:
    if prev_altitude is not None and next_altitude is not None:
        return prev_altitude + ratio * (next_altitude - prev_altitude)
    if prev_altitude is not None:
        return prev_altitude
    if next_altitude is not None:
        return next_altitude
    return DEFAULT_CRUISE_ALTITUDE_M


def _interpolate_longitude(prev_lon: float, next_lon: float, ratio: float) -> float:
    """Interpolate longitude across the dateline using the shortest path."""
    import math

    delta = ((next_lon - prev_lon + 540.0) % 360.0) - 180.0
    interpolated = prev_lon + delta * ratio
    # Normalize back to [-180, 180]
    interpolated = ((interpolated + 180.0) % 360.0) - 180.0
    # Handle edge case of -180 exactly
    if math.isclose(interpolated, -180.0):
        return 180.0
    return interpolated


def _pick_satellite(values: Iterable[str]) -> str | None:
    values = list(values)
    if not values:
        return None
    return sorted(values)[0]


def _apply_ka_events(
    rule_engine: RuleEngine,
    coverage: CoverageAnalysisResult,
) -> None:
    for gap in coverage.gaps:
        rule_engine.events.append(
            MissionEvent(
                timestamp=gap.start.timestamp,
                event_type=EventType.KA_COVERAGE_EXIT,
                transport=Transport.KA,
                affected_transport=Transport.KA,
                severity="warning",
                reason=_format_gap_reason("exit", gap.lost_satellite, gap.regained_satellite),
                satellite_id=gap.lost_satellite,
            )
        )

        if gap.end:
            rule_engine.events.append(
                MissionEvent(
                    timestamp=gap.end.timestamp,
                    event_type=EventType.KA_COVERAGE_ENTRY,
                    transport=Transport.KA,
                    affected_transport=Transport.KA,
                    severity="info",
                    reason=_format_gap_reason("entry", gap.lost_satellite, gap.regained_satellite),
                    satellite_id=gap.regained_satellite,
                )
            )

    if coverage.swaps:
        buffer = timedelta(minutes=rule_engine.config.transition_buffer_minutes)
        for idx, swap in enumerate(coverage.swaps):
            transition_id = f"{swap.from_satellite}->{swap.to_satellite}-{idx}"
            start_ts = swap.midpoint.timestamp - buffer
            end_ts = swap.midpoint.timestamp + buffer
            reason = f"Ka transition {swap.from_satellite} → {swap.to_satellite}"
            rule_engine.events.append(
                MissionEvent(
                    timestamp=start_ts,
                    event_type=EventType.KA_TRANSITION,
                    transport=Transport.KA,
                    affected_transport=Transport.KA,
                    severity="warning",
                    reason=reason,
                    satellite_id=f"{swap.from_satellite}->{swap.to_satellite}",
                    metadata={"transition_id": transition_id},
                )
            )
            rule_engine.events.append(
                MissionEvent(
                    timestamp=end_ts,
                    event_type=EventType.KA_TRANSITION,
                    transport=Transport.KA,
                    affected_transport=Transport.KA,
                    severity="info",
                    reason=f"{reason} complete",
                    satellite_id=f"{swap.from_satellite}->{swap.to_satellite}",
                    metadata={"transition_id": transition_id},
                )
            )


def _apply_x_azimuth_events(
    rule_engine: RuleEngine,
    mission: Mission,
    route: ParsedRoute,
    samples: Sequence[RouteSample],
    aar_windows: list[ResolvedAARWindow],
    transition_schedule: list[tuple[datetime, str]],
    poi_manager: POIManager | None,
    mission_start: datetime,
    mission_end: datetime,
) -> None:
    if not mission.transports.initial_x_satellite_id:
        return

    if not samples:
        return

    assignments = transition_schedule or []
    if not assignments:
        assignments = [(mission_start, mission.transports.initial_x_satellite_id)]
    assignments = sorted(assignments, key=lambda item: item[0])

    schedule_idx = 0
    current_satellite = assignments[0][1]
    violation_active = False

    for sample in samples:
        if sample.heading is None:
            continue
        in_aar_window = _falls_within_window(sample.timestamp, aar_windows)

        while (
            schedule_idx + 1 < len(assignments)
            and sample.timestamp >= assignments[schedule_idx + 1][0]
        ):
            schedule_idx += 1
            current_satellite = assignments[schedule_idx][1]

        satellite_longitude = _resolve_satellite_longitude(
            current_satellite, poi_manager
        )
        if satellite_longitude is None:
            continue

        altitude = sample.altitude if sample.altitude is not None else DEFAULT_CRUISE_ALTITUDE_M
        aft_violation, relative_azimuth, debug = rule_engine.evaluate_x_azimuth_window(
            aircraft_lat=sample.latitude,
            aircraft_lon=sample.longitude,
            aircraft_alt=altitude,
            satellite_lon=satellite_longitude,
            timestamp=sample.timestamp,
            heading_deg=sample.heading,
            is_aar_mode=False,
        )
        forward_violation = False
        if in_aar_window:
            forward_violation, _, _ = rule_engine.evaluate_x_azimuth_window(
                aircraft_lat=sample.latitude,
                aircraft_lon=sample.longitude,
                aircraft_alt=altitude,
                satellite_lon=satellite_longitude,
                timestamp=sample.timestamp,
                heading_deg=sample.heading,
                is_aar_mode=True,
            )

        violation_reason = debug.get("violation_reason")
        is_elevation_blocked = violation_reason == "elevation"

        nearest_wp = _nearest_waypoint_name(route, sample)
        debug.update(
            {
                "sample_latitude": sample.latitude,
                "sample_longitude": sample.longitude,
                "sample_timestamp": sample.timestamp.isoformat(),
                "satellite_longitude": satellite_longitude,
                "in_aar_window": in_aar_window,
                "nearest_waypoint_name": nearest_wp,
            }
        )

        is_violation = forward_violation or aft_violation
        if is_violation and not violation_active:
            if is_elevation_blocked:
                reason = _format_elevation_reason(
                    current_satellite,
                    float(debug.get("elevation_degrees", 0.0)),
                    float(debug.get("min_elevation_degrees", 0.0)),
                    debug_metadata=debug,
                )
            else:
                reason = _format_azimuth_reason(
                    current_satellite,
                    forward_violation,
                    aft_violation,
                    relative_azimuth,
                    in_aar_window,
                    debug_metadata=debug,
                )
            metadata: dict[str, float | bool | str | None] = {
                "relative_azimuth_degrees": round(relative_azimuth, 1),
                "absolute_azimuth_degrees": round(
                    float(debug.get("absolute_azimuth_degrees", relative_azimuth)), 1
                ),
                "elevation_degrees": round(
                    float(debug.get("elevation_degrees", 0.0)), 1
                ),
                "elevation_below_min": bool(debug.get("elevation_below_min", False)),
                "line_of_sight_blocked": is_elevation_blocked,
            }
            if sample.heading is not None:
                metadata["aircraft_heading_degrees"] = round(sample.heading, 1)
                metadata["absolute_azimuth_degrees"] = round(
                    (relative_azimuth + sample.heading) % 360.0, 1
                )
            metadata.update(
                {
                    "sample_latitude": round(sample.latitude, 5),
                    "sample_longitude": round(sample.longitude, 5),
                    "sample_timestamp": sample.timestamp.isoformat(),
                    "satellite_longitude": satellite_longitude,
                    "in_aar_window": in_aar_window,
                    "nearest_waypoint_name": nearest_wp,
                }
            )
            rule_engine.events.append(
                MissionEvent(
                    timestamp=sample.timestamp,
                    event_type=EventType.X_AZIMUTH_VIOLATION,
                    transport=Transport.X,
                    affected_transport=Transport.X,
                    severity="warning",
                    reason=reason,
                    satellite_id=current_satellite,
                    metadata=metadata,
                )
            )
            violation_active = True
        elif not is_violation and violation_active:
            rule_engine.events.append(
                MissionEvent(
                    timestamp=sample.timestamp,
                    event_type=EventType.X_AZIMUTH_VIOLATION,
                    transport=Transport.X,
                    affected_transport=Transport.X,
                    severity="info",
                    reason="X azimuth clear",
                    satellite_id=current_satellite,
                )
            )
            violation_active = False

    if violation_active:
        rule_engine.events.append(
            MissionEvent(
                timestamp=mission_end,
                event_type=EventType.X_AZIMUTH_VIOLATION,
                transport=Transport.X,
                affected_transport=Transport.X,
                severity="info",
                reason="X azimuth clear",
                satellite_id=current_satellite,
            )
        )


def _resolve_satellite_longitude(
    satellite_id: str, poi_manager: POIManager | None
) -> float | None:
    catalog = get_satellite_catalog()
    sat = catalog.get_satellite(satellite_id)
    if sat and sat.longitude is not None:
        return sat.longitude
    if poi_manager:
        poi = poi_manager.find_global_poi_by_name(satellite_id)
        if poi and poi.longitude is not None:
            return poi.longitude
    return None


def _format_azimuth_reason(
    satellite_id: str,
    forward_violation: bool,
    aft_violation: bool,
    azimuth: float,
    in_aar_window: bool,
    debug_metadata: dict | None = None,
) -> str:
    abs_az = float((debug_metadata or {}).get("absolute_azimuth_degrees", azimuth))
    elevation = float((debug_metadata or {}).get("elevation_degrees", 0.0))

    if aft_violation and not forward_violation and not in_aar_window:
        return f"X-Ku Conflict az={abs_az:.0f}° el={elevation:.0f}°"

    if forward_violation and not aft_violation and in_aar_window:
        return f"X-AAR Conflict az={abs_az:.0f}° el={elevation:.0f}°"

    if forward_violation and aft_violation:
        cone = "forward & aft cones"
    elif aft_violation:
        cone = "aft cone"
    else:
        cone = "forward cone"
    reason = f"X azimuth conflict ({satellite_id}, {cone}, {azimuth:.0f}° relative)"
    if debug_metadata:
        extras: list[str] = []
        abs_component = debug_metadata.get("absolute_azimuth_degrees")
        elevation_component = debug_metadata.get("elevation_degrees")
        if abs_component is not None:
            extras.append(f"abs={float(abs_component):.1f}°")
        if elevation_component is not None:
            extras.append(f"elev={float(elevation_component):.1f}°")
        if debug_metadata.get("elevation_below_min"):
            extras.append("elev_below_min")
        if extras:
            reason = f"{reason} [{' | '.join(extras)}]"
    return reason


def _format_elevation_reason(
    satellite_id: str,
    elevation: float,
    min_elevation: float,
    debug_metadata: dict | None = None,
) -> str:
    reason = (
        f"X line-of-sight blocked ({satellite_id}, elevation {elevation:.1f}° "
        f"< min {min_elevation:.1f}°)"
    )
    if debug_metadata:
        extras: list[str] = []
        abs_az = debug_metadata.get("absolute_azimuth_degrees")
        if abs_az is not None:
            extras.append(f"abs={float(abs_az):.1f}°")
        if debug_metadata.get("sample_latitude") is not None and debug_metadata.get(
            "sample_longitude"
        ) is not None:
            extras.append(
                "sample="
                f"{float(debug_metadata['sample_latitude']):.2f},"
                f"{float(debug_metadata['sample_longitude']):.2f}"
            )
        if debug_metadata.get("sample_timestamp"):
            extras.append(f"t={debug_metadata['sample_timestamp']}")
        if debug_metadata.get("nearest_waypoint_name"):
            extras.append(f"wp={debug_metadata['nearest_waypoint_name']}")
        if debug_metadata.get("satellite_longitude") is not None:
            extras.append(f"sat_lon={float(debug_metadata['satellite_longitude']):.1f}°")
        if extras:
            reason = f"{reason} [{' | '.join(extras)}]"
    return reason
def _nearest_waypoint_name(route: ParsedRoute, sample: RouteSample) -> str | None:
    """Return nearest waypoint name for debugging."""
    if not route.waypoints:
        return None

    closest_name: str | None = None
    closest_distance = float("inf")

    for waypoint in route.waypoints:
        if waypoint.latitude is None or waypoint.longitude is None:
            continue
        distance = _haversine_meters(
            sample.latitude,
            sample.longitude,
            waypoint.latitude,
            waypoint.longitude,
        )
        if distance < closest_distance:
            closest_distance = distance
            closest_name = waypoint.name or f"waypoint-{waypoint.order}"

    return closest_name


def _haversine_meters(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Compute haversine distance between two points in meters."""
    import math

    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _format_gap_reason(event: str, lost: str | None, regain: str | None) -> str:
    if event == "exit":
        return f"Ka coverage lost ({lost or 'unknown'})"
    return f"Ka coverage restored ({regain or 'unknown'})"


def _sync_ka_pois(
    mission: Mission,
    route: ParsedRoute,
    poi_manager: POIManager,
    coverage: CoverageAnalysisResult,
) -> None:
    deleted = poi_manager.delete_mission_pois_by_category(
        mission.id, KA_POI_CATEGORIES
    )
    deleted_prefix = poi_manager.delete_mission_pois_by_name_prefixes(
        mission.id, KA_POI_NAME_PREFIXES
    )
    route_cleanup = 0
    if mission.route_id:
        route_cleanup = poi_manager.delete_route_mission_pois_with_prefixes(
            mission.route_id,
            KA_POI_NAME_PREFIXES,
            exclude_mission_id=mission.id,
        )
    if deleted or deleted_prefix:
        logger.debug(
            "Deleted %d existing Ka mission POIs (category=%d, prefix=%d)",
            deleted + deleted_prefix,
            deleted,
            deleted_prefix,
        )
    if route_cleanup:
        logger.info(
            "Deleted %d Ka mission POIs on route %s (other missions)",
            route_cleanup,
            mission.route_id,
        )

    def create_poi(payload: POICreate):
        poi_manager.create_poi(payload, active_route=route)

    for gap in coverage.gaps:
        if gap.start:
            create_poi(
                POICreate(
                    name=_format_commka_exit_entry("Exit", gap.lost_satellite),
                    latitude=gap.start.latitude,
                    longitude=gap.start.longitude,
                    icon="satellite",
                    category=MISSION_EVENT_CATEGORY,
                    description=f"Loss at {gap.start.timestamp.isoformat()}",
                    route_id=mission.route_id,
                    mission_id=mission.id,
                )
            )
        if gap.end:
            create_poi(
                POICreate(
                    name=_format_commka_exit_entry("Enter", gap.regained_satellite),
                    latitude=gap.end.latitude,
                    longitude=gap.end.longitude,
                    icon="satellite",
                    category=MISSION_EVENT_CATEGORY,
                    description=f"Regain at {gap.end.timestamp.isoformat()}",
                    route_id=mission.route_id,
                    mission_id=mission.id,
                )
            )

    for swap in coverage.swaps:
        midpoint = swap.midpoint
        create_poi(
            POICreate(
                name=_format_commka_transition_label(
                    swap.from_satellite, swap.to_satellite
                ),
                latitude=midpoint.latitude,
                longitude=midpoint.longitude,
                icon="satellite",
                category=MISSION_EVENT_CATEGORY,
                description=f"Recommended swap near {midpoint.timestamp.isoformat()}",
                route_id=mission.route_id,
                mission_id=mission.id,
            )
        )


def _sync_x_aar_pois(
    mission: Mission,
    route: ParsedRoute,
    poi_manager: POIManager,
) -> None:
    deleted = poi_manager.delete_mission_pois_by_name_prefixes(
        mission.id, X_AAR_POI_PREFIXES
    )
    route_cleanup = 0
    if mission.route_id:
        route_cleanup = poi_manager.delete_route_mission_pois_with_prefixes(
            mission.route_id,
            X_AAR_POI_PREFIXES,
            exclude_mission_id=mission.id,
        )
    if deleted:
        logger.debug("Deleted %d existing X/AAR mission POIs", deleted)
    if route_cleanup:
        logger.info(
            "Deleted %d X/AAR mission POIs on route %s (other missions)",
            route_cleanup,
            mission.route_id,
        )

    transports = mission.transports
    if not transports:
        return

    def create(payload: POICreate):
        poi_manager.create_poi(payload, active_route=route)

    current_satellite = transports.initial_x_satellite_id
    for transition in transports.x_transitions or []:
        if transition.latitude is None or transition.longitude is None:
            continue
        label = _format_x_transition_label(
            current_satellite,
            transition.target_satellite_id,
            transition.is_same_satellite_transition,
        )
        create(
            POICreate(
                name=label,
                latitude=transition.latitude,
                longitude=transition.longitude,
                icon="satellite",
                category=MISSION_EVENT_CATEGORY,
                description=f"X transition target {transition.target_satellite_id or 'Unknown'}",
                route_id=mission.route_id,
                mission_id=mission.id,
            )
        )
        if (
            not transition.is_same_satellite_transition
            and transition.target_satellite_id
        ):
            current_satellite = transition.target_satellite_id

    for window in transports.aar_windows or []:
        start_coords = _find_waypoint_coordinates(route, window.start_waypoint_name)
        if start_coords:
            create(
                POICreate(
                    name="AAR\nStart",
                    latitude=start_coords[0],
                    longitude=start_coords[1],
                    icon="aar",
                    category=MISSION_EVENT_CATEGORY,
                    description=f"AAR window start ({window.start_waypoint_name})",
                    route_id=mission.route_id,
                    mission_id=mission.id,
                )
            )
        end_coords = _find_waypoint_coordinates(route, window.end_waypoint_name)
        if end_coords:
            create(
                POICreate(
                    name="AAR\nEnd",
                    latitude=end_coords[0],
                    longitude=end_coords[1],
                    icon="aar",
                    category=MISSION_EVENT_CATEGORY,
                    description=f"AAR window end ({window.end_waypoint_name})",
                    route_id=mission.route_id,
                    mission_id=mission.id,
                )
            )


def _apply_manual_outages(
    rule_engine: RuleEngine,
    outages: Sequence[KaOutage | KuOutageOverride] | None,
    transport: Transport,
) -> None:
    if not outages:
        return

    for outage in outages:
        start_time = outage.start_time
        duration = getattr(outage, "duration_seconds", 0) or 0
        end_time = start_time + timedelta(seconds=duration)
        reason = getattr(outage, "reason", None) or f"{transport.value} outage"
        rule_engine.add_manual_outage_events(start_time, end_time, transport, reason)


def _attach_statistics(
    timeline: MissionTimeline, mission_start: datetime, mission_end: datetime
) -> None:
    total_seconds = max((mission_end - mission_start).total_seconds(), 1.0)
    degraded_seconds = 0.0
    critical_seconds = 0.0
    for segment in timeline.segments:
        duration = (segment.end_time - segment.start_time).total_seconds()
        if duration <= 0:
            continue
        if segment.status == TimelineStatus.DEGRADED:
            degraded_seconds += duration
        elif segment.status == TimelineStatus.CRITICAL:
            critical_seconds += duration

    existing = timeline.statistics or {}
    preserved = {key: value for key, value in existing.items() if key.startswith("_")}
    timeline.statistics = {
        "total_duration_seconds": total_seconds,
        "degraded_seconds": degraded_seconds,
        "critical_seconds": critical_seconds,
        "nominal_seconds": total_seconds - degraded_seconds - critical_seconds,
    }
    timeline.statistics.update(preserved)


def _summarize_timeline(
    timeline: MissionTimeline,
    mission_start: datetime,
    mission_end: datetime,
    sample_count: int,
    sample_interval_seconds: int,
    generation_runtime_ms: float,
) -> TimelineSummary:
    severity_order = {
        TransportState.AVAILABLE: 0,
        TransportState.DEGRADED: 1,
        TransportState.OFFLINE: 2,
    }
    transport_states: dict[Transport, TransportState] = {
        Transport.X: TransportState.AVAILABLE,
        Transport.KA: TransportState.AVAILABLE,
        Transport.KU: TransportState.AVAILABLE,
    }

    degraded_seconds = 0.0
    critical_seconds = 0.0
    conflict_start: datetime | None = None

    for segment in timeline.segments:
        duration = (segment.end_time - segment.start_time).total_seconds()
        if duration <= 0:
            continue

        if segment.status == TimelineStatus.DEGRADED:
            degraded_seconds += duration
        elif segment.status == TimelineStatus.CRITICAL:
            critical_seconds += duration

        if segment.status != TimelineStatus.NOMINAL and conflict_start is None:
            conflict_start = segment.start_time

        for transport, state in (
            (Transport.X, segment.x_state),
            (Transport.KA, segment.ka_state),
            (Transport.KU, segment.ku_state),
        ):
            if severity_order[state] > severity_order[transport_states[transport]]:
                transport_states[transport] = state

    next_conflict_seconds = (
        (conflict_start - mission_start).total_seconds() if conflict_start else -1.0
    )

    return TimelineSummary(
        mission_start=mission_start,
        mission_end=mission_end,
        degraded_seconds=degraded_seconds,
        critical_seconds=critical_seconds,
        next_conflict_seconds=next_conflict_seconds,
        transport_states=transport_states,
        sample_count=sample_count,
        sample_interval_seconds=sample_interval_seconds,
        generation_runtime_ms=generation_runtime_ms,
    )


def _get_default_coverage_sampler() -> CoverageSampler | None:
    global _COVERAGE_SAMPLER
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
def _format_commka_exit_entry(kind: str, satellite: str | None) -> str:
    # Simplified: no satellite name, just Exit or Entry
    return f"CommKa\n{kind}"


def _format_commka_transition_label(
    from_satellite: str | None, to_satellite: str | None
) -> str:
    # Simplified: all CommKa swaps show as "CommKa\nSwap"
    return "CommKa\nSwap"


def _format_x_transition_label(
    current_satellite: str | None,
    target_satellite: str | None,
    is_same_satellite: bool,
) -> str:
    # Simplified: all X-Band swaps show as "X-Band\nSwap"
    return "X-Band\nSwap"


def _find_waypoint_coordinates(
    route: ParsedRoute, waypoint_name: str | None
) -> tuple[float, float] | None:
    if not route or not waypoint_name:
        return None
    normalized = waypoint_name.strip().lower()
    for waypoint in route.waypoints or []:
        name = (waypoint.name or f"waypoint-{waypoint.order}").strip().lower()
        if name == normalized and waypoint.latitude is not None and waypoint.longitude is not None:
            return waypoint.latitude, waypoint.longitude
    return None


def _looks_like_idl_gap(
    start_sample: RouteSample | None, end_sample: RouteSample | None
) -> bool:
    if not start_sample or not end_sample:
        return False
    lon_diff = abs(start_sample.longitude - end_sample.longitude)
    return lon_diff > 300.0
