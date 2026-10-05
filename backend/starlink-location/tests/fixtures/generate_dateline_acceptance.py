"""Generate browser fixtures through the real timeline builder using invented data.

Run with backend dependencies and PYTHONPATH=backend/starlink-location.
This script emits JSON; it never loads an operator's route or coverage polygons.
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.mission.models import Mission, MissionLeg, TransportConfig
from app.mission.timeline_builder.calculator import derive_mission_window
from app.mission.timeline_service import build_mission_timeline
from app.services.kml.parser import parse_kml_file
from app.services.route_manager import RouteManager
from tests.fixtures.synthetic_coverage import SyntheticCoverage

route = parse_kml_file(Path(__file__).with_name("synthetic-dateline-timeline.kml"))
start, _ = derive_mission_window(route)
leg = MissionLeg(
    id="synthetic-271-leg",
    name="Fabricated dateline leg",
    route_id="synthetic-271-route",
    transports=TransportConfig(initial_x_satellite_id="X-1"),
    adjusted_departure_time=start.replace(hour=23),
)
mission = Mission(id="synthetic-271", name="Fabricated timeline acceptance", legs=[leg])
with TemporaryDirectory(prefix="issue-271-route-") as routes_dir:
    manager = RouteManager(routes_dir=routes_dir)
    manager._routes[leg.route_id] = route
    timeline, _ = build_mission_timeline(
        leg, manager, coverage_sampler=SyntheticCoverage(), include_samples=True
    )
print(
    json.dumps(
        {
            "mission": mission.model_dump(mode="json"),
            "route": route.model_dump(mode="json"),
            "timeline": timeline.model_dump(mode="json"),
        }
    )
)
