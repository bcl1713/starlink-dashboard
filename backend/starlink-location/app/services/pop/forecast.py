"""Attach UTC timing to geographic crossing occurrences without service effects."""

import hashlib
import json
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone

from .models import PopCrossing, PopForecast, PopTransition


def build_forecast(
    crossings: Sequence[PopCrossing],
    timestamp_for_distance: Callable[[float], datetime],
    *,
    revision: str,
    catalog_fingerprint: str,
) -> PopForecast:
    """Publish all crossings atomically, preserving full five-minute bounds."""
    transitions = []
    previous_distance = previous_time = None
    try:
        for crossing in crossings:
            timestamp = timestamp_for_distance(crossing.distance_meters)
            if not isinstance(timestamp, datetime) or timestamp.utcoffset() is None:
                raise ValueError("Crossing timing requires a timezone-aware timestamp")
            timestamp = timestamp.astimezone(timezone.utc)
            if previous_distance is not None and (
                crossing.distance_meters <= previous_distance
                or timestamp <= previous_time
            ):
                raise ValueError("Crossing distance/time must increase monotonically")
            identity = json.dumps([revision, catalog_fingerprint, crossing.id])
            occurrence = crossing.model_copy(
                update={"id": hashlib.sha256(identity.encode()).hexdigest()}
            )
            transitions.append(
                PopTransition(
                    crossing=occurrence,
                    crossing_utc=timestamp,
                    window_start_utc=timestamp - timedelta(seconds=300),
                    window_end_utc=timestamp + timedelta(seconds=300),
                )
            )
            previous_distance, previous_time = crossing.distance_meters, timestamp
    except (ValueError, TypeError, ArithmeticError, LookupError) as exc:
        return PopForecast(
            revision=revision,
            catalog_fingerprint=catalog_fingerprint,
            status="unavailable",
            reason=f"Unavailable crossing timing: {exc}",
        )
    return PopForecast(
        revision=revision,
        catalog_fingerprint=catalog_fingerprint,
        status="ready",
        transitions=tuple(transitions),
    )
