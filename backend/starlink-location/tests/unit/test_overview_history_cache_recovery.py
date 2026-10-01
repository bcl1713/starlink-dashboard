"""Historical source ambiguity must not repeatedly trigger full recovery."""

from app.services.overview_history_prometheus import query_overview_history_bundle
from app.services.overview_history_rollups import ROLLUP_METRICS
from tests.unit import overview_history_cache_fixture

source = overview_history_cache_fixture.source
METRIC = ROLLUP_METRICS[0]


async def test_historical_raw_and_rollup_ambiguity_reconcile_once(source):
    fixture, client, reader = source
    fixture.retired_until = fixture.now - 30
    first = await reader.read()
    assert len(fixture.requests) == 16
    assert METRIC not in first["series"]
    assert first["rolling_5m"][METRIC]["state"] == "unavailable"
    for offset in range(1, 5):
        fixture.now += 1
        before = len(fixture.requests)
        result = await reader.read()
        requests = fixture.requests[before:]
        assert len(requests) == (32 if offset == 1 else 16)
        assert int(requests[0]["end"]) - int(requests[0]["start"]) == 11
        assert result == await query_overview_history_bundle(
            client, end_timestamp_seconds=fixture.now, window_seconds=fixture.window
        )


async def test_transport_recovery_and_source_changes_still_rehydrate(source):
    fixture, _, reader = source
    fixture.retired_until = fixture.now - 30
    await reader.read()
    fixture.now += 1
    await reader.read()  # Successful tail, unsuccessful full reconciliation.
    for fail_rollup, label, count in [
        (True, "first", 16),
        (False, "first", 32),
        (False, "first", 16),
        (False, "new", 32),
        (False, "new", 16),
    ]:
        fixture.now += 1
        fixture.fail_rollup, fixture.label = fail_rollup, label
        before = len(fixture.requests)
        result = await reader.read()
        assert len(fixture.requests) - before == count
        assert result["rolling_5m"][METRIC]["state"] == "unavailable"
        assert METRIC not in result["series"]


async def test_periodic_reconciliation_restores_aged_out_historical_source(source):
    fixture, client, reader = source
    fixture.window = 300
    fixture.retired_until = fixture.now - 30
    await reader.read()
    for offset in range(5, 311, 5):
        fixture.now = 10_000 + offset
        before = len(fixture.requests)
        result = await reader.read()
        requests = fixture.requests[before:]
        assert len(requests) == (32 if offset == 5 else 16)
        span = int(requests[0]["end"]) - int(requests[0]["start"])
        assert span == (300 if offset == 305 else 15)
        assert result["rolling_5m"][METRIC]["state"] == (
            "available" if offset >= 305 else "unavailable"
        )
    assert result == await query_overview_history_bundle(
        client, end_timestamp_seconds=fixture.now, window_seconds=fixture.window
    )


async def test_full_window_io_failure_does_not_suppress_real_recovery(source):
    fixture, client, reader = source
    fixture.fail_full_rollup = True
    await reader.read()
    for _ in range(3):
        fixture.now += 1
        before = len(fixture.requests)
        result = await reader.read()
        assert len(fixture.requests) - before == 32
        assert result["rolling_5m"][METRIC]["state"] == "unavailable"
    fixture.fail_full_rollup = False
    fixture.now += 1
    before = len(fixture.requests)
    result = await reader.read()
    assert len(fixture.requests) - before == 32
    assert result == await query_overview_history_bundle(
        client, end_timestamp_seconds=fixture.now, window_seconds=fixture.window
    )
