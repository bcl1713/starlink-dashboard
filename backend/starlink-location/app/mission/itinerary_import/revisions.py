"""Three-way ordinary-field merge and immutable revision capture."""



from app.mission import storage
from app.mission.models import Mission
from app.mission.planning.identity import planning_identity
from app.mission.planning.journal import atomic_write, json_bytes

from .models import RevisionConflict, RevisionPreview

DERIVED = {
    "planning_inputs",
    "evaluation_context",
    "created_at",
    "updated_at",
    "import_provenance",
}


def prepare_revision(operation, current_mission, baseline, incoming, resolutions=None):
    resolutions = resolutions or {}
    result = RevisionPreview(
        mission=current_mission.model_copy(deep=True),
        baseline_identity=planning_identity(current_mission),
    )

    def merge(path, old, cur, new):
        if new == old or new == cur:
            return cur
        if cur == old:
            result.changes.append(path)
            return new
        if isinstance(old, dict) and isinstance(cur, dict) and isinstance(new, dict):
            return {
                k: (
                    cur.get(k)
                    if k in DERIVED
                    else merge(f"{path}.{k}", old.get(k), cur.get(k), new.get(k))
                )
                for k in dict.fromkeys([*old, *cur, *new])
            }
        choice = resolutions.get(path)
        if choice == "retain":
            return cur
        if choice == "replace":
            result.changes.append(path)
            return new
        result.conflicts.append(
            RevisionConflict(field=path, baseline=old, current=cur, incoming=new)
        )
        return cur

    old = {l.id: l.model_dump(mode="json") for l in baseline.legs}
    cur = {l.id: l.model_dump(mode="json") for l in current_mission.legs}
    new = {l.id: l.model_dump(mode="json") for l in incoming.legs}
    legs = []
    for id in dict.fromkeys([*new, *cur]):
        value = merge("legs." + id, old.get(id), cur.get(id), new.get(id))
        if value is not None:
            legs.append(value)
    # ID, operator name, metadata and lifecycle are never replaced by extraction.
    result.mission = Mission.model_validate(
        {**current_mission.model_dump(mode="json"), "legs": legs}
    )
    return result


def _remap(value, ids):
    if isinstance(value, str):
        return ids.get(value, value)
    if isinstance(value, list):
        return [_remap(v, ids) for v in value]
    if isinstance(value, dict):
        return {ids.get(k, k): _remap(v, ids) for k, v in value.items()}
    return value


def align_revision(current, prepared):
    """Preserve surviving IDs by source endpoints and ordered occurrence."""
    incoming = Mission.model_validate(prepared["mission"])
    old_evidence = current.metadata["itinerary_import"].get("evidence", {})
    new_evidence = incoming.metadata["itinerary_import"].get("evidence", {})

    def groups(evidence):
        result = {}
        for id, data in evidence.items():
            leg = data["source_leg"]
            result.setdefault(
                (leg["departure_airport"], leg["arrival_airport"]), []
            ).append((leg["ordinal"], id))
        return {key: [id for _, id in sorted(items)] for key, items in result.items()}

    old, new = groups(old_evidence), groups(new_evidence)
    ids = {}
    for key, items in new.items():
        previous = old.get(key, [])
        if (
            previous
            and len(items) != len(previous)
            and max(len(items), len(previous)) > 1
        ):
            raise ValueError(
                "Repeated legs changed count; resolve the leg association before applying revision"
            )
        ids.update(zip(items, previous))
    old_routes = {l.id: l.route_id for l in current.legs}
    for leg in incoming.legs:
        old_id = ids.get(leg.id)
        if old_id not in old_routes:
            continue
        rid = old_routes[old_id]
        oldhash = current.metadata["itinerary_import"]["sources"]["routes"].get(rid)
        newhash = incoming.metadata["itinerary_import"]["sources"]["routes"].get(
            leg.route_id
        )
        if oldhash and oldhash == newhash:
            ids[leg.route_id] = rid
    aligned = _remap(prepared, ids)
    for route in aligned["routes"]:
        path = route["metadata"]["file_path"]
        from pathlib import Path

        route["metadata"]["file_path"] = str(
            Path(path).with_name(route["route_id"] + ".kml")
        )
    return aligned


def stage_revision(service, op, prepared):
    with storage.get_active_leg_lock():
        current = storage.load_mission_v2(op.mission_id)
        if not current or not current.metadata.get("itinerary_import"):
            raise ValueError("Mission has no imported source baseline")
        baseline = Mission.model_validate(
            {"id": current.id, **current.metadata["itinerary_import"]["baseline"]}
        )
        prepared = align_revision(current, prepared)
        preview = prepare_revision(
            op, current, baseline, Mission.model_validate(prepared["mission"])
        )
        preview.baseline_identity = planning_identity(current)
        prepared["revision_preview"] = preview.model_dump(mode="json")
        prepared["baseline_identity"] = planning_identity(current)
        atomic_write(
            service.store.directory(op.id) / "prepared.json", json_bytes(prepared)
        )
        return service.store.update(
            op.id,
            op.generation,
            state="ready",
            stage="review_changes",
            details={
                "revision": {
                    "changes": preview.changes,
                    "conflicts": [c.model_dump(mode="json") for c in preview.conflicts],
                }
            },
        )


def commit_revision(service, id, generation, resolutions):
    from .revision_commit import commit_prepared_revision

    return commit_prepared_revision(service, id, generation, resolutions)
