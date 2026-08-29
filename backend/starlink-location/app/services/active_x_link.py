"""Active X-band satellite link overlay data builder."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

from app.mission import storage
from app.mission.models import MissionLeg
from app.models.poi import POI
from app.models.route import ParsedRoute
from app.models.telemetry import TelemetryData
from app.satellites.geometry import is_in_azimuth_range
from app.satellites.rules import RuleEngine
from app.services.active_x_handoff import (
    empty_handoff_context,
    resolve_active_x_context,
)

logger = logging.getLogger(__name__)

LinkState = Literal["normal", "warning"]


def empty_active_x_link(state: str | None = None) -> dict[str, Any]:
    """Return an empty, Grafana-friendly active-X link response."""
    return {
        "coordinates": [],
        "links": [],
        "total": 0,
        "satellite_id": None,
        "pending_satellite_id": None,
        "handoff": empty_handoff_context(),
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
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        LookupError,
        ConnectionError,
        TimeoutError,
        ImportError,
        EOFError,
    ) as exc:  # pragma: no cover - defensive live-mode guard
        logger.debug("Active X link unavailable: telemetry missing: %s", exc)
        return empty_active_x_link(state_filter)

    if telemetry is None:
        return empty_active_x_link(state_filter)

    route = route_manager.get_active_route() if route_manager else None
    active_leg = _find_active_mission_leg(route)
    if active_leg is None:
        return empty_active_x_link(state_filter)

    active_context = resolve_active_x_context(active_leg, route, telemetry)
    satellite_id = active_context.current_satellite_id
    if not satellite_id:
        return empty_active_x_link(state_filter)

    satellite_ids = [satellite_id]
    if active_context.pending_satellite_id:
        satellite_ids.append(active_context.pending_satellite_id)

    links = _build_satellite_links(telemetry, poi_manager, satellite_ids)
    if not links:
        return empty_active_x_link(state_filter)

    current_link = links[0]
    matching_links = [
        link for link in links if state_filter is None or link["state"] == state_filter
    ]
    if state_filter is not None and not matching_links:
        return {
            **empty_active_x_link(state_filter),
            "satellite_id": satellite_id,
            "pending_satellite_id": active_context.pending_satellite_id,
            "handoff": active_context.handoff,
            "state": current_link["state"],
            "color": current_link["color"],
            "relative_azimuth_degrees": current_link["relative_azimuth_degrees"],
            "in_forbidden_window": current_link["in_forbidden_window"],
        }

    coordinates = [point for link in matching_links for point in link["coordinates"]]
    common = {
        "satellite_id": satellite_id,
        "pending_satellite_id": active_context.pending_satellite_id,
        "handoff": active_context.handoff,
        "state": current_link["state"],
        "color": current_link["color"],
        "relative_azimuth_degrees": current_link["relative_azimuth_degrees"],
        "in_forbidden_window": current_link["in_forbidden_window"],
    }
    return {
        **common,
        "links": matching_links,
        "coordinates": coordinates,
        "total": len(coordinates),
    }


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


def _build_satellite_links(
    telemetry: TelemetryData,
    poi_manager: Any,
    satellite_ids: list[str],
) -> list[dict[str, Any]]:
    aircraft = telemetry.position
    links: list[dict[str, Any]] = []
    for satellite_id in satellite_ids:
        satellite = _find_satellite_poi(poi_manager, satellite_id)
        if satellite is None:
            continue
        link_state, color, relative_azimuth, in_forbidden = _evaluate_link_state(
            telemetry, satellite
        )
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
                "sequence": len(links) * 2,
                "latitude": aircraft.latitude,
                "longitude": aircraft.longitude,
            },
            {
                **common,
                "point": "satellite",
                "sequence": len(links) * 2 + 1,
                "latitude": satellite.latitude,
                "longitude": satellite.longitude,
            },
        ]
        links.append({**common, "coordinates": coordinates})
    return links


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
