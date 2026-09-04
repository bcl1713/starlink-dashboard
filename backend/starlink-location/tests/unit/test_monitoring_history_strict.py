"""Adversarial bounds for the fixed-query monitoring history adapter."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
from app.services import monitoring_history
from app.services.monitoring_history import HistoryClient, HistoryUnavailable

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
START = int(NOW.timestamp()) - 60
END = int(NOW.timestamp())


def inclusive_values(start: int, count: int) -> list[list[int | str]]:
    return [[start + index, "1"] for index in range(count)]


def payload(values: list[Any], *, series_count: int = 1) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [{"values": values} for _ in range(series_count)],
        },
    }


def transport_for(body: dict[str, Any] | bytes) -> httpx.MockTransport:
    async def handler(_: httpx.Request) -> httpx.Response:
        if isinstance(body, bytes):
            return httpx.Response(200, content=body)
        return httpx.Response(200, json=body)

    return httpx.MockTransport(handler)


def deeply_nested_values_body(depth: int = 1200) -> bytes:
    prefix = '{"status":"success","data":{"resultType":"matrix","result":[{"values":['
    nested = "[" * depth + '"upstream-sensitive-detail"' + "]" * depth
    return (prefix + nested + "]}]}}").encode()


class TrackingTransport(httpx.AsyncBaseTransport):
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.closed = False
        self.response: httpx.Response | None = None

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        del request
        self.response = httpx.Response(200, content=self.body)
        return self.response

    async def aclose(self) -> None:
        self.closed = True


async def rejected(body: dict[str, Any] | bytes) -> None:
    client = HistoryClient(transport=transport_for(body), clock=lambda: NOW)
    with pytest.raises(HistoryUnavailable, match="monitoring history unavailable"):
        await client.fetch(range_seconds=60, step_seconds=1)


@pytest.mark.asyncio
async def test_deeply_nested_json_is_safely_rejected_and_response_is_closed() -> None:
    transport = TrackingTransport(deeply_nested_values_body())
    client = HistoryClient(transport=transport, clock=lambda: NOW)

    with pytest.raises(HistoryUnavailable) as caught:
        await client.fetch(range_seconds=60, step_seconds=1)

    assert str(caught.value) == "monitoring history unavailable"
    assert isinstance(caught.value.__cause__, RecursionError)
    assert "upstream-sensitive-detail" not in str(caught.value)
    assert transport.response is not None
    assert transport.response.is_closed
    assert transport.closed


@pytest.mark.asyncio
async def test_fetch_preserves_cancellation_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancellation = asyncio.CancelledError()

    async def cancelled(*_: object) -> None:
        raise cancellation

    monkeypatch.setattr(HistoryClient, "_fetch_all", cancelled)
    client = HistoryClient(clock=lambda: NOW)

    with pytest.raises(asyncio.CancelledError) as caught:
        await client.fetch(range_seconds=60, step_seconds=1)

    assert caught.value is cancellation


@pytest.mark.asyncio
async def test_malformed_json_and_body_overage_remain_safe_failures() -> None:
    await rejected(b"{")
    await rejected(b"x" * 2_000_001)


@pytest.mark.asyncio
async def test_timeout_remains_a_safe_failure() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        await asyncio.sleep(1)
        return httpx.Response(200, json=payload([]))

    client = HistoryClient(
        transport=httpx.MockTransport(handler),
        clock=lambda: NOW,
        timeout_seconds=0.001,
    )

    with pytest.raises(HistoryUnavailable, match="monitoring history unavailable"):
        await client.fetch(range_seconds=60, step_seconds=1)


@pytest.mark.asyncio
async def test_rejects_result_count_other_than_exactly_one() -> None:
    await rejected(payload([[START, "1"]], series_count=2))
    await rejected(payload([], series_count=0))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "values",
    [
        [[START, "1"], [START + 1]],
        [[START, "1"], {"timestamp": START + 1, "value": "2"}],
        [[START, "1"], [START + 1, "nan"]],
        [[START, "1"], [START + 1, "inf"]],
    ],
)
async def test_rejects_malformed_and_nonfinite_samples(values: list[Any]) -> None:
    await rejected(payload(values))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "values",
    [
        [[START + 1, "1"], [START, "2"]],
        [[START, "1"], [START, "2"]],
        [[START - 1, "1"]],
        [[END + 1, "1"]],
    ],
)
async def test_rejects_nonascending_duplicate_and_out_of_window_samples(
    values: list[Any],
) -> None:
    await rejected(payload(values))


@pytest.mark.asyncio
async def test_rejects_per_series_limit_before_json_decode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = [[START + (index / 100), "1"] for index in range(1802)]
    body = json.dumps(payload(values)).encode()
    decoded = False

    def forbidden_decode(_: object) -> object:
        nonlocal decoded
        decoded = True
        raise AssertionError("oversized point graph was decoded")

    monkeypatch.setattr(monitoring_history.json, "loads", forbidden_decode)
    await rejected(body)
    assert decoded is False


@pytest.mark.asyncio
async def test_accepts_maximum_default_history_for_all_fixed_queries() -> None:
    calls = 0
    default_start = int(NOW.timestamp()) - 1800

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=payload(inclusive_values(default_start, 1801)))

    client = HistoryClient(transport=httpx.MockTransport(handler), clock=lambda: NOW)

    result = await client.fetch(range_seconds=1800, step_seconds=1)

    assert calls == 6
    assert len(result.series) == 6
    assert all(len(series.samples) == 1801 for series in result.series)


@pytest.mark.asyncio
async def test_enforces_configured_aggregate_limit_before_all_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    monkeypatch.setattr(monitoring_history, "_MAX_AGGREGATE_POINTS", 7200)

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        values = [[START + (index / 100), "1"] for index in range(1800)]
        return httpx.Response(200, json=payload(values))

    client = HistoryClient(transport=httpx.MockTransport(handler), clock=lambda: NOW)
    with pytest.raises(HistoryUnavailable):
        await client.fetch(range_seconds=60, step_seconds=1)
    assert calls < 6


@pytest.mark.asyncio
async def test_rejects_aggregate_response_byte_limit_across_serial_queries() -> None:
    calls = 0
    padding = " " * 900_000
    body = json.dumps(payload([[START, "1"]])).encode() + padding.encode()

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=body)

    client = HistoryClient(transport=httpx.MockTransport(handler), clock=lambda: NOW)
    with pytest.raises(HistoryUnavailable):
        await client.fetch(range_seconds=60, step_seconds=1)
    assert calls < 6
