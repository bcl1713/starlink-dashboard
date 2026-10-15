"""Seed an invented accepted legacy leg for startup conversion verification."""

import json
import sys
from pathlib import Path

from app.mission import storage
from app.mission.models import MissionLeg, TransportConfig
from app.mission.planning.models import AcceptRouteBinding, ConfirmItinerary
from app.mission.planning.service import PlanningService
from app.mission.planning.sources import SourceStore
from app.mission.planning.store import PlanningStore
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager

root = Path(sys.argv[1])
sources = SourceStore(storage.MISSIONS_DIR, Path("/data/routes"))
routes = RouteManager("/data/routes", profile_resolver=sources.resolve_profile)
store = PlanningStore(storage.MISSIONS_DIR, routes, POIManager("/data/pois.json"))
service = PlanningService(store)
preview = service.preview_itinerary(
    (root / "itinerary.pdf").read_bytes(), "invented-legacy.pdf"
)
view = service.create(
    ConfirmItinerary(
        preview_id=preview.preview_id,
        itinerary=preview.parsed_values,
        idempotency_key="ordinary-migration-fixture",
    )
)
expected = view.expected_legs[0].leg
route_preview = service.preview_route(
    view.mission.id,
    expected.id,
    (root / "leg-1.kml").read_bytes(),
    view.revision,
    "legacy.kml",
)
accepted = service.accept_route(
    view.mission.id,
    expected.id,
    AcceptRouteBinding(
        preview_id=route_preview.preview_id,
        expected_revision=view.revision,
        discrepancy_acknowledgments=[e.code for e in route_preview.discrepancy_errors],
    ),
)
mission, manifest = store._load(view.mission.id)
leg = MissionLeg(
    id="invented-legacy-leg",
    name="Invented legacy leg",
    route_id=manifest.expected_legs[0].route.route_id,
    transports=TransportConfig(initial_x_satellite_id="X-SYNTH-A"),
)
mission.legs = [leg]
manifest.expected_legs[0].installed_leg_id = leg.id
store.persist(
    mission,
    manifest,
    files={
        storage.get_mission_leg_file_path(mission.id, leg.id)
        .resolve(): leg.model_dump_json()
        .encode()
    },
)
print("MIGRATION_SEED=" + json.dumps({"id": mission.id, "satellite": "X-SYNTH-A"}))
