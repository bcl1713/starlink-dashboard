"""Idempotent conversion retaining accepted legs, sources and unfinished work."""

from dataclasses import dataclass

from app.mission import storage
from app.mission.planning.models import PlanningManifest

from .commit import mission_files


@dataclass(frozen=True)
class MigrationResult:
    mission_id: str
    changed: bool


def convert_mission(mission):
    converted = mission.model_copy(deep=True)
    existing = converted.metadata.get("itinerary_import")
    if existing is not None:
        if existing.get("version") != 1:
            raise ValueError("Unsupported itinerary import provenance version")
        return converted
    raw = converted.metadata.pop("itinerary_planning", None)
    if raw is None:
        return converted
    manifest = PlanningManifest.model_validate(raw)
    evidence = {}
    pending = []
    for expected in manifest.expected_legs:
        if expected.retired:
            continue
        if expected.installed_leg_id:
            evidence[expected.installed_leg_id] = {
                "source_leg": expected.model_dump(mode="json"),
                "association": {},
                "ars": {},
            }
            leg = next(
                (l for l in converted.legs if l.id == expected.installed_leg_id), None
            )
            if leg:
                leg.import_provenance = {"version": 1}
        else:
            pending.append(expected.model_dump(mode="json"))
    routes = {
        s.id: s.content_hash for s in manifest.source_revisions if s.kind == "route_kml"
    }
    converted.metadata["itinerary_import"] = {
        "version": 1,
        "revision": manifest.revision,
        "legacy_manifest": raw,
        "pending_legs": pending,
        "evidence": evidence,
        "source_records": [
            s.model_dump(mode="json") for s in manifest.source_revisions
        ],
        "sources": {"routes": routes},
        "history": [],
        "baseline": {
            "name": converted.name,
            "legs": [l.model_dump(mode="json") for l in converted.legs],
        },
    }
    return converted


def migrate_itinerary_mission(mission_id, store):
    with storage.get_active_leg_lock(), storage.get_mission_lock(mission_id):
        mission = storage.load_mission_v2(mission_id)
        if mission is None:
            return MigrationResult(mission_id, False)
        converted = convert_mission(mission)
        if converted == mission:
            return MigrationResult(mission_id, False)
        store.journal.commit(mission_files(converted))
        return MigrationResult(mission_id, True)
