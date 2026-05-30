"""AAR window resolution and X-band transition scheduling."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.mission.models import MissionLeg
from app.models.route import ParsedRoute
from app.satellites.rules import RuleEngine
from app.mission.timeline_builder.calculator import (
    RouteTemporalProjector,
    ensure_timezone,
)
from app.mission.timeline_builder.utils import timestamp_for_waypoint

logger = logging.getLogger(__name__)


@dataclass
class ResolvedAARWindow:
    """AAR window with route-aligned timestamps."""

    name: str
    start_time: datetime
    end_time: datetime


def resolve_aar_windows(
    mission: MissionLeg,
    route: ParsedRoute,
    projector: RouteTemporalProjector,
) -> list[ResolvedAARWindow]:
    """Resolve AAR window timestamps from waypoint names."""
    windows: list[ResolvedAARWindow] = []
    if not mission.transports.aar_windows:
        return windows

    waypoint_lookup = {wp.name: wp for wp in route.waypoints if wp.name}

    for idx, window in enumerate(mission.transports.aar_windows or []):
        start_wp = waypoint_lookup.get(window.start_waypoint_name)
        end_wp = waypoint_lookup.get(window.end_waypoint_name)
        route_start_time = timestamp_for_waypoint(start_wp, projector)
        route_end_time = timestamp_for_waypoint(end_wp, projector)
        if window.override_start_elapsed:
            if route_start_time is None or route_end_time is None:
                logger.warning(
                    "Skipping AAR window %s: T+ override requires route waypoint times",
                    window.id or idx + 1,
                )
                continue
            duration = ensure_timezone(route_end_time) - ensure_timezone(route_start_time)
            try:
                elapsed_offset = parse_elapsed_offset(window.override_start_elapsed)
            except ValueError as exc:
                logger.warning(
                    "Skipping AAR window %s: invalid T+ override %r (%s)",
                    window.id or idx + 1,
                    window.override_start_elapsed,
                    exc,
                )
                continue
            start_time = ensure_timezone(projector.start_time) + elapsed_offset
            end_time = start_time + duration
        else:
            start_time = window.override_start_time
            end_time = window.override_end_time
            if start_time is None or end_time is None:
                start_time = route_start_time
                end_time = route_end_time
        if not start_time or not end_time or end_time <= start_time:
            continue
        # Ensure times are timezone-aware for consistent comparison
        start_time = ensure_timezone(start_time)
        end_time = ensure_timezone(end_time)
        windows.append(
            ResolvedAARWindow(
                name=window.id or f"AAR-{idx + 1}",
                start_time=start_time,
                end_time=end_time,
            )
        )

    return windows


def parse_elapsed_offset(value: str) -> timedelta:
    """Parse flight-deck mission elapsed values such as T+02:15."""

    raw = value.strip().upper()
    if raw.startswith("T+"):
        raw = raw[2:]
    parts = raw.split(":")
    if len(parts) not in (2, 3):
        raise ValueError("Elapsed AAR override must use T+HH:MM or T+HH:MM:SS")
    hours, minutes = int(parts[0]), int(parts[1])
    seconds = int(parts[2]) if len(parts) == 3 else 0
    if hours < 0 or minutes < 0 or seconds < 0 or minutes >= 60 or seconds >= 60:
        raise ValueError("Elapsed AAR override contains invalid time fields")
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)


def apply_x_transitions(
    rule_engine: RuleEngine,
    mission: MissionLeg,
    projector: RouteTemporalProjector,
    aar_windows: list[ResolvedAARWindow],
) -> list[tuple[datetime, str]]:
    """Apply X-band transition events and return the transition schedule."""
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


def _falls_within_window(timestamp: datetime, windows: list[ResolvedAARWindow]) -> bool:
    """Check if timestamp falls within any AAR window."""
    for window in windows:
        if window.start_time <= timestamp <= window.end_time:
            return True
    return False
