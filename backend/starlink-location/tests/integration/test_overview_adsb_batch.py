"""Real settings, scheduler, and adapter against a controlled HTTP transport."""

import asyncio
from contextlib import asynccontextmanager

import httpx
import pytest

from app.services.adsb_lol import AdsbLolProvider
from app.services.overview_adsb_settings import AdsbSettingsStore
from app.services.overview_adsb_traffic import AdsbTrafficService


class Clock:
    now = 1791028800.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def record(hex_code, **changes):
    return {"hex": hex_code, "lat": 40, "lon": -75, "seen_pos": 0, **changes}


@asynccontextmanager
async def runtime(tmp_path, respond, settings):
    clock = Clock()
    requests = []

    async def transport(request):
        requests.append(request.url.raw_path)
        return await respond(request, clock)

    async with httpx.AsyncClient(
        base_url="https://api.adsb.lol", transport=httpx.MockTransport(transport)
    ) as client:
        store = AdsbSettingsStore(tmp_path / "adsb.json")
        store.update({"enabled": True, "mode": "included_only", **settings})
        service = AdsbTrafficService(
            store, AdsbLolProvider(client, clock), clock, clock
        )
        try:
            yield store, service, clock, requests
        finally:
            await service.aclose()


@pytest.mark.parametrize(
    "included,excluded,expected",
    [
        (["00ab12", "000002"], [], [b"/v2/hex/00AB12%2C000002"]),
        ([" 00ab12 ", "00AB12", "000002", "000002"], [], [b"/v2/hex/00AB12%2C000002"]),
        (["000002"], [], [b"/v2/hex/000002"]),
        ([], [], []),
        (["00ab12", "000002", "abcdef"], ["000002"], [b"/v2/hex/00AB12%2CABCDEF"]),
        (["000002"], ["000002"], []),
    ],
)
async def test_one_encoded_request_for_normalized_eligible_codes(
    tmp_path, included, excluded, expected
):
    async def respond(request, clock):
        return httpx.Response(200, json={"now": clock() * 1000, "ac": []})

    async with runtime(
        tmp_path, respond, {"include_hexes": included, "exclude_hexes": excluded}
    ) as (_, service, _, requests):
        await asyncio.gather(*(service.refresh_once() for _ in range(10)))
        for _ in range(20):
            assert service.read().contacts == []
        assert requests == expected


async def test_partial_batch_preserves_missing_observation_and_deduplicates(tmp_path):
    replies = [
        [record("00ab12"), record("000002")],
        [record("00ab12"), record("00ab12", seen_pos=20), record("ABCDEF")],
        [],
    ]

    async def respond(request, clock):
        return httpx.Response(200, json={"now": clock() * 1000, "ac": replies.pop(0)})

    async with runtime(tmp_path, respond, {"include_hexes": ["00AB12", "000002"]}) as (
        _,
        service,
        clock,
        requests,
    ):
        await service.refresh_once()
        clock.advance(30)
        await service.refresh_once()
        contacts = {c.hex: c for c in service.read().contacts}
        assert set(contacts) == {"00AB12", "000002"}
        assert contacts["00AB12"].position_observed_at_ms == 1791028830000
        assert contacts["000002"].position_observed_at_ms == 1791028800000
        assert contacts["000002"].acquired_at_ms == 1791028800000
        sources = {s.key: s for s in service.read().sources}
        assert sources["hex:000002"].last_success_at_ms == 1791028830000
        assert sources["hex:000002"].error is None
        clock.advance(90)
        await service.refresh_once()
        assert [c.hex for c in service.read().contacts] == ["00AB12"]
        clock.advance(30)
        assert service.read().contacts == []
        assert requests == [b"/v2/hex/00AB12%2C000002"] * 3


@pytest.mark.parametrize("status,retry,delay", [(503, None, 15), (429, "600", 600)])
async def test_batch_failure_has_shared_backoff_without_single_code_fallback(
    tmp_path, status, retry, delay
):
    failed = True

    async def respond(request, clock):
        if failed:
            return httpx.Response(
                status, headers={"Retry-After": retry} if retry else {}
            )
        return httpx.Response(
            200, json={"now": clock() * 1000, "ac": [record("000003")]}
        )

    async with runtime(tmp_path, respond, {"include_hexes": ["00AB12", "000002"]}) as (
        store,
        service,
        clock,
        requests,
    ):
        await service.refresh_once()
        sources = service.read().sources
        assert len(sources) == 2
        assert all(s.error == "Provider acquisition failed" for s in sources)
        assert all(s.retry_at_ms == (clock() + delay) * 1000 for s in sources)
        # A new list must not sidestep the failed batch's provider deadline.
        store.update({"enabled": False, "include_hexes": ["000003"]})
        service.settings_changed()
        store.update({"enabled": True})
        service.settings_changed()
        clock.advance(delay - 0.001)
        await asyncio.gather(*(service.refresh_once() for _ in range(10)))
        assert requests == [b"/v2/hex/00AB12%2C000002"]
        clock.advance(0.001)
        failed = False
        await service.refresh_once()
        assert requests == [b"/v2/hex/00AB12%2C000002", b"/v2/hex/000003"]
        assert service.read().sources[0].error is None
        assert [c.hex for c in service.read().contacts] == ["000003"]


async def test_military_current_positions_avoid_batch_but_stale_cache_does_not(
    tmp_path,
):
    military_replies = [[record("00AB12")], []]

    async def respond(request, clock):
        contacts = military_replies.pop(0) if request.url.path == "/v2/mil" else []
        return httpx.Response(200, json={"now": clock() * 1000, "ac": contacts})

    async with runtime(
        tmp_path,
        respond,
        {
            "mode": "military_and_included",
            "include_hexes": ["00AB12", "000002", "000003"],
        },
    ) as (_, service, clock, requests):
        await service.refresh_once()
        assert requests == [b"/v2/mil", b"/v2/hex/000002%2C000003"]
        clock.advance(15)
        await service.refresh_once()
        assert requests[-2:] == [b"/v2/mil", b"/v2/hex/00AB12%2C000002%2C000003"]


@pytest.mark.parametrize(
    "count,sizes", [(1000, [1000]), (1001, [1000, 1]), (2001, [1000, 1000, 1])]
)
async def test_documented_size_limit_uses_minimum_sequential_chunks(
    tmp_path, count, sizes
):
    active = 0
    peak = 0

    async def respond(request, clock):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        return httpx.Response(200, json={"now": clock() * 1000, "ac": []})

    codes = [f"{i:06X}" for i in range(count)]
    async with runtime(tmp_path, respond, {"include_hexes": codes}) as (
        _,
        service,
        _,
        requests,
    ):
        await service.refresh_once()
        batches = [path.removeprefix(b"/v2/hex/").split(b"%2C") for path in requests]
        assert [len(batch) for batch in batches] == sizes
        assert [code.decode() for batch in batches for code in batch] == codes
        assert peak == 1


async def test_failed_chunk_stops_remaining_chunks(tmp_path):
    async def respond(request, clock):
        return httpx.Response(429, headers={"Retry-After": "600"})

    async with runtime(
        tmp_path, respond, {"include_hexes": [f"{i:06X}" for i in range(2001)]}
    ) as (_, service, clock, requests):
        await service.refresh_once()
        assert len(requests) == 1
        assert len(requests[0].split(b"%2C")) == 1000
        clock.advance(15)
        await service.refresh_once()
        assert len(requests) == 1


async def test_later_chunk_failure_escalates_until_whole_batch_recovers(tmp_path):
    fail_last = True

    async def respond(request, clock):
        if fail_last and request.url.path == "/v2/hex/0003E8":
            return httpx.Response(503)
        return httpx.Response(200, json={"now": clock() * 1000, "ac": []})

    async with runtime(
        tmp_path, respond, {"include_hexes": [f"{i:06X}" for i in range(1001)]}
    ) as (_, service, clock, requests):
        for attempt, delay in enumerate([15, 30, 60], start=1):
            await service.refresh_once()
            sources = {s.key: s for s in service.read().sources}
            assert sources["hex:000000"].error is None
            assert sources["hex:0003E8"].retry_at_ms == (clock() + delay) * 1000
            clock.advance(delay - 0.001)
            await service.refresh_once()
            assert len(requests) == attempt * 2
            clock.advance(0.001)
        fail_last = False
        await service.refresh_once()
        assert all(s.error is None for s in service.read().sources)
        clock.advance(15)
        fail_last = True
        await service.refresh_once()
        assert service.read().sources[-1].retry_at_ms == (clock() + 15) * 1000


@pytest.mark.parametrize(
    "changes",
    [{"enabled": False}, {"exclude_hexes": ["00AB12"]}, {"include_hexes": ["000003"]}],
)
async def test_settings_change_discards_inflight_included_batch(tmp_path, changes):
    entered, release = asyncio.Event(), asyncio.Event()

    async def respond(request, clock):
        entered.set()
        await release.wait()
        return httpx.Response(
            200, json={"now": clock() * 1000, "ac": [record("00AB12")]}
        )

    async with runtime(tmp_path, respond, {"include_hexes": ["00AB12", "000002"]}) as (
        store,
        service,
        _,
        requests,
    ):
        refresh = asyncio.create_task(service.refresh_once())
        try:
            await asyncio.wait_for(entered.wait(), timeout=1)
            store.update(changes)
            service.settings_changed()
        finally:
            release.set()
            await refresh
        assert requests == [b"/v2/hex/00AB12%2C000002"]
        assert service.read().contacts == []
        assert service.read().sources == []


async def test_settings_change_between_chunks_discards_old_response_and_stops(tmp_path):
    async def respond(request, clock):
        store.update({"include_hexes": ["ABCDEF"]})
        return httpx.Response(
            200, json={"now": clock() * 1000, "ac": [record("000001")]}
        )

    async with runtime(
        tmp_path, respond, {"include_hexes": [f"{i:06X}" for i in range(1001)]}
    ) as (store, service, _, requests):
        await service.refresh_once()
        assert len(requests) == 1
        assert service.read().contacts == []
        assert service.read().sources == []
