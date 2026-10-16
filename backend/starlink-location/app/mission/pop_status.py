"""Local status adapter for captured routes, telemetry, and PoP observations."""

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timezone

from app.core.config import ConfigManager
from app.mission.active_context import resolve_active_mission_leg_context
from app.mission.effective_route import prepare_effective_route
from app.mission.pop_forecast import forecast_for_live, forecast_for_mission
from app.mission.timeline_builder.calculator import (
    RouteTemporalProjector,
    derive_mission_window,
)
from app.services.pop.catalog import load_catalog
from app.services.pop.geometry import nearest_pop
from app.services.pop.live import evaluate_live
from app.services.pop.models import (
    PopCatalog,
    PopForecast,
    PopLiveState,
    PopObservation,
)
from app.services.position_freshness import position_observation, speed_is_fresh

# Task 4 supplies simulation position/IP evidence here, never through real discovery.
ObservationProvider = Callable[[str, object, PopCatalog | None], PopObservation]


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
    ):
        self.route_manager = route_manager
        self.config_provider = config_provider or (lambda: ConfigManager().get_config())
        self.observation_provider = observation_provider or _observation
        self.state = PopLiveState(revision="")
        self._revision = ""
        self._epoch = 0
        self._last_now = None
        self._last_lifecycle = None

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
    ):
        """Capture one local sample, with separate mission and observation clocks.

        `now` is UTC mission/live time; `observed_now` is real collection time for
        existing freshness checks. Pass a changed `lifecycle_token` for reset or
        seek (including forward seeks); backward clock movement also rebases.
        Providers receive (mode, telemetry, captured catalog), and must return
        matching-source evidence without external calls. Live default is cached;
        simulation default is unknown until its position provider is installed.
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
        if unavailable_reason or catalog is None:
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
            except (ValueError, TypeError, AttributeError) as exc:
                forecast = PopForecast(
                    revision=revision,
                    catalog_fingerprint=catalog.fingerprint,
                    status="unavailable" if enabled else "disabled",
                    reason=str(exc),
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
        if forecast.status == "ready":
            if flight_phase == "pre_departure":
                point = route.points[0]
                nearest = nearest_pop(point.latitude, point.longitude, catalog)
            elif valid:
                nearest = nearest_pop(position.latitude, position.longitude, catalog)
        next_id = (
            forecast.transitions[0].crossing.to_pop_id if forecast.transitions else None
        )
        if catalog is not None:
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
        return {
            "pop_forecast": forecast.model_dump(mode="json"),
            "pop_observation": observation.model_dump(mode="json"),
            "pop_advisories": [a.model_dump(mode="json") for a in advisories],
        }

    def status_payload(self, telemetry, *, now=None):
        """Resolve the active effective route and configured catalog without network I/O."""
        from app.services.flight_state import get_flight_state_manager

        now = now or datetime.now(timezone.utc)
        config = self.config_provider()
        route, enabled, token, reason = None, True, None, None
        if self.route_manager is not None:
            resolution = resolve_active_mission_leg_context(self.route_manager)
            if resolution.context is not None:
                context = resolution.context
                enabled = context.leg.transports.starshield_enabled is not False
                token = (context.parent_mission_id, context.route_id)
                try:
                    route = prepare_effective_route(context.leg, self.route_manager)
                except (ValueError, TypeError, AttributeError) as exc:
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
        return self.snapshot(
            telemetry,
            route=route,
            catalog=catalog,
            enabled=enabled,
            mode=config.mode,
            now=now,
            lifecycle_token=(token, flight.departure_time),
            flight_phase=flight.phase.value,
            unavailable_reason=reason,
        )
