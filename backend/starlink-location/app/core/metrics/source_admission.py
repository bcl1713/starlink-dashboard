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


def route_source_identity(route):
    if route is None:
        return None
    # Accepted phase detection updates these actuals itself. Geometry and planned
    # timing must remain the inputs associated with source collection/progress.
    from app.models.route import RouteTimingProfile

    # The legacy observation owner materializes an empty timing profile for an
    # untimed route. That is not a planned-input change.
    source = (
        route
        if route.timing_profile is not None
        else route.model_copy(update={"timing_profile": RouteTimingProfile()})
    )
    record = source.model_dump_json(
        exclude={
            "timing_profile": {
                "flight_status",
                "actual_departure_time",
                "actual_arrival_time",
            }
        }
    )
    return sha256(record.encode()).hexdigest()


def poi_identity(pois):
    return sha256("".join(poi.model_dump_json() for poi in pois).encode()).hexdigest()


def phase_identity(status):
    # These two values advance with the selected wall/mission clock, not a phase
    # mutation. Their prepared values still belong to the complete gauge frame.
    record = status.model_dump_json(
        exclude={"time_until_departure_seconds", "time_since_departure_seconds"}
    )
    return sha256(record.encode()).hexdigest()


def current_poi_identity(manager):
    from app.services.poi.manager import POIManager

    if isinstance(manager, POIManager):
        return manager.metrics_input_identity()
    return poi_identity(manager.list_pois())


def replay_input_identity(service, tick):
    """Re-read the known mission only; do not enumerate missions or cache files."""
    from app.mission.storage import load_mission_v2
    from app.services.flight_state import get_flight_state_manager

    return (
        service.route_manager.get_active_route_id(),
        model_identity(service.route_manager.get_active_route()),
        model_identity(tick.plan.artifacts.route),
        current_poi_identity(service.poi_manager),
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
        and frame.identity.poi_id == current_poi_identity(manager)
        and frame.identity.phase_id
        == phase_identity(get_flight_state_manager().get_status())
    )
