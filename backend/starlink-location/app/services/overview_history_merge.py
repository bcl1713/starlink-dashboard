"""Replace authoritative overlap intervals without mutating published snapshots."""

from app.services.overview_history_prometheus import MAX_OVERVIEW_HISTORY_SAMPLES
from app.services.overview_history_rollups import ROLLUP_FUNCTIONS, ROLLUP_METRICS


def merge_history(previous: dict, incoming: dict, overlap_start: int) -> dict:
    """Clip old points, replace the complete tail, and withhold failed rollups."""
    start = incoming["start_timestamp_seconds"]
    end = incoming["end_timestamp_seconds"]

    def merge(old: list, new: list) -> list:
        points = [
            *[point for point in old if start <= point[0] < overlap_start],
            *[point for point in new if start <= point[0] <= end],
        ]
        by_time = {point[0]: point for point in points}
        return [by_time[t] for t in sorted(by_time)[-MAX_OVERVIEW_HISTORY_SAMPLES:]]

    raw = {}
    ambiguous = {
        metric for metric, identity in previous["_identity"].items() if identity is None
    }
    for metric in previous["series"].keys() | incoming["series"].keys():
        if metric in ambiguous:
            continue
        points = merge(
            previous["series"].get(metric, []), incoming["series"].get(metric, [])
        )
        if points:
            raw[metric] = points
    rollups = {}
    for metric in ROLLUP_METRICS:
        old, new = previous["rolling_5m"][metric], incoming["rolling_5m"][metric]
        available = old["state"] == new["state"] == "available"
        observed = {point[0] for point in raw.get(metric, [])}
        rollups[metric] = {"state": "available" if available else "unavailable"}
        for statistic in ROLLUP_FUNCTIONS:
            rollups[metric][statistic] = (
                [
                    point
                    for point in merge(old[statistic], new[statistic])
                    if point[0] in observed
                ]
                if available
                else []
            )
    return {
        **incoming,
        "series": raw,
        "rolling_5m": rollups,
        "_identity": previous["_identity"],
    }
