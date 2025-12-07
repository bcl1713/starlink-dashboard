"""Core timeline calculation and route projection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from app.satellites.coverage import CoverageSampler

from app.models.route import ParsedRoute
from app.services.route_eta_calculator import RouteETACalculator
from app.simulation.route import calculate_bearing
from app.mission.timeline_builder.coverage import RouteSample
from app.mission.timeline_builder.utils import (
    DEFAULT_CRUISE_ALTITUDE_M,
    interpolate_altitude,
    interpolate_longitude,
)

logger = logging.getLogger(__name__)

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
            segment = self.calculator._haversine_distance(
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
                altitude=(
                    point.altitude
                    if point.altitude is not None
                    else DEFAULT_CRUISE_ALTITUDE_M
                ),
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
                lon = interpolate_longitude(
                    prev_point.longitude, next_point.longitude, ratio
                )
                altitude = interpolate_altitude(
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


def derive_mission_window(route: ParsedRoute) -> tuple[datetime, datetime]:
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


def generate_timeline_samples(
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
