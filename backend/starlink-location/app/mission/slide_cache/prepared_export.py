"""Read a consistent ready mission; waiting exports follow superseding saves."""

import time
from hashlib import sha256

from app.mission import storage
from app.mission.exporter.snapshot_inputs import canonical_json

from . import coordinator
from .identity import decode_snapshot, renderer_revision
from .store import default_store


def captured_snapshot(metadata, sources, warnings, records):
    import json

    from app.mission.exporter.snapshot import ExportSnapshot, LegSnapshot

    legs = []
    for raw in json.loads(metadata)["legs"]:
        record = records[raw["id"]]
        if record["snapshot"]:
            legs.extend(decode_snapshot(record["snapshot"]).legs)
        else:
            cached = next(
                (s.content for s in sources if s.name == f"cache/{raw['id']}"), b"null"
            )
            try:
                from app.mission.models import MissionLegTimeline

                timeline = MissionLegTimeline.model_validate_json(cached).model_dump(
                    mode="json"
                )
            except (ValueError, TypeError):
                timeline = None
            legs.append(
                LegSnapshot(
                    raw["id"],
                    canonical_json(raw),
                    None,
                    canonical_json(timeline) if timeline else None,
                    (),
                    (),
                    None,
                    "cached" if timeline else "missing",
                    (
                        "Background preparation unavailable; cached predictions retain their original basis",
                    ),
                )
            )
    digest = sha256(metadata)
    for source in sources:
        digest.update(canonical_json([source.name, source.digest]))
    return ExportSnapshot(
        json.loads(metadata)["id"],
        digest.hexdigest(),
        metadata,
        tuple(legs),
        sources,
        warnings + tuple(w for leg in legs for w in leg.warnings),
    )


def await_prepared(mission_id, route_manager, poi_manager, *, cancel, wall_seconds=600):
    """Wait for shared workers; disconnect only cancels this export's wait."""
    from app.mission.exporter.export_cancel import check_cancelled

    cache, revision = default_store(), renderer_revision()
    deadline, retry = time.monotonic() + wall_seconds, True
    while True:
        check_cancelled(cancel)
        revision = renderer_revision()
        with storage.get_active_leg_lock():
            metadata, sources, warnings, expected = coordinator.reconcile(
                mission_id, route_manager, poi_manager, cache, revision, retry=retry
            )
            records = cache.records(mission_id)
            if all(
                records[leg]["fingerprint"] == fingerprint
                and records[leg]["state"] in {"ready", "failed"}
                for leg, fingerprint in expected.items()
            ):
                return captured_snapshot(metadata, sources, warnings, records), records
        retry = False
        if coordinator._runtime is None or time.monotonic() >= deadline:
            # Explicit background-task disablement and deadline preserve data/CSV
            # delivery without moving heavy preparation into the request.
            for record in records.values():
                if record["state"] not in {"ready", "failed"}:
                    record["state"] = "failed"
                    record["warning"] = (
                        "runtime" if coordinator._runtime is None else "deadline"
                    )
            return captured_snapshot(metadata, sources, warnings, records), records
        if coordinator._runtime:
            coordinator._runtime.wake.set()
        cancel.wait(0.1)
