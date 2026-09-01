"""POI synchronization for mission timeline events."""

from __future__ import annotations

import logging

from app.mission.models import MissionLeg
from app.mission.timeline_builder.coverage import CoverageAnalysisResult
from app.mission.timeline_builder.utils import find_waypoint_coordinates
from app.models.route import ParsedRoute
from app.services.poi_manager import POICreate, POIManager

logger = logging.getLogger(__name__)

MISSION_EVENT_CATEGORY = "mission-event"
KA_POI_NAME_PREFIXES = (
    "Ka Coverage Exit",
    "Ka Coverage Entry",
    "Ka Transition",
    "Ka Swap",
    "CommKa",
)
X_AAR_POI_PREFIXES = (
    "X-Band",
    "AAR",
)


def collect_ka_pois(
    mission: MissionLeg,
    route: ParsedRoute,
    coverage: CoverageAnalysisResult,
    parent_mission_id: str | None = None,
) -> list[POICreate]:
    """Collect Ka coverage POI payloads for a mission leg."""
    effective_mission_id = parent_mission_id or mission.id
    payloads: list[POICreate] = []

    for gap in coverage.gaps:
        if gap.start:
            payloads.append(
                POICreate(
                    name=_format_commka_exit_entry("Exit", gap.lost_satellite),
                    latitude=gap.start.latitude,
                    longitude=gap.start.longitude,
                    icon="satellite",
                    category=MISSION_EVENT_CATEGORY,
                    description=f"Loss at {gap.start.timestamp.isoformat()}",
                    route_id=mission.route_id,
                    mission_id=effective_mission_id,
                )
            )
        if gap.end:
            payloads.append(
                POICreate(
                    name=_format_commka_exit_entry("Enter", gap.regained_satellite),
                    latitude=gap.end.latitude,
                    longitude=gap.end.longitude,
                    icon="satellite",
                    category=MISSION_EVENT_CATEGORY,
                    description=f"Regain at {gap.end.timestamp.isoformat()}",
                    route_id=mission.route_id,
                    mission_id=effective_mission_id,
                )
            )

    for swap in coverage.swaps:
        midpoint = swap.midpoint
        payloads.append(
            POICreate(
                name=_format_commka_transition_label(
                    swap.from_satellite, swap.to_satellite
                ),
                latitude=midpoint.latitude,
                longitude=midpoint.longitude,
                icon="satellite",
                category=MISSION_EVENT_CATEGORY,
                description=f"Recommended swap near {midpoint.timestamp.isoformat()}",
                route_id=mission.route_id,
                mission_id=effective_mission_id,
            )
        )
    return payloads


def collect_x_aar_pois(
    mission: MissionLeg,
    route: ParsedRoute,
    parent_mission_id: str | None = None,
) -> list[POICreate]:
    """Collect X-band and AAR POI payloads for a mission leg."""
    effective_mission_id = parent_mission_id or mission.id
    payloads: list[POICreate] = []

    transports = mission.transports
    if not transports:
        return payloads

    current_satellite = transports.initial_x_satellite_id
    for transition in transports.x_transitions or []:
        if transition.latitude is None or transition.longitude is None:
            continue
        label = _format_x_transition_label(
            current_satellite,
            transition.target_satellite_id,
            transition.is_same_satellite_transition,
        )
        payloads.append(
            POICreate(
                name=label,
                latitude=transition.latitude,
                longitude=transition.longitude,
                icon="satellite",
                category=MISSION_EVENT_CATEGORY,
                description=f"X transition target {transition.target_satellite_id or 'Unknown'}",
                route_id=mission.route_id,
                mission_id=effective_mission_id,
            )
        )
        if (
            not transition.is_same_satellite_transition
            and transition.target_satellite_id
        ):
            current_satellite = transition.target_satellite_id

    for window in transports.aar_windows or []:
        start_coords = find_waypoint_coordinates(route, window.start_waypoint_name)
        if start_coords:
            payloads.append(
                POICreate(
                    name="AAR\nStart",
                    latitude=start_coords[0],
                    longitude=start_coords[1],
                    icon="aar",
                    category=MISSION_EVENT_CATEGORY,
                    description=f"AAR window start ({window.start_waypoint_name})",
                    route_id=mission.route_id,
                    mission_id=effective_mission_id,
                )
            )
        end_coords = find_waypoint_coordinates(route, window.end_waypoint_name)
        if end_coords:
            payloads.append(
                POICreate(
                    name="AAR\nEnd",
                    latitude=end_coords[0],
                    longitude=end_coords[1],
                    icon="aar",
                    category=MISSION_EVENT_CATEGORY,
                    description=f"AAR window end ({window.end_waypoint_name})",
                    route_id=mission.route_id,
                    mission_id=effective_mission_id,
                )
            )
    return payloads


def sync_ka_pois(
    mission: MissionLeg,
    route: ParsedRoute,
    poi_manager: POIManager,
    coverage: CoverageAnalysisResult,
    parent_mission_id: str | None = None,
) -> None:
    """Synchronize Ka POIs for compatibility with older callers."""
    effective_mission_id = parent_mission_id or mission.id
    payloads = collect_ka_pois(mission, route, coverage, parent_mission_id)
    poi_manager.replace_timeline_event_pois(
        route_id=mission.route_id or "",
        mission_id=effective_mission_id,
        generated_pois=payloads,
        route=route,
    )


def sync_x_aar_pois(
    mission: MissionLeg,
    route: ParsedRoute,
    poi_manager: POIManager,
    parent_mission_id: str | None = None,
) -> None:
    """Synchronize X/AAR POIs for compatibility with older callers."""
    effective_mission_id = parent_mission_id or mission.id
    payloads = collect_x_aar_pois(mission, route, parent_mission_id)
    poi_manager.replace_timeline_event_pois(
        route_id=mission.route_id or "",
        mission_id=effective_mission_id,
        generated_pois=payloads,
        route=route,
    )


def _format_commka_exit_entry(kind: str, satellite: str | None) -> str:
    """Format Ka coverage exit/entry POI name."""
    # Simplified: no satellite name, just Exit or Entry
    return f"CommKa\n{kind}"


def _format_commka_transition_label(
    from_satellite: str | None, to_satellite: str | None
) -> str:
    """Format Ka transition POI name."""
    # Format: "Ka Transition AOR → POR" for display and frontend parsing
    if from_satellite and to_satellite:
        return f"Ka Transition {from_satellite} → {to_satellite}"
    return "CommKa\nSwap"


def _format_x_transition_label(
    current_satellite: str | None,
    target_satellite: str | None,
    is_same_satellite: bool,
) -> str:
    """Format X-band transition POI name."""
    # Simplified: all X-Band swaps show as "X-Band\nSwap"
    return "X-Band\nSwap"
