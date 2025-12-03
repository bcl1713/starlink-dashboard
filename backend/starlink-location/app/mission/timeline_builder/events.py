"""Event application logic for mission timeline generation."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from app.mission.timeline_builder.aar import ResolvedAARWindow
from app.mission.models import MissionLeg, Transport, KaOutage, KuOutageOverride
from app.models.route import ParsedRoute
from app.satellites.rules import EventType, MissionEvent, RuleEngine
from app.satellites.catalog import get_satellite_catalog
from app.services.poi_manager import POIManager
from app.mission.timeline_builder.coverage import (
    CoverageAnalysisResult,
    RouteSample,
)
from app.mission.timeline_builder.utils import (
    DEFAULT_CRUISE_ALTITUDE_M,
    nearest_waypoint_name,
)

logger = logging.getLogger(__name__)


def apply_ka_events(
    rule_engine: RuleEngine,
    coverage: CoverageAnalysisResult,
) -> None:
    """Apply Ka coverage gap and swap events to the rule engine."""
    for gap in coverage.gaps:
        rule_engine.events.append(
            MissionEvent(
                timestamp=gap.start.timestamp,
                event_type=EventType.KA_COVERAGE_EXIT,
                transport=Transport.KA,
                affected_transport=Transport.KA,
                severity="warning",
                reason=_format_gap_reason(
                    "exit", gap.lost_satellite, gap.regained_satellite
                ),
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
                    reason=_format_gap_reason(
                        "entry", gap.lost_satellite, gap.regained_satellite
                    ),
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


def apply_x_azimuth_events(
    rule_engine: RuleEngine,
    mission: MissionLeg,
    route: ParsedRoute,
    samples: Sequence[RouteSample],
    aar_windows: list[ResolvedAARWindow],
    transition_schedule: list[tuple[datetime, str]],
    poi_manager: POIManager | None,
    mission_start: datetime,
    mission_end: datetime,
) -> None:
    """Apply X-band azimuth violation events."""
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

        altitude = (
            sample.altitude
            if sample.altitude is not None
            else DEFAULT_CRUISE_ALTITUDE_M
        )
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

        nearest_wp = nearest_waypoint_name(route, sample.latitude, sample.longitude)
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


def apply_manual_outages(
    rule_engine: RuleEngine,
    outages: Sequence[KaOutage | KuOutageOverride] | None,
    transport: Transport,
) -> None:
    """Apply manually configured outages to the timeline."""
    if not outages:
        return

    for outage in outages:
        start_time = outage.start_time
        duration = getattr(outage, "duration_seconds", 0) or 0
        end_time = start_time + timedelta(seconds=duration)
        reason = getattr(outage, "reason", None) or f"{transport.value} outage"
        rule_engine.add_manual_outage_events(start_time, end_time, transport, reason)


def _format_gap_reason(event: str, lost: str | None, regain: str | None) -> str:
    """Format reason string for Ka coverage gap events."""
    if event == "exit":
        return f"Ka coverage lost ({lost or 'unknown'})"
    return f"Ka coverage restored ({regain or 'unknown'})"


def _format_azimuth_reason(
    satellite_id: str,
    forward_violation: bool,
    aft_violation: bool,
    azimuth: float,
    in_aar_window: bool,
    debug_metadata: dict | None = None,
) -> str:
    """Format reason string for X-band azimuth violations."""
    # abs_az = float((debug_metadata or {}).get("absolute_azimuth_degrees", azimuth))
    rel_az = float((debug_metadata or {}).get("relative_azimuth_degrees", azimuth))
    elevation = float((debug_metadata or {}).get("elevation_degrees", 0.0))

    if aft_violation and not forward_violation and not in_aar_window:
        return f"X-Ku Conflict az={rel_az:.0f}° el={elevation:.0f}°"

    if forward_violation and not aft_violation and in_aar_window:
        return f"X-AAR Conflict az={rel_az:.0f}° el={elevation:.0f}°"

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
    """Format reason string for elevation violations."""
    reason = (
        f"X line-of-sight blocked ({satellite_id}, elevation {elevation:.1f}° "
        f"< min {min_elevation:.1f}°)"
    )
    if debug_metadata:
        extras: list[str] = []
        abs_az = debug_metadata.get("absolute_azimuth_degrees")
        if abs_az is not None:
            extras.append(f"abs={float(abs_az):.1f}°")
        if (
            debug_metadata.get("sample_latitude") is not None
            and debug_metadata.get("sample_longitude") is not None
        ):
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
            extras.append(
                f"sat_lon={float(debug_metadata['satellite_longitude']):.1f}°"
            )
        if extras:
            reason = f"{reason} [{' | '.join(extras)}]"
    return reason


def _resolve_satellite_longitude(
    satellite_id: str, poi_manager: POIManager | None
) -> float | None:
    """Resolve satellite longitude from catalog or POI manager."""
    catalog = get_satellite_catalog()
    sat = catalog.get_satellite(satellite_id)
    if sat and sat.longitude is not None:
        return sat.longitude
    if poi_manager:
        poi = poi_manager.find_global_poi_by_name(satellite_id)
        if poi and poi.longitude is not None:
            return poi.longitude
    return None


def _falls_within_window(
    timestamp: datetime, windows: Sequence[ResolvedAARWindow]
) -> bool:
    """Check if timestamp falls within any AAR window."""
    for window in windows:
        if window.start_time <= timestamp <= window.end_time:
            return True
    return False
