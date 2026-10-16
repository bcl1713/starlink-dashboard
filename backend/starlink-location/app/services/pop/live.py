"""Pure observation matching and occurrence-specific advisory reconciliation."""

import unicodedata
from datetime import datetime

from .models import (
    PopCatalog,
    PopForecast,
    PopLiveAdvisory,
    PopLiveState,
    PopObservation,
)


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


_COUNTRIES = {
    alias: code
    for code, aliases in {
        "us": ("us", "usa", "united states", "united states of america"),
        "au": ("au", "aus", "australia"),
        "de": ("de", "deu", "germany", "deutschland"),
        "jp": ("jp", "jpn", "japan"),
    }.items()
    for alias in aliases
}


def _country(value: str) -> str:
    value = _normalized(value)
    return _COUNTRIES.get(value, value)


def match_observed_pop(observation: PopObservation, catalog: PopCatalog) -> str | None:
    """Match explicit normalized city aliases and country, never nearby geography."""
    if observation.status != "known" or observation.entry is None:
        return None
    city, country = _normalized(observation.entry.city), _country(
        observation.entry.country
    )
    matches = [
        site.id
        for site in catalog.sites
        if country == _country(site.country)
        and city in {_normalized(name) for name in (site.city, *site.aliases)}
    ]
    return matches[0] if len(matches) == 1 else None


def evaluate_live(
    forecast: PopForecast,
    observation: PopObservation,
    *,
    catalog: PopCatalog,
    nearest_id: str | None,
    next_id: str | None,
    now: datetime,
    state: PopLiveState,
) -> tuple[PopLiveState, tuple[PopLiveAdvisory, ...]]:
    """Reconcile one captured revision; caller rejects superseded input results.

    The captured catalog is required so observed matching agrees with forecasting.
    Keep crossed records after the upcoming forecast drops them; only the earliest
    unresolved occurrence can complete on a sample (including region re-entry).
    """
    if state.revision != forecast.revision or forecast.status == "disabled":
        state = PopLiveState(revision=forecast.revision)
    if forecast.status == "disabled":
        return state, ()
    unknown = observation.status == "unknown" or observation.entry is None
    advisories = [PopLiveAdvisory(kind="observation_unknown")] if unknown else []
    if (
        forecast.status != "ready"
        or forecast.catalog_fingerprint != catalog.fingerprint
    ):
        return state, tuple(advisories)

    tracked = {t.crossing.id: t for t in state.tracked_transitions}
    tracked.update({t.crossing.id: t for t in forecast.transitions})
    ordered = tuple(sorted(tracked.values(), key=lambda t: t.crossing.distance_meters))
    completed, overdue = set(state.completed_ids), set(state.overdue_ids)
    observed = match_observed_pop(observation, catalog)
    pending = [t for t in ordered if t.crossing.id not in completed]
    if pending and observed is not None and observed == pending[0].crossing.to_pop_id:
        completed.add(pending[0].crossing.id)
        overdue.discard(pending[0].crossing.id)
    for transition in ordered:
        id = transition.crossing.id
        if id in completed:
            continue
        if now > transition.window_end_utc:
            overdue.add(id)
        if id in overdue or now >= transition.window_start_utc:
            advisories.append(
                PopLiveAdvisory(
                    kind="overdue" if id in overdue else "window",
                    transition_id=id,
                    observed_pop_id=observed,
                )
            )
    if (
        not unknown
        and nearest_id is not None
        and (observed is None or observed not in {nearest_id, next_id})
    ):
        advisories.append(PopLiveAdvisory(kind="mismatch", observed_pop_id=observed))
    return PopLiveState(
        revision=forecast.revision,
        completed_ids=frozenset(completed),
        overdue_ids=frozenset(overdue),
        tracked_transitions=ordered,
    ), tuple(advisories)
