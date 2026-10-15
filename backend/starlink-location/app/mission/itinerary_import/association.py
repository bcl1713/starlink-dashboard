"""Precision-aware global route association without file-order tie breaking."""

from collections.abc import Mapping, Sequence
from functools import lru_cache

from app.mission.planning.models import ExpectedLeg
from app.models.route import ParsedRoute

from .models import AssociationResult, ImportIssue


def endpoints(route: ParsedRoute) -> tuple[str, str] | None:
    primary = sorted(
        (w for w in route.waypoints if w.role != "alternate"), key=lambda w: w.order
    )
    if not primary or not primary[0].name or not primary[-1].name:
        return None
    return primary[0].name.strip().upper(), primary[-1].name.strip().upper()


def _evidence(leg, route):
    timing = route.timing_profile
    if (
        endpoints(route)
        != (leg.departure_airport.strip().upper(), leg.arrival_airport.strip().upper())
        or not timing
        or not timing.departure_time
        or not timing.arrival_time
        or timing.arrival_time <= timing.departure_time
    ):
        return None
    dep, arr = timing.departure_time, timing.arrival_time
    # Admit nearby service-day shifts across midnight. Repeated endpoint
    # candidates still require a unique global assignment; clock proximity
    # beyond minute equivalence never ranks them.
    minute = lambda t: t.replace(second=0, microsecond=0)
    deltas = [
        (minute(a) - minute(b)).total_seconds()
        for a, b in [(dep, leg.departure_time), (arr, leg.arrival_time)]
    ]
    close = all(abs(d) <= 60 for d in deltas)
    if not close and any(abs(d) >= 12 * 3600 for d in deltas):
        return None
    return {
        "minute_equivalent": close,
        "departure_offset_seconds": (dep - leg.departure_time).total_seconds(),
        "arrival_offset_seconds": (arr - leg.arrival_time).total_seconds(),
        "duration_difference_seconds": (
            (arr - dep) - (leg.arrival_time - leg.departure_time)
        ).total_seconds(),
    }


def associate_routes(
    legs: Sequence[ExpectedLeg], routes: Mapping[str, ParsedRoute]
) -> AssociationResult:
    """Accept only edges forced across all optimal one-to-one assignments.

    An endpoint/date match admits an edge; minute equivalence strengthens it.
    Larger clock differences alone cannot rank repeated matching routes.
    """
    if len(routes) > 16 or len(legs) > 16:
        raise ValueError("Automatic route association supports at most 16 legs/routes")
    ids = list(routes)
    edges = {
        (i, j): e
        for i, leg in enumerate(legs)
        for j, rid in enumerate(ids)
        if (e := _evidence(leg, routes[rid])) is not None
    }

    @lru_cache(None)
    def best(i, mask):
        if i == len(legs):
            return (0, 0)
        score = best(i + 1, mask)
        for j in range(len(ids)):
            if mask & (1 << j) or (i, j) not in edges:
                continue
            rest = best(i + 1, mask | (1 << j))
            candidate = (rest[0] + 1, rest[1] + int(edges[i, j]["minute_equivalent"]))
            score = max(score, candidate)
        return score

    possibilities = [set() for _ in legs]
    seen = set()

    def visit(i, mask):
        if i == len(legs) or (i, mask) in seen:
            return
        seen.add((i, mask))
        score = best(i, mask)
        if best(i + 1, mask) == score:
            possibilities[i].add(None)
            visit(i + 1, mask)
        for j in range(len(ids)):
            if mask & (1 << j) or (i, j) not in edges:
                continue
            rest = best(i + 1, mask | (1 << j))
            if (rest[0] + 1, rest[1] + int(edges[i, j]["minute_equivalent"])) == score:
                possibilities[i].add(j)
                visit(i + 1, mask | (1 << j))

    visit(0, 0)
    result = AssociationResult()
    for i, leg in enumerate(legs):
        choices = possibilities[i]
        if len(choices) == 1 and None not in choices:
            j = next(iter(choices))
            result.assignments[leg.id] = ids[j]
            result.evidence[leg.id] = edges[i, j]
        else:
            result.issues.append(
                ImportIssue(
                    code="route_association_unresolved",
                    leg_id=leg.id,
                    message="Choose the route for this leg; source evidence does not identify one unique match.",
                    candidates=[ids[j] for j in range(len(ids)) if (i, j) in edges],
                )
            )
    for rid in ids:
        if rid not in result.assignments.values() and not any(
            rid in issue.candidates for issue in result.issues
        ):
            result.issues.append(
                ImportIssue(
                    code="unassigned_route",
                    route_id=rid,
                    message="This route does not match an itinerary leg.",
                )
            )
    return result
