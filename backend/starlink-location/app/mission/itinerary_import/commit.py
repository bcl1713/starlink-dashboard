"""Journal ordinary mission creation and import completion together."""

from pathlib import Path

from app.mission import storage
from app.mission.models import Mission
from app.mission.planning.journal import json_bytes


def mission_files(mission):
    files = {
        storage.get_mission_file_path(mission.id): json_bytes(
            mission.model_copy(update={"legs": []}).model_dump(mode="json")
        )
    }
    for leg in mission.legs:
        files[storage.get_mission_leg_file_path(mission.id, leg.id)] = json_bytes(
            leg.model_dump(mode="json")
        )
    return files


def commit_initial(service, operation, prepared):
    mission = Mission.model_validate(prepared["mission"])
    with storage.get_active_leg_lock(), storage.get_mission_lock(
        mission.id
    ), service.store.lock:
        current = service.store.read(operation.id)
        if current.generation != operation.generation or current.state != "running":
            raise ValueError("Import operation generation is stale")
        if storage.load_mission_v2(mission.id):
            raise ValueError("Mission already exists")
        service.check_environment(prepared)
        import hashlib

        from app.mission.planning.models import SourceRevision
        from app.mission.planning.sources import SourceStore

        source_store = SourceStore(
            service.mission_root, service.route_manager.routes_dir
        )
        source_files = {}
        records = []
        sources = [
            (
                operation.id,
                "itinerary_pdf",
                "itinerary.pdf",
                (service.store.directory(operation.id) / "source.pdf").read_bytes(),
            )
        ]
        sources.extend(
            (
                r["route_id"],
                "route_kml",
                Path(r["metadata"]["file_path"]).name,
                (
                    service.store.directory(operation.id) / f"{r['route_id']}.kml"
                ).read_bytes(),
            )
            for r in prepared["routes"]
        )
        for id, kind, name, data in sources:
            suffix = "pdf" if kind == "itinerary_pdf" else "kml"
            source = SourceRevision(
                id=id,
                owner=mission.id,
                kind=kind,
                filename=name,
                content_hash=hashlib.sha256(data).hexdigest(),
                owned_relative_path=f"staging/{id}.{suffix}",
            )
            accepted, owned = source_store.acceptance_files(source, mission.id, data)
            source_files.update(owned)
            records.append(accepted.model_dump(mode="json"))
        mission.metadata["itinerary_import"]["source_records"] = records
        files = mission_files(mission)
        files.update(source_files)
        for route in prepared["routes"]:
            rid = route["route_id"]
            files[service.route_manager.routes_dir / f"{rid}.kml"] = (
                service.store.directory(operation.id) / f"{rid}.kml"
            ).read_bytes()
        for item in prepared["artifacts"]:
            files[storage.get_leg_timeline_path(item["leg"]["id"], mission.id)] = (
                json_bytes(item["timeline"])
            )
        current.state = "committed"
        current.stage = "complete"
        current.generation += 1
        files[service.store.directory(operation.id) / "operation.json"] = json_bytes(
            current.model_dump(mode="json")
        )
        service.journal.commit(files)
    for route in prepared["routes"]:
        from app.models.route import ParsedRoute

        parsed = ParsedRoute.model_validate(route)
        service.route_manager.add_route(parsed.route_id, parsed)
    from app.mission.slide_cache.coordinator import saved_mission

    saved_mission(None, mission)
    return current
