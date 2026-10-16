"""Capture genuine planning inputs in the actual image; never fabricate intervals."""

import base64
import json
import sys
from pathlib import Path

from app.mission import storage
from app.mission.planning.grid import build_context
from app.mission.planning.inputs import build_inputs, draft_to_mission_leg
from app.mission.planning.models import (
    AcceptRouteBinding,
    ConfirmItinerary,
    PlanningDraft,
)
from app.mission.planning.service import PlanningService
from app.mission.planning.sources import SourceStore
from app.mission.planning.store import PlanningStore
from app.satellites.rules import ConstraintConfig
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager


def main():
    records = json.loads(sys.argv[1])
    data_root = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("/data")
    sources = SourceStore(storage.MISSIONS_DIR, data_root / "routes")
    routes = RouteManager(
        data_root / "routes", profile_resolver=sources.resolve_profile
    )
    routes._load_existing_routes()
    pois = POIManager(data_root / "pois.json")
    service = PlanningService(PlanningStore(storage.MISSIONS_DIR, routes, pois))
    result = {}
    for name, item in records.items():
        mission = storage.load_mission_v2(item["missionId"])
        leg = next(leg for leg in mission.legs if leg.id == item["legId"])
        route = routes.get_route(leg.route_id)
        preview = service.preview_itinerary(
            base64.b64decode(sys.argv[2]), name + ".pdf"
        )
        view = service.create(
            ConfirmItinerary(
                preview_id=preview.preview_id,
                itinerary=preview.parsed_values,
                idempotency_key="pop-" + name,
            )
        )
        expected = view.expected_legs[0].leg
        proposed = service.preview_route(
            view.mission.id,
            expected.id,
            Path(route.metadata.file_path).read_bytes(),
            view.revision,
            name + ".kml",
        )
        service.accept_route(
            view.mission.id,
            expected.id,
            AcceptRouteBinding(
                preview_id=proposed.preview_id,
                expected_revision=view.revision,
                discrepancy_acknowledgments=[
                    e.code for e in proposed.discrepancy_errors
                ],
            ),
        )
        _, manifest = service.store._load(view.mission.id)
        expected = manifest.expected_legs[0].model_copy(deep=True)
        expected.ar_rows = []
        draft = PlanningDraft(
            permitted_satellite_ids=(leg.transports.initial_x_satellite_id,),
            initial_x_satellite_id=leg.transports.initial_x_satellite_id,
            starshield_enabled=True,
            no_ars_confirmed=True,
            ka_outages=leg.transports.ka_outages,
            ku_overrides=leg.transports.ku_overrides,
        )
        inputs = build_inputs(expected, draft, routes, pois, ConstraintConfig())
        context = build_context(inputs, draft)
        planned = draft_to_mission_leg(
            inputs, draft, context, leg_id=leg.id, name=leg.name
        )
        result[name] = planned.model_dump(mode="json")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
