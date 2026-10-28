"""Project every leg without alert publication, ledger writes or live admission changes."""

from copy import deepcopy
from dataclasses import replace

from app.mission import storage
from app.services.pop.geometry import route_geometry_fingerprint

from .clock import observation_now
from .errors import OperatorError
from .event_ledger import identity
from .event_models import EventNotification, SourceCapture
from .event_projection import derive_events
from .event_sources import EventSourceAdapter
from .mission_timeline_inputs import capture_active_timing, require_leg_route
from .mission_timeline_models import MissionTimelineSnapshot, TimelineLeg
from .production_event_inputs import capture_current
from .production_live_timing import attach_boundary_geometry, refresh_boundary_times
from .replay_context import current_records, source_run
from .restriction_windows import compact_event_model

_FAILURES = (
    OperatorError,
    OSError,
    ValueError,
    TypeError,
    AttributeError,
    RuntimeError,
    LookupError,
)


def _prepare(adapter, inputs, leg):
    require_leg_route(adapter, inputs, leg)
    cache = getattr(adapter, "mission_timeline_cache", None)
    if cache is None:
        cache = adapter.mission_timeline_cache = {}
    health = adapter.service.store.health()
    key = (str(health.store_id), str(health.api_epoch), inputs.revision, leg.id)
    if key not in cache:
        artifacts = inputs.prepare(leg)
        model = artifacts.timeline.model_dump(mode="json")
        model["capability_spans"] = [
            s.model_dump(mode="json") for s in artifacts.call_capabilities.spans
        ]
        model["route_geometry_identity"] = identity(
            leg.route_id, route_geometry_fingerprint(artifacts.route.points)
        )
        attach_boundary_geometry(model, artifacts)
        missing = [
            field
            for field in ("ka", "x", "starshield")
            if all(
                getattr(s, field) == "unknown"
                for s in artifacts.call_capabilities.spans
            )
        ]
        if inputs.pop_unavailable:
            missing.append("PoP catalog")
        if inputs.coverage_sampler is None:
            missing.append("Ka coverage")
        compact = compact_event_model(model)
        compact["scheduled_departure_at"] = artifacts.projector.sample_at_distance(
            0
        ).timestamp
        compact["scheduled_arrival_at"] = artifacts.projector.sample_at_distance(
            artifacts.projector.total_distance
        ).timestamp
        cache[key] = compact, missing
        while len(cache) > 32:
            cache.pop(next(iter(cache)))
    return deepcopy(cache[key])


def _current_pop(adapter, inputs, leg, as_of, *, live_available):
    """Copy accepted producer evidence without evaluating or advancing its state."""
    service = getattr(adapter, "pop_service", None)
    publication = service.read_publication() if service else None
    if not publication:
        return None
    health = adapter.service.store.health()
    from app.mission.effective_route import prepare_effective_route
    from app.mission.exporter.snapshot_views import RouteView

    route = prepare_effective_route(leg, RouteView(inputs.sources))
    payload = publication.get("payload", {})
    forecast = payload.get("pop_forecast", {})
    if (
        publication.get("mission_id"),
        publication.get("leg_id"),
        publication.get("route_id"),
        publication.get("mode"),
        publication.get("simulation_run_id"),
    ) != (
        inputs.mission.id,
        leg.id,
        leg.route_id,
        health.source_mode,
        source_run(health),
    ):
        return None
    if route is None or publication.get(
        "route_geometry_identity"
    ) != route_geometry_fingerprint(route.points):
        return None
    if (
        inputs.pop_catalog is None
        or forecast.get("catalog_fingerprint") != inputs.pop_catalog.fingerprint
    ):
        return None
    if health.source_mode == "simulation" and publication.get(
        "lifecycle_token"
    ) != inputs.context.get("lifecycle"):
        return None
    from .time_models import utc_timestamp

    age = (
        observation_now(adapter.clock) - utc_timestamp(publication["captured_at"])
    ).total_seconds()
    fresh = live_available and 0 <= age <= 30 and forecast.get("status") == "ready"
    ref = "model:" + leg.id + ":live-pop"
    return (
        leg.id + ":live-pop",
        {
            "_leg_id": leg.id,
            "_event_source_ref": ref,
            "pop_forecast": forecast,
            "pop_advisories": payload.get("pop_advisories", []),
        },
        SourceCapture(
            source=ref,
            revision=identity(payload),
            captured_at=publication["captured_at"],
            freshness="fresh" if fresh else "stale",
            aligned=fresh,
            reason=(
                "Live PoP publication"
                if fresh
                else "Last known PoP publication; current timing unavailable"
            ),
        ),
    )


def build_mission_timeline(runtime, mission_id, adapter):
    # Use only local records/saved references here, never Production.capture():
    # that method intentionally publishes and retires operational alert sources.
    as_of = runtime.clock.now()
    captured = EventSourceAdapter(runtime.service).capture(mission_id, as_of=as_of)
    health = runtime.health()
    mission = storage.load_mission_v2(mission_id)
    models, sources, legs = {}, [], []
    scheduled = live = None
    planning_reason = "Current planning inputs unavailable"
    if hasattr(adapter, "config_provider"):
        try:
            with storage.get_active_leg_lock():
                scheduled = capture_current(
                    adapter, mission_id, as_of=as_of, scheduled=True
                )
            mission = scheduled.mission
        except _FAILURES:
            pass
    for leg in mission.legs if mission else []:
        model, coverage, reason = None, "unavailable", planning_reason
        if scheduled is not None:
            try:
                model, missing = _prepare(adapter, scheduled, leg)
                model["time_basis"] = "planned_utc"
                coverage = "partial" if missing else "available"
                reason = (
                    "Transport inputs unavailable: " + ", ".join(missing)
                    if missing
                    else None
                )
            except _FAILURES:
                reason = "Leg route or transport inputs unavailable"
        if model is None and leg.id in captured.models:
            model = deepcopy(captured.models[leg.id])
            model["time_basis"] = "planned_utc"
            coverage, reason = (
                "last_known",
                "Saved plan; current-input alignment unavailable",
            )
        if model is not None:
            active = bool(leg.is_active and scheduled)
            # Unknown/stale airborne timing never becomes a scheduled countdown.
            if active and scheduled.context.get("phase") != "pre_departure":
                try:
                    # Preparation can outlast the position freshness window.
                    # Time accepted boundaries using the newest admitted sample.
                    with storage.get_active_leg_lock():
                        live = capture_active_timing(
                            adapter,
                            scheduled,
                            leg,
                            as_of=runtime.clock.now(),
                            expected_identity=(
                                captured.store_id,
                                captured.api_epoch,
                                captured.source_mode,
                                captured.simulation_run_id,
                            ),
                        )
                except _FAILURES:
                    live = None
                if live is not None:
                    model, available = refresh_boundary_times(
                        model, live, as_of=runtime.clock.now()
                    )
                else:
                    model = dict(
                        model, time_basis="live_unavailable", boundary_times={}
                    )
                    model.pop("pop_forecast", None)
                    model.pop("pop_advisories", None)
                    available = False
                if not available:
                    coverage, reason = (
                        "partial",
                        "Live timing unavailable; schedule is reference only",
                    )
            elif (
                leg.is_active
                and scheduled is None
                and hasattr(adapter, "context_provider")
            ):
                # Even if static capture fails, an airborne saved plan is reference.
                context = adapter.context_provider()
                if context.get("phase") != "pre_departure":
                    model = dict(
                        model, time_basis="live_unavailable", boundary_times={}
                    )
                    model.pop("pop_forecast", None)
                    model.pop("pop_advisories", None)
            models[leg.id] = model
            if active and scheduled.context.get("phase") != "pre_departure":
                pop_ref = "model:" + leg.id + ":live-pop"
                gap = None
                if leg.transports.starshield_enabled is False:
                    sources.append(
                        SourceCapture(
                            source=pop_ref,
                            freshness="disabled",
                            reason="PoP advisories deliberately disabled with Starshield",
                        )
                    )
                else:
                    pop = None
                    try:
                        pop = _current_pop(
                            adapter,
                            scheduled,
                            leg,
                            runtime.clock.now(),
                            live_available=live is not None,
                        )
                    except _FAILURES:
                        pass
                    if pop:
                        model_key, pop_model, pop_source = pop
                        models[model_key] = pop_model
                        sources.append(pop_source)
                        if pop_source.freshness != "fresh":
                            gap = "PoP timing unavailable; transition advisories are last known"
                    else:
                        gap = "PoP timing unavailable; current transition advisory evidence unavailable"
                        sources.append(SourceCapture(source=pop_ref, reason=gap))
                if gap:
                    if coverage == "available":
                        coverage = "partial"
                    reason = "; ".join(value for value in (reason, gap) if value)
        legs.append(
            TimelineLeg(
                leg_id=leg.id,
                name=leg.name,
                coverage=coverage,
                reason=reason,
                scheduled_departure_at=(model or {}).get("scheduled_departure_at"),
                scheduled_arrival_at=(model or {}).get("scheduled_arrival_at"),
            )
        )
        sources.append(
            SourceCapture(
                source="model:" + leg.id,
                revision=identity(model),
                captured_at=as_of,
                freshness=(
                    "fresh"
                    if scheduled is not None
                    and model is not None
                    and coverage in ("available", "partial")
                    and model.get("time_basis") != "live_unavailable"
                    else "unknown"
                ),
                aligned=coverage in ("available", "partial") and scheduled is not None,
                reason=reason,
            )
        )
    if scheduled is not None:
        # Expensive preparation runs outside the repository gate. Reject an input
        # edit that raced it, instead of presenting the old model as current.
        with storage.get_active_leg_lock():
            current = capture_current(
                adapter,
                mission_id,
                as_of=runtime.clock.now(),
                validation_only=True,
                scheduled=True,
            )
        if current.revision != scheduled.revision:
            raise OperatorError("event_snapshot_changed", retryable=True)
    inputs = replace(
        captured,
        # Alert projection retains inactive call milestones for retirement.
        # Chronology excludes withdrawn calls but keeps completed-call history.
        records=[
            record
            for record in current_records(captured.records, health)
            if record.payload.entry_type != "call"
            or (not record.deleted and record.payload.status != "cancelled")
        ],
        models=models,
        sources=sources,
    )
    as_of = runtime.clock.now()
    events = derive_events(inputs, as_of=as_of, policy=runtime.event_policy)
    for event in events:
        if event.kind == "pop_advisory" and event.due_at is not None:
            event.time_basis = (
                "live_route_eta"
                if event.source_ref.endswith(":live-pop")
                else "planned_utc"
            )
        # Chronology-only rows never qualify for alerts or acknowledgments.
        event.notification = EventNotification(
            available=False,
            acknowledgment_available=False,
            reason="Read-only mission chronology",
        )
    return MissionTimelineSnapshot(
        mission_id=mission_id,
        store_id=captured.store_id,
        api_epoch=captured.api_epoch,
        source_mode=captured.source_mode,
        simulation_run_id=captured.simulation_run_id,
        H=captured.H,
        as_of=as_of,
        generation=identity(
            captured.store_id,
            captured.api_epoch,
            captured.simulation_run_id,
            captured.H,
            models,
            [leg.model_dump() for leg in legs],
        ),
        legs=legs,
        sources=sources,
        events=events,
    )
