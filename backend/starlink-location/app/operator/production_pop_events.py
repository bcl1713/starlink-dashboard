"""Capture the real #348 producer as a separately timed advisory source."""

from copy import deepcopy

from app.mission import storage

from .errors import OperatorError
from .event_ledger import identity
from .event_models import SourceCapture
from .replay_context import source_run


def sample_identity(adapter):
    telemetry = adapter.telemetry_provider()
    if telemetry is None:
        raise OperatorError("event_source_unavailable", retryable=True)
    position = telemetry.position
    return identity(
        [
            getattr(position, name, None)
            for name in (
                "latitude",
                "longitude",
                "speed",
                "heading",
                "observed_at",
                "speed_observed_at",
            )
        ]
    )


def live_pop_events(adapter, inputs, leg, *, as_of):
    if adapter.pop_service is None:
        return None
    with storage.get_active_leg_lock():
        adapter._validate(inputs.mission.id, inputs.revision)
        sample = sample_identity(adapter)
        telemetry = deepcopy(adapter.telemetry_provider())
        result = adapter.pop_service.status_payload(telemetry, now=as_of)
        published = adapter.pop_service.read_publication()
        health = adapter.service.store.health()
        aligned = (
            published.get("mission_id"),
            published.get("leg_id"),
            published.get("mode"),
            published.get("simulation_run_id"),
        ) == (inputs.mission.id, leg.id, health.source_mode, source_run(health))
        status = result["pop_forecast"]["status"]
        source_ref = "model:" + leg.id + ":live-pop"
        source = SourceCapture(
            source=source_ref,
            revision=identity(result),
            generation=identity(inputs.revision, sample),
            input_identity=inputs.revision,
            captured_at=as_of,
            freshness=(
                "fresh"
                if aligned and status == "ready"
                else "disabled" if status == "disabled" else "unknown"
            ),
            aligned=aligned,
            guardable=aligned and status == "ready",
            reason="Live PoP observations and ETA windows; visual advisories only",
        )

        def validate():
            adapter._validate(inputs.mission.id, inputs.revision)
            if sample_identity(adapter) != sample:
                raise OperatorError("event_snapshot_changed", retryable=True)

        adapter.publication.publish(
            source,
            validate=validate,
            snapshot_validate=lambda: adapter._validate_snapshot(
                inputs.mission.id, inputs.revision, telemetry.position
            ),
        )
        adapter.live_sources.add(source_ref)
        from app.mission.availability_context import snapshot_for_leg

        model = {
            "transport_availability": snapshot_for_leg(
                inputs.mission, leg, run_id=source_run(health)
            ).model_dump(mode="json"),
            "transport_generations": inputs.mission.metadata.get(
                "transport_cue_generations", {}
            ).get(leg.id, {}),
            "transport_as_of": as_of.isoformat(),
            "_leg_id": leg.id,
            "_event_source_ref": source_ref,
            "pop_forecast": result["pop_forecast"],
            "pop_advisories": result["pop_advisories"],
        }
        return leg.id + ":live-pop", source, model
