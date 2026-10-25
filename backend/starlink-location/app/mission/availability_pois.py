"""Pure applicability of canonical transport cues, independent of lifecycle state."""

from app.mission.models import Transport


def poi_transport(kind):
    if kind and kind.startswith("x_band_"):
        return Transport.X
    if kind and kind.startswith("ka_"):
        return Transport.KA
    if kind and kind.startswith("starshield_"):
        return Transport.KU
    return None


def apply_poi_availability(poi, availability, *, now=None):
    """Resolve retained geometry again; current failure also suppresses delayed cues."""
    transport = poi_transport(poi.kind)
    if transport is None:
        return poi
    at = poi.expected_arrival_time or now
    if now is not None and at is not None:
        at = max(at, now)
    active = bool(at is not None and availability.resolve(at)[transport])
    if now is not None:
        active = active and availability.resolve(now)[transport]
    return poi.model_copy(
        update={
            "transport_active": active,
            "inactive_reason": None if active else "transport_unavailable",
        }
    )


def cue_identity(poi):
    return (poi.kind, poi.expected_arrival_time, poi.latitude, poi.longitude)


def merge_retained_pois(generated, retained, availability):
    """Retain omitted transport geometry for the same route without duplicates."""
    from app.models.poi import POICreate

    result = list(generated)
    seen = {cue_identity(p) for p in result}
    for previous in retained:
        if poi_transport(previous.kind) is None or cue_identity(previous) in seen:
            continue
        value = POICreate.model_validate(previous.model_dump())
        value._route_segment_index = previous.planned_route_segment_index
        result.append(value)
        seen.add(cue_identity(previous))
    return tuple(apply_poi_availability(p, availability) for p in result)


def project_current_pois(pois, route_manager, *, run_service=None, now=None):
    """Capture current parent/run once for active APIs; manual records remain intact."""
    from datetime import datetime, timezone

    from app.mission.active_context import resolve_active_mission_leg_context
    from app.mission.availability_context import snapshot_for_leg
    from app.simulation.run_timing import published_replay

    if route_manager is None:
        return pois
    context = resolve_active_mission_leg_context(route_manager).context
    if context is None:
        return pois
    selected = published_replay(run_service)
    clock = (
        selected[2].simulation_time if selected else now or datetime.now(timezone.utc)
    )
    snapshot = snapshot_for_leg(
        context.parent_mission,
        context.leg,
        run_id=selected[2].run_id if selected else None,
    )
    return [
        (
            apply_poi_availability(p, snapshot, now=clock)
            if p.generated_source == "mission-timeline"
            and p.mission_id == context.parent_mission_id
            and (p.route_id is None or p.route_id == context.route_id)
            else p
        )
        for p in pois
    ]
