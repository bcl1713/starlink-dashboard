"""Interval arithmetic and collection-gap summaries."""

from datetime import datetime


def merge_ranges(ranges):
    merged = []
    for left, right in sorted(ranges):
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], right))
        else:
            merged.append((left, right))
    return merged


def uncovered(start, end, ranges):
    remaining = []
    cursor = start
    for left, right in merge_ranges(ranges):
        if right <= cursor or left >= end:
            continue
        if left > cursor:
            remaining.append((cursor, min(left, end)))
        cursor = max(cursor, right)
    if cursor < end:
        remaining.append((cursor, end))
    return remaining


def iso(value, now):
    return datetime.fromtimestamp(value, now.tzinfo).isoformat()


def coverage_gaps(start, end, samples):
    points = sorted({datetime.fromisoformat(row["timestamp"]) for row in samples})
    if not points:
        return [
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "reason": "source_unavailable",
            }
        ]
    gaps, previous = [], start
    for point in points + [end]:
        if (point - previous).total_seconds() > 10:
            gaps.append(
                {
                    "start": previous.isoformat(),
                    "end": point.isoformat(),
                    "reason": "missing_observations",
                }
            )
        previous = point
    return gaps
