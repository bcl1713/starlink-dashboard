"""Deterministic provider fixtures through the shipped evaluator, not API observations."""

import json
from datetime import datetime, timedelta, timezone

from app.services.ground_entry_point import GroundEntryPoint
from app.services.pop.catalog import DEFAULT_CATALOG_PATH, load_catalog
from app.services.pop.live import evaluate_live
from app.services.pop.models import (
    PopCrossing,
    PopForecast,
    PopLiveState,
    PopObservation,
    PopTransition,
)

catalog = load_catalog(DEFAULT_CATALOG_PATH)
center = datetime(2026, 10, 25, 16, tzinfo=timezone.utc)
transition = PopTransition(
    crossing=PopCrossing(
        id="sanitized-occurrence",
        from_pop_id="los-angeles",
        to_pop_id="dallas",
        segment_index=0,
        fraction=0.5,
        latitude=35,
        longitude=-105,
        distance_meters=1000,
    ),
    crossing_utc=center,
    window_start_utc=center - timedelta(minutes=5),
    window_end_utc=center + timedelta(minutes=5),
)
forecast = PopForecast(
    revision="sanitized-provider-fixture",
    catalog_fingerprint=catalog.fingerprint,
    status="ready",
    transitions=(transition,),
)
reports = {}
for name, city, country, offset, expected in [
    ("early", "Dallas", "US", -10, []),
    ("late", "Los Angeles", "US", 6, []),
    ("mismatch", "Tokyo", "JP", -10, ["mismatch"]),
]:
    observation = PopObservation(
        ip="203.0.113.1",
        entry=GroundEntryPoint("203.0.113.1", city, country, 0, 0),
        status="known",
        source="live",
    )
    state, advisory = evaluate_live(
        forecast,
        observation,
        catalog=catalog,
        nearest_id="los-angeles",
        next_id="dallas",
        now=center + timedelta(minutes=offset),
        state=PopLiveState(revision=forecast.revision),
    )
    assert [item.kind for item in advisory] == expected
    if name == "late":
        assert state.unconfirmed_ids == {"sanitized-occurrence"}
    if name == "early":
        assert state.completed_ids == {"sanitized-occurrence"}
    reports[name] = {
        "observation": observation.model_dump(mode="json"),
        "state": state.model_dump(mode="json"),
        "advisories": [item.model_dump(mode="json") for item in advisory],
    }
print(
    json.dumps(
        {
            "fixtureKind": "deterministic provider observation fixtures, independent of real HTTP simulation observations",
            "cases": reports,
            "forecast": forecast.model_dump(mode="json"),
        }
    )
)
