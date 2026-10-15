import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from app.services.orbital_catalog import OrbitalCatalogService
from app.services.orbital_catalog_models import eligible_objects, validate_catalog

NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
OBJECT = json.loads(
    (Path(__file__).parents[1] / "fixtures/orbital-catalog.json").read_text()
)[0]


def test_catalog_validation_and_stable_subset():
    objects = [{**OBJECT, "NORAD_CAT_ID": str(i)} for i in range(1, 16386)]
    accepted = validate_catalog(objects)
    assert len(accepted["objects"]) == 16384
    assert accepted["objects"][0]["NORAD_CAT_ID"] == "1"
    assert accepted["objects"][-1]["NORAD_CAT_ID"] == "16384"
    assert accepted["truncated_count"] == 1
    assert (
        validate_catalog(list(reversed(objects)))["generation"]
        == accepted["generation"]
    )
    assert (
        validate_catalog([{**OBJECT, "NORAD_CAT_ID": 100001}])["generation"]
        == validate_catalog([OBJECT])["generation"]
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"NORAD_CAT_ID": "abc"},
        {"NORAD_CAT_ID": True},
        {"EPOCH": "bad"},
        {"MEAN_MOTION": 0},
        {"MEAN_MOTION": 100},
        {"ECCENTRICITY": 1},
        {"ECCENTRICITY": -0.1},
        {"INCLINATION": 181},
        {"INCLINATION": -1},
        {"BSTAR": float("nan")},
        {"MEAN_MOTION_DOT": True},
        {"RA_OF_ASC_NODE": 361},
        {"TIME_SYSTEM": "TAI"},
        {"MEAN_ELEMENT_THEORY": "OTHER"},
    ],
)
def test_invalid_objects_are_rejected_individually(changes):
    result = validate_catalog([OBJECT, {**OBJECT, "NORAD_CAT_ID": "2", **changes}])
    assert result["objects"] == [OBJECT]
    assert result["rejected_count"] == 1


def test_duplicates_missing_elements_and_empty_response():
    missing = {key: value for key, value in OBJECT.items() if key != "BSTAR"}
    for payload in [[], {}, [missing], [OBJECT, OBJECT]]:
        with pytest.raises(ValueError):
            validate_catalog(payload)


@pytest.mark.parametrize(
    "offset, count", [(-259200, 1), (-259200.001, 0), (600, 1), (600.001, 0)]
)
def test_epochs_expire_individually_at_exact_boundaries(offset, count):
    obj = {**OBJECT, "EPOCH": (NOW + timedelta(seconds=offset)).isoformat()}
    assert len(eligible_objects([obj], NOW)) == count


async def test_attempt_clock_survives_restart_and_failure(tmp_path):
    now = [NOW]
    calls = []

    def provider(request):
        calls.append(request)
        raise httpx.ReadTimeout("timed out")

    def service():
        return OrbitalCatalogService(
            tmp_path,
            httpx.AsyncClient(transport=httpx.MockTransport(provider)),
            lambda: now[0],
        )

    first = service()
    try:
        await asyncio.gather(*(first.acquire(str(i)) for i in range(20)))
        await first.get_catalog("0")
        assert len(calls) == 1
    finally:
        await first.aclose()
    second = service()
    try:
        await second.acquire("new")
        await second.get_catalog("new")
        assert len(calls) == 1
        now[0] += timedelta(seconds=7200)
        await second.acquire("new")
        await second.get_catalog("new")
        assert len(calls) == 2
    finally:
        await second.aclose()


@pytest.mark.parametrize("code", [301, 403, 404, 429, 503])
async def test_http_errors_suspend_and_resume_preserves_longer_backoff(tmp_path, code):
    now = [NOW]
    calls = []

    def provider(request):
        calls.append(request)
        return httpx.Response(code, headers={"Retry-After": "10000"})

    service = OrbitalCatalogService(
        tmp_path,
        httpx.AsyncClient(transport=httpx.MockTransport(provider)),
        lambda: now[0],
    )
    try:
        await service.acquire("a")
        envelope = await service.get_catalog("a")
        assert envelope["suspended"] is True
        assert (
            envelope["retry_after_at"] == (NOW + timedelta(seconds=10000)).isoformat()
        )
        await service.resume_provider()
        now[0] += timedelta(seconds=7200)
        await service.acquire("a")
        await service.get_catalog("a")
        assert len(calls) == 1
        now[0] += timedelta(seconds=2800)
        await service.acquire("a")
        await service.get_catalog("a")
        assert len(calls) == 2
    finally:
        await service.aclose()


async def test_viewer_demand_and_diagnostics(tmp_path):
    now = [NOW]
    calls = []

    def provider(request):
        calls.append(request)
        return httpx.Response(200, json=[OBJECT])

    service = OrbitalCatalogService(
        tmp_path,
        httpx.AsyncClient(transport=httpx.MockTransport(provider)),
        lambda: now[0],
    )
    try:
        assert (await service.get_status())["active_viewers"] == 0
        assert calls == []
        assert service.running is False
        await service.acquire("a")
        envelope = await service.get_catalog("a")
        assert envelope["objects"] == [OBJECT]
        assert envelope["eligible_count"] == 1
        await service.acquire("b")
        assert (await service.get_catalog("b"))["generation"] == envelope["generation"]
        assert len(calls) == 1
        now[0] += timedelta(seconds=76)
        assert (await service.get_status())["active_viewers"] == 0
        assert service.running is False
        with pytest.raises(LookupError):
            await service.get_catalog("a")
    finally:
        await service.aclose()


async def test_corrupt_state_fails_closed_and_resume_repairs_with_cooldown(tmp_path):
    (tmp_path / "provider-state.json").write_text("{")
    calls = []

    def provider(request):
        calls.append(request)
        return httpx.Response(200, json=[OBJECT])

    service = OrbitalCatalogService(
        tmp_path,
        httpx.AsyncClient(transport=httpx.MockTransport(provider)),
        lambda: NOW,
    )
    try:
        await service.acquire("a")
        assert (await service.get_catalog("a"))["suspended"] is True
        assert calls == []
        await service.resume_provider()
        assert (await service.get_catalog("a"))["last_attempt_at"] == NOW.isoformat()
        assert calls == []
    finally:
        await service.aclose()


async def test_empty_refresh_and_oversize_stream_preserve_last_good_catalog(tmp_path):
    now = [NOW]
    responses = [
        httpx.Response(200, json=[OBJECT]),
        httpx.Response(200, json=[]),
        httpx.Response(200, content=b" " * (16 * 1024 * 1024 + 1)),
    ]
    service = OrbitalCatalogService(
        tmp_path,
        httpx.AsyncClient(transport=httpx.MockTransport(lambda r: responses.pop(0))),
        lambda: now[0],
    )
    try:
        await service.acquire("a")
        good = await service.get_catalog("a")
        for _ in range(2):
            now[0] += timedelta(seconds=7200)
            await service.acquire("a")
            assert (await service.get_catalog("a"))["generation"] == good["generation"]
    finally:
        await service.aclose()


async def test_cancelled_download_reserves_clock_before_restart(tmp_path):
    started = asyncio.Event()
    calls = []

    async def provider(request):
        calls.append(request)
        started.set()
        await asyncio.Event().wait()

    first = OrbitalCatalogService(
        tmp_path,
        httpx.AsyncClient(transport=httpx.MockTransport(provider)),
        lambda: NOW,
    )
    await first.acquire("a")
    await asyncio.wait_for(started.wait(), 2)
    await first.aclose()
    second = OrbitalCatalogService(
        tmp_path,
        httpx.AsyncClient(transport=httpx.MockTransport(provider)),
        lambda: NOW,
    )
    try:
        await second.acquire("a")
        await second.get_catalog("a")
        assert len(calls) == 1
    finally:
        await second.aclose()


async def test_provider_state_write_failure_never_reaches_network(
    tmp_path, monkeypatch
):
    calls = []
    service = OrbitalCatalogService(
        tmp_path,
        httpx.AsyncClient(transport=httpx.MockTransport(lambda r: calls.append(r))),
        lambda: NOW,
    )

    def fail(*args):
        raise OSError("cannot persist attempt")

    monkeypatch.setattr(service.store, "_atomic_write", fail)
    try:
        await service.acquire("a")
        await service.get_catalog("a")
        assert calls == []
    finally:
        await service.aclose()


@pytest.mark.asyncio
async def test_catalog_retains_future_members_for_worker_eligibility_without_reinstall(
    tmp_path,
):
    now = NOW
    objects = [
        {**OBJECT, "NORAD_CAT_ID": "1", "EPOCH": NOW.isoformat()},
        {
            **OBJECT,
            "NORAD_CAT_ID": "2",
            "EPOCH": (NOW + timedelta(minutes=10, seconds=1)).isoformat(),
        },
    ]
    calls = 0

    def fetch(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=objects)

    async with httpx.AsyncClient(transport=httpx.MockTransport(fetch)) as client:
        service = OrbitalCatalogService(tmp_path, client=client, clock=lambda: now)
        await service.acquire("future-eligibility")
        before = await service.get_catalog("future-eligibility")
        assert before["eligible_count"] == 1
        assert [obj["NORAD_CAT_ID"] for obj in before["objects"]] == ["1", "2"]
        now += timedelta(seconds=1)
        after = await service.get_catalog("future-eligibility")
        assert after["generation"] == before["generation"]
        assert after["objects"] == before["objects"]
        assert after["eligible_count"] == 2
        assert calls == 1
        await service.aclose()
