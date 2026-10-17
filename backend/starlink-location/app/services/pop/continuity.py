"""Pure boundary sweep over canonical transition windows and capability evidence."""

import itertools
from collections.abc import Sequence
from datetime import datetime, timedelta

from app.services.pop.continuity_models import (
    CallContinuityInterval,
    CallContinuityProjection,
    CapabilitySpan,
)
from app.services.pop.models import PopForecast, _utc


def _validate(forecast, capabilities, start, end):
    if start >= end or not forecast.revision.strip():
        raise ValueError("Invalid continuity flight bounds or forecast revision")
    previous = None
    for span in sorted(capabilities, key=lambda c: c.start_utc):
        if span.start_utc >= span.end_utc or (
            previous is not None and span.start_utc < previous
        ):
            raise ValueError(
                "Capability evidence must be ordered non-overlapping intervals"
            )
        previous = span.end_utc
    ids = set()
    for transition in forecast.transitions:
        crossing = transition.crossing_utc
        if (
            transition.window_start_utc != crossing - timedelta(seconds=300)
            or transition.window_end_utc != crossing + timedelta(seconds=300)
            or not transition.crossing.id
            or transition.crossing.id in ids
        ):
            raise ValueError("Invalid canonical transition window or identity")
        ids.add(transition.crossing.id)


def _classify(span, active, forecast_status):
    if span is None:
        return "unknown", ()
    alternatives = tuple(
        name for name, value in (("Ka", span.ka), ("X", span.x)) if value == "available"
    )
    if span.existing_call_outage:
        return "existing_outage", alternatives
    if forecast_status not in ("ready", "disabled"):
        return "unknown", alternatives
    if not active:
        if not alternatives and span.starshield != "available":
            return "unknown", ()
        return "ordinary", alternatives
    if alternatives:
        return "advisory", alternatives
    if span.x_concurrency_only:
        return "x_fallback", ("X",)
    if span.starshield == "available" and span.ka == span.x == "unavailable":
        return "planned_outage", ()
    return "unknown", ()


def project_call_continuity(
    forecast: PopForecast,
    capabilities: Sequence[CapabilitySpan],
    *,
    start_utc: datetime,
    end_utc: datetime,
) -> CallContinuityProjection:
    """Classify half-open flight spans, retaining canonical forecast and RF data.

    Capability spans must already share the forecast's route, clock and input
    revision. Adapters own this check; this pure service rejects ambiguous
    overlapping evidence rather than selecting whichever record comes first.
    """
    start, end = _utc(start_utc), _utc(end_utc)
    _validate(forecast, capabilities, start, end)
    windows = forecast.transitions if forecast.status == "ready" else ()
    boundaries = {start, end}
    for lower, upper in [
        *((c.start_utc, c.end_utc) for c in capabilities),
        *((t.window_start_utc, t.window_end_utc) for t in windows),
    ]:
        if lower < end and upper > start:
            boundaries.update((max(start, lower), min(end, upper)))
    intervals = []
    total = pop = longest = run = 0.0
    ordered = sorted(boundaries)
    for lower, upper in itertools.pairwise(ordered):
        span = next((c for c in capabilities if c.start_utc <= lower < c.end_utc), None)
        active = tuple(
            t.crossing.id
            for t in windows
            if t.window_start_utc <= lower < t.window_end_utc
        )
        classification, alternatives = _classify(span, active, forecast.status)
        intervals.append(
            CallContinuityInterval(
                start_utc=lower,
                end_utc=upper,
                classification=classification,
                transition_ids=active,
                usable_alternatives=alternatives,
                source_ids=span.source_ids if span else (),
            )
        )
        seconds = (upper - lower).total_seconds()
        if classification in ("planned_outage", "existing_outage"):
            total += seconds
            run += seconds
            longest = max(longest, run)
            if classification == "planned_outage":
                pop += seconds
        else:
            run = 0.0
    return CallContinuityProjection(
        revision=forecast.revision,
        intervals=tuple(intervals),
        planned_communications_outage_seconds=total,
        pop_call_outage_seconds=pop,
        longest_call_outage_seconds=longest,
    )
