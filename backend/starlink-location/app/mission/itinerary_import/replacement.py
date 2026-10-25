"""Transactional ordinary KML replacement retaining accepted transport choices."""

import hashlib

from fastapi import HTTPException

from app.mission import storage
from app.mission.availability import resolved_leg_availability
from app.mission.planning.deadlines import run_bounded
from app.mission.planning.identity import planning_identity
from app.mission.planning.journal import json_bytes
from app.mission.planning.sources import SourceStore
from app.mission.timeline_preparation import prepare_mission_timeline

from .commit import mission_files
from .editing import refresh_leg
from .worker import parse_route


def replace_route(service, mission_id, leg_id, data, filename):
    if len(data) > 40 * 1024 * 1024:
        raise ValueError("KML exceeds 40 MiB")
    with storage.get_active_leg_lock():
        mission = storage.load_mission_v2(mission_id)
        if mission is None:
            raise HTTPException(404, "Mission not found")
        leg = next((item for item in mission.legs if item.id == leg_id), None)
        if leg is None:
            raise HTTPException(404, "Leg not found")
        if leg.is_active:
            raise HTTPException(409, "Deactivate the leg before replacing its route")
        identity = planning_identity(mission)
    sources = SourceStore(service.mission_root, service.route_manager.routes_dir)
    source = sources.stage(data, "kml", mission_id, filename)
    try:
        route = run_bounded(parse_route, (str(sources.path(source)),), 60)
        route.route_id = source.id
        route.content_hash = hashlib.sha256(data).hexdigest()
        route.metadata.file_path = str(
            service.route_manager.routes_dir / f"{source.id}.kml"
        )
        leg.route_id = route.route_id
        # Foreign anchors must never validate on new geometry. Only exact unique
        # named/position evidence can retain a route-bound occurrence.
        old_route = service.route_manager.get_route(
            next(
                item.route_id
                for item in storage.load_mission_v2(mission_id).legs
                if item.id == leg_id
            )
        )
        from .rebind import rebind_leg

        rebind_leg(leg, old_route, route)
        from types import SimpleNamespace

        manager = SimpleNamespace(get_route=lambda _: route)
        refresh_leg(
            leg,
            manager,
            service.poi_manager,
            availability=resolved_leg_availability(mission, leg),
        )
        artifacts = prepare_mission_timeline(
            leg,
            manager,
            service.poi_manager,
            parent_mission_id=mission_id,
            availability=resolved_leg_availability(mission, leg),
        )
        accepted, files = sources.acceptance_files(source, mission_id, data)
        mission.metadata["itinerary_import"].setdefault("source_records", []).append(
            accepted.model_dump(mode="json")
        )
        mission.metadata["itinerary_import"]["sources"]["routes"][
            route.route_id
        ] = route.content_hash
        files.update(mission_files(mission))
        files[storage.get_leg_timeline_path(leg_id, mission_id)] = json_bytes(
            artifacts.timeline.model_dump(mode="json")
        )
        with storage.get_active_leg_lock(), storage.get_mission_lock(mission_id):
            if planning_identity(storage.load_mission_v2(mission_id)) != identity:
                raise ValueError("Mission changed; retry the route replacement")
            service.journal.commit(files)
        service.route_manager.add_route(route.route_id, route)
        from app.mission.slide_cache.coordinator import saved_mission

        saved_mission(None, mission)
        return {"leg": leg.model_dump(mode="json"), "warnings": []}
    finally:
        sources.discard(source)
