"""Capture immutable planning inputs under the active-leg gate; compute outside."""

import json
import math
from dataclasses import asdict
from datetime import timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING

from app.mission import storage
from app.mission.effective_route import prepare_effective_route
from app.mission.models import MissionLeg, TransportConfig
from app.mission.timeline_builder.aar import apply_manual_aar_tracks
from app.mission.timeline_builder.calculator import (
    RouteTemporalProjector,
    derive_mission_window,
    route_with_adjusted_departure,
)
from app.satellites.rules import ConstraintConfig, EventType, RuleEngine

from .identity import planning_identity
from .match import resolve_anchor
from .models import PlanningInputs
from .satellites import resolve_positions
from .types import PlanningSpan

if TYPE_CHECKING:
    from app.services.poi_manager import POIManager
    from app.services.route_manager import RouteManager

    from .models import ExpectedLeg, PlanningDraft


def route_record(route):
    """Only immutable geometry/timing, never source filesystem paths or live state."""
    return {
        "route_id": route.route_id,
        "content_hash": route.content_hash,
        "ingestion_profile": route.ingestion_profile,
        "source_departure_time": route.source_departure_time,
        "points": [p.model_dump(mode="json") for p in route.points],
        "timing_profile": {
            "departure_time": route.timing_profile.departure_time.isoformat(),
            "arrival_time": route.timing_profile.arrival_time.isoformat(),
        },
        "metadata": {
            "name": "Planning route",
            "file_path": "",
            "point_count": len(route.points),
            "imported_at": "2000-01-01T00:00:00Z",
        },
    }


def _json(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=lambda v: v.isoformat()
    )


def structural_draft(draft):
    record = draft.model_dump(
        mode="json",
        exclude={
            "initial_x_satellite_id",
            "swaps",
            "evaluation_context",
            "access_confirmation",
            "no_ars_confirmed",
        },
    )
    for ar in record["ar_corrections"]:
        ar.pop("confirmed", None)
    return record


def input_identity(inputs):
    record = inputs.model_dump(mode="json")
    for field in (
        "route_json",
        "anchor_route_json",
        "structural_draft_json",
        "constraints_json",
        "coverage_json",
        "ka_coverage_events_json",
    ):
        record[field] = json.loads(record[field])
    return planning_identity(record)


def build_inputs(
    leg: "ExpectedLeg",
    draft: "PlanningDraft",
    route_manager: "RouteManager",
    poi_manager: "POIManager",
    constraints: ConstraintConfig,
) -> PlanningInputs:
    if draft.unresolved_x_transitions or draft.unresolved_aar_windows:
        raise ValueError(
            "Resolve pending legacy X transitions and AR windows using accepted timed route occurrences before computing"
        )
    # Copies alone are captured while sharing the activation/publication gate.
    with storage.get_active_leg_lock():
        leg = leg.model_copy(deep=True)
        draft = draft.model_copy(deep=True)
        if not leg.route:
            raise ValueError("A bound route is required")
        source = route_manager.get_route(leg.route.route_id)
        if source is None or source.content_hash != leg.route.content_hash:
            raise ValueError("Bound immutable route is missing or changed")
        source = source.model_copy(deep=True)
        if len(source.points) < 2:
            raise ValueError("Planning requires at least two timed route positions")
        positions = resolve_positions(draft.permitted_satellite_ids, poi_manager)
        configuration = ConstraintConfig(**asdict(constraints))
        from app.mission.exporter.snapshot_inputs import (
            _coverage_inputs,
            captured_coverage,
        )

        coverage_sources = _coverage_inputs()
    coverage_sampler = captured_coverage(coverage_sources)
    coverage_json = (
        _json(
            {
                "data": coverage_sampler.coverage_data,
                "polygons": coverage_sampler.satellite_polygons,
            }
        )
        if coverage_sampler is not None
        else "null"
    )
    rows = draft.ar_corrections or leg.ar_rows
    draft.ar_corrections = [row.model_copy(deep=True) for row in rows]
    preliminary = MissionLeg(
        id=leg.id,
        name=f"{leg.departure_airport}–{leg.arrival_airport}",
        route_id=leg.route.route_id,
        adjusted_departure_time=draft.adjusted_departure_time,
        transports=TransportConfig(
            initial_x_satellite_id=draft.initial_x_satellite_id or "",
            manual_aar_tracks=draft.manual_aar_tracks,
            manual_route_splice=draft.manual_route_splice,
        ),
    )
    view = SimpleNamespace(get_route=lambda _: source)
    route = prepare_effective_route(preliminary, view)
    anchor_route = route_with_adjusted_departure(source, draft.adjusted_departure_time)
    start, end = derive_mission_window(route)
    projector = RouteTemporalProjector(route, start, end)
    ar_windows, unresolved, assumptions = (
        [],
        [],
        [
            "Ku capability assumes availability except configured outages; operational enablement is applied separately.",
            "Geometry is sampled at each left boundary and held until the next boundary.",
            "Geostationary satellite latitude is approximated as equatorial by the shared look-angle model.",
        ],
    )
    if leg.ar_section_status == "unrecognized":
        unresolved.append("AR section is unrecognized; explicitly review its contents")
    for ar in rows:
        if ar.match_status == "excluded":
            continue
        if not ar.start_anchor or not ar.end_anchor:
            unresolved.append(f"AR {ar.id} has unresolved occurrence anchors")
            continue
        entry = resolve_anchor(ar.start_anchor, anchor_route)
        exit = resolve_anchor(ar.end_anchor, anchor_route)
        height, assumption = None, None
        if ar.source_altitude is not None and ar.confirmed_units is not None:
            height = ar.geometric_height_meters()
            if height < 0:
                height = None
        if height is None:
            unresolved.append(
                f"AR {ar.id} requires usable altitude and confirmed units"
            )
            assumption = f"AR {ar.id}: unconfirmed/unusable height; route height then cruise fallback used"
        elif ar.confirmed_units == "flight_level":
            assumption = f"AR {ar.id}: flight level × 30.48 m is approximate pressure-altitude geometry"
        if assumption:
            assumptions.append(assumption)
        ar_windows.append(
            PlanningSpan(
                start_time=entry,
                end_time=exit,
                reason=f"ar:{ar.id}",
                height_meters=height,
                assumption=assumption,
            )
        )
    engine = RuleEngine(configuration)
    from app.mission.derived_route import build_derived_route_estimate

    splice = draft.manual_route_splice
    manual_tracks = [
        t
        for t in draft.manual_aar_tracks
        if not splice
        or t.id != splice.enabled_track_id
        or build_derived_route_estimate(anchor_route, t, splice).available
    ]
    apply_manual_aar_tracks(engine, manual_tracks, projector)
    overlays = []
    for event in engine.events:
        if event.event_type != EventType.MANUAL_AAR_TRACK_START:
            continue
        finish = next(
            e
            for e in engine.events
            if e.event_type == EventType.MANUAL_AAR_TRACK_END
            and e.metadata["track_id"] == event.metadata["track_id"]
        )
        overlays.append(
            PlanningSpan(
                start_time=event.timestamp,
                end_time=finish.timestamp,
                reason=f"manual_ar:{event.metadata['track_id']}",
            )
        )

    def outages(items, transport):
        return tuple(
            PlanningSpan(
                start_time=x.start_time,
                end_time=x.start_time + timedelta(seconds=x.duration_seconds),
                reason=f"{transport}_outage:{getattr(x, 'reason', None) or x.id}",
            )
            for x in items
            if x.duration_seconds > 0
        )

    safety = [
        PlanningSpan(
            start_time=x.start_time, end_time=x.end_time, reason="Safety-of-Flight (AR)"
        )
        for x in ar_windows
    ]
    for a, b, reason in (
        (
            start,
            min(end, start + timedelta(minutes=configuration.takeoff_buffer_minutes)),
            "takeoff",
        ),
        (
            max(start, end - timedelta(minutes=configuration.landing_buffer_minutes)),
            end,
            "landing",
        ),
    ):
        if a < b:
            safety.append(
                PlanningSpan(
                    start_time=a, end_time=b, reason=f"Safety-of-Flight ({reason})"
                )
            )
    if any(
        p.altitude is None or not math.isfinite(p.altitude) or p.altitude < 0
        for p in route.points
    ):
        assumptions.append(
            "Route height gaps use a valid endpoint height, then the documented 10,668 m cruise fallback."
        )
    # Derive Ka events once, independent of X schedules and B's buffer edges.
    # Preserve canonical coverage/handoff interpolation and its sampled estimate.
    from app.mission.models import Transport, TransportState
    from app.mission.state import generate_transport_intervals
    from app.mission.timeline_builder.calculator import generate_timeline_samples
    from app.mission.timeline_builder.coverage import analyze_ka_coverage
    from app.mission.timeline_builder.events import apply_ka_events

    ka_samples = generate_timeline_samples(projector, coverage_sampler)
    coverage = analyze_ka_coverage(ka_samples, projector, coverage_sampler is not None)
    ka_engine = RuleEngine(configuration)
    apply_ka_events(ka_engine, coverage)
    ka_intervals = generate_transport_intervals(
        ka_engine.get_sorted_events(), start, end, [Transport.KA]
    )[Transport.KA]
    ka_windows = tuple(
        PlanningSpan(
            start_time=i.start,
            end_time=i.end,
            reason="; ".join(i.reasons),
            state=i.state.value,
        )
        for i in ka_intervals
        if i.end > i.start and i.state != TransportState.AVAILABLE
    )
    assumptions.append(
        "Ka coverage/handover events retain canonical 60-second sampling and interpolation, derived once before X candidate/buffer expansion."
    )
    if coverage_sampler is None:
        assumptions.append(
            "Ka coverage input unavailable; legacy configured-outages-only capability assumption retained."
        )
    return PlanningInputs(
        coverage_json=coverage_json,
        ka_coverage_windows=ka_windows,
        ka_coverage_events_json=_json(
            [e.model_dump(mode="json") for e in coverage.coverage_events]
        ),
        route_json=_json(route_record(route)),
        anchor_route_json=_json(route_record(anchor_route)),
        structural_draft_json=_json(structural_draft(draft)),
        constraints_json=_json(asdict(configuration)),
        start_time=start,
        end_time=end,
        ar_windows=tuple(ar_windows),
        overlays=tuple(overlays),
        ka_outages=outages(draft.ka_outages, "ka"),
        ku_outages=outages(draft.ku_overrides, "ku"),
        safety_windows=tuple(safety),
        satellites=positions,
        starshield_enabled=draft.starshield_enabled,
        assumptions=tuple(assumptions),
        unresolved=tuple(unresolved),
    )


def draft_to_mission_leg(
    inputs, draft, context, *, leg_id, name="Planned communications"
):
    from .canonical import draft_to_mission_leg as project

    return project(inputs, draft, context, leg_id=leg_id, name=name)


def canonical_inputs(
    mission, route, constraints=None, satellite_catalog=None, poi_manager=None
):
    from .canonical import canonical_inputs as validate

    return validate(mission, route, constraints, satellite_catalog, poi_manager)
