"""Active X-band satellite link overlay data builder."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

from app.mission import storage
from app.mission.models import MissionLeg, XTransition
from app.models.poi import POI
from app.models.route import ParsedRoute
from app.models.telemetry import TelemetryData
from app.satellites.geometry import is_in_azimuth_range
from app.satellites.rules import RuleEngine
from app.services.route_eta_calculator import RouteETACalculator

logger = logging.getLogger(__name__)

LinkState = Literal["normal", "warning"]


def empty_active_x_link(state: str | None = None) -> dict[str, Any]:
    """Return an empty, Grafana-friendly active-X link response."""
    return {
        "coordinates": [],
        "total": 0,
        "satellite_id": None,
        "state": state,
        "color": None,
        "relative_azimuth_degrees": None,
        "in_forbidden_window": None,
    }


def build_active_x_link(
    coordinator: Any,
    route_manager: Any,
    poi_manager: Any,
    state_filter: LinkState | None = None,
) -> dict[str, Any]:
    """Build a two-point route from aircraft to active X-band satellite.

    The active satellite is resolved from the active mission leg. X transitions
    are ordered by their projected progress along the active route, matching the
    mission timeline's route-projection semantics for live route-following use.
    The visual state is derived from the existing normal X-band forbidden
    relative-azimuth rule window (135°–225°).
    """
    try:
        telemetry = coordinator.get_current_telemetry() if coordinator else None
    except Exception as exc:  # pragma: no cover - defensive live-mode guard
        logger.debug("Active X link unavailable: telemetry missing: %s", exc)
        return empty_active_x_link(state_filter)

    if telemetry is None:
        return empty_active_x_link(state_filter)

    route = route_manager.get_active_route() if route_manager else None
    active_leg = _find_active_mission_leg(route)
    if active_leg is None:
        return empty_active_x_link(state_filter)

    satellite_id = _resolve_active_satellite_id(active_leg, route, telemetry)
    if not satellite_id:
        return empty_active_x_link(state_filter)

    satellite = _find_satellite_poi(poi_manager, satellite_id)
    if satellite is None:
        return empty_active_x_link(state_filter)

    link_state, color, relative_azimuth, in_forbidden = _evaluate_link_state(
        telemetry, satellite
    )
    if state_filter is not None and link_state != state_filter:
        return {
            **empty_active_x_link(state_filter),
            "satellite_id": satellite_id,
            "state": link_state,
            "color": color,
            "relative_azimuth_degrees": relative_azimuth,
            "in_forbidden_window": in_forbidden,
        }

    aircraft = telemetry.position
    common = {
        "satellite_id": satellite_id,
        "state": link_state,
        "color": color,
        "relative_azimuth_degrees": relative_azimuth,
        "in_forbidden_window": in_forbidden,
    }
    coordinates = [
        {
            **common,
            "point": "aircraft",
            "sequence": 0,
            "latitude": aircraft.latitude,
            "longitude": aircraft.longitude,
        },
        {
            **common,
            "point": "satellite",
            "sequence": 1,
            "latitude": satellite.latitude,
            "longitude": satellite.longitude,
        },
    ]
    return {**common, "coordinates": coordinates, "total": len(coordinates)}


def _find_active_mission_leg(route: ParsedRoute | None = None) -> MissionLeg | None:
    missions_dir = storage.MISSIONS_DIR
    if not missions_dir.exists():
        return None

    active_route_id = _route_id(route) if route is not None else None
    first_active_leg: MissionLeg | None = None
    for mission_dir in sorted(missions_dir.iterdir()):
        if not mission_dir.is_dir():
            continue
        mission = storage.load_mission_v2(mission_dir.name)
        if mission is None:
            continue
        for leg in mission.legs:
            if not leg.is_active:
                continue
            if first_active_leg is None:
                first_active_leg = leg
            if active_route_id is not None and leg.route_id == active_route_id:
                return leg
    return first_active_leg


def _route_id(route: ParsedRoute) -> str | None:
    file_path = route.metadata.file_path
    if not file_path:
        return None
    return Path(file_path).stem


def _resolve_active_satellite_id(
    leg: MissionLeg,
    route: ParsedRoute | None,
    telemetry: TelemetryData,
) -> str | None:
    current_satellite = leg.transports.initial_x_satellite_id
    if not current_satellite:
        return None
    if route is None or not leg.transports.x_transitions:
        return current_satellite

    current_progress = _project_progress(
        route,
        telemetry.position.latitude,
        telemetry.position.longitude,
    )
    if current_progress is None:
        return current_satellite

    transitions: list[tuple[float, XTransition]] = []
    for transition in leg.transports.x_transitions:
        progress = _project_progress(route, transition.latitude, transition.longitude)
        if progress is not None:
            transitions.append((progress, transition))

    for progress, transition in sorted(transitions, key=lambda item: item[0]):
        if current_progress >= progress and transition.target_satellite_id:
            current_satellite = transition.target_satellite_id
    return current_satellite


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


def _find_satellite_poi(poi_manager: Any, satellite_id: str) -> POI | None:
    if poi_manager is None:
        return None
    for poi in poi_manager.list_pois():
        if poi.category == "satellite" and poi.name == satellite_id:
            return poi
    return None


def _evaluate_link_state(
    telemetry: TelemetryData, satellite: POI
) -> tuple[str, str, float, bool]:
    rule_engine = RuleEngine()
    aircraft = telemetry.position
    altitude_m = aircraft.altitude * 0.3048
    _is_violation, relative_azimuth, _debug = rule_engine.evaluate_x_azimuth_window(
        aircraft_lat=aircraft.latitude,
        aircraft_lon=aircraft.longitude,
        aircraft_alt=altitude_m,
        satellite_lon=satellite.longitude,
        timestamp=telemetry.timestamp,
        heading_deg=aircraft.heading,
        is_aar_mode=False,
    )
    in_forbidden = is_in_azimuth_range(
        relative_azimuth,
        rule_engine.config.normal_azimuth_min,
        rule_engine.config.normal_azimuth_max,
    )
    if in_forbidden:
        return "warning", "yellow", round(relative_azimuth, 1), True
    return "normal", "green", round(relative_azimuth, 1), False
