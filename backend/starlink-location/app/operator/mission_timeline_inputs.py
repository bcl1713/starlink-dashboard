"""Read-only active-leg admission over executable chronology inputs."""

from copy import deepcopy
from dataclasses import replace

from app.mission.active_context import resolve_active_mission_leg_context
from app.mission.exporter.snapshot_views import RouteView

from .clock import observation_now
from .errors import OperatorError
from .event_ledger import identity
from .production_event_inputs import capture_current, require_fresh_position
from .replay_context import operating_run


def require_leg_route(adapter, inputs, leg):
    """Prove this leg's current accepted bytes/profile, independent of other legs."""
    unavailable = "route_profile_unavailable/" + leg.route_id
    if any(source.name == unavailable for source in inputs.sources):
        raise OperatorError("event_source_unavailable", retryable=True)
    route = RouteView(inputs.sources).get_route(leg.route_id)
    file = next(
        (source for source in inputs.sources if source.name == "kml/" + leg.route_id),
        None,
    )
    accepted = adapter.route_manager.source_file_revision(leg.route_id)
    if route is None or accepted != (file.digest if file is not None else None):
        raise OperatorError("event_source_unavailable", retryable=True)


def _source_identity(adapter):
    health = adapter.service.store.health()
    return (
        str(health.store_id),
        str(health.api_epoch),
        health.source_mode,
        operating_run(health),
    )


def capture_active_timing(adapter, inputs, leg, *, as_of, expected_identity):
    """Caller holds repository admission; ordinary alert capture is unchanged."""
    if _source_identity(adapter) != expected_identity:
        raise OperatorError("event_source_unavailable", retryable=True)
    current = capture_current(
        adapter, inputs.mission.id, as_of=as_of, scheduled=True, validation_only=True
    )
    if current.revision != inputs.revision:
        raise OperatorError("event_snapshot_changed", retryable=True)
    active = resolve_active_mission_leg_context(adapter.route_manager).context
    if (
        active is None
        or (active.parent_mission_id, active.leg.id, active.route_id)
        != (inputs.mission.id, leg.id, leg.route_id)
        or current.context.get("active_route_id") != leg.route_id
    ):
        raise OperatorError("event_source_unavailable", retryable=True)
    require_leg_route(adapter, current, leg)
    telemetry = adapter.telemetry_provider()
    if telemetry is None:
        raise OperatorError("event_source_unavailable", retryable=True)
    position = deepcopy(telemetry.position)
    require_fresh_position(position, observation_now(adapter.clock))
    if (
        _source_identity(adapter) != expected_identity
        or dict(adapter.context_provider()) != current.context
    ):
        raise OperatorError("event_snapshot_changed", retryable=True)
    return replace(
        current,
        position=position,
        sample_revision=identity(
            position.latitude,
            position.longitude,
            position.speed,
            position.observed_at,
            position.speed_observed_at,
        ),
    )
