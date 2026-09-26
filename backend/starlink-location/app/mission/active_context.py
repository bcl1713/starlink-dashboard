"""Resolve the active persisted v2 mission leg and its active route."""

import logging
from dataclasses import dataclass
from typing import Literal

from app.mission.models import Mission, MissionLeg
from app.mission.storage import (
    get_active_leg_lock,
    list_mission_metadata_v2,
    load_mission_v2,
)
from app.models.route import ParsedRoute
from app.services.route_manager import RouteManager

logger = logging.getLogger(__name__)

ActiveMissionLegState = Literal[
    "available",
    "no_active_mission",
    "route_unavailable",
    "inconsistent_active_mission",
]


@dataclass(frozen=True)
class ActiveMissionLegContext:
    """The single active persisted mission leg and matching active route."""

    parent_mission_id: str
    parent_mission: Mission
    leg: MissionLeg
    route_id: str
    route: ParsedRoute


@dataclass(frozen=True)
class ActiveMissionLegResolution:
    """The explicit outcome of resolving the active mission leg context."""

    state: ActiveMissionLegState
    context: ActiveMissionLegContext | None = None


def _unavailable(
    state: ActiveMissionLegState,
    parent_mission_id: str | None = None,
    leg_id: str | None = None,
    expected_route_id: str | None = None,
    observed_route_id: str | None = None,
) -> ActiveMissionLegResolution:
    logger.warning(
        "Active mission context unavailable: parent_id=%s leg_id=%s "
        "expected_route_id=%s observed_route_id=%s state=%s",
        parent_mission_id,
        leg_id,
        expected_route_id,
        observed_route_id,
        state,
    )
    return ActiveMissionLegResolution(state=state)


def resolve_active_mission_leg_context(
    route_manager: RouteManager,
) -> ActiveMissionLegResolution:
    """Resolve exactly one active leg from v2 storage and its active route."""
    with get_active_leg_lock():
        active_legs: list[tuple[str, Mission, MissionLeg]] = []
        for metadata in list_mission_metadata_v2():
            mission = load_mission_v2(metadata.id)
            if mission is None:
                continue
            active_legs.extend(
                (mission.id, mission, leg) for leg in mission.legs if leg.is_active
            )

    if not active_legs:
        return _unavailable("no_active_mission")

    if len(active_legs) > 1:
        parent_mission_id, _, leg = active_legs[0]
        conflicts = [
            f"{parent_id}/{active_leg.id}" for parent_id, _, active_leg in active_legs
        ]
        bounded_conflicts = conflicts[:10]
        logger.warning(
            "Active mission context unavailable: parent_id=%s leg_id=%s "
            "conflicting_active_legs=%s conflicting_active_leg_count=%s "
            "state=%s",
            parent_mission_id,
            leg.id,
            bounded_conflicts,
            len(conflicts),
            "inconsistent_active_mission",
        )
        return ActiveMissionLegResolution(state="inconsistent_active_mission")

    parent_mission_id, parent_mission, leg = active_legs[0]
    route_id = leg.route_id
    observed_route_id = route_manager.get_active_route_id()
    route = (
        route_manager.get_route(route_id)
        if route_id and not route_id.isspace()
        else None
    )
    active_route = route_manager.get_active_route()

    if (
        not route_id
        or route_id.isspace()
        or route is None
        or observed_route_id != route_id
        or active_route != route
    ):
        return _unavailable(
            "route_unavailable",
            parent_mission_id=parent_mission_id,
            leg_id=leg.id,
            expected_route_id=route_id if route_id else None,
            observed_route_id=observed_route_id,
        )

    return ActiveMissionLegResolution(
        state="available",
        context=ActiveMissionLegContext(
            parent_mission_id=parent_mission_id,
            parent_mission=parent_mission,
            leg=leg,
            route_id=route_id,
            route=route,
        ),
    )
