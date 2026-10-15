"""Reuse owned source routes only where new uploads offer no association."""

import hashlib

from app.mission import storage
from app.mission.planning.journal import atomic_write

from .association import associate_routes
from .worker import parse_route


def reuse_routes(service, operation, data, routes, payload, directory):
    if not operation.revision:
        return
    with storage.get_active_leg_lock():
        current = storage.load_mission_v2(operation.mission_id)
        provenance = current.metadata["itinerary_import"]
        hashes = provenance["sources"]["routes"]
        candidates = {}
        for rid, expected in hashes.items():
            path = service.route_manager.routes_dir / f"{rid}.kml"
            if not path.exists():
                continue
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != expected:
                raise ValueError("Retained route changed")
            candidates[rid] = content
    uploaded = associate_routes(data.expected_legs, routes)
    # Ambiguous new uploads must be corrected, not silently replaced by old data.
    missing = [
        l
        for l in data.expected_legs
        if l.id not in uploaded.assignments
        and not any(i.leg_id == l.id and i.candidates for i in uploaded.issues)
    ]
    retained = {}
    for rid, content in candidates.items():
        atomic_write(directory / f"{rid}.kml", content)
        route = service.bounded(
            parse_route, (str(directory / f"{rid}.kml"),), operation, limit=60
        )
        route.route_id = rid
        route.content_hash = hashes[rid]
        route.metadata.file_path = str(service.route_manager.routes_dir / f"{rid}.kml")
        retained[rid] = route
    association = associate_routes(missing, retained)
    for rid in association.assignments.values():
        routes[rid] = retained[rid]
        payload["files"].append({"id": rid, "name": f"Retained route {rid}.kml"})
