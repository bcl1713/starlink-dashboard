"""Read-only accepted replay plans and deterministic semantic identities."""

import copy
import hashlib
import json
import math
from dataclasses import dataclass

from app.mission.models import MissionLeg
from app.mission.timeline_builder.calculator import TimelineComputationError
from app.mission.timeline_preparation import TimelineArtifacts, prepare_mission_timeline
from app.models.simulation_run import (
    MultiplierPacing,
    NormalizedPacing,
    PacingInput,
    SimulationPreview,
)
from app.satellites.coverage import CoverageSampler
from app.satellites.rules import MissionEvent
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager


class SimulationValidationError(ValueError):
    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(message)


@dataclass(frozen=True)
class PreparedMissionRun:
    mission_id: str
    leg_id: str
    route_id: str
    artifacts: TimelineArtifacts
    normalized: NormalizedPacing
    preview: SimulationPreview
    replay_events: tuple[MissionEvent, ...]
    initial_x_satellite_id: str | None


def normalize_pacing(pacing: PacingInput, duration_seconds: float) -> NormalizedPacing:
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise SimulationValidationError(
            "route", "Flight duration must be finite and positive"
        )
    if isinstance(pacing, MultiplierPacing):
        multiplier = pacing.multiplier
        runtime = duration_seconds / multiplier
    else:
        runtime = pacing.runtime_seconds
        multiplier = duration_seconds / runtime
    if not math.isfinite(multiplier) or not 0.1 <= multiplier <= 1000:
        raise SimulationValidationError(
            "pacing", "Effective multiplier must be between 0.1 and 1000"
        )
    if not math.isfinite(runtime) or runtime <= 0:
        raise SimulationValidationError("pacing", "Runtime must be finite and positive")
    return NormalizedPacing(
        pacing=pacing,
        effective_multiplier=multiplier,
        expected_runtime_seconds=runtime,
        flight_duration_seconds=duration_seconds,
    )


def prepare_mission_run(
    mission_id: str,
    leg: MissionLeg,
    pacing: PacingInput,
    route_manager: RouteManager,
    poi_manager: POIManager,
    coverage_sampler: CoverageSampler | None = None,
) -> PreparedMissionRun:
    try:
        artifacts = prepare_mission_timeline(
            leg.model_copy(deep=True),
            route_manager,
            poi_manager,
            coverage_sampler,
            parent_mission_id=mission_id,
            normalize_for_simulation=True,
        )
    except (TimelineComputationError, ValueError, OverflowError) as exc:
        raise SimulationValidationError("route", str(exc)) from exc
    projector = artifacts.projector
    normalized = normalize_pacing(
        pacing, (projector.end_time - projector.start_time).total_seconds()
    )
    semantic = {
        "mission_id": mission_id,
        "leg_id": leg.id,
        "route_id": leg.route_id,
        "points": [p.model_dump(mode="json") for p in artifacts.route.points],
        "waypoints": [p.model_dump(mode="json") for p in artifacts.route.waypoints],
        "start": projector.start_time.isoformat(),
        "end": projector.end_time.isoformat(),
        "pacing": pacing.model_dump(mode="json"),
        "initial_x": leg.transports.initial_x_satellite_id,
        "events": [vars(event) for event in artifacts.events],
    }
    token = hashlib.sha256(
        json.dumps(semantic, sort_keys=True, default=str, allow_nan=False).encode()
    ).hexdigest()
    preview = SimulationPreview(
        **normalized.model_dump(),
        plan_token=token,
        planned_departure=projector.start_time,
        planned_arrival=projector.end_time
    )
    replay_events = tuple(
        copy.deepcopy(e) for e in artifacts.events if e.timestamp <= projector.end_time
    )
    return PreparedMissionRun(
        mission_id,
        leg.id,
        leg.route_id,
        artifacts,
        normalized,
        preview,
        replay_events,
        leg.transports.initial_x_satellite_id,
    )
