"""Pure observation matching and occurrence-specific advisory reconciliation."""

import unicodedata
from datetime import datetime

from .models import (
    PopCatalog,
    PopForecast,
    PopLiveAdvisory,
    PopLiveState,
    PopObservation,
    PopOccurrence,
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
    """Prefer explicit identity; GeoIP aliases support tentative comparison only."""
    if (
        observation.status != "known"
        or observation.entry is None
        or observation.freshness == "stale"
        or getattr(observation.entry, "freshness", "fresh") == "stale"
    ):
        return None
    entry = observation.entry
    if getattr(entry, "identity_source", None) == "operator_static_cidr":
        return next(
            (site.id for site in catalog.sites if site.id == entry.pop_id), None
        )
    city, country = _normalized(entry.city), _country(entry.country)
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
    """Retain forecast history while bounding transition risk to modeled windows.

    A newly observed destination can supersede missed predecessors. One unchanged
    observation cannot consume a later return to the same region. Supersession
    records missing evidence; it never asserts that the skipped transition occurred.
    """
    if state.revision != forecast.revision or forecast.status == "disabled":
        state = PopLiveState(revision=forecast.revision)
    if forecast.status == "disabled":
        return state, ()
    unknown = (
        observation.status == "unknown"
        or observation.entry is None
        or observation.freshness == "stale"
        or getattr(observation.entry, "freshness", "fresh") == "stale"
    )
    advisories = [PopLiveAdvisory(kind="observation_unknown")] if unknown else []
    if (
        forecast.status != "ready"
        or forecast.catalog_fingerprint != catalog.fingerprint
    ):
        return state, tuple(advisories)

    tracked = {t.crossing.id: t for t in state.tracked_transitions}
    tracked.update({t.crossing.id: t for t in forecast.transitions})
    ordered = tuple(sorted(tracked.values(), key=lambda t: t.crossing.distance_meters))
    completed = set(state.completed_ids)
    superseded = set(state.superseded_ids)
    unconfirmed = set(state.unconfirmed_ids)
    history = {item.transition_id: item for item in state.occurrences}
    observed = match_observed_pop(observation, catalog)
    pending = [t for t in ordered if t.crossing.id not in completed | superseded]
    if (
        pending
        and observed is not None
        and observed != state.last_observed_pop_id
        and observed != pending[0].crossing.from_pop_id
    ):
        candidate = next((t for t in pending if t.crossing.to_pop_id == observed), None)
        if candidate is not None:
            for predecessor in pending:
                if predecessor.crossing.id == candidate.crossing.id:
                    break
                superseded.add(predecessor.crossing.id)
                unconfirmed.discard(predecessor.crossing.id)
            id = candidate.crossing.id
            completed.add(id)
            unconfirmed.discard(id)
            observed_at = now
            if observation.source == "live" and observation.sampled_at:
                try:
                    sampled_at = datetime.fromisoformat(observation.sampled_at)
                    if sampled_at.tzinfo is not None and sampled_at <= now:
                        observed_at = sampled_at
                except ValueError:
                    pass
            history[id] = PopOccurrence(
                transition_id=id,
                disposition="observed",
                expected_utc=candidate.crossing_utc,
                window_start_utc=candidate.window_start_utc,
                window_end_utc=candidate.window_end_utc,
                from_city=candidate.crossing.from_city,
                to_city=candidate.crossing.to_city,
                observed_at=observed_at,
                timing_residual_seconds=(
                    observed_at - candidate.crossing_utc
                ).total_seconds(),
            )
    for transition in ordered:
        id = transition.crossing.id
        if id in completed:
            continue
        if id in superseded:
            disposition = "superseded"
        elif now > transition.window_end_utc:
            unconfirmed.add(id)
            disposition = "unconfirmed"
        else:
            disposition = "pending"
            if now >= transition.window_start_utc:
                advisories.append(
                    PopLiveAdvisory(
                        kind="window", transition_id=id, observed_pop_id=observed
                    )
                )
        history[id] = PopOccurrence(
            transition_id=id,
            disposition=disposition,
            expected_utc=transition.crossing_utc,
            window_start_utc=transition.window_start_utc,
            window_end_utc=transition.window_end_utc,
            from_city=transition.crossing.from_city,
            to_city=transition.crossing.to_city,
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
        superseded_ids=frozenset(superseded),
        unconfirmed_ids=frozenset(unconfirmed),
        last_observed_pop_id=observed or state.last_observed_pop_id,
        tracked_transitions=ordered,
        occurrences=tuple(history[t.crossing.id] for t in ordered),
    ), tuple(advisories)
