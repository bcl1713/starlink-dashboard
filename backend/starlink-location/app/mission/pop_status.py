"""Local status adapter for captured routes, telemetry, and PoP observations."""

import copy
import hashlib
import json
from collections.abc import Callable
from contextlib import nullcontext
from datetime import datetime, timezone
from functools import wraps

from app.core.config import ConfigManager
from app.mission.active_context import resolve_active_mission_leg_context
from app.mission.effective_route import prepare_effective_route
from app.mission.pop_forecast import forecast_for_live, forecast_for_mission
from app.mission.timeline_builder.calculator import (
    RouteTemporalProjector,
    TimelineComputationError,
    derive_mission_window,
)
from app.services.pop.catalog import load_catalog
from app.services.pop.geometry import nearest_pop, route_geometry_fingerprint
from app.services.pop.live import evaluate_live
from app.services.pop.models import (
    PopCatalog,
    PopForecast,
    PopLiveState,
    PopObservation,
)
from app.services.position_freshness import position_observation, speed_is_fresh

# Observation providers are local reads; simulation never uses real discovery.
ObservationProvider = Callable[[str, object, PopCatalog | None], PopObservation]


def _source_admission(function):
    @wraps(function)
    def guarded(self, *args, **kwargs):
        from app.mission.storage import get_active_leg_lock

        gate = (
            get_active_leg_lock()
            if (
                self.route_manager is not None
                or self.snapshot_context_provider is not None
                or self.capability_provider is not None
            )
            else nullcontext()
        )
        with gate:
            return function(self, *args, **kwargs)

    return guarded


def _observation(mode, telemetry, catalog):
    if mode == "live":
        from app.services.ground_entry_point import get_cached_pop_observation

        return get_cached_pop_observation()
    return PopObservation(ip=None, entry=None, status="unknown", source="simulation")


class PopStatusService:
    """Own lifecycle state; HTTP reads perform no external observation lookup."""

    def __init__(
        self,
        route_manager=None,
        config_provider=None,
        *,
        observation_provider: ObservationProvider | None = None,
        snapshot_context_provider=None,
        capability_provider=None,
        poi_manager=None,
    ):
        self.route_manager = route_manager
        self.config_provider = config_provider or (lambda: ConfigManager().get_config())
        self.observation_provider = observation_provider or _observation
        self.snapshot_context_provider = snapshot_context_provider
        # Optional local producer for one route/config/clock-aligned sample.
        self.capability_provider = capability_provider
        self.poi_manager = poi_manager
        self.state = PopLiveState(revision="")
        self._revision = ""
        self._epoch = 0
        self._last_now = None
        self._last_lifecycle = None
        self._published_snapshot = None
        self._replay_capability_cache = None

    def _replay_capabilities(self, active, context, catalog, availability):
        """Own one detached capability projection for the selected replay inputs."""
        from app.mission.exporter.snapshot_inputs import SourcePayload
        from app.mission.exporter.snapshot_views import POIView, RouteView
        from app.mission.pop_capabilities import capability_input_revision
        from app.mission.pop_coverage_evidence import current_coverage_snapshot
        from app.mission.timeline_preparation import prepare_mission_timeline

        try:
            route, projector = context["route"], context["projector"]
            current_route = prepare_effective_route(
                active.leg, self.route_manager, normalize_for_simulation=True
            )
            # Flight-state publication updates this observation on the source
            # route. It does not alter accepted replay geometry or timing.
            current_route.timing_profile.flight_status = (
                route.timing_profile.flight_status
            )
            coverage = current_coverage_snapshot()
            if (
                (context.get("mission_id"), context.get("leg_id"))
                != (active.parent_mission_id, active.leg.id)
                or route.model_dump() != current_route.model_dump()
                or projector.route_snapshot != route.model_dump()
                or coverage is None
            ):
                self._replay_capability_cache = None
                return None
            revision = capability_input_revision(
                active.leg, route, ka_snapshot=coverage, availability=availability
            )
            assignments = {
                active.leg.transports.initial_x_satellite_id,
                *(
                    item.target_satellite_id
                    for item in active.leg.transports.x_transitions
                ),
            }
            if active.leg.transports.planning_inputs is not None:
                assignments.update(
                    item.satellite_id
                    for item in active.leg.transports.planning_inputs.satellites
                )
            names = {name.strip().casefold() for name in assignments if name}
            poi_payloads = (
                tuple(
                    point.model_dump_json().encode()
                    for point in self.poi_manager.list_pois()
                    if point.mission_id is None
                    and point.route_id is None
                    and point.name.strip().casefold() in names
                )
                if self.poi_manager is not None
                else None
            )
            key = (
                context["simulation_run_id"],
                active.parent_mission_id,
                active.leg.id,
                revision,
                catalog.fingerprint if catalog else None,
                (
                    hashlib.sha256(b"\0".join(poi_payloads)).hexdigest()
                    if poi_payloads is not None
                    else None
                ),
            )
            if self._replay_capability_cache is not None:
                cached_key, captured = self._replay_capability_cache
                if cached_key == key:
                    return captured
            supplied = context.get("call_capabilities")
            # Accepted RF identity predates POI fallback-source capture. Rebuild
            # once per key when that provider participates, then reuse our copy.
            if (
                self.poi_manager is None
                and supplied is not None
                and supplied.input_revision == revision
            ):
                captured = copy.deepcopy(supplied)
            else:
                source = self.route_manager.get_route(active.leg.route_id).model_copy(
                    deep=True
                )
                if source.timing_profile is not None:
                    source.timing_profile.flight_status = (
                        route.timing_profile.flight_status
                    )
                routes = RouteView(
                    (
                        SourcePayload(
                            "route/" + active.leg.route_id,
                            source.model_dump_json().encode(),
                        ),
                    )
                )
                artifacts = prepare_mission_timeline(
                    active.leg,
                    routes,
                    POIView(poi_payloads) if poi_payloads is not None else None,
                    parent_mission_id=active.parent_mission_id,
                    normalize_for_simulation=True,
                    pop_catalog=catalog,
                    availability=availability,
                )
                captured = artifacts.call_capabilities
                if (
                    artifacts.route.model_dump() != route.model_dump()
                    or captured.input_revision != revision
                    or current_coverage_snapshot() != coverage
                ):
                    self._replay_capability_cache = None
                    return None
            self._replay_capability_cache = (key, captured)
            return captured
        except (
            OSError,
            ValueError,
            TypeError,
            AttributeError,
            TimelineComputationError,
        ):
            self._replay_capability_cache = None
            return None

    def reconcile(self, forecast, observation, *, catalog, nearest_id, next_id, now):
        """Reject results captured before a route/reset/mode revision superseded them."""
        if forecast.revision != self._revision:
            return None
        self.state, advisories = evaluate_live(
            forecast,
            observation,
            catalog=catalog,
            nearest_id=nearest_id,
            next_id=next_id,
            now=now,
            state=self.state,
        )
        return advisories

    @_source_admission
    def snapshot(
        self,
        telemetry,
        *,
        route,
        catalog,
        enabled,
        mode,
        now,
        lifecycle_token=None,
        flight_phase="in_flight",
        observed_now=None,
        unavailable_reason=None,
        projector=None,
        call_capabilities=None,
        mission_id=None,
        leg_id=None,
        simulation_run_id=None,
    ):
        """Capture one local sample, with separate mission and observation clocks.

        `now` is UTC mission/live time; `observed_now` is real collection time for
        existing freshness checks. Pass a changed `lifecycle_token` for reset or
        seek (including forward seeks); backward clock movement also rebases.
        Providers receive (mode, telemetry, captured catalog), and must return
        matching-source evidence without external calls. Live default is cached;
        simulation default is unknown until its position provider is installed.
        A captured replay `projector` uses its authoritative mission timing.
        """
        lifecycle = (mode, lifecycle_token, enabled, flight_phase)
        if lifecycle != self._last_lifecycle or (
            self._last_now is not None and now < self._last_now
        ):
            self._epoch += 1
        self._last_lifecycle, self._last_now = lifecycle, now
        identity = [
            route.model_dump(mode="json") if route else None,
            catalog.fingerprint if catalog else None,
            lifecycle,
            self._epoch,
        ]
        revision = hashlib.sha256(
            json.dumps(identity, sort_keys=True, default=str).encode()
        ).hexdigest()
        self._revision = revision
        if self.state.revision != revision:
            self.state = PopLiveState(revision=revision)
        observation = self.observation_provider(mode, telemetry, catalog)
        if observation.source != mode:
            observation = PopObservation(
                ip=None, entry=None, status="unknown", source=mode
            )
        position = telemetry.position
        observed_now = observed_now or now
        _, position_state = position_observation(
            position.latitude, position.longitude, position.observed_at, observed_now
        )
        valid = position_state == "fresh" and speed_is_fresh(
            position.speed, position.speed_observed_at, observed_now
        )
        continuity_forecast = None
        if not enabled:
            forecast = PopForecast(
                revision=revision,
                catalog_fingerprint=catalog.fingerprint if catalog else "",
                status="disabled",
            )
        elif unavailable_reason or catalog is None:
            forecast = PopForecast(
                revision=revision,
                catalog_fingerprint=catalog.fingerprint if catalog else "",
                status="unavailable" if enabled else "disabled",
                reason=unavailable_reason or "Unavailable PoP catalog",
            )
        elif flight_phase == "pre_departure" and route is not None:
            try:
                start, end = derive_mission_window(route)
                forecast = forecast_for_mission(
                    route,
                    RouteTemporalProjector(route, start, end),
                    catalog,
                    revision=revision,
                    starshield_enabled=enabled,
                )
            except (
                TimelineComputationError,
                ValueError,
                TypeError,
                AttributeError,
            ) as exc:
                forecast = PopForecast(
                    revision=revision,
                    catalog_fingerprint=catalog.fingerprint,
                    status="unavailable" if enabled else "disabled",
                    reason=str(exc),
                )
        elif projector is not None and valid:
            forecast = forecast_for_mission(
                route,
                projector,
                catalog,
                revision=revision,
                starshield_enabled=enabled,
            )
            continuity_forecast = forecast
            # A fresh replay lifecycle may start after a crossing center. Retain
            # its still-open window for observation reconciliation; ended history
            # must not block a later occurrence after a seek or region re-entry.
            forecast = forecast.model_copy(
                update={
                    "transitions": tuple(
                        t for t in forecast.transitions if t.window_end_utc > now
                    )
                }
            )
        else:
            forecast = forecast_for_live(
                route,
                catalog,
                revision=revision,
                starshield_enabled=enabled,
                now=now,
                latitude=position.latitude,
                longitude=position.longitude,
                speed_knots=position.speed,
                telemetry_valid=valid,
            )
        nearest = None
        if forecast.status == "ready" and valid and flight_phase != "pre_departure":
            nearest = nearest_pop(position.latitude, position.longitude, catalog)
        next_id = next(
            (
                t.crossing.to_pop_id
                for t in forecast.transitions
                if t.crossing_utc > now
            ),
            None,
        )
        # Planned geometry starts at the route origin. Ground egress remains
        # truthful display evidence, but cannot reconcile future flight crossings.
        if catalog is not None and flight_phase != "pre_departure":
            advisories = (
                self.reconcile(
                    forecast,
                    observation,
                    catalog=catalog,
                    nearest_id=nearest,
                    next_id=next_id,
                    now=now,
                )
                or ()
            )
        else:
            advisories = ()
        if continuity_forecast is not None:
            # Only presentation drops crossed centers. Reconciliation above has
            # already completed or retained each relevant captured occurrence.
            forecast = forecast.model_copy(
                update={
                    "transitions": tuple(
                        t for t in forecast.transitions if t.crossing_utc > now
                    )
                }
            )
        continuity_forecast = continuity_forecast or forecast
        from app.mission.pop_capabilities import status_call_continuity

        # Include still bounded tracked windows after their crossing center.
        by_id = {t.crossing.id: t for t in continuity_forecast.transitions}
        by_id.update(
            {
                t.crossing.id: t
                for t in self.state.tracked_transitions
                if t.window_end_utc > now
            }
        )
        continuity_forecast = continuity_forecast.model_copy(
            update={"transitions": tuple(by_id.values())}
        )
        if call_capabilities is None and self.capability_provider is not None:
            call_capabilities = self.capability_provider(
                route=route, forecast=continuity_forecast, now=now
            )
        continuity = status_call_continuity(
            call_capabilities,
            continuity_forecast,
            route,
            now=now,
            flight_phase=flight_phase,
            projector=projector,
            completed_ids=self.state.completed_ids,
        )
        result = {
            "call_continuity": (
                continuity.model_dump(mode="json") if continuity else None
            ),
            "pop_forecast": forecast.model_dump(mode="json"),
            "pop_observation": observation.model_dump(mode="json"),
            "pop_advisories": [a.model_dump(mode="json") for a in advisories],
        }

        self._published_snapshot = {
            "payload": copy.deepcopy(result),
            "as_of": now,
            "captured_at": observed_now,
            "mode": mode,
            "input_identity": revision,
            "route_geometry_identity": (
                route_geometry_fingerprint(route.points) if route else None
            ),
            "route_id": route.route_id if route else None,
            "mission_id": mission_id,
            "leg_id": leg_id,
            "simulation_run_id": simulation_run_id,
            "lifecycle_token": copy.deepcopy(lifecycle_token),
        }
        return result

    def read_publication(self):
        """Copy the last local publication without evaluating or advancing state."""
        return copy.deepcopy(self._published_snapshot)

    @_source_admission
    def status_payload(self, telemetry, *, now=None):
        """Resolve local inputs; optional simulation callback supplies snapshot kwargs.

        `snapshot_context_provider() -> dict` is simulation-only. Replay supplies
        route/projector, mission `now`, real `observed_now`, lifecycle token,
        enabled flag and flight phase from one published replay selection.
        """
        from app.services.flight_state import get_flight_state_manager

        now = now or datetime.now(timezone.utc)
        config = self.config_provider()
        route, enabled, token, reason = None, True, None, None
        active_context = None
        if self.route_manager is not None:
            resolution = resolve_active_mission_leg_context(self.route_manager)
            if resolution.context is not None:
                context = resolution.context
                active_context = context
                enabled = context.leg.transports.starshield_enabled is not False
                token = (context.parent_mission_id, context.route_id)
                try:
                    route = prepare_effective_route(context.leg, self.route_manager)
                except (
                    TimelineComputationError,
                    ValueError,
                    TypeError,
                    AttributeError,
                ) as exc:
                    reason = str(exc)
            elif resolution.state == "no_active_mission":
                route = self.route_manager.get_active_route()
            else:
                reason = resolution.state
        catalog = None
        try:
            catalog = load_catalog(config.pop.catalog_path)
        except (OSError, ValueError) as exc:
            reason = f"Unavailable PoP catalog: {exc}"
        flight = get_flight_state_manager().get_status()
        context = {
            "route": route,
            "catalog": catalog,
            "enabled": enabled,
            "mode": config.mode,
            "now": now,
            "lifecycle_token": (token, flight.departure_time),
            "flight_phase": flight.phase.value,
            "unavailable_reason": reason,
            "mission_id": active_context.parent_mission_id if active_context else None,
            "leg_id": (
                getattr(active_context.leg, "id", None) if active_context else None
            ),
        }
        if config.mode == "simulation" and self.snapshot_context_provider is not None:
            context.update(self.snapshot_context_provider())
        availability = None
        if (
            active_context is not None
            and getattr(active_context, "parent_mission", None) is not None
        ):
            from app.mission.availability_context import snapshot_for_leg
            from app.mission.models import Transport

            availability = snapshot_for_leg(
                active_context.parent_mission,
                active_context.leg,
                run_id=context.get("simulation_run_id"),
            )
            context["enabled"] = availability.resolve(context["now"])[Transport.KU]
        selected_replay = (
            config.mode == "simulation"
            and active_context is not None
            and context.get("simulation_run_id") is not None
            and context.get("projector") is not None
        )
        if selected_replay:
            context["call_capabilities"] = self._replay_capabilities(
                active_context, context, catalog, availability
            )
        else:
            self._replay_capability_cache = None
        if (
            not selected_replay
            and active_context is not None
            and context.get("call_capabilities") is not None
        ):
            from app.mission.pop_capabilities import (
                capability_input_revision,
                saved_call_capabilities,
            )

            supplied = context["call_capabilities"]
            if supplied.input_revision != capability_input_revision(
                active_context.leg, context["route"], availability=availability
            ):
                context["call_capabilities"] = saved_call_capabilities(
                    active_context.leg,
                    active_context.parent_mission_id,
                    context["route"],
                    availability=availability,
                )
        if (
            active_context is not None
            and context["flight_phase"] == "pre_departure"
            and "call_capabilities" not in context
        ):
            from app.mission.pop_capabilities import saved_call_capabilities

            try:
                context["call_capabilities"] = saved_call_capabilities(
                    active_context.leg,
                    active_context.parent_mission_id,
                    route,
                    availability=availability,
                )
            except (OSError, ValueError, TypeError, AttributeError):
                context["call_capabilities"] = None
        result = self.snapshot(telemetry, **context)
        if availability is not None:
            result["transport_availability"] = {
                k.value: v for k, v in availability.resolve(context["now"]).items()
            }
            result["availability_revision"] = availability.revision
        return result
