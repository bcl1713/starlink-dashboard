"""Revalidate, prepare and atomically install a reviewed ordinary revision."""

import hashlib
import json
from datetime import datetime, timezone

from fastapi import HTTPException

from app.mission import storage
from app.mission.models import Mission
from app.mission.planning.identity import planning_identity
from app.mission.planning.journal import json_bytes
from app.mission.timeline_preparation import prepare_mission_timeline
from app.models.route import ParsedRoute

from .commit import mission_files, source_files
from .editing import refresh_leg
from .revisions import prepare_revision


def commit_prepared_revision(service, id, generation, resolutions):
    with service.guard, service.store.lock:
        op = service.store.read(id)
        if op.generation != generation or op.state != "ready":
            raise ValueError("Import generation is stale")
        if op.deadline <= datetime.now(timezone.utc):
            raise ValueError("Import deadline exceeded")
        prepared = json.loads(
            (service.store.directory(id) / "prepared.json").read_bytes()
        )
    with storage.get_active_leg_lock():
        current = storage.load_mission_v2(op.mission_id)
        if not current or planning_identity(current) != prepared["baseline_identity"]:
            raise ValueError("Revision preview is stale")
        service.check_environment(prepared)
        baseline = Mission.model_validate(
            {"id": current.id, **current.metadata["itinerary_import"]["baseline"]}
        )
        incoming = Mission.model_validate(prepared["mission"])
        preview = prepare_revision(op, current, baseline, incoming, resolutions)
        if preview.conflicts:
            raise ValueError("Resolve conflicting revision fields before applying")
    mission = preview.mission
    new_routes = {
        r["route_id"]: ParsedRoute.model_validate(r) for r in prepared["routes"]
    }
    from types import SimpleNamespace

    manager = SimpleNamespace(
        get_route=lambda rid: new_routes.get(rid)
        or service.route_manager.get_route(rid)
    )
    files = {}
    for leg in mission.legs:
        old = next((l for l in current.legs if l.id == leg.id), None)
        if old and old == leg:
            continue
        if old and old.is_active:
            raise HTTPException(
                409, "Deactivate affected legs before applying itinerary changes"
            )
        refresh_leg(leg, manager, service.poi_manager)
        artifacts = prepare_mission_timeline(
            leg, manager, service.poi_manager, parent_mission_id=mission.id
        )
        files[storage.get_leg_timeline_path(leg.id, mission.id)] = json_bytes(
            artifacts.timeline.model_dump(mode="json")
        )
    for old in current.legs:
        if not any(l.id == old.id for l in mission.legs):
            if old.is_active:
                raise HTTPException(
                    409, "Deactivate affected legs before applying itinerary changes"
                )
            files[storage.get_mission_leg_file_path(mission.id, old.id)] = None
            files[storage.get_leg_timeline_path(old.id, mission.id)] = None
    provenance = incoming.metadata["itinerary_import"]
    previous = current.metadata["itinerary_import"]
    provenance["revision"] = previous["revision"] + 1
    provenance["history"] = [
        *previous.get("history", []),
        {
            "revision": previous["revision"],
            "snapshot_id": id,
            "snapshot_hash": hashlib.sha256(
                json_bytes(current.model_dump(mode="json"))
            ).hexdigest(),
        },
    ]
    provenance["baseline"] = {
        "name": mission.name,
        "legs": [l.model_dump(mode="json") for l in incoming.legs],
    }
    sources, records = source_files(service, op, prepared)
    files.update(sources)
    provenance["source_records"] = [*previous.get("source_records", []), *records]
    mission.metadata["itinerary_import"] = provenance
    files[
        storage.get_mission_directory(mission.id) / ".itinerary-history" / f"{id}.json"
    ] = json_bytes(current.model_dump(mode="json"))
    files.update(mission_files(mission))
    with storage.get_active_leg_lock(), storage.get_mission_lock(
        mission.id
    ), service.store.lock:
        latest = service.store.read(id)
        if (
            latest.generation != generation
            or latest.state != "ready"
            or planning_identity(storage.load_mission_v2(mission.id))
            != prepared["baseline_identity"]
        ):
            raise ValueError("Revision preview is stale")
        service.check_environment(prepared)
        latest.state = "committed"
        latest.stage = "complete"
        latest.generation += 1
        files[service.store.directory(id) / "operation.json"] = json_bytes(
            latest.model_dump(mode="json")
        )
        service.journal.commit(files)
    for rid, route in new_routes.items():
        service.route_manager.add_route(rid, route)
    from app.mission.slide_cache.coordinator import saved_mission

    saved_mission(current, mission)
    return latest
