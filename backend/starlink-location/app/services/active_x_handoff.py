"""Position-based active X-band satellite handoff resolution."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.mission.models import MissionLeg, XTransition
from app.models.route import ParsedRoute
from app.models.telemetry import TelemetryData
from app.services.route_eta_calculator import RouteETACalculator

logger = logging.getLogger(__name__)

HANDOFF_ZONE_RADIUS_METERS = 200_000.0


@dataclass
class XHandoffTracker:
    """In-process guard state for live X-band handoff transitions."""

    armed_transition_ids: set[str] = field(default_factory=set)
    committed_transition_ids: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class ActiveXContext:
    """Current and pending X-band satellite context for a live position."""

    current_satellite_id: str | None
    pending_satellite_id: str | None
    handoff: dict[str, Any]


_HANDOFF_TRACKERS: dict[str, XHandoffTracker] = {}


def reset_x_handoff_state() -> None:
    """Reset live handoff memory.

    This is primarily for tests; production state is intentionally process-local
    so a committed handoff does not flap if the aircraft jitters back into the
    geographic transition bubble.
    """

    _HANDOFF_TRACKERS.clear()


def empty_handoff_context(route_progress: float | None = None) -> dict[str, Any]:
    """Return the default handoff context payload."""

    return {
        "phase": "outside",
        "transition_id": None,
        "transition_satellite_id": None,
        "radius_meters": HANDOFF_ZONE_RADIUS_METERS,
        "distance_to_transition_meters": None,
        "in_handoff_zone": False,
        "route_progress_percent": route_progress,
        "transition_progress_percent": None,
    }


def resolve_active_x_context(
    leg: MissionLeg,
    route: ParsedRoute | None,
    telemetry: TelemetryData,
) -> ActiveXContext:
    """Resolve live active and pending X satellites from actual position."""

    current_satellite = leg.transports.initial_x_satellite_id
    if not current_satellite:
        return ActiveXContext(None, None, empty_handoff_context())
    if route is None or not leg.transports.x_transitions:
        return ActiveXContext(current_satellite, None, empty_handoff_context())

    current_progress = _project_progress(
        route,
        telemetry.position.latitude,
        telemetry.position.longitude,
    )
    if current_progress is None:
        return ActiveXContext(current_satellite, None, empty_handoff_context())

    tracker = _tracker_for(leg, route)
    latest_handoff = empty_handoff_context(route_progress=current_progress)
    transitions = _project_transitions(route, leg.transports.x_transitions)

    for transition_progress, transition in transitions:
        if not transition.target_satellite_id:
            continue
        handoff = _handoff_context(
            transition=transition,
            transition_progress=transition_progress,
            telemetry=telemetry,
            route_progress=current_progress,
        )
        if transition.id in tracker.committed_transition_ids:
            current_satellite = transition.target_satellite_id
            latest_handoff = {**handoff, "phase": "committed"}
            continue

        in_zone = bool(handoff["in_handoff_zone"])
        has_passed = current_progress >= transition_progress
        if in_zone:
            tracker.armed_transition_ids.add(transition.id)
            return ActiveXContext(
                current_satellite,
                transition.target_satellite_id,
                {**handoff, "phase": "in_handoff_zone"},
            )
        if has_passed and transition.id in tracker.armed_transition_ids:
            tracker.committed_transition_ids.add(transition.id)
            current_satellite = transition.target_satellite_id
            latest_handoff = {**handoff, "phase": "committed"}
            continue
        return ActiveXContext(current_satellite, None, {**handoff, "phase": "outside"})

    return ActiveXContext(current_satellite, None, latest_handoff)


def _project_transitions(
    route: ParsedRoute,
    transitions: list[XTransition],
) -> list[tuple[float, XTransition]]:
    projected: list[tuple[float, XTransition]] = []
    for transition in transitions:
        progress = _project_progress(route, transition.latitude, transition.longitude)
        if progress is not None:
            projected.append((progress, transition))
    return sorted(projected, key=lambda item: item[0])


def _tracker_for(leg: MissionLeg, route: ParsedRoute) -> XHandoffTracker:
    transition_ids = ",".join(
        transition.id for transition in leg.transports.x_transitions or []
    )
    key = f"{leg.id}:{_route_id(route) or ''}:{transition_ids}"
    return _HANDOFF_TRACKERS.setdefault(key, XHandoffTracker())


def _route_id(route: ParsedRoute) -> str | None:
    file_path = route.metadata.file_path
    if not file_path:
        return None
    return Path(file_path).stem


def _handoff_context(
    transition: XTransition,
    transition_progress: float,
    telemetry: TelemetryData,
    route_progress: float,
) -> dict[str, Any]:
    aircraft = telemetry.position
    distance_meters = _distance_meters(
        aircraft.latitude,
        aircraft.longitude,
        transition.latitude,
        transition.longitude,
    )
    return {
        "phase": "outside",
        "transition_id": transition.id,
        "transition_satellite_id": transition.target_satellite_id,
        "radius_meters": HANDOFF_ZONE_RADIUS_METERS,
        "distance_to_transition_meters": round(distance_meters, 1),
        "in_handoff_zone": distance_meters <= HANDOFF_ZONE_RADIUS_METERS,
        "route_progress_percent": round(route_progress, 6),
        "transition_progress_percent": round(transition_progress, 6),
    }


def _project_progress(
    route: ParsedRoute,
    latitude: float,
    longitude: float,
) -> float | None:
    try:
        projection = RouteETACalculator(route).project_poi_to_route(latitude, longitude)
    except Exception as exc:  # pragma: no cover - defensive geometry guard
        logger.debug("Failed to project active X link point onto route: %s", exc)
        return None
    progress = projection.get("projected_route_progress")
    return float(progress) if progress is not None else None


def _distance_meters(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    radius_meters = 6_371_000.0
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    return radius_meters * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
