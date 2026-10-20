"""Capture existing local data without publishing plans or advancing predictors."""

from dataclasses import dataclass, field
from datetime import datetime

from app.mission import storage
from app.services.pop.geometry import route_geometry_fingerprint

from .event_ledger import identity
from .event_models import SourceCapture
from .queries import select_records
from .replay_context import operating_run, source_run
from .time_models import utc_timestamp


@dataclass(frozen=True)
class CapturedEventInputs:
    mission_id: str
    store_id: str
    api_epoch: str
    source_mode: str
    simulation_run_id: str | None
    H: int
    records: list
    sources: list[SourceCapture]
    models: dict = field(default_factory=dict)
    clock_regression: bool = False


class EventSourceAdapter:
    def __init__(self, service, *, live_provider=None):
        self.service, self.live_provider = service, live_provider

    def _saved_model(self, leg, mission_id):
        timeline = storage.load_mission_timeline(leg.id, mission_id)
        if timeline is None:
            return None
        payload = timeline.model_dump(mode="json")
        payload["route_geometry_identity"] = identity(
            leg.route_id, route_geometry_fingerprint(timeline.samples or [])
        )
        return payload, identity(payload), timeline.created_at

    def capture(self, mission_id: str, *, as_of: datetime) -> CapturedEventInputs:
        health = self.service.store.health()
        sources, models = [], {}
        with self.service.store.connect() as connection:
            high_water = connection.execute(
                "SELECT coalesce(max(journal_seq), 0) FROM revisions"
            ).fetchone()[0]
            records = select_records(
                connection,
                "SELECT * FROM current_records WHERE mission_id=?",
                (mission_id,),
            )
        try:
            mission = storage.load_mission_v2(mission_id)
            for leg in mission.legs if mission else []:
                saved = self._saved_model(leg, mission_id)
                if saved is not None:
                    payload, revision, created_at = saved
                    models[leg.id] = payload
                    sources.append(
                        SourceCapture(
                            source="model:" + leg.id,
                            revision=revision,
                            generation=revision,
                            input_identity=identity(leg.model_dump(mode="json")),
                            captured_at=created_at,
                            reason="Saved plan current-input alignment is unknown",
                        )
                    )
                else:
                    sources.append(
                        SourceCapture(
                            source="model:" + leg.id, reason="Timeline unavailable"
                        )
                    )
            if mission is None:
                sources.append(
                    SourceCapture(
                        source="planning", reason="Mission association missing"
                    )
                )
        except (OSError, ValueError, TypeError, AttributeError):
            sources.append(
                SourceCapture(source="planning", reason="Planning source unavailable")
            )
        if self.live_provider:
            try:
                published = self.live_provider(mission_id)
                if published:
                    leg_id, publication = published
                    if publication and publication.get("mode") == health.source_mode:
                        payload = dict(models.get(leg_id, {}))
                        payload.update(publication["payload"])
                        if publication.get("route_geometry_identity") is not None:
                            payload["route_geometry_identity"] = identity(
                                publication.get("route_id"),
                                publication["route_geometry_identity"],
                            )
                        models[leg_id] = payload
                        # A locally captured prediction does not prove every route,
                        # configuration, lifecycle and catalog writer participates.
                        # Production acknowledgment therefore fails closed.
                        captured = utc_timestamp(publication["captured_at"])
                        freshness = (
                            "fresh"
                            if 0
                            <= (
                                as_of - utc_timestamp(publication["as_of"])
                            ).total_seconds()
                            <= 30
                            else "stale"
                        )
                        status = payload.get("pop_forecast", {}).get("status")
                        if status == "disabled":
                            freshness = "disabled"
                        elif status != "ready":
                            freshness = "unknown"
                        aligned = (
                            publication.get("mission_id") == mission_id
                            and publication.get("leg_id") == leg_id
                            and publication.get("simulation_run_id")
                            == source_run(health)
                            and publication.get("inputs_aligned") is True
                        )
                        source = SourceCapture(
                            source="model:" + leg_id,
                            revision=payload.get("pop_forecast", {}).get("revision"),
                            generation=identity(publication),
                            input_identity=publication.get("input_identity"),
                            captured_at=captured,
                            freshness=freshness,
                            aligned=aligned,
                            guardable=False,
                            reason="Local prediction publication; cross-store invalidation is unguarded",
                        )
                        sources = [s for s in sources if s.source != source.source] + [
                            source
                        ]
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                sources.append(
                    SourceCapture(source="live", reason="Live publication unavailable")
                )
        return CapturedEventInputs(
            mission_id=mission_id,
            store_id=str(health.store_id),
            api_epoch=str(health.api_epoch),
            source_mode=health.source_mode,
            simulation_run_id=operating_run(health),
            H=high_water,
            records=records,
            sources=sources,
            models=models,
            clock_regression=health.clock_regression,
        )
