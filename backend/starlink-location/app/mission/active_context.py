"""Resolve the accepted persisted v2 mission leg and its active route."""

from dataclasses import dataclass
from typing import Literal

from app.mission.active_context_cache import get_active_mission_snapshot
from app.mission.models import Mission, MissionLeg
from app.models.route import ParsedRoute
from app.services.route_manager import RouteManager

ActiveMissionLegState = Literal[
    "available", "no_active_mission", "route_unavailable", "inconsistent_active_mission"
]


@dataclass(frozen=True)
class ActiveMissionLegContext:
    """Detached mission models; editing a response cannot change cached truth."""

    parent_mission_id: str
    parent_mission: Mission
    leg: MissionLeg
    route_id: str
    route: ParsedRoute


@dataclass(frozen=True)
class ActiveMissionLegResolution:
    state: ActiveMissionLegState
    context: ActiveMissionLegContext | None = None
    generation: int = 0


def resolve_active_mission_leg_context(
    route_manager: RouteManager,
) -> ActiveMissionLegResolution:
    snapshot = get_active_mission_snapshot(route_manager)
    binding = snapshot.binding
    context = None
    if binding is not None:
        mission = Mission.model_validate_json(snapshot.mission_json)
        leg = next(leg for leg in mission.legs if leg.id == binding.leg.id)
        context = ActiveMissionLegContext(
            binding.parent_mission_id, mission, leg, binding.route_id, binding.route
        )
    return ActiveMissionLegResolution(snapshot.state, context, snapshot.generation)
