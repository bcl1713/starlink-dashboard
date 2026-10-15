"""Rebuild planning evaluation from ordinary fields without choosing a new plan."""

import json
from types import SimpleNamespace

from app.mission.planning.grid import build_context
from app.mission.planning.inputs import build_inputs
from app.mission.planning.match import _baseline_delta, _candidates
from app.mission.planning.models import (
    AnchoredSwap,
    ExpectedLeg,
    ItineraryAR,
    PlanningDraft,
    RouteBinding,
)
from app.mission.timeline_builder.aar import resolve_aar_windows
from app.mission.timeline_builder.calculator import (
    RouteTemporalProjector,
    derive_mission_window,
)
from app.satellites.rules import ConstraintConfig


def refresh_context(
    mission, route, config=None, satellite_catalog=None, poi_manager=None
):
    """Current manual fields are authoritative; the optimizer is never invoked."""
    start, end = derive_mission_window(route)
    projector = RouteTemporalProjector(route, start, end)
    windows = resolve_aar_windows(mission, route, projector)
    if len(windows) != len(mission.transports.aar_windows):
        raise ValueError("Resolve AR windows against the current route before saving")
    # Resolve positions normally; the canonical builder already validates configured IDs.
    ids = {
        mission.transports.initial_x_satellite_id,
        *[s.target_satellite_id for s in mission.transports.x_transitions],
    }
    ids.discard(None)
    ids.discard("")
    previous = {}
    if mission.transports.planning_inputs:
        previous = {
            a["id"]: a
            for a in json.loads(
                mission.transports.planning_inputs.structural_draft_json
            ).get("ar_corrections", [])
        }
    rows = []
    for original, window in zip(mission.transports.aar_windows, windows):
        a = _candidates(window.start_time - _baseline_delta(route), "second", route)
        b = _candidates(window.end_time - _baseline_delta(route), "second", route)
        if len(a) != 1 or len(b) != 1:
            raise ValueError("AR occurrence is ambiguous on this route")
        if original.override_start_time or original.override_start_elapsed:
            a[0] = a[0].model_copy(
                update={"timing_mode": "fixed_utc", "source_time": window.start_time}
            )
            b[0] = b[0].model_copy(
                update={"timing_mode": "fixed_utc", "source_time": window.end_time}
            )
        old = previous.get(original.id, {})
        rows.append(
            ItineraryAR(
                id=original.id,
                track=old.get("track", original.start_waypoint_name),
                entry_time=window.start_time,
                exit_time=window.end_time,
                source_time_precision="second",
                source_altitude=old.get("source_altitude"),
                confirmed_units=old.get("confirmed_units"),
                start_anchor=a[0],
                end_anchor=b[0],
                match_status="matched",
            )
        )
    swaps = []
    for swap in mission.transports.x_transitions:
        anchor = swap.anchor
        if anchor is None:
            projected = projector.project(swap.latitude, swap.longitude)
            candidates = _candidates(
                projected.timestamp - _baseline_delta(route), "second", route
            )
            if len(candidates) != 1:
                raise ValueError("Resolve the handover occurrence before saving")
            anchor = candidates[0]
        swaps.append(
            AnchoredSwap(
                id=swap.id, target_satellite_id=swap.target_satellite_id, anchor=anchor
            )
        )
    draft = PlanningDraft(
        permitted_satellite_ids=sorted(ids),
        initial_x_satellite_id=mission.transports.initial_x_satellite_id,
        starshield_enabled=mission.transports.starshield_enabled,
        swaps=swaps,
        ar_corrections=rows,
        manual_aar_tracks=mission.transports.manual_aar_tracks,
        manual_route_splice=mission.transports.manual_route_splice,
        ka_outages=mission.transports.ka_outages,
        ku_overrides=mission.transports.ku_overrides,
        adjusted_departure_time=mission.adjusted_departure_time,
    )
    leg = ExpectedLeg(
        id=mission.id,
        ordinal=1,
        departure_airport="IMPORT",
        arrival_airport="IMPORT",
        departure_time=start,
        arrival_time=end,
        route=RouteBinding(
            route_id=route.route_id,
            source_id=route.route_id,
            content_hash=route.content_hash,
            filename="route.kml",
        ),
    )
    inputs = build_inputs(
        leg,
        draft,
        SimpleNamespace(get_route=lambda _: route),
        poi_manager,
        config or ConstraintConfig(),
    )
    context = build_context(inputs, draft)
    return inputs, draft, context


def refresh_leg(leg, route_manager, poi_manager=None):
    from app.mission.effective_route import prepare_effective_route

    if not leg.import_provenance:
        return leg
    route = prepare_effective_route(leg, route_manager)
    inputs, _draft, context = refresh_context(leg, route, poi_manager=poi_manager)
    leg.transports.planning_inputs = inputs
    leg.transports.evaluation_context = context
    return leg
