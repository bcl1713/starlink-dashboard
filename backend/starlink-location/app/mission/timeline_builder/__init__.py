"""Timeline computation module for mission planning.

This module provides comprehensive timeline generation capabilities including:
- Route-based temporal projection and sampling
- Ka coverage analysis (gaps and swap opportunities)
- X-band azimuth violation detection
- AAR window resolution
- POI synchronization for mission events
- Timeline statistics and summaries
"""

from app.mission.timeline_builder.aar import (
    ResolvedAARWindow,
    apply_x_transitions,
    resolve_aar_windows,
)
from app.mission.timeline_builder.calculator import (
    TIMELINE_SAMPLE_INTERVAL_SECONDS,
    RouteProjection,
    RouteTemporalProjector,
    TimelineComputationError,
    derive_mission_window,
    generate_timeline_samples,
    route_takeoff_delta,
    route_with_adjusted_departure,
)
from app.mission.timeline_builder.coverage import (
    CoverageAnalysisResult,
    KaCoverageGap,
    KaCoverageSwap,
    RouteSample,
    analyze_ka_coverage,
)
from app.mission.timeline_builder.events import (
    apply_ka_events,
    apply_manual_outages,
    apply_x_azimuth_events,
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
    find_waypoint_coordinates,
    haversine_meters,
    interpolate_altitude,
    interpolate_longitude,
    nearest_waypoint_name,
    pick_satellite,
    timestamp_for_waypoint,
)

__all__ = [
    # Utils
    "DEFAULT_CRUISE_ALTITUDE_M",
    "TIMELINE_SAMPLE_INTERVAL_SECONDS",
    "CoverageAnalysisResult",
    "KaCoverageGap",
    "KaCoverageSwap",
    # AAR
    "ResolvedAARWindow",
    "RouteProjection",
    # Coverage
    "RouteSample",
    "RouteTemporalProjector",
    # Calculator
    "TimelineComputationError",
    # Stats
    "TimelineSummary",
    "analyze_ka_coverage",
    "annotate_aar_markers",
    # Events
    "apply_ka_events",
    "apply_manual_outages",
    "apply_x_azimuth_events",
    "apply_x_transitions",
    "attach_statistics",
    "derive_mission_window",
    "ensure_datetime",
    "find_waypoint_coordinates",
    "generate_timeline_samples",
    "haversine_meters",
    "interpolate_altitude",
    "interpolate_longitude",
    "nearest_waypoint_name",
    "pick_satellite",
    "resolve_aar_windows",
    "route_takeoff_delta",
    "route_with_adjusted_departure",
    "summarize_timeline",
    # POIs
    "sync_ka_pois",
    "sync_x_aar_pois",
    "timestamp_for_waypoint",
]
