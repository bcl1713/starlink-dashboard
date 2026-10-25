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
routes = RouteManager()
routes.reload_all_routes()
snapshot = capture_export_snapshot(mission_id, routes, POIManager())
result = []
for leg in snapshot.legs:
    assert leg.preparation_origin == "rebuilt", (
        leg.leg_id,
        leg.preparation_origin,
        leg.warnings,
    )
    assert leg.utc_bounds is not None
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
        if interval.end_time > datetime.fromisoformat(after)
    ]
    interval_evidence = [
        {
            "start": interval.start_time.isoformat(),
            "end": interval.end_time.isoformat(),
            "decisions": [decision.value for decision in interval.decisions],
        }
        for interval in briefing.intervals
    ]
    print(
        json.dumps(
            {
                "diagnostic": "actual production snapshot/customer intervals",
                "leg_id": leg.leg_id,
                "cutoff": after,
                "bounds": [value.isoformat() for value in leg.utc_bounds],
                "origin": leg.preparation_origin,
                "intervals": interval_evidence,
            }
        ),
        file=sys.stderr,
        flush=True,
    )
    assert future_intervals
    assert future_intervals[0].start_time <= datetime.fromisoformat(after)
    assert future_intervals[-1].end_time == leg.utc_bounds[1]
    assert all(
        left.end_time == right.start_time
        for left, right in zip(future_intervals, future_intervals[1:])
    )
    assert all(
        all(decision.value == "Down" for decision in interval.decisions)
        for interval in future_intervals
    )
    result.append(
        {
            "leg_id": leg.leg_id,
            "origin": leg.preparation_origin,
            "timeline": timeline,
            "customer_intervals": interval_evidence,
            "map_pois": [json.loads(raw) for raw in leg.map_pois],
        }
    )
print(json.dumps({"fingerprint": snapshot.fingerprint, "legs": result}))
