"""UTC bounds, occurrence identity, and fail-closed timing publication."""

from datetime import datetime, timedelta, timezone

import pytest

from app.services.pop.forecast import build_forecast
from app.services.pop.models import PopCrossing

BASE = datetime(2035, 1, 1, tzinfo=timezone.utc)


def crossing(distance=100, identity="first"):
    return PopCrossing(
        id=identity,
        from_pop_id="a",
        to_pop_id="b",
        segment_index=0,
        fraction=0.5,
        latitude=0,
        longitude=0,
        distance_meters=distance,
    )


def test_exact_unclipped_bounds_and_utc_normalization():
    center = BASE.astimezone(timezone(timedelta(hours=9)))
    result = build_forecast(
        [crossing()], lambda _: center, revision="r", catalog_fingerprint="c"
    )
    assert result.status == "ready"
    transition = result.transitions[0]
    assert transition.crossing_utc == BASE
    assert transition.crossing_utc.utcoffset() == timedelta(0)
    assert transition.window_start_utc == BASE - timedelta(seconds=300)
    assert transition.window_end_utc == BASE + timedelta(seconds=300)
    assert "Z" in result.model_dump_json()


def test_empty_crossings_are_ready_without_timing_callback():
    def unavailable(_):
        raise ValueError("missing timing")

    result = build_forecast([], unavailable, revision="r", catalog_fingerprint="c")
    assert result.status == "ready"
    assert result.transitions == ()


def test_reentry_occurrences_and_revisions_have_distinct_stable_ids():
    records = [crossing(), crossing(200, "return")]

    def build(revision="r", catalog="c"):
        return build_forecast(
            records,
            lambda d: BASE + timedelta(seconds=d),
            revision=revision,
            catalog_fingerprint=catalog,
        )

    original = build()
    ids = {t.crossing.id for t in original.transitions}
    assert len(ids) == 2
    assert original == build()
    assert ids.isdisjoint(t.crossing.id for t in build(revision="new").transitions)
    assert ids.isdisjoint(t.crossing.id for t in build(catalog="new").transitions)
    # Overlapping windows stay distinct.
    assert (
        original.transitions[0].window_end_utc
        > original.transitions[1].window_start_utc
    )


@pytest.mark.parametrize(
    "timing",
    [
        lambda _: None,
        lambda _: BASE.replace(tzinfo=None),
        lambda d: BASE - timedelta(seconds=d),
    ],
)
def test_invalid_timing_discards_all_transitions(timing):
    result = build_forecast(
        [crossing(), crossing(200, "second")],
        timing,
        revision="r",
        catalog_fingerprint="c",
    )
    assert result.status == "unavailable"
    assert result.reason
    assert result.transitions == ()


def test_timing_exception_cannot_publish_partial_result():
    def timing(distance):
        if distance > 100:
            raise ValueError("missing anchor")
        return BASE

    result = build_forecast(
        [crossing(), crossing(200, "second")],
        timing,
        revision="r",
        catalog_fingerprint="c",
    )
    assert result.status == "unavailable"
    assert result.transitions == ()
