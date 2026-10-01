"""A simulated hour proves retained-state bounds, not wall-clock resource growth."""

import asyncio

from tests.unit.overview_history_cache_fixture import source as source


async def test_one_simulated_hour_keeps_two_readers_and_retained_work_bounded(source):
    fixture, _, reader = source
    tasks = len(asyncio.all_tasks())
    full_refreshes = 0
    for _ in range(3600):
        result = await reader.read()
        assert await reader.read() is result
        assert len(fixture.requests) == 16
        span = int(fixture.requests[0]["end"]) - int(fixture.requests[0]["start"])
        if span == 1800:
            full_refreshes += 1
        else:
            assert span == 11
        assert len(result["series"]) <= 11
        assert len(result["rolling_5m"]) == 5
        assert all(len(trace) <= 1801 for trace in result["series"].values())
        assert all(
            len(entry[statistic]) <= 1801
            for entry in result["rolling_5m"].values()
            for statistic in ("min", "avg", "max")
        )
        assert len(reader._identity) <= 11
        assert reader._flight is None
        assert len(asyncio.all_tasks()) == tasks
        assert fixture.active == 0
        fixture.requests.clear()
        fixture.now += 1
    assert full_refreshes == 12  # Cold load plus periodic five-minute reconciliation.
    await reader.aclose()
