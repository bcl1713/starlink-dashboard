"""Parent-aware immutable inputs for detached planning candidates."""

from app.mission.availability import resolved_leg_availability
from app.mission.models import MissionLeg, TransportConfig


def for_run(mission, run_id=None):
    """Select operational history on a copy; persisted selectors never select live reads."""
    return mission.model_copy(
        update={
            "availability": mission.availability.model_copy(
                update={"simulation_run_id": run_id}
            )
        }
    )


def expected_snapshot(mission, card, draft=None, *, run_id=None):
    draft = draft or card.draft
    leg = MissionLeg(
        id=card.id,
        name=card.id,
        route_id=card.route.route_id if card.route else "",
        transports=TransportConfig(
            initial_x_satellite_id=draft.initial_x_satellite_id or "" if draft else "",
            starshield_enabled=draft.starshield_enabled if draft else True,
            availability_overrides=draft.availability_overrides if draft else None,
        ),
    )
    if not (
        mission.availability.revision
        or mission.availability.defaults
        or mission.availability.history
    ):
        from app.mission.availability_planning import leg_snapshot

        leg.id = card.id
        return leg_snapshot(leg)
    return resolved_leg_availability(for_run(mission, run_id), leg)


def selection_context(mission, card, route_manager, draft=None):
    """Capture eligibility and the actual effective flight window before X guards."""
    from app.mission.effective_route import prepare_effective_route
    from app.mission.timeline_builder.calculator import derive_mission_window

    draft = draft or card.draft
    start, end = card.departure_time, card.arrival_time
    if (
        draft is not None
        and card.route is not None
        and route_manager.get_route(card.route.route_id) is not None
    ):
        leg = MissionLeg(
            id=card.id,
            name=card.id,
            route_id=card.route.route_id,
            adjusted_departure_time=draft.adjusted_departure_time,
            transports=TransportConfig(
                initial_x_satellite_id=draft.initial_x_satellite_id or "",
                manual_aar_tracks=draft.manual_aar_tracks,
                manual_route_splice=draft.manual_route_splice,
            ),
        )
        start, end = derive_mission_window(prepare_effective_route(leg, route_manager))
    return dict(
        availability=expected_snapshot(mission, card, draft), start=start, end=end
    )
