"""Normal application source producer; no fixture authority or new prediction engine."""

from dataclasses import replace

from app.mission import storage
from app.services.pop.geometry import route_geometry_fingerprint

from .errors import OperatorError
from .event_ledger import identity
from .event_models import SourceCapture
from .event_sources import EventSourceAdapter
from .production_event_inputs import capture_current


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
        self.pop_service = pop_service
        self.publication.input_gate = storage.get_active_leg_lock

    def _validate(self, mission_id, revision):
        try:
            current = capture_current(self, mission_id, as_of=self.clock.now())
        except (OSError, ValueError, TypeError, AttributeError, RuntimeError) as exc:
            raise OperatorError("event_source_unavailable", retryable=True) from exc
        if current.revision != revision:
            raise OperatorError("event_snapshot_changed", retryable=True)

    def capture(self, mission_id, *, as_of):
        captured = super().capture(mission_id, as_of=as_of)
        try:
            with storage.get_active_leg_lock():
                mission = storage.load_mission_v2(mission_id)
                if mission is not None and not any(
                    leg.is_active for leg in mission.legs
                ):
                    refs = {
                        s.source
                        for s in captured.sources
                        if s.source.startswith("model:")
                    }
                    refs.update(
                        source.source
                        for (mid, _), (_, source, _) in self.cache.items()
                        if mid == mission_id
                    )
                    refs.update(ref + ":live-pop" for ref in tuple(refs))
                    for ref in refs:
                        self.publication.invalidate(ref)
                    return replace(
                        captured,
                        models={},
                        sources=[
                            s
                            for s in captured.sources
                            if not s.source.startswith("model:")
                        ]
                        + [
                            SourceCapture(
                                source=ref,
                                freshness="disabled",
                                aligned=True,
                                reason="Mission leg inactive",
                            )
                            for ref in refs
                        ],
                    )
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
                    if any(s.name == "coverage/missing" for s in inputs.sources):
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
                    model["unavailable_inputs"] = missing
                    item = (inputs.revision, source, model)
                with storage.get_active_leg_lock():
                    self._validate(mission_id, inputs.revision)
                    self.publication.publish(
                        item[1],
                        validate=lambda m=mission_id, r=inputs.revision: self._validate(
                            m, r
                        ),
                    )
                    self.cache[key] = item
                models[leg.id] = item[2]
                sources = [s for s in sources if s.source != item[1].source] + [item[1]]
                if item[2].get("unavailable_inputs"):
                    sources.append(
                        SourceCapture(
                            source=item[1].source + ":prerequisites",
                            reason="Transport inputs unavailable: "
                            + ", ".join(item[2]["unavailable_inputs"]),
                        )
                    )
                from .production_pop_events import live_pop_events

                live = live_pop_events(self, inputs, leg, as_of=as_of)
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
                    if s.source.startswith("model:")
                    else s
                )
                for s in sources
            ]
            for (mid, leg_id), (_revision, source, model) in self.cache.items():
                if mid == mission_id:
                    self.publication.invalidate(source.source)
                    models[leg_id] = model
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
        for source_ref in self.live_sources:
            self.publication.invalidate(source_ref)
        self.live_sources.clear()
