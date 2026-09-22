"""Typed mission POI synchronization for timeline events."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from app.mission.models import MissionLeg
from app.mission.timeline_builder.aar import ResolvedAARWindow
from app.mission.timeline_builder.coverage import CoverageAnalysisResult
from app.mission.timeline_builder.utils import find_waypoint_coordinates
from app.models.poi import MissionPoiKind
from app.models.route import ParsedRoute, RoutePoint, RouteWaypoint
from app.services.poi_manager import POICreate, POIManager

MISSION_EVENT_CATEGORY = "mission-event"
MISSION_POI_KINDS: set[MissionPoiKind] = {
    "departure",
    "arrival",
    "aar_start",
    "aar_end",
    "x_band_transition",
    "ka_coverage_exit",
    "ka_coverage_entry",
    "ka_transition",
}


def sync_mission_pois(
    mission: MissionLeg,
    route: ParsedRoute,
    poi_manager: POIManager,
    *,
    mission_start: datetime,
    mission_end: datetime,
    aar_windows: Sequence[ResolvedAARWindow],
    transition_schedule: Sequence[tuple[datetime, str, str | None]],
    coverage: CoverageAnalysisResult,
    parent_mission_id: str | None = None,
) -> None:
    """Replace generated mission POIs while preserving manually managed POIs."""
    effective_mission_id = parent_mission_id or mission.id
    if not mission.route_id:
        return

    poi_manager.delete_leg_pois(
        route_id=mission.route_id,
        mission_id=effective_mission_id,
        kinds=MISSION_POI_KINDS,
        generated_source="mission-timeline",
    )

    def create(
        *,
        name: str,
        latitude: float,
        longitude: float,
        icon: str,
        kind: MissionPoiKind,
        expected_arrival_time: datetime,
        description: str | None = None,
    ) -> None:
        poi_manager.create_poi(
            POICreate(
                name=name,
                latitude=latitude,
                longitude=longitude,
                icon=icon,
                category=MISSION_EVENT_CATEGORY,
                description=description,
                route_id=mission.route_id,
                mission_id=effective_mission_id,
                kind=kind,
                expected_arrival_time=expected_arrival_time,
            ),
            active_route=route,
            generated_source="mission-timeline",
        )

    departure = _endpoint(route, "departure", route.points[0], "Departure")
    arrival = _endpoint(route, "arrival", route.points[-1], "Arrival")
    create(
        name=departure.name or "Departure",
        latitude=departure.latitude,
        longitude=departure.longitude,
        icon="airport",
        kind="departure",
        expected_arrival_time=mission_start,
    )
    create(
        name=arrival.name or "Arrival",
        latitude=arrival.latitude,
        longitude=arrival.longitude,
        icon="flag",
        kind="arrival",
        expected_arrival_time=mission_end,
    )

    _create_aar_pois(create, mission, route, aar_windows)
    _create_x_transition_pois(create, mission, transition_schedule)
    _create_ka_pois(create, coverage)


def _endpoint(
    route: ParsedRoute, role: str, fallback: RoutePoint, fallback_name: str
) -> RouteWaypoint:
    """Use a labelled endpoint waypoint when present, else the route endpoint."""
    for waypoint in route.waypoints:
        if waypoint.role == role:
            if waypoint.name and waypoint.name.strip():
                return waypoint
            return RouteWaypoint(
                name=fallback_name,
                latitude=waypoint.latitude,
                longitude=waypoint.longitude,
                order=waypoint.order,
                role=waypoint.role,
            )
    return RouteWaypoint(
        name=fallback_name,
        latitude=fallback.latitude,
        longitude=fallback.longitude,
        order=fallback.sequence,
        role=role,
    )


def _create_aar_pois(
    create, mission: MissionLeg, route: ParsedRoute, aar_windows
) -> None:
    source_windows = {
        window.id or f"AAR-{index + 1}": window
        for index, window in enumerate(mission.transports.aar_windows or [])
    }
    for resolved in aar_windows:
        source = source_windows.get(resolved.name)
        if source is None:
            continue
        start = find_waypoint_coordinates(route, source.start_waypoint_name)
        if start:
            create(
                name="AAR\nStart",
                latitude=start[0],
                longitude=start[1],
                icon="aar",
                kind="aar_start",
                expected_arrival_time=resolved.start_time,
                description=f"AAR window start ({source.start_waypoint_name})",
            )
        end = find_waypoint_coordinates(route, source.end_waypoint_name)
        if end:
            create(
                name="AAR\nEnd",
                latitude=end[0],
                longitude=end[1],
                icon="aar",
                kind="aar_end",
                expected_arrival_time=resolved.end_time,
                description=f"AAR window end ({source.end_waypoint_name})",
            )


def _create_x_transition_pois(create, mission: MissionLeg, transition_schedule) -> None:
    transitions = mission.transports.x_transitions or []
    if not transitions:
        return
    transition_timestamps = {
        transition_id: timestamp
        for timestamp, _, transition_id in transition_schedule
        if transition_id is not None
    }
    for transition in transitions:
        timestamp = transition_timestamps.get(transition.id)
        if timestamp is None:
            continue
        create(
            name="X-Band\nSwap",
            latitude=transition.latitude,
            longitude=transition.longitude,
            icon="satellite",
            kind="x_band_transition",
            expected_arrival_time=timestamp,
            description=f"X transition target {transition.target_satellite_id}",
        )


def _create_ka_pois(create, coverage: CoverageAnalysisResult) -> None:
    for gap in coverage.gaps:
        if gap.start:
            create(
                name="CommKa\nExit",
                latitude=gap.start.latitude,
                longitude=gap.start.longitude,
                icon="satellite",
                kind="ka_coverage_exit",
                expected_arrival_time=gap.start.timestamp,
                description=f"Loss at {gap.start.timestamp.isoformat()}",
            )
        if gap.end:
            create(
                name="CommKa\nEnter",
                latitude=gap.end.latitude,
                longitude=gap.end.longitude,
                icon="satellite",
                kind="ka_coverage_entry",
                expected_arrival_time=gap.end.timestamp,
                description=f"Regain at {gap.end.timestamp.isoformat()}",
            )
    for swap in coverage.swaps:
        midpoint = swap.midpoint
        create(
            name=_ka_transition_name(swap.from_satellite, swap.to_satellite),
            latitude=midpoint.latitude,
            longitude=midpoint.longitude,
            icon="satellite",
            kind="ka_transition",
            expected_arrival_time=midpoint.timestamp,
            description=f"Recommended swap near {midpoint.timestamp.isoformat()}",
        )


def _ka_transition_name(from_satellite: str | None, to_satellite: str | None) -> str:
    if from_satellite and to_satellite:
        return f"Ka Transition {from_satellite} → {to_satellite}"
    return "CommKa\nSwap"
