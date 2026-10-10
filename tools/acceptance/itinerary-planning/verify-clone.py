"""Read-only production exporter reconstruction proof inside the owned backend."""

import hashlib
import json
import sys
from pathlib import Path

from app.mission import storage
from app.mission.exporter.snapshot import capture_export_snapshot
from app.mission.planning.sources import SourceStore
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager


def stored_bytes():
    roots = [storage.MISSIONS_DIR, Path("/data/routes")]
    files = [
        path
        for root in roots
        for path in root.rglob("*")
        if path.is_file() and path.suffix != ".lock"
    ]
    files.append(Path("/data/pois.json"))
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}


before = stored_bytes()
sources = SourceStore(storage.MISSIONS_DIR, Path("/data/routes"))
routes = RouteManager("/data/routes", profile_resolver=sources.resolve_profile)
routes.reload_all_routes()
pois = POIManager("/data/pois.json")
snapshot = capture_export_snapshot(sys.argv[1], routes, pois)
receipt = {"mission_id": snapshot.mission_id, "legs": []}
for leg in snapshot.legs:
    assert leg.preparation_origin == "rebuilt", (leg.leg_id, leg.warnings)
    timeline = json.loads(leg.timeline_json)
    receipt["legs"].append(
        {
            "leg_id": leg.leg_id,
            "preparation_origin": leg.preparation_origin,
            "context": json.loads(leg.leg_json)["transports"]["evaluation_context"],
            "intervals": [
                s["metadata"]["planning_interval"] for s in timeline["segments"]
            ],
        }
    )
assert receipt["legs"]
assert stored_bytes() == before
receipt["stored_files_unchanged"] = True
print("CANONICAL_RECEIPT=" + json.dumps(receipt))
