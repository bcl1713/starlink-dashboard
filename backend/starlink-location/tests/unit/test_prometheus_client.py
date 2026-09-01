"""Tests for the bounded Prometheus history client."""

from __future__ import annotations

import asyncio
import contextlib
import gc
import inspect
import json
import threading
from collections.abc import AsyncIterator, Awaitable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
from app.services import prometheus_client
from app.services.prometheus_client import (
    MonitoringPrometheusClient,
    MonitoringPrometheusError,
    MonitoringRateLimitError,
    MonitoringUnavailableError,
)

UTC_NOW = datetime(2026, 8, 29, 12, 0, 5, tzinfo=timezone.utc)
METRICS = [
    "latitude_degrees",
    "longitude_degrees",
    "latency_ms",
    "throughput_down_mbps",
    "throughput_up_mbps",
    "packet_loss_percent",
]
EXPRESSIONS = [
    "starlink_dish_latitude_degrees",
    "starlink_dish_longitude_degrees",
    "starlink_network_latency_ms_current",
    "starlink_network_throughput_down_mbps_current",
    "starlink_network_throughput_up_mbps_current",
    "starlink_network_packet_loss_percent",
]


def prom_response(expr: str, values: list[list[Any]] | None = None) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": (
                []
                if values is None
                else [{"metric": {"__name__": expr}, "values": values}]
            ),
        },
    }


def make_transport(
    handler: Any,
) -> httpx.MockTransport:
    async def async_handler(request: httpx.Request) -> httpx.Response:
        return await handler(request)

    return httpx.MockTransport(async_handler)


def make_client(
    handler: Any,
    *,
    clock: Any = lambda: UTC_NOW,
    **kwargs: Any,
) -> MonitoringPrometheusClient:
    return MonitoringPrometheusClient(
        base_url="http://prometheus:9090/root/",
        transport=make_transport(handler),
        clock=clock,
        **kwargs,
    )


async def successful_handler(request: httpx.Request) -> httpx.Response:
    expr = request.url.params["query"]
    return httpx.Response(200, json=prom_response(expr, [[1788004745, "1.5"]]))


@pytest.mark.asyncio
async def test_fixed_query_map_order_and_exact_path_params() -> None:
    seen: list[tuple[str, dict[str, str]]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, dict(request.url.params)))
        expr = request.url.params["query"]
        return httpx.Response(200, json=prom_response(expr, [[1788004745, "1"]]))

    response = await make_client(handler).get_history(
        range_seconds=60,
        step_seconds=10,
        client_id="server-client",
    )

    assert [series.metric for series in response.series] == METRICS
    assert [params["query"] for _, params in seen] == EXPRESSIONS
    assert {path for path, _ in seen} == {"/root/api/v1/query_range"}
    assert all(list(params) == ["query", "start", "end", "step"] for _, params in seen)
    assert {params["end"] for _, params in seen} == {"1788004805.0"}
    assert {params["start"] for _, params in seen} == {"1788004745.0"}
    assert {params["step"] for _, params in seen} == {"10"}


def test_public_signature_does_not_accept_untrusted_upstream_controls() -> None:
    params = set(inspect.signature(MonitoringPrometheusClient.get_history).parameters)

    assert {
        "query",
        "url",
        "hostname",
        "headers",
        "credentials",
        "kwargs",
    } & params == set()


@pytest.mark.asyncio
async def test_bounds_and_utc_window_validation() -> None:
    client = make_client(successful_handler)

    for kwargs in [
        {"range_seconds": 59, "step_seconds": 10},
        {"range_seconds": 3601, "step_seconds": 10},
        {"range_seconds": 60, "step_seconds": 0},
        {"range_seconds": 60, "step_seconds": 61},
    ]:
        with pytest.raises(MonitoringPrometheusError):
            await client.get_history(client_id="a", **kwargs)

    response = await client.get_history(
        range_seconds=60,
        step_seconds=10,
        client_id="a",
    )
    assert response.window_end.tzinfo == timezone.utc
    assert response.window_start.timestamp() == response.window_end.timestamp() - 60


@pytest.mark.asyncio
async def test_empty_result_returns_all_series_with_empty_samples() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        expr = request.url.params["query"]
        return httpx.Response(200, json=prom_response(expr, None))

    response = await make_client(handler).get_history(
        range_seconds=60,
        step_seconds=10,
        client_id="a",
    )

    assert [series.metric for series in response.series] == METRICS
    assert all(series.samples == [] for series in response.series)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "status_code"),
    [
        (
            {"status": "success", "data": {"resultType": "matrix", "result": [{}, {}]}},
            200,
        ),
        ({"status": "success", "data": {"resultType": "vector", "result": []}}, 200),
        (
            {
                "status": "success",
                "data": {"resultType": "matrix", "result": [], "x": 1},
            },
            200,
        ),
        (
            {
                "status": "error",
                "error": "boom",
                "data": {"resultType": "matrix", "result": []},
            },
            200,
        ),
        ({"status": "success", "data": {"resultType": "matrix", "result": []}}, 503),
    ],
)
async def test_rejects_bad_prometheus_shapes_and_upstream_status(
    body: dict[str, Any],
    status_code: int,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=body)

    with pytest.raises(MonitoringPrometheusError):
        await make_client(handler).get_history(
            range_seconds=60,
            step_seconds=10,
            client_id="a",
        )


@pytest.mark.asyncio
async def test_rejects_malformed_json_wrong_identity_and_bad_points() -> None:
    bad_bodies = [
        b"{bad",
        json.dumps(prom_response("wrong_metric", [[1788004745, "1"]])).encode(),
        json.dumps(prom_response(EXPRESSIONS[0], [[1788004745, "1", "x"]])).encode(),
        json.dumps(
            prom_response(EXPRESSIONS[0], [[1788004745, "1"], [1788004745, "2"]])
        ).encode(),
        json.dumps(
            prom_response(EXPRESSIONS[0], [[1788004746, "1"], [1788004745, "2"]])
        ).encode(),
    ]

    for body in bad_bodies:

        async def handler(request: httpx.Request, body: bytes = body) -> httpx.Response:
            return httpx.Response(200, content=body)

        with pytest.raises(MonitoringPrometheusError):
            await make_client(handler).get_history(
                range_seconds=60,
                step_seconds=10,
                client_id=str(body[:5]),
            )


@pytest.mark.asyncio
async def test_rejects_malformed_utf8_bare_json_constant_and_huge_timestamp() -> None:
    bad_bodies = [
        b"\xff",
        json.dumps(prom_response(EXPRESSIONS[0], [[1788004745, "1"]]))
        .replace("1788004745", "NaN", 1)
        .encode(),
        json.dumps(prom_response(EXPRESSIONS[0], [[1e300, "1"]])).encode(),
    ]

    for body in bad_bodies:

        async def handler(request: httpx.Request, body: bytes = body) -> httpx.Response:
            return httpx.Response(200, content=body)

        with pytest.raises(MonitoringPrometheusError) as exc:
            await make_client(handler).get_history(
                range_seconds=60,
                step_seconds=10,
                client_id=str(body[:5]),
            )

        message = str(exc.value)
        assert "prometheus:9090" not in message
        decoded_prefix = body.decode("utf-8", errors="ignore")[:20]
        if decoded_prefix:
            assert decoded_prefix not in message


@pytest.mark.asyncio
async def test_deep_json_recursion_maps_to_stable_malformed_json() -> None:
    body = b"[" * 1024 + b"0" + b"]" * 1024

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with pytest.raises(MonitoringPrometheusError) as exc:
        await make_client(handler).get_history(
            range_seconds=60,
            step_seconds=10,
            client_id="deep-json",
        )

    assert exc.value.code == "malformed_json"
    assert str(exc.value) == "malformed monitoring JSON"
    assert "[" * 20 not in str(exc.value)


@pytest.mark.asyncio
async def test_huge_sample_value_overflow_maps_to_stable_bad_point() -> None:
    huge_integer = "1" + ("0" * 4000)

    async def handler(request: httpx.Request) -> httpx.Response:
        expr = request.url.params["query"]
        body = (
            '{"status":"success","data":{"resultType":"matrix","result":[{"metric":'
            f'{{"__name__":"{expr}"}},"values":[[1788004745,{huge_integer}]]'
            "}]}}"
        )
        return httpx.Response(200, content=body)

    with pytest.raises(MonitoringPrometheusError) as exc:
        await make_client(handler).get_history(
            range_seconds=60,
            step_seconds=10,
            client_id="huge-value",
        )

    assert exc.value.code == "bad_point"
    assert str(exc.value) == "malformed monitoring sample point"
    assert huge_integer[:20] not in str(exc.value)


@pytest.mark.asyncio
async def test_accepts_one_identified_series_with_extra_string_labels() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        expr = request.url.params["query"]
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [
                        {
                            "metric": {
                                "__name__": expr,
                                "job": "starlink",
                                "instance": "backend:8000",
                            },
                            "values": [[1788004745, "1"]],
                        }
                    ],
                },
            },
        )

    response = await make_client(handler).get_history(
        range_seconds=60,
        step_seconds=10,
        client_id="labels",
    )

    assert [series.samples[0].value for series in response.series] == [1.0] * 6


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metric",
    [
        {},
        {"job": "starlink"},
        {"__name__": "wrong"},
        {"__name__": 1},
        {"__name__": EXPRESSIONS[0], "job": 1},
        {"__name__": EXPRESSIONS[0], 1: "starlink"},
        [("__name__", EXPRESSIONS[0])],
    ],
)
async def test_rejects_bad_metric_identity_labels(metric: object) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [{"metric": metric, "values": [[1788004745, "1"]]}],
                },
            },
        )

    with pytest.raises(MonitoringPrometheusError):
        await make_client(handler).get_history(
            range_seconds=60,
            step_seconds=10,
            client_id=str(metric),
        )


@pytest.mark.asyncio
async def test_aggregate_point_budget_rejects_before_constructing_excess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructed = 0
    original_model = prometheus_client.MonitoringSample

    def counting_sample(**data: Any) -> object:
        nonlocal constructed
        constructed += 1
        return original_model(**data)

    monkeypatch.setattr(prometheus_client, "MonitoringSample", counting_sample)

    async def handler(request: httpx.Request) -> httpx.Response:
        expr = request.url.params["query"]
        values = [[1788004745 + index, "1"] for index in range(8)]
        return httpx.Response(200, json=prom_response(expr, values))

    with pytest.raises(MonitoringPrometheusError):
        await make_client(handler).get_history(
            range_seconds=60,
            step_seconds=10,
            client_id="budget",
        )

    assert constructed <= 42


@pytest.mark.asyncio
async def test_point_cap_and_non_finite_normalization() -> None:
    async def too_many(request: httpx.Request) -> httpx.Response:
        expr = request.url.params["query"]
        values = [[1788004700 + index, "1"] for index in range(8)]
        return httpx.Response(200, json=prom_response(expr, values))

    with pytest.raises(MonitoringPrometheusError):
        await make_client(too_many).get_history(
            range_seconds=60,
            step_seconds=10,
            client_id="a",
        )

    async def non_finite(request: httpx.Request) -> httpx.Response:
        expr = request.url.params["query"]
        return httpx.Response(
            200,
            json=prom_response(expr, [[1788004745, "NaN"], [1788004755, "+Inf"]]),
        )

    response = await make_client(non_finite).get_history(
        range_seconds=60,
        step_seconds=10,
        client_id="b",
    )
    assert [sample.value for sample in response.series[0].samples] == [None, None]


@pytest.mark.asyncio
async def test_streaming_byte_cap_crossing_and_safe_exception_message() -> None:
    class ChunkyStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield b'{"status":"success",'
            yield b'"data":{"resultType":"matrix","result":[]}}'

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=ChunkyStream())

    with pytest.raises(MonitoringPrometheusError) as exc:
        await make_client(handler, byte_limit=20).get_history(
            range_seconds=60,
            step_seconds=10,
            client_id="a",
        )

    message = str(exc.value)
    assert "prometheus:9090" not in message
    assert "resultType" not in message


@pytest.mark.asyncio
async def test_timeout_and_disconnect_cancellation_preserve_cancellation() -> None:
    async def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("connect http://secret")

    with pytest.raises(MonitoringPrometheusError) as exc:
        await make_client(timeout_handler).get_history(
            range_seconds=60,
            step_seconds=10,
            client_id="a",
        )
    assert "secret" not in str(exc.value)

    disconnect = asyncio.Event()
    disconnect.set()
    with pytest.raises(asyncio.CancelledError):
        await make_client(successful_handler).get_history(
            range_seconds=60,
            step_seconds=10,
            client_id="b",
            cancel_event=disconnect,
        )


@pytest.mark.asyncio
async def test_rate_limit_raises_retry_after() -> None:
    client = make_client(successful_handler, rate_limit_count=2)

    await client.get_history(range_seconds=60, step_seconds=10, client_id="a")
    await client.get_history(range_seconds=60, step_seconds=10, client_id="a")
    with pytest.raises(MonitoringRateLimitError) as exc:
        await client.get_history(range_seconds=60, step_seconds=10, client_id="a")

    assert 0 < exc.value.retry_after_seconds <= 60


@pytest.mark.asyncio
async def test_rate_limit_blocks_thirteenth_request_without_churn_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 1000.0
    monkeypatch.setattr(prometheus_client.time, "monotonic", lambda: now)
    client = make_client(successful_handler)
    cap = MonitoringPrometheusClient._max_rate_limit_identities

    for _ in range(12):
        await client._enforce_rate_limit("original")

    with pytest.raises(MonitoringRateLimitError):
        await client._enforce_rate_limit("original")

    for index in range(cap - 1):
        await client._enforce_rate_limit(f"churn-{index}")

    for index in range(20):
        with pytest.raises(MonitoringRateLimitError) as exc:
            await client._enforce_rate_limit(f"blocked-churn-{index}")
        assert exc.value.retry_after_seconds == 60

    assert len(client._requests) == cap
    assert "original" in client._requests
    with pytest.raises(MonitoringRateLimitError) as exc:
        await client._enforce_rate_limit("original")
    assert exc.value.retry_after_seconds == 60


@pytest.mark.asyncio
async def test_rate_limit_evicts_expired_identity_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 1000.0
    monkeypatch.setattr(prometheus_client.time, "monotonic", lambda: now)
    client = make_client(successful_handler)

    for index in range(200):
        await client._enforce_rate_limit(f"expired-{index}")

    now += 61
    await client._enforce_rate_limit("current")

    assert set(client._requests) == {"current"}


@pytest.mark.asyncio
async def test_rate_limit_unseen_identity_fails_closed_at_unexpired_hard_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 1000.0
    monkeypatch.setattr(prometheus_client.time, "monotonic", lambda: now)
    client = make_client(successful_handler)
    cap = MonitoringPrometheusClient._max_rate_limit_identities

    for index in range(cap):
        await client._enforce_rate_limit(f"identity-{index}")

    with pytest.raises(MonitoringRateLimitError) as exc:
        await client._enforce_rate_limit("newcomer")

    assert len(client._requests) == cap
    assert "newcomer" not in client._requests
    assert "identity-0" in client._requests
    assert exc.value.retry_after_seconds == 60


@pytest.mark.asyncio
async def test_rate_limit_known_identity_still_accounts_at_full_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 1000.0
    monkeypatch.setattr(prometheus_client.time, "monotonic", lambda: now)
    client = make_client(successful_handler)
    cap = MonitoringPrometheusClient._max_rate_limit_identities

    await client._enforce_rate_limit("known")
    for index in range(cap - 1):
        await client._enforce_rate_limit(f"identity-{index}")

    for _ in range(11):
        await client._enforce_rate_limit("known")

    assert len(client._requests) == cap
    assert "known" in client._requests
    with pytest.raises(MonitoringRateLimitError) as exc:
        await client._enforce_rate_limit("known")
    assert exc.value.retry_after_seconds == 60


@pytest.mark.asyncio
async def test_rate_limit_prunes_full_cap_then_accepts_unseen_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 1000.0
    monkeypatch.setattr(prometheus_client.time, "monotonic", lambda: now)
    client = make_client(successful_handler)
    cap = MonitoringPrometheusClient._max_rate_limit_identities

    for index in range(cap):
        await client._enforce_rate_limit(f"identity-{index}")

    now += 61
    await client._enforce_rate_limit("newcomer")

    assert len(client._requests) == 1
    assert set(client._requests) == {"newcomer"}


@pytest.mark.asyncio
async def test_rate_limit_full_cap_sweep_uses_actual_earliest_expiry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 1000.0
    monkeypatch.setattr(prometheus_client.time, "monotonic", lambda: now)
    client = make_client(successful_handler)
    cap = MonitoringPrometheusClient._max_rate_limit_identities

    await client._enforce_rate_limit("a")

    now = 1010.0
    for index in range(cap - 1):
        await client._enforce_rate_limit(f"identity-{index}")

    now = 1050.0
    await client._enforce_rate_limit("a")

    assert len(client._requests) == cap
    assert list(client._requests["a"]) == [1000.0, 1050.0]
    assert "identity-0" in client._requests

    now = 1060.0
    with pytest.raises(MonitoringRateLimitError) as exc:
        await client._enforce_rate_limit("newcomer")

    assert exc.value.retry_after_seconds == 10
    assert len(client._requests) == cap
    assert list(client._requests["a"]) == [1050.0]
    assert "newcomer" not in client._requests
    assert "identity-0" in client._requests

    now = 1070.0
    await client._enforce_rate_limit("newcomer")

    assert len(client._requests) == 2
    assert set(client._requests) == {"a", "newcomer"}
    assert list(client._requests["a"]) == [1050.0]
    assert list(client._requests["newcomer"]) == [1070.0]


@pytest.mark.asyncio
async def test_semaphore_max_four_and_queue_full() -> None:
    active = 0
    max_active = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.05)
        expr = request.url.params["query"]
        active -= 1
        return httpx.Response(200, json=prom_response(expr, [[1788004745, "1"]]))

    client = make_client(handler)
    await client.get_history(range_seconds=60, step_seconds=10, client_id="a")
    assert max_active <= 4


@pytest.mark.asyncio
async def test_process_wide_upstream_limit_across_client_instances() -> None:
    active = 0
    max_active = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.02)
        expr = request.url.params["query"]
        active -= 1
        return httpx.Response(200, json=prom_response(expr, [[1788004745, "1"]]))

    first = make_client(handler)
    second = make_client(handler)

    await asyncio.gather(
        first.get_history(range_seconds=60, step_seconds=10, client_id="a"),
        second.get_history(range_seconds=70, step_seconds=10, client_id="b"),
    )

    assert max_active <= 4


def test_process_wide_upstream_limit_across_threads_and_event_loops() -> None:
    active = 0
    max_active = 0
    lock = threading.Lock()
    release = threading.Event()
    ready = threading.Barrier(2)
    all_slots_busy = threading.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
            if active == 4:
                all_slots_busy.set()
        await asyncio.to_thread(release.wait)
        with lock:
            active -= 1
        expr = request.url.params["query"]
        return httpx.Response(200, json=prom_response(expr, [[1788004745, "1"]]))

    async def run_client(client_id: str, range_seconds: int) -> None:
        client = make_client(handler)
        ready.wait(timeout=1)
        await client.get_history(
            range_seconds=range_seconds,
            step_seconds=10,
            client_id=client_id,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(asyncio.run, run_client("thread-a", 60)),
            executor.submit(asyncio.run, run_client("thread-b", 70)),
        ]
        try:
            assert all_slots_busy.wait(timeout=1)
        finally:
            release.set()
        for future in futures:
            future.result(timeout=2)

    assert max_active <= 4
    assert MonitoringPrometheusClient._inspect_upstream_slots_in_use_for_tests() == 0


@pytest.mark.asyncio
async def test_process_wide_queue_full_across_client_instances() -> None:
    release = asyncio.Event()
    all_slots_busy = asyncio.Event()
    active = 0
    lock = asyncio.Lock()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active
        async with lock:
            active += 1
            if active == 4:
                all_slots_busy.set()
        await release.wait()
        try:
            expr = request.url.params["query"]
            return httpx.Response(200, json=prom_response(expr, [[1788004745, "1"]]))
        finally:
            async with lock:
                active -= 1

    blocker = make_client(handler)
    queued = make_client(handler, admission_timeout_seconds=0.001)

    blocked = asyncio.create_task(
        blocker.get_history(range_seconds=60, step_seconds=10, client_id="a")
    )
    await asyncio.wait_for(all_slots_busy.wait(), timeout=1)

    with pytest.raises(MonitoringUnavailableError):
        await queued.get_history(range_seconds=70, step_seconds=10, client_id="b")

    release.set()
    await blocked


def test_process_wide_queue_full_across_event_loops() -> None:
    release = threading.Event()
    all_slots_busy = threading.Event()
    active = 0
    lock = threading.Lock()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active
        with lock:
            active += 1
            if active == 4:
                all_slots_busy.set()
        await asyncio.to_thread(release.wait)
        try:
            expr = request.url.params["query"]
            return httpx.Response(200, json=prom_response(expr, [[1788004745, "1"]]))
        finally:
            with lock:
                active -= 1

    async def block_slots() -> None:
        client = make_client(handler)
        await client.get_history(range_seconds=60, step_seconds=10, client_id="a")

    async def queued_request() -> None:
        client = make_client(handler, admission_timeout_seconds=0.001)
        with pytest.raises(MonitoringUnavailableError):
            await asyncio.wait_for(
                client.get_history(
                    range_seconds=70,
                    step_seconds=10,
                    client_id="b",
                ),
                timeout=0.2,
            )

    with ThreadPoolExecutor(max_workers=1) as executor:
        blocker = executor.submit(asyncio.run, block_slots())
        try:
            assert all_slots_busy.wait(timeout=1)
            asyncio.run(queued_request())
        finally:
            release.set()
        blocker.result(timeout=2)

    assert MonitoringPrometheusClient._inspect_upstream_slots_in_use_for_tests() == 0


@pytest.mark.asyncio
async def test_cancelled_cross_loop_admission_does_not_leak_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = asyncio.Event()
    all_slots_busy = asyncio.Event()
    admission_entered = threading.Event()
    admission_entries = 0
    admission_lock = threading.Lock()
    active = 0
    lock = asyncio.Lock()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active
        async with lock:
            active += 1
            if active == 4:
                all_slots_busy.set()
        await release.wait()
        try:
            expr = request.url.params["query"]
            return httpx.Response(200, json=prom_response(expr, [[1788004745, "1"]]))
        finally:
            async with lock:
                active -= 1

    blockers = [
        asyncio.create_task(
            make_client(handler).get_history(
                range_seconds=60 + index,
                step_seconds=10,
                client_id=str(index),
            )
        )
        for index in range(4)
    ]
    await asyncio.wait_for(all_slots_busy.wait(), timeout=1)

    waiting_client = make_client(handler, admission_timeout_seconds=1)
    original_acquire = waiting_client._acquire_upstream_slot

    async def observed_acquire() -> None:
        nonlocal admission_entries
        with admission_lock:
            admission_entries += 1
        admission_entered.set()
        await original_acquire()

    monkeypatch.setattr(waiting_client, "_acquire_upstream_slot", observed_acquire)
    waiting = asyncio.create_task(
        waiting_client.get_history(
            range_seconds=100,
            step_seconds=10,
            client_id="waiting",
        )
    )
    assert await asyncio.wait_for(
        asyncio.to_thread(admission_entered.wait, 1),
        timeout=1.5,
    )
    assert admission_entries >= 1
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting

    release.set()
    await asyncio.gather(*blockers)

    assert MonitoringPrometheusClient._inspect_upstream_slots_in_use_for_tests() == 0


@pytest.mark.asyncio
async def test_awaitable_cancel_callback_forms_during_admission() -> None:
    release = asyncio.Event()
    all_slots_busy = asyncio.Event()
    active = 0
    lock = asyncio.Lock()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active
        async with lock:
            active += 1
            if active == 4:
                all_slots_busy.set()
        await release.wait()
        try:
            expr = request.url.params["query"]
            return httpx.Response(200, json=prom_response(expr, [[1788004745, "1"]]))
        finally:
            async with lock:
                active -= 1

    blockers = [
        asyncio.create_task(
            make_client(handler).get_history(
                range_seconds=60 + index,
                step_seconds=10,
                client_id=str(index),
            )
        )
        for index in range(4)
    ]
    await asyncio.wait_for(all_slots_busy.wait(), timeout=1)

    false_future: asyncio.Future[bool] = asyncio.Future()
    false_future.set_result(False)
    callback_calls = 0

    class AwaitableTrue:
        def __await__(self) -> Any:
            async def inner() -> bool:
                return True

            return inner().__await__()

    def callback() -> bool | Awaitable[bool]:
        nonlocal callback_calls
        callback_calls += 1
        if callback_calls == 1:
            return false_future
        return AwaitableTrue()

    with pytest.raises(asyncio.CancelledError):
        await make_client(handler, admission_timeout_seconds=1).get_history(
            range_seconds=100,
            step_seconds=10,
            client_id="waiting",
            cancel_callback=callback,
        )

    release.set()
    await asyncio.gather(*blockers)
    assert callback_calls >= 2
    assert MonitoringPrometheusClient._inspect_upstream_slots_in_use_for_tests() == 0


@pytest.mark.asyncio
async def test_awaitable_cancel_callback_forms_during_shared_flight_wait() -> None:
    release = asyncio.Event()
    entered = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        entered.set()
        await release.wait()
        expr = request.url.params["query"]
        return httpx.Response(200, json=prom_response(expr, [[1788004745, "1"]]))

    true_future: asyncio.Future[bool] = asyncio.Future()
    true_future.set_result(True)
    false_future: asyncio.Future[bool] = asyncio.Future()
    false_future.set_result(False)
    callback_calls = 0

    async def coroutine_false() -> bool:
        return False

    class AwaitableFalse:
        def __await__(self) -> Any:
            return coroutine_false().__await__()

    def callback() -> bool | Awaitable[bool]:
        nonlocal callback_calls
        callback_calls += 1
        if callback_calls == 1:
            return false_future
        if callback_calls == 2:
            return coroutine_false()
        if callback_calls == 3:
            return AwaitableFalse()
        return true_future

    client = make_client(handler)
    survivor = asyncio.create_task(
        client.get_history(range_seconds=60, step_seconds=10, client_id="a")
    )
    waiter = asyncio.create_task(
        client.get_history(
            range_seconds=60,
            step_seconds=10,
            client_id="b",
            cancel_callback=callback,
        )
    )
    await asyncio.wait_for(_wait_for_flight_waiters(client, 2), timeout=1)

    with pytest.raises(asyncio.CancelledError):
        await waiter

    release.set()
    response = await survivor
    assert response.series[0].samples[0].value == 1.0
    assert callback_calls >= 4


@pytest.mark.asyncio
async def test_single_flight_shares_results_errors_and_live_only_cache() -> None:
    calls = 0
    release = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        await release.wait()
        expr = request.url.params["query"]
        return httpx.Response(200, json=prom_response(expr, [[1788004745, "1"]]))

    client = make_client(handler)
    one = asyncio.create_task(
        client.get_history(range_seconds=60, step_seconds=10, client_id="a")
    )
    two = asyncio.create_task(
        client.get_history(range_seconds=60, step_seconds=10, client_id="b")
    )
    await asyncio.wait_for(_wait_for_flight_waiters(client, 2), timeout=1)
    release.set()

    first_response, second_response = await asyncio.gather(one, two)
    assert first_response == second_response
    assert calls == 6

    await client.get_history(range_seconds=60, step_seconds=10, client_id="c")
    assert calls == 12


@pytest.mark.asyncio
async def test_series_failure_cancels_blocked_siblings_and_restores_capacity() -> None:
    cancelled: set[str] = set()
    entered: set[str] = set()

    async def handler(request: httpx.Request) -> httpx.Response:
        expr = request.url.params["query"]
        if expr == EXPRESSIONS[0]:
            while len(entered) < 3:
                await asyncio.sleep(0)
            return httpx.Response(200, content=b"{bad")
        entered.add(expr)
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.add(expr)
            raise
        return httpx.Response(200, json=prom_response(expr, [[1788004745, "1"]]))

    client = make_client(handler)
    with pytest.raises(MonitoringPrometheusError) as exc:
        await client.get_history(range_seconds=60, step_seconds=10, client_id="a")

    assert exc.value.code == "malformed_json"
    assert cancelled == set(EXPRESSIONS[1:4])
    assert client._flights == {}
    assert MonitoringPrometheusClient._inspect_upstream_slots_in_use_for_tests() == 0
    assert not _internal_pending_tasks()


@pytest.mark.asyncio
async def test_timeout_cancels_siblings_and_restores_capacity() -> None:
    cancelled: set[str] = set()
    entered: set[str] = set()

    async def handler(request: httpx.Request) -> httpx.Response:
        expr = request.url.params["query"]
        if expr == EXPRESSIONS[0]:
            while len(entered) < 3:
                await asyncio.sleep(0)
            raise httpx.TimeoutException("timeout http://secret")
        entered.add(expr)
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.add(expr)
            raise
        return httpx.Response(200, json=prom_response(expr, [[1788004745, "1"]]))

    client = make_client(handler)
    with pytest.raises(MonitoringPrometheusError) as exc:
        await client.get_history(range_seconds=60, step_seconds=10, client_id="a")

    assert exc.value.code == "upstream_timeout"
    assert "secret" not in str(exc.value)
    assert cancelled == set(EXPRESSIONS[1:4])
    assert client._flights == {}
    assert MonitoringPrometheusClient._inspect_upstream_slots_in_use_for_tests() == 0
    assert not _internal_pending_tasks()


@pytest.mark.asyncio
async def test_total_history_deadline_bounds_trickling_valid_streams_and_cleans_up() -> (
    None
):
    cancelled: set[str] = set()

    class TrickleStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            try:
                for _ in range(20):
                    await asyncio.sleep(0.01)
                    yield b" "
            except asyncio.CancelledError:
                cancelled.add("stream")
                raise

        async def aclose(self) -> None:
            return None

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=TrickleStream())

    client = make_client(
        handler,
        timeout_seconds=1,
        total_history_timeout_seconds=0.04,
    )
    started = asyncio.get_running_loop().time()
    with pytest.raises(MonitoringPrometheusError) as exc:
        await client.get_history(range_seconds=60, step_seconds=10, client_id="a")
    elapsed = asyncio.get_running_loop().time() - started

    assert exc.value.code == "upstream_timeout"
    assert elapsed < 0.2
    assert cancelled == {"stream"}
    assert client._flights == {}
    assert MonitoringPrometheusClient._inspect_upstream_slots_in_use_for_tests() == 0
    assert not _internal_pending_tasks()


@pytest.mark.asyncio
async def test_queue_full_cleans_flight_and_internal_tasks() -> None:
    release = asyncio.Event()
    all_slots_busy = asyncio.Event()
    active = 0
    lock = asyncio.Lock()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active
        async with lock:
            active += 1
            if active == 4:
                all_slots_busy.set()
        await release.wait()
        try:
            expr = request.url.params["query"]
            return httpx.Response(200, json=prom_response(expr, [[1788004745, "1"]]))
        finally:
            async with lock:
                active -= 1

    client = make_client(handler, admission_timeout_seconds=0.001)
    task = asyncio.create_task(
        client.get_history(range_seconds=60, step_seconds=10, client_id="a")
    )
    await asyncio.wait_for(all_slots_busy.wait(), timeout=1)

    with pytest.raises(MonitoringUnavailableError):
        await task

    release.set()
    assert client._flights == {}
    assert MonitoringPrometheusClient._inspect_upstream_slots_in_use_for_tests() == 0
    assert not _internal_pending_tasks()


@pytest.mark.asyncio
async def test_caller_cancellation_cleans_siblings_and_restores_capacity() -> None:
    cancelled: set[str] = set()
    all_slots_busy = asyncio.Event()
    active = 0
    lock = asyncio.Lock()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active
        expr = request.url.params["query"]
        async with lock:
            active += 1
            if active == 4:
                all_slots_busy.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.add(expr)
            raise
        finally:
            async with lock:
                active -= 1

    client = make_client(handler)
    task = asyncio.create_task(
        client.get_history(range_seconds=60, step_seconds=10, client_id="a")
    )
    await asyncio.wait_for(all_slots_busy.wait(), timeout=1)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert cancelled == set(EXPRESSIONS[:4])
    assert client._flights == {}
    assert MonitoringPrometheusClient._inspect_upstream_slots_in_use_for_tests() == 0
    assert not _internal_pending_tasks()

    async def failing(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("internal-url")

    failing_client = make_client(failing)
    first = asyncio.create_task(
        failing_client.get_history(range_seconds=60, step_seconds=10, client_id="d")
    )
    second = asyncio.create_task(
        failing_client.get_history(range_seconds=60, step_seconds=10, client_id="e")
    )
    with pytest.raises(MonitoringPrometheusError):
        await first
    with pytest.raises(MonitoringPrometheusError):
        await second


@pytest.mark.asyncio
async def test_completed_flight_success_never_caches_during_delayed_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    cleanup_release = asyncio.Event()
    original_cleanup = MonitoringPrometheusClient._cleanup_flight

    async def delayed_cleanup(self: MonitoringPrometheusClient, *args: Any) -> None:
        await cleanup_release.wait()
        await original_cleanup(self, *args)

    monkeypatch.setattr(MonitoringPrometheusClient, "_cleanup_flight", delayed_cleanup)

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        expr = request.url.params["query"]
        return httpx.Response(200, json=prom_response(expr, [[1788004745, "1"]]))

    client = make_client(handler)
    await client.get_history(range_seconds=60, step_seconds=10, client_id="a")
    await client.get_history(range_seconds=60, step_seconds=10, client_id="b")
    cleanup_release.set()
    await asyncio.sleep(0)

    assert calls == 12


@pytest.mark.asyncio
async def test_completed_flight_error_never_caches_during_delayed_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    cleanup_release = asyncio.Event()
    original_cleanup = MonitoringPrometheusClient._cleanup_flight

    async def delayed_cleanup(self: MonitoringPrometheusClient, *args: Any) -> None:
        await cleanup_release.wait()
        await original_cleanup(self, *args)

    monkeypatch.setattr(MonitoringPrometheusClient, "_cleanup_flight", delayed_cleanup)

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("internal-url")

    client = make_client(handler)
    with pytest.raises(MonitoringPrometheusError):
        await client.get_history(range_seconds=60, step_seconds=10, client_id="a")
    with pytest.raises(MonitoringPrometheusError):
        await client.get_history(range_seconds=60, step_seconds=10, client_id="b")
    cleanup_release.set()
    await asyncio.sleep(0)

    assert calls == 12


@pytest.mark.asyncio
async def test_disconnect_during_live_shared_flight_cancels_only_that_waiter() -> None:
    release = asyncio.Event()
    entered = asyncio.Event()
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        entered.set()
        await release.wait()
        expr = request.url.params["query"]
        return httpx.Response(200, json=prom_response(expr, [[1788004745, "1"]]))

    client = make_client(handler)
    disconnect = asyncio.Event()
    first = asyncio.create_task(
        client.get_history(range_seconds=60, step_seconds=10, client_id="a")
    )
    second = asyncio.create_task(
        client.get_history(
            range_seconds=60,
            step_seconds=10,
            client_id="b",
            cancel_event=disconnect,
        )
    )
    await asyncio.wait_for(_wait_for_flight_waiters(client, 2), timeout=1)
    disconnect.set()

    with pytest.raises(asyncio.CancelledError):
        await second

    release.set()
    response = await first
    assert response.series[0].samples[0].value == 1.0
    assert calls == 6


@pytest.mark.asyncio
async def test_abandoned_shield_wrapper_settled_after_disconnect_and_shared_error() -> (
    None
):
    release = asyncio.Event()
    entered = asyncio.Event()
    loop = asyncio.get_running_loop()
    unhandled: list[object] = []
    previous_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: unhandled.append(context))

    async def handler(request: httpx.Request) -> httpx.Response:
        entered.set()
        await release.wait()
        raise httpx.ConnectError("internal-url")

    client = make_client(handler)
    disconnect = asyncio.Event()
    survivor = asyncio.create_task(
        client.get_history(range_seconds=60, step_seconds=10, client_id="a")
    )
    leaving = asyncio.create_task(
        client.get_history(
            range_seconds=60,
            step_seconds=10,
            client_id="b",
            cancel_event=disconnect,
        )
    )
    try:
        await asyncio.wait_for(_wait_for_flight_waiters(client, 2), timeout=1)
        disconnect.set()

        with pytest.raises(asyncio.CancelledError):
            await leaving
        release.set()
        with pytest.raises(MonitoringPrometheusError) as exc:
            await survivor

        gc.collect()
        await asyncio.sleep(0)
    finally:
        loop.set_exception_handler(previous_handler)
    assert exc.value.code == "upstream_transport_error"
    assert unhandled == []


@pytest.mark.asyncio
async def test_abandoned_shield_wrapper_settled_after_caller_cancel_and_success() -> (
    None
):
    release = asyncio.Event()
    entered = asyncio.Event()
    loop = asyncio.get_running_loop()
    unhandled: list[object] = []
    previous_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: unhandled.append(context))

    async def handler(request: httpx.Request) -> httpx.Response:
        entered.set()
        await release.wait()
        expr = request.url.params["query"]
        return httpx.Response(200, json=prom_response(expr, [[1788004745, "1"]]))

    client = make_client(handler)
    survivor = asyncio.create_task(
        client.get_history(range_seconds=60, step_seconds=10, client_id="a")
    )
    leaving = asyncio.create_task(
        client.get_history(range_seconds=60, step_seconds=10, client_id="b")
    )
    try:
        await asyncio.wait_for(_wait_for_flight_waiters(client, 2), timeout=1)
        leaving.cancel()

        with pytest.raises(asyncio.CancelledError):
            await leaving
        release.set()
        response = await survivor

        gc.collect()
        await asyncio.sleep(0)
    finally:
        loop.set_exception_handler(previous_handler)
    assert response.series[0].samples[0].value == 1.0
    assert unhandled == []


@pytest.mark.asyncio
async def test_sole_waiter_disconnect_cancels_upstream() -> None:
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        expr = request.url.params["query"]
        return httpx.Response(200, json=prom_response(expr, [[1788004745, "1"]]))

    client = make_client(handler)
    disconnect = asyncio.Event()
    task = asyncio.create_task(
        client.get_history(
            range_seconds=60,
            step_seconds=10,
            client_id="a",
            cancel_event=disconnect,
        )
    )
    await started.wait()
    disconnect.set()

    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(cancelled.wait(), timeout=1)


@pytest.mark.asyncio
async def test_disconnect_callback_is_polled_while_waiting() -> None:
    release = asyncio.Event()
    entered = asyncio.Event()
    disconnected = False

    async def handler(request: httpx.Request) -> httpx.Response:
        entered.set()
        await release.wait()
        expr = request.url.params["query"]
        return httpx.Response(200, json=prom_response(expr, [[1788004745, "1"]]))

    async def callback() -> bool:
        return disconnected

    client = make_client(handler)
    task = asyncio.create_task(
        client.get_history(
            range_seconds=60,
            step_seconds=10,
            client_id="a",
            cancel_callback=callback,
        )
    )
    await asyncio.wait_for(entered.wait(), timeout=1)
    disconnected = True

    with pytest.raises(asyncio.CancelledError):
        await task
    release.set()


@pytest.mark.asyncio
async def test_disconnect_during_admission_and_no_pending_task_leaks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = asyncio.Event()
    all_slots_busy = asyncio.Event()
    admission_entered = asyncio.Event()
    admission_entries = 0
    active = 0
    lock = asyncio.Lock()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active
        async with lock:
            active += 1
            if active == 4:
                all_slots_busy.set()
        await release.wait()
        try:
            expr = request.url.params["query"]
            return httpx.Response(200, json=prom_response(expr, [[1788004745, "1"]]))
        finally:
            async with lock:
                active -= 1

    blockers = [make_client(handler) for _ in range(4)]
    blocking_tasks = [
        asyncio.create_task(
            client.get_history(
                range_seconds=60 + index, step_seconds=10, client_id=str(index)
            )
        )
        for index, client in enumerate(blockers)
    ]
    await asyncio.wait_for(all_slots_busy.wait(), timeout=1)

    disconnect = asyncio.Event()
    waiting_client = make_client(handler)
    original_acquire = waiting_client._acquire_upstream_slot

    async def observed_acquire() -> None:
        nonlocal admission_entries
        admission_entries += 1
        admission_entered.set()
        await original_acquire()

    monkeypatch.setattr(waiting_client, "_acquire_upstream_slot", observed_acquire)
    waiting = asyncio.create_task(
        waiting_client.get_history(
            range_seconds=80,
            step_seconds=10,
            client_id="waiting",
            cancel_event=disconnect,
        )
    )
    await asyncio.wait_for(admission_entered.wait(), timeout=1)
    assert admission_entries >= 1
    before = asyncio.all_tasks()
    disconnect.set()
    with pytest.raises(asyncio.CancelledError):
        await waiting

    release.set()
    await asyncio.gather(*blocking_tasks)
    await asyncio.sleep(0)
    leaked = [
        task
        for task in asyncio.all_tasks() - before
        if task is not asyncio.current_task() and not task.done()
    ]
    for task in leaked:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    assert leaked == []


@pytest.mark.asyncio
async def test_no_coalescing_different_bucket_and_waiter_cancellation_isolated() -> (
    None
):
    calls = 0
    times = [UTC_NOW, datetime(2026, 8, 29, 12, 0, 15, tzinfo=timezone.utc)]
    release = asyncio.Event()

    def clock() -> datetime:
        return times[min(calls // 6, 1)]

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        await release.wait()
        expr = request.url.params["query"]
        return httpx.Response(200, json=prom_response(expr, [[1788004745, "1"]]))

    client = make_client(handler, clock=clock)
    first = asyncio.create_task(
        client.get_history(range_seconds=60, step_seconds=10, client_id="a")
    )
    await asyncio.sleep(0)
    second = asyncio.create_task(
        client.get_history(range_seconds=60, step_seconds=10, client_id="b")
    )
    second.cancel()
    release.set()

    response = await first
    assert response.series[0].samples[0].value == 1.0
    with pytest.raises(asyncio.CancelledError):
        await second

    release.clear()
    third = asyncio.create_task(
        client.get_history(range_seconds=60, step_seconds=10, client_id="c")
    )
    await asyncio.sleep(0)
    release.set()
    await third
    assert calls == 12


def _internal_pending_tasks() -> list[asyncio.Task[Any]]:
    current = asyncio.current_task()
    internal_names = (
        "_fetch_history",
        "_fetch_series",
        "_acquire_upstream_slot",
        "_await_with_disconnect",
        "_watch_cancel_event",
        "_watch_cancel_callback",
        "_cleanup_flight",
    )
    return [
        task
        for task in asyncio.all_tasks()
        if task is not current
        and not task.done()
        and any(name in task.get_coro().__qualname__ for name in internal_names)
    ]


async def _wait_for_flight_waiters(
    client: MonitoringPrometheusClient,
    count: int,
) -> None:
    while True:
        async with client._flight_lock:
            if any(flight.waiters == count for flight in client._flights.values()):
                return
        await asyncio.sleep(0)
