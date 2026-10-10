"""Read-only production canonical and exporter reconstruction in the owned backend."""

import base64
import gzip
import hashlib
import json
import sys
from pathlib import Path

from app.mission import storage
from app.mission.exporter.snapshot import (
    capture_export_snapshot,
    prepare_export_snapshot,
)
from app.mission.exporter.snapshot_inputs import _read_dependencies, canonical_json
from app.mission.models import Mission
from app.mission.planning.sources import SourceStore
from app.mission.timeline_preparation import prepare_mission_timeline
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
original = Mission.model_validate_json(gzip.decompress(base64.b64decode(sys.argv[2])))
clone = storage.load_mission_v2(sys.argv[1])
assert original.id != clone.id
snapshots = [
    prepare_export_snapshot(
        canonical_json(original.model_dump(mode="json")),
        _read_dependencies(original, routes, pois),
    ),
    capture_export_snapshot(clone.id, routes, pois),
]
receipt = {"original_mission_id": original.id, "mission_id": clone.id, "legs": []}
assert len(original.legs) == len(clone.legs) > 0
for original_leg, cloned_leg, original_export, clone_export in zip(
    original.legs, clone.legs, snapshots[0].legs, snapshots[1].legs
):
    assert (
        original_leg.id
        == cloned_leg.id
        == original_export.leg_id
        == clone_export.leg_id
    )
    assert original_leg.route_id != cloned_leg.route_id
    assert (
        original_leg.transports.evaluation_context
        == cloned_leg.transports.evaluation_context
    )
    evaluations = [
        prepare_mission_timeline(
            leg, routes, pois, discover_coverage=False
        ).planning_evaluation
        for leg in (original_leg, cloned_leg)
    ]
    assert evaluations[0] is not None and evaluations[0] == evaluations[1]
    intervals = []
    for exported in (original_export, clone_export):
        assert exported.preparation_origin == "rebuilt", (
            exported.leg_id,
            exported.warnings,
        )
        intervals.append(
            [
                s["metadata"]["planning_interval"]
                for s in json.loads(exported.timeline_json)["segments"]
            ]
        )
    assert (
        intervals[0]
        == intervals[1]
        == [interval.model_dump(mode="json") for interval in evaluations[0].intervals]
    )
    receipt["legs"].append(
        {
            "leg_id": cloned_leg.id,
            "preparation_origins": [
                original_export.preparation_origin,
                clone_export.preparation_origin,
            ],
            "context": cloned_leg.transports.evaluation_context.model_dump(mode="json"),
            "canonical_evaluations_equal": True,
            "export_intervals_equal": True,
            "outage_seconds": evaluations[0].outage_seconds,
            "swap_count": evaluations[0].swap_count,
            "longest_gap_seconds": evaluations[0].longest_gap_seconds,
            "intervals": intervals[0],
        }
    )
assert stored_bytes() == before
receipt["stored_files_unchanged"] = True
receipt["stored_file_hashes"] = before
print("CANONICAL_RECEIPT=" + json.dumps(receipt))
