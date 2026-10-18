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
        live_provider=None
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
                    source = SourceCapture(
                        source="model:" + leg.id,
                        revision=identity(model),
                        generation=inputs.revision,
                        input_identity=inputs.revision,
                        captured_at=as_of,
                        freshness="fresh",
                        aligned=True,
                        guardable=True,
                        reason="Current captured mission inputs; modeled mission UTC requirements",
                    )
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
            while len(self.cache) > 32:
                self.cache.pop(next(iter(self.cache)))
            return replace(captured, models=models, sources=sources)
        except (
            OperatorError,
            OSError,
            ValueError,
            TypeError,
            AttributeError,
            RuntimeError,
        ):
            # Keep explicit source uncertainty and let the feed retain old heads.
            models, sources = dict(captured.models), list(captured.sources)
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
                                "reason": "Current route, catalog, configuration, lifecycle or position inputs unavailable",
                            }
                        )
                    ]
            return replace(captured, models=models, sources=sources)

    def close(self):
        for _revision, source, _model in self.cache.values():
            self.publication.invalidate(source.source)
        self.cache.clear()
