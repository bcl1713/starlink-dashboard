"""Integrity-checked portable revision snapshots."""

import hashlib
from uuid import UUID

from app.mission import storage
from app.mission.models import Mission
from app.mission.planning.journal import json_bytes


def history_records(mission):
    raw = mission.metadata.get("itinerary_import", {})
    for record in raw.get("history", []):
        UUID(record["snapshot_id"])
        yield record


def capture_history(mission):
    result = []
    for record in history_records(mission):
        id = record["snapshot_id"]
        content = (
            storage.get_mission_directory(mission.id)
            / ".itinerary-history"
            / f"{id}.json"
        ).read_bytes()
        if hashlib.sha256(content).hexdigest() != record["snapshot_hash"]:
            raise ValueError("Retained revision snapshot changed")
        Mission.model_validate_json(content)
        result.append((f"package/itinerary/history/{id}.json", content))
    return result


def stage_history(zf, original, mission, remaps, old_owner):
    from app.mission.planning.packages import _remap

    files = {}
    old_records = list(history_records(original))
    new_records = list(history_records(mission))
    for old, new in zip(old_records, new_records):
        data = zf.read(f"itinerary/history/{old['snapshot_id']}.json")
        if hashlib.sha256(data).hexdigest() != old["snapshot_hash"]:
            raise ValueError("Revision snapshot changed in package")
        previous = Mission.model_validate_json(data)
        if previous.id != old_owner:
            raise ValueError("Revision snapshot has wrong owner")
        updated = _remap(
            previous.model_dump(mode="json"), remaps, old_owner, mission.id
        )
        updated["id"] = mission.id
        content = json_bytes(updated)
        new["snapshot_hash"] = hashlib.sha256(content).hexdigest()
        files[
            storage.get_mission_directory(mission.id)
            / ".itinerary-history"
            / f"{new['snapshot_id']}.json"
        ] = content
    return files
