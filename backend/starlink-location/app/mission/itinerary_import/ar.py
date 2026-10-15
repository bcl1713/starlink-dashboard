"""Resolve AR boundaries against KML takeoff/landing, preserving source evidence."""

from app.mission.planning.match import _anchor, _baseline_delta, _candidates
from app.mission.planning.models import ExpectedLeg
from app.models.route import ParsedRoute

from .models import ARResolution, ImportIssue


def _near(a, b):
    return (
        abs(
            (
                a.replace(second=0, microsecond=0) - b.replace(second=0, microsecond=0)
            ).total_seconds()
        )
        <= 60
    )


def _boundary(route, time, track=None):
    delta = _baseline_delta(route)
    named = []
    if track:
        for waypoint in route.waypoints:
            if (
                waypoint.name or ""
            ).strip().upper() == track.strip().upper() and waypoint.point_sequence is not None:
                index = waypoint.point_sequence
                if 0 <= index < len(route.points):
                    point = route.points[index]
                    if (
                        point.expected_arrival_time is not None
                        and point.timing_source != "interpolated"
                    ):
                        named.append(
                            _anchor(
                                route,
                                index,
                                0,
                                point.expected_arrival_time,
                                point.occurrence_id,
                            )
                        )
        nearby = [a for a in named if _near(a.source_time + delta, time)]
        if nearby or named:
            return nearby or named
    # Use the existing source-bound interpolation, not the closest named point.
    return _candidates(time - delta, "second", route)


def resolve_import_ars(
    leg: ExpectedLeg, route: ParsedRoute, choices=None
) -> ARResolution:
    result = ARResolution()
    timing = route.timing_profile
    for source in leg.ar_rows:
        row = source.model_copy(deep=True)
        if row.match_status == "excluded":
            result.rows.append(row)
            continue
        row.start_anchor = row.end_anchor = None
        row.confirmed = False
        row.match_status = "unresolved"
        start = end = []
        entry = exit = None
        if timing and timing.departure_time and timing.arrival_time:
            entry_offset = source.entry_time - leg.departure_time
            exit_offset = leg.arrival_time - source.exit_time
            entry = timing.departure_time + entry_offset
            exit = timing.arrival_time - exit_offset
            result.evidence[row.id] = {
                "source_entry_time": source.entry_time.isoformat(),
                "source_exit_time": source.exit_time.isoformat(),
                "precision": source.source_time_precision,
                "entry_offset_seconds": entry_offset.total_seconds(),
                "exit_offset_seconds": exit_offset.total_seconds(),
                "effective_entry_candidate": entry.isoformat(),
                "effective_exit_candidate": exit.isoformat(),
            }
            if timing.departure_time <= entry < exit <= timing.arrival_time:
                start, end = _boundary(route, entry, source.track), _boundary(
                    route, exit
                )
        pairs = [
            (a, b)
            for a in start
            for b in end
            if a.source_time < b.source_time
            and a.segment_index + a.fraction < b.segment_index + b.fraction
            and timing.departure_time <= a.source_time + _baseline_delta(route)
            and b.source_time + _baseline_delta(route) <= timing.arrival_time
        ]
        # Duplicate KML representations at the same occurrence are one boundary.
        unique = {
            (a.segment_index, a.fraction, b.segment_index, b.fraction): (a, b)
            for a, b in pairs
        }
        import json

        options = [
            {
                "value": json.dumps([a.occurrence_id, b.occurrence_id]),
                "label": f"{a.source_time.isoformat()} → {b.source_time.isoformat()}",
            }
            for a, b in unique.values()
        ]
        result.evidence.setdefault(row.id, {})["candidate_pairs"] = options
        choice = (choices or {}).get(row.id)
        if choice:
            unique = {
                key: (a, b)
                for key, (a, b) in unique.items()
                if json.dumps([a.occurrence_id, b.occurrence_id]) == choice
            }
        if len(unique) == 1:
            row.start_anchor, row.end_anchor = next(iter(unique.values()))
            row.match_status = "matched"
        else:
            row.match_status = "ambiguous" if unique else "unresolved"
            result.issues.append(
                ImportIssue(
                    code="ar_association_" + row.match_status,
                    leg_id=leg.id,
                    field=row.id,
                    message="Resolve the AR boundary association for this route.",
                    candidates=[o["value"] for o in options],
                )
            )
        result.rows.append(row)
    return result
