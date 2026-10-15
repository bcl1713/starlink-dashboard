"""Review uses the same pure customer overview eligibility as export."""

from app.mission.exporter.map_inputs import prepare_map_input

from .models import PlanningError


def check_map_review(snapshot_leg, projected_leg):
    result = prepare_map_input(snapshot_leg, projected_leg, include_markers=False)
    return tuple(
        PlanningError(
            code=f"map_{item.code}",
            message=item.message,
            field="route",
            action="Review the timed route and this customer map limitation before publication",
        )
        for item in result.diagnostics
        if item.severity == "error"
    )


def check_prepared_map(leg, artifacts, constraints, poi_manager):
    from app.mission.exporter.customer_projection import project_briefing_leg
    from app.mission.exporter.snapshot import (
        LegSnapshot,
        _availability_basis,
        _event_sources,
        _restrictions,
    )
    from app.mission.exporter.snapshot_inputs import (
        canonical_json,
        capture_default_coverage,
    )
    from app.satellites.catalog import get_satellite_catalog

    captured = LegSnapshot(
        leg.id,
        canonical_json(leg.model_dump(mode="json")),
        canonical_json(artifacts.route.model_dump(mode="json")),
        canonical_json(artifacts.timeline.model_dump(mode="json")),
        _event_sources(artifacts, constraints)
        + _availability_basis(
            artifacts,
            capture_default_coverage(),
            get_satellite_catalog(read_only=True),
            poi_manager,
            (),
        ),
        _restrictions(leg, artifacts, constraints),
        (artifacts.projector.start_time, artifacts.projector.end_time),
        "rebuilt",
        (),
    )
    return check_map_review(captured, project_briefing_leg(captured))
