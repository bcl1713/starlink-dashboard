"""Exercise the preserved single-leg builder in the production Python runtime.

There is no surviving single-leg HTTP export route in v2; this is a builder
compatibility check, distinct from the normal ZIP API/Nginx check.
"""

import json
from pathlib import Path

from inspect_pptx import inspect

from app.core.config import ConfigManager
from app.mission.exporter import TimelineExportFormat, generate_timeline_export
from app.mission.exporter.snapshot import capture_export_snapshot
from app.mission.exporter.snapshot_views import SnapshotViews
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager

output = Path("/probe/direct")
output.mkdir()
routes = RouteManager("/data/routes")
routes._load_existing_routes()
pois = POIManager("/data/pois.json")
frozen = capture_export_snapshot("f01-mission", routes, pois)
views = SnapshotViews(frozen)
results = {}
for enabled in (False, True):
    ConfigManager.get_instance().update_config(
        {"customer_briefing_trial_enabled": enabled}
    )
    artifact = generate_timeline_export(
        TimelineExportFormat.PPTX,
        views.mission().legs[0],
        views.timeline("f01"),
        parent_mission_id=frozen.mission_id,
        route_manager=views.route_manager,
        poi_manager=views.poi_manager,
    )
    path = output / f"direct-{enabled}.pptx"
    path.write_bytes(artifact.content)
    results[str(enabled)] = inspect(path)
# Static map optimization may contain volatile iteration timing; the flag cannot
# enter a trial path. The dedicated fixed-clock comparison separately pins maps.
assert [s["text"] for s in results["False"]["slides"]] == [
    s["text"] for s in results["True"]["slides"]
]
(output / "result.json").write_text(
    json.dumps(
        {
            "builder": "legacy single-leg",
            "http_endpoint": "not present in v2",
            "flag_text_equivalence": True,
            "inspection": results,
        },
        indent=2,
    )
    + "\n"
)
