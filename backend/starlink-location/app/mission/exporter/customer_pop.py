"""Advisory-only partitions over the existing immutable availability partition."""

from dataclasses import replace
from itertools import pairwise

from app.services.pop.models import PopForecast

POP_EVENT = "Starshield PoP transition possible — brief call interruption."
POP_NOTE = (
    "PoP transitions may briefly interrupt calls (typically 1–2 seconds). "
    "Marked windows indicate possible transition timing."
)


def partition_pop_windows(intervals, forecast: PopForecast | None):
    """Clip display bounds only; preserve every original decision and restriction."""
    if not intervals or forecast is None or forecast.status != "ready":
        return intervals
    transitions = forecast.transitions
    result = []
    for interval in intervals:
        a, b = interval.start_time, interval.end_time
        edges = {a, b}
        for transition in transitions:
            low, high = transition.window_start_utc, transition.window_end_utc
            if max(a, low) < min(b, high):
                edges.update((max(a, low), min(b, high)))
        for low, high in pairwise(sorted(edges)):
            identities = tuple(
                t.crossing.id
                for t in transitions
                if t.window_start_utc <= low < t.window_end_utc
            )
            result.append(
                replace(
                    interval,
                    start_time=low,
                    end_time=high,
                    pop_transition_ids=identities,
                )
            )
    return tuple(
        replace(i, id=f"{intervals[0].id}-pop-{n:03d}", window_number=n)
        for n, i in enumerate(result, 1)
    )


def transition_records(forecast: PopForecast | None):
    """Full canonical bounds survive flight clipping and pagination unchanged."""
    from .customer_document import stamp

    if forecast is None or forecast.status != "ready":
        return []
    return [
        {
            "id": t.crossing.id,
            "fromPopId": t.crossing.from_pop_id,
            "toPopId": t.crossing.to_pop_id,
            "crossingUtc": stamp(t.crossing_utc),
            "windowStartUtc": stamp(t.window_start_utc),
            "windowEndUtc": stamp(t.window_end_utc),
        }
        for t in forecast.transitions
    ]
