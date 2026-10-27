"""Occurrence-specific PoP reconciliation without service-state changes."""

from datetime import datetime, timedelta, timezone

import pytest

from app.services.ground_entry_point import GroundEntryPoint
from app.services.pop.catalog import DEFAULT_CATALOG_PATH, load_catalog
from app.services.pop.live import evaluate_live, match_observed_pop
from app.services.pop.models import (
    PopCrossing,
    PopForecast,
    PopLiveState,
    PopObservation,
    PopTransition,
)

T = datetime(2035, 1, 1, 12, tzinfo=timezone.utc)
CATALOG = load_catalog(DEFAULT_CATALOG_PATH)


def observation(city="Los Angeles", country="US", status="known"):
    return PopObservation(
        ip="203.0.113.1",
        source="live",
        status=status,
        entry=(
            GroundEntryPoint("203.0.113.1", city, country, 0, 0)
            if status == "known"
            else None
        ),
    )


def transition(id="one", source="los-angeles", target="dallas", minute=0):
    center = T + timedelta(minutes=minute)
    return PopTransition(
        crossing=PopCrossing(
            id=id,
            from_pop_id=source,
            to_pop_id=target,
            segment_index=0,
            fraction=0.5,
            latitude=0,
            longitude=0,
            distance_meters=100 + minute,
        ),
        crossing_utc=center,
        window_start_utc=center - timedelta(minutes=5),
        window_end_utc=center + timedelta(minutes=5),
    )


def forecast(transitions=None, revision="r", status="ready"):
    return PopForecast(
        revision=revision,
        catalog_fingerprint=CATALOG.fingerprint,
        status=status,
        transitions=(transition(),) if transitions is None else transitions,
    )


def run(obs=None, *, now=T, state=None, nearest="los-angeles", next="dallas", f=None):
    return evaluate_live(
        f or forecast(),
        obs or observation(),
        catalog=CATALOG,
        nearest_id=nearest,
        next_id=next,
        now=now,
        state=state or PopLiveState(revision="r"),
    )


@pytest.mark.parametrize(
    "city,country,want",
    [
        ("  LOS  ANGELES ", "United States of America", "los-angeles"),
        ("Dallas", "USA", "dallas"),
        ("Frankfurt am Main", "Germany", "frankfurt"),
        ("Sydney", "Australia", "sydney"),
        ("Tokyo", "Japan", "tokyo"),
        ("El Segundo", "US", None),
        ("Dallas", "DE", None),
    ],
)
def test_explicit_city_country_identity_only(city, country, want):
    assert match_observed_pop(observation(city, country), CATALOG) == want


def test_window_starts_at_minus_five_and_early_destination_completes_occurrence():
    assert run(now=T - timedelta(minutes=6))[1] == ()
    assert [a.kind for a in run(now=T - timedelta(minutes=5))[1]] == ["window"]
    state, advisories = run(observation("Dallas"), now=T - timedelta(minutes=10))
    assert state.completed_ids == {"one"} and advisories == ()
    assert run(now=T, state=state)[1] == ()


def test_unconfirmed_identity_survives_leaving_upcoming_forecast():
    state, _ = run(now=T - timedelta(minutes=2))
    state, advisories = run(
        now=T + timedelta(minutes=6),
        state=state,
        nearest="dallas",
        next=None,
        f=forecast(()),
    )
    assert state.unconfirmed_ids == {"one"}
    assert not state.overdue_ids
    assert [(a.kind, a.transition_id) for a in advisories] == [
        ("mismatch", None),
    ]
    state, advisories = run(
        observation("Dallas"), state=state, nearest="dallas", next=None, f=forecast(())
    )
    assert state.completed_ids == {"one"} and not state.overdue_ids and advisories == ()


def test_mismatch_persists_until_nearest_or_next_matches_and_unknown_is_distinct():
    for city in ("Tokyo", "El Segundo", "Tokyo"):
        assert [
            a.kind for a in run(observation(city), now=T - timedelta(minutes=10))[1]
        ] == ["mismatch"]
    assert run(now=T - timedelta(minutes=10))[1] == ()
    assert run(observation("Dallas"), now=T - timedelta(minutes=10))[1] == ()
    state, advisories = run(observation(status="unknown"))
    assert not state.completed_ids
    assert {a.kind for a in advisories} == {"observation_unknown", "window"}


def test_no_next_only_nearest_is_normal():
    assert run(f=forecast(()), next=None)[1] == ()
    assert [
        a.kind for a in run(observation("Dallas"), f=forecast(()), next=None)[1]
    ] == ["mismatch"]


def test_reentry_completes_one_occurrence_at_a_time():
    f = forecast(
        (
            transition("one"),
            transition("two", "dallas", "los-angeles", 20),
            transition("three", minute=40),
        )
    )
    state, _ = run(observation("Dallas"), f=f, now=T - timedelta(minutes=10))
    assert state.completed_ids == {"one"}
    state, _ = run(observation("Dallas"), f=f, state=state)
    assert state.completed_ids == {"one"}
    state, _ = run(
        observation(), f=f, state=state, nearest="dallas", next="los-angeles"
    )
    assert state.completed_ids == {"one", "two"}
    state, _ = run(observation("Dallas"), f=f, state=state)
    assert state.completed_ids == {"one", "two", "three"}


def test_revision_rebases_and_disabled_clears_lifecycle():
    state, _ = run(observation("Dallas"))
    state, _ = run(
        state=state, f=forecast(revision="new"), now=T - timedelta(minutes=10)
    )
    assert state.revision == "new" and not state.completed_ids
    state, advisories = run(state=state, f=forecast(status="disabled"))
    assert not state.tracked_transitions and advisories == ()


def test_unavailable_inputs_do_not_complete_or_activate_old_predictions():
    state, _ = run(now=T - timedelta(minutes=2))
    state, advisories = run(
        observation("Dallas"), state=state, f=forecast((), status="unavailable")
    )
    assert not state.completed_ids and advisories == ()


def test_skipped_destination_supersedes_predecessor_and_records_timing():
    f = forecast((transition("one"), transition("two", "dallas", "tokyo", 20)))
    state, _ = run(observation("Unlisted"), f=f, now=T + timedelta(minutes=10))
    state, advisories = run(
        observation("Tokyo", "JP"),
        f=f,
        state=state,
        now=T + timedelta(minutes=30),
        nearest="tokyo",
        next=None,
    )
    assert state.completed_ids == {"two"}
    assert state.superseded_ids == {"one"}
    assert not state.overdue_ids
    assert not advisories
    result = next(item for item in state.occurrences if item.transition_id == "two")
    assert result.disposition == "observed"
    assert result.observed_at == T + timedelta(minutes=30)
    assert result.timing_residual_seconds == 600


def test_expired_forecast_is_unconfirmed_history_without_latched_risk():
    state, advisories = run(observation("Unlisted"), now=T + timedelta(minutes=30))
    assert not any(a.kind in {"window", "overdue"} for a in advisories)
    assert state.unconfirmed_ids == {"one"}
    assert state.occurrences[0].disposition == "unconfirmed"
    assert state.occurrences[0].observed_at is None


def test_initial_origin_and_repeated_samples_cannot_complete_later_reentry():
    f = forecast(
        (
            transition("one"),
            transition("two", "dallas", "los-angeles", 20),
            transition("three", minute=40),
        )
    )
    state, _ = run(f=f, now=T - timedelta(minutes=10))
    assert not state.completed_ids
    state, _ = run(observation("Dallas"), f=f, state=state)
    assert state.completed_ids == {"one"}
    state, _ = run(
        observation("Dallas"), f=f, state=state, now=T + timedelta(minutes=30)
    )
    assert state.completed_ids == {"one"}
    assert "three" not in state.superseded_ids


def test_stale_evidence_cannot_complete_and_static_identity_does_not_need_city_alias():
    from dataclasses import replace

    entry = replace(observation("Dallas").entry, freshness="stale")
    state, advisories = run(observation("Dallas").model_copy(update={"entry": entry}))
    assert not state.completed_ids
    assert any(a.kind == "observation_unknown" for a in advisories)
    entry = replace(
        entry,
        freshness="fresh",
        pop_id="tokyo",
        identity_source="operator_static_cidr",
        city="Contradictory",
    )
    assert (
        match_observed_pop(observation().model_copy(update={"entry": entry}), CATALOG)
        == "tokyo"
    )


def test_eta_updates_cannot_rearm_expired_window_or_rewrite_its_history():
    state, _ = run(now=T + timedelta(minutes=10))
    assert state.unconfirmed_ids == {"one"}
    shifted = forecast((transition(minute=15),))
    state, advisories = run(state=state, now=T + timedelta(minutes=12), f=shifted)
    assert not any(item.kind == "window" for item in advisories)
    assert state.occurrences[0].disposition == "unconfirmed"
    assert state.occurrences[0].expected_utc == T


def test_active_window_stays_bounded_when_live_eta_moves_later():
    state, _ = run(now=T - timedelta(minutes=2))
    state, advisories = run(
        state=state, now=T + timedelta(minutes=10), f=forecast((transition(minute=12),))
    )
    assert state.unconfirmed_ids == {"one"}
    assert not any(item.kind == "window" for item in advisories)
