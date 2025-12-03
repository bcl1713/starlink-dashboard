"""Timeline computation module for mission planning.

This module provides comprehensive timeline generation capabilities including:
- Route-based temporal projection and sampling
- Ka coverage analysis (gaps and swap opportunities)
- X-band azimuth violation detection
- AAR window resolution
- POI synchronization for mission events
- Timeline statistics and summaries
"""

from app.mission.timeline_builder.calculator import (
    TimelineComputationError,
    RouteTemporalProjector,
    RouteProjection,
    derive_mission_window,
    generate_timeline_samples,
    TIMELINE_SAMPLE_INTERVAL_SECONDS,
)
from app.mission.timeline_builder.coverage import (
    RouteSample,
    KaCoverageGap,
    KaCoverageSwap,
    CoverageAnalysisResult,
    analyze_ka_coverage,
)
from app.mission.timeline_builder.events import (
    apply_ka_events,
    apply_x_azimuth_events,
    apply_manual_outages,
)
from app.mission.timeline_builder.aar import (
    ResolvedAARWindow,
    resolve_aar_windows,
    apply_x_transitions,
)
from app.mission.timeline_builder.pois import (
    sync_ka_pois,
    sync_x_aar_pois,
)
from app.mission.timeline_builder.stats import (
    TimelineSummary,
    annotate_aar_markers,
    attach_statistics,
    summarize_timeline,
)
from app.mission.timeline_builder.utils import (
    DEFAULT_CRUISE_ALTITUDE_M,
    ensure_datetime,
    interpolate_altitude,
    interpolate_longitude,
    haversine_meters,
    pick_satellite,
    nearest_waypoint_name,
    find_waypoint_coordinates,
    timestamp_for_waypoint,
)

__all__ = [
    # Calculator
    "TimelineComputationError",
    "RouteTemporalProjector",
    "RouteProjection",
    "derive_mission_window",
    "generate_timeline_samples",
    "TIMELINE_SAMPLE_INTERVAL_SECONDS",
    # Coverage
    "RouteSample",
    "KaCoverageGap",
    "KaCoverageSwap",
    "CoverageAnalysisResult",
    "analyze_ka_coverage",
    # Events
    "apply_ka_events",
    "apply_x_azimuth_events",
    "apply_manual_outages",
    # AAR
    "ResolvedAARWindow",
    "resolve_aar_windows",
    "apply_x_transitions",
    # POIs
    "sync_ka_pois",
    "sync_x_aar_pois",
    # Stats
    "TimelineSummary",
    "annotate_aar_markers",
    "attach_statistics",
    "summarize_timeline",
    # Utils
    "DEFAULT_CRUISE_ALTITUDE_M",
    "ensure_datetime",
    "interpolate_altitude",
    "interpolate_longitude",
    "haversine_meters",
    "pick_satellite",
    "nearest_waypoint_name",
    "find_waypoint_coordinates",
    "timestamp_for_waypoint",
]
