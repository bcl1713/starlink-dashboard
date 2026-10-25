"""Captured call continuity over an immutable physical availability partition."""

from dataclasses import replace
from itertools import pairwise

from app.services.pop.continuity_models import CallContinuityProjection
from app.services.pop.models import PopForecast

POP_EVENT = "Starshield Transition Window"
POP_NOTE = (
    "PoP changes may drop calls and require reestablishment. RF may remain connected. "
    "Full windows are planned outages only without an alternative; "
    "coordinate X fallback when available."
)


def captured_continuity(timeline, forecast, bounds):
    """Accept only the complete projection captured with this planned forecast."""
    raw = timeline.get("call_continuity")
    if not raw or not forecast or not bounds:
        return None
    projection = CallContinuityProjection.model_validate(raw)
    if projection.revision != forecast.revision or not projection.intervals:
        return None
    cursor = bounds[0]
    for interval in projection.intervals:
        if interval.start_utc != cursor or interval.end_utc > bounds[1]:
            return None
        expected = tuple(
            t.crossing.id
            for t in forecast.transitions
            if t.window_start_utc <= interval.start_utc < t.window_end_utc
        )
        if interval.transition_ids != expected:
            return None
        cursor = interval.end_utc
    return projection if cursor == bounds[1] else None


def partition_pop_windows(
    intervals,
    forecast: PopForecast | None,
    continuity=None,
    *,
    starshield_enabled=True,
    availability=None,
):
    """Clip display bounds only; preserve every original decision and restriction."""
    if (
        not intervals
        or not starshield_enabled
        or (forecast and forecast.status == "disabled")
    ):
        return intervals
    transitions = (
        forecast.transitions if forecast and forecast.status == "ready" else ()
    )
    calls = continuity.intervals if continuity else ()
    result = []
    for interval in intervals:
        a, b = interval.start_time, interval.end_time
        edges = {a, b}
        for transition in transitions:
            low, high = transition.window_start_utc, transition.window_end_utc
            if max(a, low) < min(b, high):
                edges.update((max(a, low), min(b, high)))
        for call in calls:
            if max(a, call.start_utc) < min(b, call.end_utc):
                edges.update((max(a, call.start_utc), min(b, call.end_utc)))
        for low, high in pairwise(sorted(edges)):
            identities = tuple(
                t.crossing.id
                for t in transitions
                if t.window_start_utc <= low < t.window_end_utc
                and (availability is None or availability.resolve(low)["Ku"])
            )
            call = next((c for c in calls if c.start_utc <= low < c.end_utc), None)
            classification = call.classification if call else "unknown"
            call_sources = call.source_ids if call else ()
            alternatives = call.usable_alternatives if call else ()
            if (
                interval.physical_posture == "Communications unavailable"
                and classification != "existing_outage"
            ):
                classification = "existing_outage"
                alternatives = ()
                call_sources = tuple(
                    dict.fromkeys((*call_sources, *interval.active_source_ids))
                )
            posture = interval.posture
            remaining = interval.remaining_transports
            if classification in {"planned_outage", "existing_outage"}:
                posture, remaining = "Communications unavailable", ()
            elif classification == "x_fallback":
                posture, remaining = "Limited / elevated risk", (
                    "Planned X-Band fallback",
                )
            elif classification == "unknown":
                posture, remaining = "Posture uncertain", ()
            result.append(
                replace(
                    interval,
                    start_time=low,
                    end_time=high,
                    pop_transition_ids=identities,
                    call_classification=classification,
                    call_source_ids=call_sources,
                    call_alternatives=alternatives,
                    posture=posture,
                    remaining_transports=remaining,
                )
            )
    if forecast is None and not calls:
        return tuple(result)
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
