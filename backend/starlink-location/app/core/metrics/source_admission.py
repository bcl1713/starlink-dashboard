"""Short-lived source identities checked under existing repository admission.

Only identity strings survive capture. These are not metric storage, a mission
cache, or callbacks retained by the collector. No function takes a frame lock.
"""

from hashlib import sha256


def model_identity(value):
    return (
        sha256(value.model_dump_json().encode()).hexdigest()
        if value is not None
        else None
    )


def poi_identity(pois):
    return sha256("".join(poi.model_dump_json() for poi in pois).encode()).hexdigest()


def phase_identity(status):
    # These two values advance with the selected wall/mission clock, not a phase
    # mutation. Their prepared values still belong to the complete gauge frame.
    record = status.model_dump_json(
        exclude={"time_until_departure_seconds", "time_since_departure_seconds"}
    )
    return sha256(record.encode()).hexdigest()


def replay_input_identity(service, tick):
    """Re-read the known mission only; do not enumerate missions or cache files."""
    from app.mission.storage import load_mission_v2
    from app.services.flight_state import get_flight_state_manager

    return (
        service.route_manager.get_active_route_id(),
        model_identity(service.route_manager.get_active_route()),
        model_identity(tick.plan.artifacts.route),
        poi_identity(service.poi_manager.list_pois()),
        phase_identity(
            get_flight_state_manager().get_status(
                mission_now=tick.frame.simulation_time
            )
        ),
        model_identity(load_mission_v2(tick.plan.mission_id)),
    )


def frame_inputs_are_current(frame, active_route, poi_manager):
    """Validate coupled inputs after detached preparation, before publication."""
    from app.core import eta_service
    from app.services.flight_state import get_flight_state_manager

    manager = poi_manager if poi_manager is not None else eta_service.get_poi_manager()
    return (
        frame.identity.route_id == model_identity(active_route)
        and frame.identity.poi_id == poi_identity(manager.list_pois())
        and frame.identity.phase_id
        == phase_identity(get_flight_state_manager().get_status())
    )
