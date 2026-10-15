"""Picklable computations run only inside owned deadline workers."""

from pathlib import Path
from types import SimpleNamespace

from app.mission import storage
from app.mission.planning.canonical import draft_to_mission_leg
from app.mission.planning.grid import build_context
from app.mission.planning.inputs import build_inputs
from app.mission.planning.models import ExpectedLeg, PlanningDraft
from app.mission.planning.optimizer import optimize
from app.mission.timeline_preparation import prepare_mission_timeline
from app.models.route import ParsedRoute
from app.satellites import catalog
from app.satellites.rules import ConstraintConfig


def parse_route(path):
    from app.services.kml.parser import parse_kml_file

    return parse_kml_file(Path(path), profile="planning_v1")


def build_leg(leg_data, route_data, positions, constraints, mission_root, mission_id):
    storage.MISSIONS_DIR = Path(mission_root)
    captured = catalog.SatelliteCatalog()
    for position in positions:
        captured.add_satellite(
            catalog.Satellite(position["id"], "X", longitude=position["longitude"])
        )
    catalog._catalog = captured
    leg = ExpectedLeg.model_validate(leg_data)
    route = ParsedRoute.model_validate(route_data)
    manager = SimpleNamespace(
        get_route=lambda id: route if id == route.route_id else None
    )
    draft = PlanningDraft(
        permitted_satellite_ids=[p["id"] for p in positions],
        ar_corrections=leg.ar_rows,
        starshield_enabled=True,
    )
    inputs = build_inputs(leg, draft, manager, None, ConstraintConfig(**constraints))
    context = build_context(inputs, draft)
    proposal = optimize(
        inputs, draft, context, configured_satellite_ids=draft.permitted_satellite_ids
    )
    ordinary = draft_to_mission_leg(
        inputs,
        proposal.proposed_draft,
        proposal.context,
        leg_id=leg.id,
        name=f"{leg.departure_airport}–{leg.arrival_airport}",
    )
    ordinary.import_provenance = {"version": 1}
    rows = {row.id: row for row in leg.ar_rows}
    for window in ordinary.transports.aar_windows:
        row = rows[window.id]
        window.start_anchor = row.start_anchor
        window.end_anchor = row.end_anchor
        window.override_start_time = None
        window.override_end_time = None
    artifacts = prepare_mission_timeline(
        ordinary,
        manager,
        None,
        parent_mission_id=mission_id,
        satellite_catalog=captured,
        constraint_config=ConstraintConfig(**constraints),
        discover_coverage=False,
    )
    return {
        "leg": ordinary.model_dump(mode="json"),
        "timeline": artifacts.timeline.model_dump(mode="json"),
    }
