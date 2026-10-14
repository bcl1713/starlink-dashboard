"""Synthetic records; no operational documents or shared stores."""


def anchor_fields(**changes):
    return {
        "route_id": "route-owned",
        "content_hash": "a" * 64,
        "segment_index": 0,
        "fraction": 0.5,
        "occurrence_id": "occurrence-1",
        "source_time": "2026-10-25T12:00:30Z",
        "latitude": 35.0,
        "longitude": 179.5,
        "timing_mode": "route_bound",
        **changes,
    }


def expected_leg_fields(**changes):
    return {
        "id": "expected-1",
        "ordinal": 1,
        "departure_airport": "AAAA",
        "arrival_airport": "BBBB",
        "departure_time": "2026-10-25T12:00:00Z",
        "arrival_time": "2026-10-25T14:00:00Z",
        **changes,
    }


def ar_fields(**changes):
    return {
        "id": "ar-1",
        "track": "SYNTHETIC",
        "source_page": 1,
        "source_row": 3,
        "source_text": "SYNTHETIC 12:10 12:20 210",
        "entry_time": "2026-10-25T12:10:00Z",
        "exit_time": "2026-10-25T12:20:00Z",
        "source_time_precision": "minute",
        "source_altitude": 210,
        **changes,
    }


def schedule_key(inputs, draft):
    from app.mission.planning.grid import swap_times

    return (
        draft.initial_x_satellite_id,
        tuple(
            sorted(
                (time.isoformat(), swap.target_satellite_id)
                for time, swap in zip(swap_times(inputs, draft), draft.swaps)
            )
        ),
    )


def timed_swap(inputs, seconds, satellite, *, origin="manual", id=None):
    from datetime import timedelta

    from app.mission.planning.match import _candidates
    from app.mission.planning.models import AnchoredSwap
    from app.models.route import ParsedRoute

    route = ParsedRoute.model_validate_json(inputs.anchor_route_json)
    time = route.source_departure_time + timedelta(seconds=seconds)
    anchor = _candidates(time, "second", route)[0]
    return AnchoredSwap(
        id=id or f"test-{seconds}-{satellite}",
        target_satellite_id=satellite,
        anchor=anchor,
        origin=origin,
    )


def exhaustive_schedules(inputs, draft, context):
    """Independent Cartesian enumeration; intentionally no solver utilities."""
    import itertools
    import json
    from datetime import timedelta

    from app.mission.planning.match import resolve_anchor
    from app.models.route import ParsedRoute

    route = ParsedRoute.model_validate_json(inputs.anchor_route_json)
    buffer = timedelta(
        minutes=json.loads(inputs.constraints_json)["transition_buffer_minutes"]
    )
    locked = {}
    initials = set(draft.permitted_satellite_ids)
    for lock in draft.locks:
        if lock.kind == "initial":
            initials &= {lock.target_satellite_id}
        else:
            locked[resolve_anchor(lock.anchor, route)] = lock
    choices = [
        t
        for t in context.candidate_times
        if inputs.start_time < t < inputs.end_time
        and t - buffer >= inputs.start_time
        and t + buffer <= inputs.end_time
        and t not in locked
    ]
    for initial in sorted(initials):
        for assignments in itertools.product(
            [None, *sorted(draft.permitted_satellite_ids)], repeat=len(choices)
        ):
            chosen = [(t, s) for t, s in zip(choices, assignments) if s]
            if any(b - a < 2 * buffer for (a, _), (b, _) in itertools.pairwise(chosen)):
                continue
            swaps = [
                timed_swap(
                    inputs,
                    (t - inputs.start_time).total_seconds(),
                    s,
                    origin="generated",
                )
                for t, s in chosen
            ]
            for time, lock in locked.items():
                existing = next((s for s in draft.swaps if s.id == lock.swap_id), None)
                if existing:
                    swaps.append(existing)
                else:
                    swaps.append(
                        timed_swap(
                            inputs,
                            (time - inputs.start_time).total_seconds(),
                            lock.target_satellite_id,
                            id=lock.swap_id or lock.id,
                        )
                    )
            swaps.sort(key=lambda s: resolve_anchor(s.anchor, route))
            yield draft.model_copy(
                deep=True,
                update={
                    "initial_x_satellite_id": initial,
                    "swaps": swaps,
                    "evaluation_context": context,
                },
            )


def canonical_evaluation(inputs, draft, context):
    import json
    from types import SimpleNamespace

    from app.mission.planning.inputs import draft_to_mission_leg
    from app.mission.timeline_preparation import prepare_mission_timeline
    from app.models.route import ParsedRoute
    from app.satellites.catalog import Satellite, SatelliteCatalog
    from app.satellites.rules import ConstraintConfig

    catalog = SatelliteCatalog()
    for sat in inputs.satellites:
        catalog.add_satellite(Satellite(sat.satellite_id, "X", longitude=sat.longitude))
    source = ParsedRoute.model_validate_json(inputs.anchor_route_json)
    manager = SimpleNamespace(get_route=lambda _: source)
    leg = draft_to_mission_leg(inputs, draft, context, leg_id="test-canonical")
    return prepare_mission_timeline(
        leg,
        manager,
        discover_coverage=False,
        satellite_catalog=catalog,
        constraint_config=ConstraintConfig(**json.loads(inputs.constraints_json)),
    ).planning_evaluation
