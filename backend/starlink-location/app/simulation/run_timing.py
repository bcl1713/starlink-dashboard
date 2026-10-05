"""Mission-time projection with independently real source provenance."""

from math import isfinite

from app.models.mission_time import MissionTimeContext
from app.models.poi import POI
from app.models.simulation_run import SimulationRunStatus
from app.services.eta_calculator import ETACalculator
from app.simulation.run_plan import PreparedMissionRun
from app.simulation.run_replay import ReplayFrame


def mission_time_context(status: SimulationRunStatus) -> MissionTimeContext | None:
    if status.state not in ("running", "completed") or status.run is None:
        return None
    run = status.run
    return MissionTimeContext(
        runtime_id=status.runtime_id,
        run_id=run.run_id,
        revision=status.revision,
        simulation_time=run.simulation_time,
        observed_at=run.observed_at,
        phase=run.phase,
        effective_multiplier=run.effective_multiplier,
    )


def planned_poi_eta(
    plan: PreparedMissionRun, frame: ReplayFrame, poi: POI
) -> float | None:
    if (
        not isfinite(poi.latitude)
        or not -90 <= poi.latitude <= 90
        or not isfinite(poi.longitude)
        or not -180 <= poi.longitude <= 180
        or poi.route_id != plan.route_id
    ):
        return None
    projector = plan.artifacts.projector
    timestamp = (
        poi.expected_arrival_time
        if poi.generated_source == "mission-timeline"
        else None
    )
    if timestamp is None:
        projection = projector.project(poi.latitude, poi.longitude)
        timestamp = projection.timestamp
    if not projector.start_time <= timestamp <= projector.end_time:
        return None
    return max(0.0, (timestamp - frame.simulation_time).total_seconds())


def planned_poi_metrics(
    plan: PreparedMissionRun, frame: ReplayFrame, pois: list[POI]
) -> dict:
    calculator = ETACalculator()
    result = {}
    for poi in pois:
        eta = planned_poi_eta(plan, frame, poi)
        result[poi.id] = {
            "poi_name": poi.name,
            "poi_category": poi.category or "",
            "eta_seconds": eta if eta is not None else -1,
            "distance_meters": calculator.calculate_distance(
                frame.position.latitude,
                frame.position.longitude,
                poi.latitude,
                poi.longitude,
            ),
            "eta_type": "estimated",
            "flight_phase": frame.phase.value,
        }
    return result


def published_replay(service):
    """Read a coherent published selection; never advance the producer."""
    if service is None:
        return None
    from app.mission.storage import get_active_leg_lock

    with get_active_leg_lock():
        status = service.status()
        context = mission_time_context(status)
        plan, frame = service.runtime.selected_plan(), service.runtime.frame()
        if context is None or plan is None or frame is None:
            return None
        return plan, frame, context
