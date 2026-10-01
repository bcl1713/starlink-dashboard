"""Incremental history versus authoritative full-range fixtures."""

import asyncio
import copy

import pytest

from app.services.overview_history_prometheus import (
    OverviewHistoryPrometheusResponseError,
    plan_overview_history_query,
    query_overview_history_bundle,
)
from app.services.overview_history_rollups import ROLLUP_METRICS
from tests.unit.overview_history_cache_fixture import source as source


@pytest.mark.parametrize("window", [1, 300, 900, 1800, 3600, 3601, 1907, 86400])
async def test_tail_matches_full_reference_on_fixed_grid_with_deletion_and_lateness(
    source, window
):
    fixture, client, reader = source
    fixture.window = window
    first = await reader.read()
    retained = copy.deepcopy(first)
    assert await reader.read() is first
    assert len(fixture.requests) == 16
    previous = first
    for offset in [1, 2, 5, 11, 16]:
        fixture.now = 10_000 + offset
        fixture.deleted.add(fixture.now - 3)
        fixture.corrections[fixture.now - 4] = 999
        before = len(fixture.requests)
        result = await reader.read()
        tail_requests = fixture.requests[before:]
        if not tail_requests:
            assert result is previous  # Same evaluation interval reuses its snapshot.
            continue
        assert all(int(r["end"]) - int(r["start"]) <= 30 for r in tail_requests)
        reference = await query_overview_history_bundle(
            client, end_timestamp_seconds=fixture.now, window_seconds=window
        )
        assert result == reference
        assert (
            result["end_timestamp_seconds"] - result["start_timestamp_seconds"]
            == window
        )
        assert all(len(points) <= 1801 for points in result["series"].values())
        previous = result
    assert first == retained  # Published data was never mutated by later refreshes.


@pytest.mark.parametrize("window", [1801, 3601, 1907, 86401])
def test_custom_duration_keeps_epoch_grid_and_sample_cap(window):
    previous = None
    for now in range(10_000, 10_010):
        plan = plan_overview_history_query(
            end_timestamp_seconds=now, window_seconds=window
        )
        assert plan.start_timestamp_seconds % plan.step_seconds == 0
        assert plan.end_timestamp_seconds % plan.step_seconds == 0
        assert (
            plan.end_timestamp_seconds - plan.start_timestamp_seconds
        ) // plan.step_seconds + 1 <= 1801
        assert plan.end_timestamp_seconds - window <= plan.start_timestamp_seconds
        if previous is not None:
            assert (
                plan.start_timestamp_seconds - previous.start_timestamp_seconds
            ) % plan.step_seconds == 0
        previous = plan


async def test_callers_across_seconds_share_one_refresh_and_cancellation_is_isolated(
    source,
):
    fixture, _, reader = source
    fixture.release = asyncio.Event()
    first = asyncio.create_task(reader.read())
    await fixture.started.wait()
    fixture.now += 1
    second = asyncio.create_task(reader.read())
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    fixture.release.set()
    result = await second
    assert result["end_timestamp_seconds"] == 10_000
    assert len(fixture.requests) == 16
    assert fixture.max_active <= 3
    refreshed = await reader.read()
    assert refreshed["end_timestamp_seconds"] == 10_001
    assert await reader.read() is refreshed


async def test_invalidation_ignores_old_flight_even_when_window_changes_back(source):
    fixture, _, reader = source
    fixture.release = asyncio.Event()
    request = asyncio.create_task(reader.read())
    await fixture.started.wait()
    fixture.window = 900
    reader.invalidate()
    fixture.window = 1800
    reader.invalidate()
    fixture.corrections[10_000] = 999
    fixture.release.set()
    result = await request
    assert result["window_seconds"] == 1800
    assert len(fixture.requests) == 32


async def test_window_switches_clock_rewind_and_idle_gap_rehydrate(source):
    fixture, _, reader = source
    await reader.read()
    for window, now in [(3600, 10_001), (300, 10_002), (300, 9_999), (300, 10_100)]:
        fixture.window, fixture.now = window, now
        before = len(fixture.requests)
        result = await reader.read()
        assert len(fixture.requests) - before == 16
        assert (
            int(fixture.requests[before]["end"])
            - int(fixture.requests[before]["start"])
            >= window - 2
        )
        assert result["window_seconds"] == window


async def test_raw_failure_shares_backoff_does_not_advance_and_recovers(source):
    fixture, _, reader = source
    first = await reader.read()
    fixture.now += 1
    fixture.fail_raw = True
    with pytest.raises(OverviewHistoryPrometheusResponseError):
        await reader.read()
    before = len(fixture.requests)
    with pytest.raises(OverviewHistoryPrometheusResponseError):
        await reader.read()
    assert len(fixture.requests) == before
    assert reader._public is first
    fixture.now += 1
    fixture.fail_raw = False
    assert (await reader.read())["end_timestamp_seconds"] == fixture.now


async def test_rollup_failure_withholds_whole_metric_and_recovery_refills(source):
    fixture, client, reader = source
    await reader.read()
    fixture.now += 1
    fixture.fail_rollup = True
    result = await reader.read()
    assert result["series"]
    assert all(
        entry == {"state": "unavailable", "min": [], "avg": [], "max": []}
        for entry in result["rolling_5m"].values()
    )
    fixture.now += 1
    fixture.fail_rollup = False
    before = len(fixture.requests)
    result = await reader.read()
    assert len(fixture.requests) - before == 32
    assert result == await query_overview_history_bundle(
        client, end_timestamp_seconds=fixture.now, window_seconds=fixture.window
    )


async def test_source_change_and_ambiguous_series_do_not_splice_old_history(source):
    fixture, client, reader = source
    await reader.read()
    for label, ambiguous in [("new", False), ("new", True), ("new", False)]:
        fixture.now += 1
        fixture.label, fixture.ambiguous = label, ambiguous
        result = await reader.read()
        assert result == await query_overview_history_bundle(
            client, end_timestamp_seconds=fixture.now, window_seconds=fixture.window
        )
    assert "_identity" not in result


async def test_periodic_full_reconciliation_corrects_older_samples(source):
    fixture, _, reader = source
    await reader.read()
    fixture.corrections[9_000] = 999
    for offset in range(5, 301, 5):
        fixture.now = 10_000 + offset
        before = len(fixture.requests)
        result = await reader.read()
        span = int(fixture.requests[before]["end"]) - int(
            fixture.requests[before]["start"]
        )
        assert span == (1800 if offset == 300 else 15)
    assert [9000, 999] in result["series"][ROLLUP_METRICS[0]]


async def test_shutdown_drains_shared_work_and_closes_reader(source):
    fixture, _, reader = source
    fixture.release = asyncio.Event()
    request = asyncio.create_task(reader.read())
    await fixture.started.wait()
    await reader.aclose()
    with pytest.raises(asyncio.CancelledError):
        await request
    assert reader._flight is None
    assert fixture.active == 0
    with pytest.raises(OverviewHistoryPrometheusResponseError, match="closed"):
        await reader.read()


async def test_deadline_cancels_upstream_work_and_recovers(source, monkeypatch):
    import app.services.overview_history_cache as cache

    fixture, _, reader = source
    monkeypatch.setattr(cache, "REFRESH_TIMEOUT_SECONDS", 0.01)
    fixture.release = asyncio.Event()
    with pytest.raises(OverviewHistoryPrometheusResponseError):
        await reader.read()
    assert reader._public is None
    assert reader._flight is None
    assert fixture.active == 0
    fixture.release.set()
    fixture.now += 1
    monkeypatch.setattr(cache, "REFRESH_TIMEOUT_SECONDS", 5)
    assert (await reader.read())["end_timestamp_seconds"] == fixture.now


async def test_persistent_ambiguity_does_not_repeat_full_window_loads(source):
    fixture, _, reader = source
    fixture.ambiguous = True
    await reader.read()
    for _ in range(3):
        fixture.now += 1
        before = len(fixture.requests)
        result = await reader.read()
        assert ROLLUP_METRICS[0] not in result["series"]
        assert len(fixture.requests) - before == 16
        assert (
            int(fixture.requests[before]["end"])
            - int(fixture.requests[before]["start"])
            == 11
        )


async def test_delayed_sample_and_later_nan_replace_the_authoritative_overlap(source):
    fixture, client, reader = source
    metric = ROLLUP_METRICS[0]
    fixture.deleted.add(9995)
    first = await reader.read()
    assert all(point[0] != 9995 for point in first["series"][metric])
    fixture.deleted.remove(9995)
    fixture.corrections[9995] = 0  # Late valid zero must appear, not be filtered out.
    for invalid in [False, True, False]:
        fixture.now += 1
        fixture.invalid = {9995} if invalid else set()
        result = await reader.read()
        reference = await query_overview_history_bundle(
            client, end_timestamp_seconds=fixture.now, window_seconds=fixture.window
        )
        assert result == reference
        assert ([9995, 0] in result["series"][metric]) is not invalid
        for statistic in ("min", "avg", "max"):
            assert ([9995, 0] in result["rolling_5m"][metric][statistic]) is not invalid
