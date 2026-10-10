"""Installed-leg projection and validation of persisted planning snapshots."""

import json
from dataclasses import asdict

from app.mission.models import AARWindow, MissionLeg, TransportConfig, XTransition
from app.models.route import ParsedRoute

from .identity import planning_identity
from .inputs import resolve_positions, route_record
from .models import PlanningDraft, PlanningInputs


def draft_to_mission_leg(
    inputs, draft, context, *, leg_id, name="Planned communications"
):
    """Project a validated evaluation into canonical legacy fields; no writes."""
    from .grid import validate_context

    validate_context(inputs, draft, context)
    route = ParsedRoute.model_validate_json(inputs.route_json)
    windows = [
        AARWindow(
            id=x.reason.removeprefix("ar:"),
            start_waypoint_name="",
            end_waypoint_name="",
            override_start_time=x.start_time,
            override_end_time=x.end_time,
        )
        for x in inputs.ar_windows
    ]
    return MissionLeg(
        id=leg_id,
        name=name,
        route_id=route.route_id,
        adjusted_departure_time=draft.adjusted_departure_time,
        transports=TransportConfig(
            initial_x_satellite_id=draft.initial_x_satellite_id,
            starshield_enabled=draft.starshield_enabled,
            planning_policy=draft.planning_policy,
            evaluation_context=context,
            planning_inputs=inputs,
            x_transitions=[
                XTransition(
                    id=s.id,
                    target_satellite_id=s.target_satellite_id,
                    latitude=s.anchor.latitude,
                    longitude=s.anchor.longitude,
                    anchor=s.anchor,
                )
                for s in draft.swaps
            ],
            aar_windows=windows,
            manual_aar_tracks=draft.manual_aar_tracks,
            manual_route_splice=draft.manual_route_splice,
            ka_outages=draft.ka_outages,
            ku_overrides=draft.ku_overrides,
        ),
    )


def canonical_inputs(
    mission, route, constraints=None, satellite_catalog=None, poi_manager=None
):
    """Reject changed route/transport payloads before using persisted geometry."""
    from .models import AnchoredSwap

    inputs = PlanningInputs.model_validate(
        mission.transports.planning_inputs.model_dump()
    )
    if planning_identity(route_record(route)) != planning_identity(
        json.loads(inputs.route_json)
    ):
        raise ValueError("Planning effective route changed; rebuild evaluation context")
    if constraints is not None and asdict(constraints) != json.loads(
        inputs.constraints_json
    ):
        raise ValueError("Planning constraints changed; rebuild evaluation context")
    if satellite_catalog is not None or poi_manager is not None:
        positions = resolve_positions(
            [s.satellite_id for s in inputs.satellites], poi_manager, satellite_catalog
        )
        if positions != inputs.satellites:
            raise ValueError(
                "Planning satellite positions changed; rebuild evaluation context"
            )
    draft = PlanningDraft.model_validate(json.loads(inputs.structural_draft_json))
    draft.initial_x_satellite_id = mission.transports.initial_x_satellite_id
    draft.swaps = [
        AnchoredSwap(
            id=s.id, target_satellite_id=s.target_satellite_id, anchor=s.anchor
        )
        for s in mission.transports.x_transitions
    ]
    context = mission.transports.evaluation_context
    expected = draft_to_mission_leg(inputs, draft, context, leg_id=mission.id)
    omitted = {
        "initial_x_satellite_id",
        # Preserved legacy metadata; the planning evaluator uses Ka outage windows.
        "initial_ka_satellite_ids",
        "x_transitions",
        "evaluation_context",
        "planning_inputs",
    }
    if (
        expected.transports.model_dump(exclude=omitted)
        != mission.transports.model_dump(exclude=omitted)
        or expected.adjusted_departure_time != mission.adjusted_departure_time
    ):
        raise ValueError(
            "Planning transport inputs changed; rebuild evaluation context"
        )
    return inputs, draft, context
