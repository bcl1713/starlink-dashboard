"""Coverage analysis for Ka satellite coverage gaps and swaps."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from app.mission.timeline_builder.calculator import RouteTemporalProjector

from app.mission.timeline_builder.utils import pick_satellite

logger = logging.getLogger(__name__)


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


def analyze_ka_coverage(
    samples: Sequence[RouteSample],
    projector: RouteTemporalProjector,
    coverage_enabled: bool,
) -> CoverageAnalysisResult:
    """Analyze Ka coverage along the route to detect gaps and swap opportunities."""
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
                lost_satellite=pick_satellite(prev_set),
                regained_satellite=None,
            )
            continue

        # Gap end
        if gap_state and curr_set:
            boundary = _interpolate_sample(projector, prev_sample, curr_sample)
            gap_state.end = boundary
            gap_state.regained_satellite = pick_satellite(curr_set)
            is_same_satellite = (
                gap_state.lost_satellite
                and gap_state.lost_satellite == gap_state.regained_satellite
            )
            if is_same_satellite and _looks_like_idl_gap(
                gap_state.start, gap_state.end
            ):
                gap_state = None
                continue
            gaps.append(gap_state)
            gap_state = None

        # Overlap detection
        if len(curr_set) >= 2:
            if len(prev_set) == 1 and prev_set.issubset(curr_set):
                overlap_state = {
                    "from": pick_satellite(prev_set),
                    "to": pick_satellite(curr_set - prev_set),
                    "start": _interpolate_sample(projector, prev_sample, curr_sample),
                }
                continue
            elif overlap_state:
                overlap_state["last"] = curr_sample
                continue

        if overlap_state and len(curr_set) == 1 and curr_set == {overlap_state["to"]}:
            end_boundary = _interpolate_sample(projector, prev_sample, curr_sample)
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


def _interpolate_sample(
    projector: RouteTemporalProjector,
    prev_sample: RouteSample,
    next_sample: RouteSample,
) -> RouteSample:
    """Interpolate a sample between two existing samples."""
    mid = (prev_sample.distance_meters + next_sample.distance_meters) / 2.0
    sample = projector.sample_at_distance(mid)
    sample.coverage = set()
    return sample


def _looks_like_idl_gap(
    start_sample: RouteSample | None, end_sample: RouteSample | None
) -> bool:
    """Check if gap appears to be due to International Date Line crossing."""
    if not start_sample or not end_sample:
        return False
    lon_diff = abs(start_sample.longitude - end_sample.longitude)
    return lon_diff > 300.0
