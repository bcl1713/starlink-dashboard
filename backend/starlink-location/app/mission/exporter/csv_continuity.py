"""Exact captured call intervals for CSV; physical transport columns are retained."""

from itertools import pairwise

from .customer_pop import captured_continuity

CONTINUITY_COLUMNS = (
    "Call Continuity",
    "Call Interval Start UTC",
    "Call Interval End UTC",
    "PoP Transition IDs",
    "Call Alternatives",
    "Call Source IDs",
    "Planned Communications Outage Seconds",
    "PoP Call Outage Seconds",
    "Longest Call Outage Seconds",
)


def apply_csv_continuity(timeline):
    """Adapt the shared projection on a private normalized timeline copy."""
    segments = timeline.segments
    if not segments:
        return
    bounds = (min(s.start_time for s in segments), max(s.end_time for s in segments))
    projection = captured_continuity(
        timeline.model_dump(mode="json"), timeline.pop_forecast, bounds
    )
    calls = projection.intervals if projection else ()
    resolved = bool(calls) and all(c.classification != "unknown" for c in calls)
    totals = (
        (
            projection.planned_communications_outage_seconds,
            projection.pop_call_outage_seconds,
            projection.longest_call_outage_seconds,
        )
        if resolved
        else ("Unresolved",) * 3
    )
    result = []
    for segment in segments:
        edges = {segment.start_time, segment.end_time}
        for call in calls:
            if max(segment.start_time, call.start_utc) < min(
                segment.end_time, call.end_utc
            ):
                edges.update(
                    (
                        max(segment.start_time, call.start_utc),
                        min(segment.end_time, call.end_utc),
                    )
                )
        for start, end in pairwise(sorted(edges)):
            call = next((c for c in calls if c.start_utc <= start < c.end_utc), None)
            classification = call.classification if call else "unknown"
            metadata = dict(segment.metadata)
            posture = {
                "planned_outage": "Communications unavailable",
                "existing_outage": "Communications unavailable",
                "x_fallback": "Planned X-Band fallback",
                "unknown": "Call continuity unresolved",
            }.get(classification)
            if posture:
                metadata["call_posture"] = posture
            metadata["call_continuity_csv"] = dict(
                zip(
                    CONTINUITY_COLUMNS,
                    (
                        classification,
                        start.isoformat().replace("+00:00", "Z"),
                        end.isoformat().replace("+00:00", "Z"),
                        "; ".join(call.transition_ids) if call else "",
                        (
                            "; ".join(call.usable_alternatives)
                            if call and call.transition_ids
                            else ""
                        ),
                        "; ".join(call.source_ids) if call else "",
                        *totals,
                    ),
                )
            )
            result.append(
                segment.model_copy(
                    update={"start_time": start, "end_time": end, "metadata": metadata}
                )
            )
    timeline.segments = result
