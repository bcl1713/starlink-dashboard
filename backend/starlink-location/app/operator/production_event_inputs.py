"""Immutable, current application inputs for the existing mission preparer."""

import json
from copy import deepcopy
from dataclasses import dataclass, replace
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

from app.mission.exporter.snapshot_inputs import (
    SourcePayload,
    canonical_json,
    captured_coverage,
)
from app.mission.exporter.snapshot_views import (
    RouteView,
    captured_catalog,
    captured_pois,
)
from app.mission.models import Mission
from app.mission.pop_coverage_evidence import coverage_snapshot
from app.services.pop.catalog import parse_catalog
from app.services.position_freshness import position_observation, speed_is_fresh

from .clock import observation_now
from .errors import OperatorError
from .event_ledger import identity
from .production_input_cache import capture_static, validation_key
from .replay_context import source_run


@dataclass(frozen=True)
class ModelInputs:
    mission: Mission
    sources: tuple
    revision: str
    pop_catalog: object
    context: dict
    coverage_sampler: object
    position: object
    sample_revision: str
    pop_unavailable: bool = False

    def prepare(self, leg):
        from app.mission.timeline_preparation import prepare_mission_timeline
        from app.satellites.rules import ConstraintConfig

        return prepare_mission_timeline(
            leg,
            RouteView(self.sources),
            captured_pois(self.sources),
            self.coverage_sampler,
            self.mission.id,
            discover_coverage=False,
            satellite_catalog=captured_catalog(self.sources),
            constraint_config=ConstraintConfig(),
            pop_catalog=self.pop_catalog,
        )


def require_fresh_position(position, as_of):
    _, freshness = position_observation(
        position.latitude, position.longitude, position.observed_at, as_of
    )
    if freshness != "fresh" or not speed_is_fresh(
        position.speed, position.speed_observed_at, as_of
    ):
        raise OperatorError(
            "event_source_unavailable",
            retryable=True,
            fields={"source": "Position or speed evidence stale or unavailable"},
        )


def capture_current(
    adapter, mission_id, *, as_of, validation_only=False, scheduled=False
):
    """Caller holds repository admission; detached models never consult live inputs."""
    config = adapter.config_provider().model_copy(deep=True)
    context = dict(adapter.context_provider())
    health = adapter.service.store.health()
    if (context.get("source_mode"), context.get("simulation_run_id")) != (
        health.source_mode,
        source_run(health),
    ) or config.mode != health.source_mode:
        raise OperatorError("event_source_unavailable", retryable=True)
    position = None
    if not scheduled:
        telemetry = adapter.telemetry_provider()
        if telemetry is None:
            raise OperatorError("event_source_unavailable", retryable=True)
        position = deepcopy(telemetry.position)
        require_fresh_position(position, observation_now(adapter.clock))
    metadata, sources = capture_static(adapter, mission_id, scheduled=scheduled)
    try:
        content = config.pop.catalog_path.read_bytes()
    except OSError:
        content = b"null"
    key = validation_key(adapter, metadata, sources, config, context, content)
    sample_revision = (
        identity(
            position.latitude,
            position.longitude,
            position.speed,
            position.observed_at,
            position.speed_observed_at,
        )
        if position is not None
        else "scheduled"
    )
    cache_name = "_scheduled_capture" if scheduled else "_validated_capture"
    cached = getattr(adapter, cache_name, None)
    if validation_only and cached is not None and cached[0] == key:
        return replace(cached[1], position=position, sample_revision=sample_revision)
    mission = Mission.model_validate_json(metadata)
    from app.mission.active_context import resolve_active_mission_leg_context

    active = resolve_active_mission_leg_context(adapter.route_manager).context
    if not scheduled and (active is None or active.parent_mission_id != mission_id):
        raise OperatorError(
            "event_source_unavailable",
            retryable=True,
            fields={"source": "Active mission and route association unavailable"},
        )
    for leg in mission.legs:
        file = next((s for s in sources if s.name == "kml/" + leg.route_id), None)
        if (
            not scheduled
            and file is not None
            and adapter.route_manager.source_file_revision(leg.route_id) != file.digest
        ):
            raise OperatorError(
                "event_source_unavailable",
                retryable=True,
                fields={
                    "source": "Route file changed; awaiting accepted route publication"
                },
            )
    if not scheduled and not any(
        leg.is_active and leg.route_id == context.get("active_route_id")
        for leg in mission.legs
    ):
        raise OperatorError("event_source_unavailable", retryable=True)
    try:
        catalog = parse_catalog(content)
    except (ValueError, TypeError):
        catalog = None
    sources = tuple(
        s
        for s in sources
        if not s.name.startswith("cache/")
        and s.name not in ("ground_entry", "pop_catalog", "pop_catalog_identity")
    )
    sources += (
        SourcePayload("pop_catalog", content),
        SourcePayload(
            "pop_catalog_identity",
            canonical_json(
                {
                    "fingerprint": catalog.fingerprint if catalog else "",
                    "status": "ready" if catalog else "unavailable",
                }
            ),
        ),
    )
    try:
        sampler = captured_coverage(sources)
        coverage = coverage_snapshot(sampler)
    except (
        OSError,
        ValueError,
        TypeError,
        AttributeError,
        BadZipFile,
        ParseError,
        StopIteration,
    ):
        sampler, coverage = None, {"valid": False}
    if not coverage["valid"]:
        sampler = None
    revision = identity(
        json.loads(metadata),
        [(s.name, s.digest) for s in sources],
        config.model_dump(mode="json"),
        context,
        coverage,
    )
    result = ModelInputs(
        mission,
        sources,
        revision,
        catalog,
        context,
        sampler,
        position,
        sample_revision,
        catalog is None,
    )
    setattr(adapter, cache_name, (key, result))
    return result
