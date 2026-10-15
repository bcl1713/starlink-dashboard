"""Coverage analysis for Ka satellite coverage gaps and swaps."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.mission.timeline_builder.calculator import RouteTemporalProjector

from app.mission.models import KaCoverageEvent
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
    coverage_events: list[KaCoverageEvent] = field(default_factory=list)


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
    coverage_events = [
        KaCoverageEvent(
            timestamp=samples[0].timestamp,
            event_type="starting",
            reason="Starting Ka coverage: "
            + (", ".join(sorted(samples[0].coverage)) or "unavailable"),
            coverage=sorted(samples[0].coverage),
        )
    ]

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

        boundary = _interpolate_sample(projector, prev_sample, curr_sample)
        for event_type, satellites in (
            ("entry", curr_set - prev_set),
            ("exit", prev_set - curr_set),
        ):
            for satellite in sorted(satellites):
                coverage_events.append(
                    KaCoverageEvent(
                        timestamp=boundary.timestamp,
                        event_type=event_type,
                        satellite_id=satellite,
                        coverage=sorted(curr_set),
                        reason=f"{satellite} footprint {event_type}",
                    )
                )
        if not curr_set or not prev_set:
            event_type = "restored" if curr_set else "lost"
            coverage_events.append(
                KaCoverageEvent(
                    timestamp=boundary.timestamp,
                    event_type=event_type,
                    coverage=sorted(curr_set),
                    reason=f"Ka coverage {event_type}",
                )
            )

        # Gap start
        if not curr_set and prev_set and gap_state is None:
            gap_state = KaCoverageGap(
                start=boundary,
                end=None,
                lost_satellite=pick_satellite(prev_set),
                regained_satellite=None,
            )
            overlap_state = None
            continue

        # Gap end
        if gap_state and curr_set:
            gap_state.end = boundary
            gap_state.regained_satellite = pick_satellite(curr_set)
            gaps.append(gap_state)
            gap_state = None

        # Overlap detection
        if len(curr_set) >= 2:
            if len(prev_set) == 1 and prev_set.issubset(curr_set):
                overlap_state = {
                    "from": pick_satellite(prev_set),
                    "to": pick_satellite(curr_set - prev_set),
                    "start": boundary,
                }
                continue
            elif overlap_state:
                overlap_state["last"] = curr_sample
                continue

        if overlap_state and len(curr_set) == 1 and curr_set == {overlap_state["to"]}:
            end_boundary = boundary
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
            coverage_events.append(
                KaCoverageEvent(
                    timestamp=midpoint.timestamp,
                    event_type="handoff",
                    coverage=sorted({overlap_state["from"], overlap_state["to"]}),
                    reason=f"Recommended handoff {overlap_state['from']} → {overlap_state['to']}",
                )
            )
            overlap_state = None
        elif overlap_state and len(curr_set) < 2:
            overlap_state = None

    if gap_state:
        gaps.append(gap_state)

    return CoverageAnalysisResult(
        gaps=gaps,
        swaps=swaps,
        coverage_events=sorted(coverage_events, key=lambda event: event.timestamp),
    )


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
