"""Authoritative per-leg retirement, including heads recovered after restart."""

from dataclasses import replace

from app.mission import storage

from .errors import OperatorError
from .event_ledger import identity
from .event_models import OperationalEvent, SourceCapture


def retire_inactive(adapter, captured, mission, *, as_of):
    active = {leg.id for leg in mission.legs if leg.is_active} if mission else set()
    known = {}
    known.update(
        {
            "model:" + leg_id: leg_id
            for (mid, leg_id) in adapter.cache
            if mid == captured.mission_id
        }
    )
    with adapter.service.store.connect() as db:
        for row in db.execute(
            "SELECT o.event_json FROM event_heads h JOIN event_occurrences o USING (occurrence_id) WHERE o.mission_id=? AND h.retired=0",
            (captured.mission_id,),
        ):
            event = OperationalEvent.model_validate_json(row[0])
            if (
                event.source_ref
                and event.source_ref.startswith("model:")
                and (
                    event.freshness == "fresh" or event.source_ref.endswith(":live-pop")
                )
            ):
                known[event.source_ref] = event.leg_id
    retired = {ref for ref, leg_id in known.items() if leg_id not in active}
    retired.update(
        ref + ":live-pop" for ref in tuple(retired) if not ref.endswith(":live-pop")
    )
    for ref in retired:
        adapter.publication.invalidate(ref)
    revision = identity(mission.model_dump(mode="json") if mission else None)
    lifecycle = SourceCapture(
        source="planning:lifecycle:" + captured.mission_id,
        revision=revision,
        generation=revision,
        captured_at=as_of,
        freshness="fresh",
        aligned=True,
        guardable=True,
    )

    def validate():
        current = storage.load_mission_v2(captured.mission_id)
        if identity(current.model_dump(mode="json") if current else None) != revision:
            raise OperatorError("event_snapshot_changed", retryable=True)

    adapter.publication.publish(lifecycle, validate=validate)
    adapter.lifecycle_sources.add(lifecycle.source)
    return (
        replace(
            captured,
            models={
                key: model
                for key, model in captured.models.items()
                if model.get("_event_source_ref", "model:" + key) not in retired
            },
            sources=[
                source for source in captured.sources if source.source not in retired
            ]
            + [lifecycle]
            + [
                SourceCapture(
                    source=ref,
                    freshness="disabled",
                    aligned=True,
                    reason="Mission leg inactive or removed",
                )
                for ref in sorted(retired)
            ],
        ),
        active,
    )
