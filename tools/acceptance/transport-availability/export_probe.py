"""Read the actual production export snapshot and customer interval projection."""

import json
import sys
from datetime import datetime
from pathlib import Path

from app.mission import storage
from app.mission.exporter.customer_projection import project_briefing_leg
from app.mission.exporter.snapshot import capture_export_snapshot
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager

storage.MISSIONS_DIR = Path("/app/data/operator/transport-availability/missions")
mission_id, after = sys.argv[1:]
snapshot = capture_export_snapshot(mission_id, RouteManager(), POIManager())
result = []
for leg in snapshot.legs:
    timeline = json.loads(leg.timeline_json)
    future = [
        segment
        for segment in timeline["segments"]
        if datetime.fromisoformat(segment["start_time"])
        >= datetime.fromisoformat(after)
    ]
    assert future
    assert all(
        all(segment[f"{key}_state"] == "offline" for key in ("x", "ka", "ku"))
        for segment in future
    )
    briefing = project_briefing_leg(leg)
    future_intervals = [
        interval
        for interval in briefing.intervals
        if interval.start_time >= datetime.fromisoformat(after)
    ]
    assert future_intervals
    assert all(
        all(decision.value == "Down" for decision in interval.decisions)
        for interval in future_intervals
    )
    result.append(
        {
            "leg_id": leg.leg_id,
            "origin": leg.preparation_origin,
            "timeline": timeline,
            "map_pois": [json.loads(raw) for raw in leg.map_pois],
        }
    )
print(json.dumps({"fingerprint": snapshot.fingerprint, "legs": result}))
