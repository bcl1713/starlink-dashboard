"""Normal application source producer; no fixture authority or new prediction engine."""

from dataclasses import replace

from app.mission import storage
from app.services.pop.geometry import route_geometry_fingerprint

from .clock import observation_now
from .errors import OperatorError
from .event_ledger import identity
from .event_models import SourceCapture
from .event_sources import EventSourceAdapter
from .production_event_inputs import capture_current, require_fresh_position
from .production_live_timing import attach_boundary_geometry, refresh_boundary_times


class ProductionEventSources(EventSourceAdapter):
    def __init__(
        self,
        service,
        *,
        clock,
        publication,
        route_manager,
        config_provider,
        telemetry_provider,
        context_provider,
        poi_manager=None,
        live_provider=None,
        pop_service=None
    ):
        super().__init__(service, live_provider=live_provider)
        self.clock, self.publication = clock, publication
        self.route_manager, self.poi_manager = route_manager, poi_manager
        self.config_provider, self.telemetry_provider, self.context_provider = (
            config_provider,
            telemetry_provider,
            context_provider,
        )
        self.cache = {}
        self.live_sources = set()
        self.lifecycle_sources = set()
        self.pop_service = pop_service
        self.publication.input_gate = storage.get_active_leg_lock

    def _validate(self, mission_id, revision):
        try:
            current = capture_current(self, mission_id, as_of=self.clock.now())
        except (OSError, ValueError, TypeError, AttributeError, RuntimeError) as exc:
            raise OperatorError("event_source_unavailable", retryable=True) from exc
        if current.revision != revision:
            raise OperatorError("event_snapshot_changed", retryable=True)
        return current

    def _validate_timing(self, mission_id, revision, sample):
        # Planning and telemetry must be checked against the same capture. A
        # second full recapture repeats I/O and widens the telemetry race.
        current = self._validate(mission_id, revision)
        if current.sample_revision != sample:
            raise OperatorError("event_snapshot_changed", retryable=True)

    def _validate_snapshot(self, mission_id, revision, position):
        # A display snapshot may use a still-fresh captured observation even
        # when the aircraft has published a newer sample. Actions remain strict.
        self._validate(mission_id, revision)
        require_fresh_position(position, observation_now(self.clock))

    def capture(self, mission_id, *, as_of):
        captured = super().capture(mission_id, as_of=as_of)
        try:
            with storage.get_active_leg_lock():
                mission = storage.load_mission_v2(mission_id)
                from .production_event_lifecycle import retire_inactive

                captured, active = retire_inactive(self, captured, mission, as_of=as_of)
                if not active:
                    return captured
                inputs = capture_current(self, mission_id, as_of=as_of)
            models, sources = dict(captured.models), list(captured.sources)
            for leg in inputs.mission.legs:
                if not leg.is_active or leg.route_id != inputs.context.get(
                    "active_route_id"
                ):
                    continue
                key = (mission_id, leg.id)
                item = self.cache.get(key)
                if item is None or item[0] != inputs.revision:
                    artifacts = inputs.prepare(leg)
                    model = artifacts.timeline.model_dump(mode="json")
                    model["capability_spans"] = [
                        span.model_dump(mode="json")
                        for span in artifacts.call_capabilities.spans
                    ]
                    model["route_geometry_identity"] = identity(
                        leg.route_id, route_geometry_fingerprint(artifacts.route.points)
                    )
                    missing = [
                        field
                        for field in ("ka", "x", "starshield")
                        if all(
                            getattr(span, field) == "unknown"
                            for span in artifacts.call_capabilities.spans
                        )
                    ]
                    if inputs.pop_unavailable:
                        missing.append("PoP catalog")
                    if inputs.coverage_sampler is None:
                        missing.append("Ka coverage")
                    source = SourceCapture(
                        source="model:" + leg.id,
                        revision=identity(model),
                        generation=inputs.revision,
                        input_identity=inputs.revision,
                        captured_at=as_of,
                        freshness="fresh",
                        aligned=True,
                        guardable=True,
                        reason="Current mission transport estimate",
                    )
                    attach_boundary_geometry(model, artifacts)
                    model["unavailable_inputs"] = missing
                    item = (inputs.revision, source, model)
                with storage.get_active_leg_lock():
                    # Preparation can outlast several telemetry samples. Verify
                    # static inputs, then time the accepted model with the newest
                    # sample rather than rejecting normal aircraft movement.
                    inputs = self._validate(mission_id, inputs.revision)
                    timing_as_of = self.clock.now()
                    model, timing_available = refresh_boundary_times(
                        item[2], inputs, as_of=timing_as_of
                    )
                    timed_source = item[1].model_copy(
                        update={
                            "revision": identity(item[2], model["time_basis"]),
                            "generation": identity(
                                inputs.revision, inputs.sample_revision
                            ),
                            "captured_at": timing_as_of,
                            "freshness": "fresh" if timing_available else "unknown",
                            "guardable": timing_available,
                            "reason": (
                                "Live route-aware transport estimate"
                                if model["time_basis"] == "live_route_eta"
                                else (
                                    "Preflight planning estimate"
                                    if timing_available
                                    else "Live restriction timing unavailable; planning times are reference only"
                                )
                            ),
                        }
                    )
                    self.publication.publish(
                        timed_source,
                        validate=lambda m=mission_id, r=inputs.revision, t=inputs.sample_revision: self._validate_timing(
                            m, r, t
                        ),
                        snapshot_validate=lambda m=mission_id, r=inputs.revision, p=inputs.position: self._validate_snapshot(
                            m, r, p
                        ),
                    )
                    self.cache[key] = item
                models[leg.id] = model
                sources = [s for s in sources if s.source != timed_source.source] + [
                    timed_source
                ]
                if item[2].get("unavailable_inputs"):
                    sources.append(
                        SourceCapture(
                            source=item[1].source + ":prerequisites",
                            reason="Transport inputs unavailable: "
                            + ", ".join(item[2]["unavailable_inputs"]),
                        )
                    )
                from .production_pop_events import live_pop_events

                live = live_pop_events(self, inputs, leg, as_of=self.clock.now())
                if live is not None:
                    model_key, live_source, live_model = live
                    models[model_key] = live_model
                    sources = [s for s in sources if s.source != live_source.source] + [
                        live_source
                    ]
            while len(self.cache) > 32:
                _revision, evicted, _model = self.cache.pop(next(iter(self.cache)))
                self.publication.invalidate(evicted.source)
                self.publication.invalidate(evicted.source + ":live-pop")
                self.live_sources.discard(evicted.source + ":live-pop")
            return replace(captured, models=models, sources=sources)
        except (
            OperatorError,
            OSError,
            ValueError,
            TypeError,
            AttributeError,
            RuntimeError,
        ) as error:
            # Keep explicit source uncertainty and let the feed retain old heads.
            models, sources = dict(captured.models), list(captured.sources)
            reason = (
                (error.fields or {}).get("source")
                if isinstance(error, OperatorError)
                else None
            )
            reason = reason or (
                "Configured model catalog unavailable"
                if isinstance(error, (OSError, ValueError))
                else "Current model inputs unavailable"
            )
            sources = [
                (
                    s.model_copy(
                        update={
                            "freshness": "unknown",
                            "aligned": False,
                            "guardable": False,
                            "reason": reason,
                        }
                    )
                    if s.source.startswith("model:") and s.freshness != "disabled"
                    else s
                )
                for s in sources
            ]
            for (mid, leg_id), (_revision, source, model) in self.cache.items():
                if mid == mission_id and not any(
                    s.source == source.source and s.freshness == "disabled"
                    for s in sources
                ):
                    self.publication.invalidate(source.source)
                    models[leg_id] = dict(
                        {
                            k: v
                            for k, v in model.items()
                            if k not in ("pop_forecast", "pop_advisories")
                        },
                        time_basis="live_unavailable",
                        boundary_times={},
                    )
                    sources = [s for s in sources if s.source != source.source] + [
                        source.model_copy(
                            update={
                                "freshness": "unknown",
                                "aligned": False,
                                "guardable": False,
                                "reason": reason,
                            }
                        )
                    ]
            return replace(captured, models=models, sources=sources)

    def close(self):
        for _revision, source, _model in self.cache.values():
            self.publication.invalidate(source.source)
        self.cache.clear()
        self._static_capture = None
        for source_ref in self.live_sources | self.lifecycle_sources:
            self.publication.invalidate(source_ref)
        self.live_sources.clear()
        self.lifecycle_sources.clear()
