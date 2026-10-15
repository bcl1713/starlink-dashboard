"""Contract tests for the five Prometheus trailing-window traces."""

import asyncio

import httpx
import pytest

from app.services.overview_history_prometheus import (
    MAX_OVERVIEW_HISTORY_SAMPLES,
    plan_overview_history_query,
)
from app.services.overview_history_rollups import (
    ROLLUP_METRICS,
    query_overview_history_rollups,
    rolling_promql,
)


@pytest.mark.parametrize(
    ("statistic", "function"),
    [("min", "min_over_time"), ("avg", "avg_over_time"), ("max", "max_over_time")],
)
@pytest.mark.parametrize(
    "metric",
    [
        "starlink_network_latency_ms_current",
        "starlink_network_throughput_down_mbps_current",
        "starlink_network_throughput_up_mbps_current",
        "starlink_network_packet_loss_percent",
        "starlink_dish_obstruction_percent",
    ],
)
def test_rollup_uses_trailing_five_minutes(metric, statistic, function):
    assert rolling_promql(metric, statistic) == f"{function}({metric}[5m])"


@pytest.mark.parametrize(
    ("metric", "statistic"),
    [("untrusted_metric", "min"), ("starlink_network_latency_ms_current", "sum")],
)
def test_rejects_unapproved_promql_inputs(metric, statistic):
    with pytest.raises(ValueError, match="Unsupported overview rollup"):
        rolling_promql(metric, statistic)


@pytest.mark.parametrize("window", [300, 900, 1800, 3600, 86400])
def test_shared_bounded_plan(window):
    plan = plan_overview_history_query(
        end_timestamp_seconds=1_782_000_000, window_seconds=window
    )
    assert plan.end_timestamp_seconds - plan.start_timestamp_seconds == window
    assert (window // plan.step_seconds) + 1 <= MAX_OVERVIEW_HISTORY_SAMPLES
    assert all(metric in plan.metric_names for metric in ROLLUP_METRICS)


@pytest.mark.asyncio
async def test_queries_all_fifteen_traces_on_the_same_plan_with_partial_failure():
    plan = plan_overview_history_query(
        end_timestamp_seconds=1_782_000_000, window_seconds=3600
    )
    requests: list[httpx.Request] = []
    latency, down, up, loss, obstruction = (
        "starlink_network_latency_ms_current",
        "starlink_network_throughput_down_mbps_current",
        "starlink_network_throughput_up_mbps_current",
        "starlink_network_packet_loss_percent",
        "starlink_dish_obstruction_percent",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        query = request.url.params["query"]
        if query == rolling_promql(obstruction, "max"):
            return httpx.Response(503)
        if query == rolling_promql(obstruction, "avg"):
            return httpx.Response(200, json={"status": "error", "error": "timeout"})
        if query == rolling_promql(obstruction, "min"):
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {"resultType": "vector", "result": []},
                },
            )
        if query == rolling_promql(down, "min"):
            series = []
        else:
            series = [
                {
                    "metric": {},  # PromQL aggregation generally removes __name__.
                    "values": [
                        [1_781_996_400, "2.5"],
                        [1_781_996_402, "NaN"],
                        [1_781_996_404, "3.5"],
                        [1_781_996_406, "Infinity"],
                        [1_781_996_408, "not-a-number"],
                        [1_781_996_410, "4.5"],
                    ],
                }
            ]
        if query == rolling_promql(up, "avg"):
            series.append(
                {
                    "metric": {"__name__": "unexpected_metric"},
                    "values": [[1_781_996_400, "999"]],
                }
            )
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {"resultType": "matrix", "result": series},
            },
        )

    async with httpx.AsyncClient(
        base_url="http://prometheus:9090", transport=httpx.MockTransport(handler)
    ) as client:
        result = await query_overview_history_rollups(client, plan)

    assert len(requests) == 15
    assert {request.url.path for request in requests} == {"/api/v1/query_range"}
    assert {request.url.params["query"] for request in requests} == {
        rolling_promql(metric, statistic)
        for metric in ROLLUP_METRICS
        for statistic in ("min", "avg", "max")
    }
    assert {
        (
            request.url.params["start"],
            request.url.params["end"],
            request.url.params["step"],
        )
        for request in requests
    } == {("1781996400", "1782000000", "2")}
    assert result[latency] == {
        "state": "available",
        "min": [[1_781_996_400.0, 2.5], [1_781_996_404.0, 3.5], [1_781_996_410.0, 4.5]],
        "avg": [[1_781_996_400.0, 2.5], [1_781_996_404.0, 3.5], [1_781_996_410.0, 4.5]],
        "max": [[1_781_996_400.0, 2.5], [1_781_996_404.0, 3.5], [1_781_996_410.0, 4.5]],
    }
    assert result[down]["state"] == "available"
    assert result[down]["min"] == []
    assert result[up]["state"] == "unavailable"
    assert result[up]["avg"] == []
    assert result[loss]["state"] == "available"
    assert result[obstruction] == {
        "state": "unavailable",
        "min": [],
        "avg": [],
        "max": [],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"status": "success", "data": {"resultType": "vector", "result": []}},
        {"status": "error", "error": "failed"},
        {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [{"metric": {}, "values": "bad"}],
            },
        },
        {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {"metric": {"__name__": "wrong"}, "values": [[1782000000, "1"]]}
                ],
            },
        },
    ],
)
async def test_bad_matrix_is_unavailable_without_erasing_other_metrics(payload):
    plan = plan_overview_history_query(
        end_timestamp_seconds=1_782_000_000, window_seconds=300
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["query"] == rolling_promql(ROLLUP_METRICS[0], "max"):
            return httpx.Response(200, json=payload)
        return httpx.Response(
            200,
            json={"status": "success", "data": {"resultType": "matrix", "result": []}},
        )

    async with httpx.AsyncClient(
        base_url="http://prometheus:9090", transport=httpx.MockTransport(handler)
    ) as client:
        result = await query_overview_history_rollups(client, plan)
    assert result[ROLLUP_METRICS[0]]["state"] == "unavailable"
    assert result[ROLLUP_METRICS[1]] == {
        "state": "available",
        "min": [],
        "avg": [],
        "max": [],
    }


@pytest.mark.asyncio
async def test_bounds_and_deduplicates_out_of_window_samples():
    plan = plan_overview_history_query(
        end_timestamp_seconds=1_782_000_000, window_seconds=1800
    )
    samples = [[plan.start_timestamp_seconds - 1, "1"]]
    samples.extend([[plan.start_timestamp_seconds + i, str(i)] for i in range(1801)])
    samples.extend(
        [[plan.end_timestamp_seconds, "999"], [plan.end_timestamp_seconds + 1, "1"]]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [{"metric": {}, "values": samples}],
                },
            },
        )

    async with httpx.AsyncClient(
        base_url="http://prometheus:9090", transport=httpx.MockTransport(handler)
    ) as client:
        result = await query_overview_history_rollups(client, plan)
    trace = result[ROLLUP_METRICS[0]]["min"]
    assert len(trace) == MAX_OVERVIEW_HISTORY_SAMPLES
    assert trace[0] == [float(plan.start_timestamp_seconds), 0.0]
    assert trace[-1] == [float(plan.end_timestamp_seconds), 1800.0]


@pytest.mark.asyncio
async def test_never_exceeds_three_in_flight_queries():
    plan = plan_overview_history_query(
        end_timestamp_seconds=1_782_000_000, window_seconds=300
    )
    active = 0
    peak = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.001)
        active -= 1
        return httpx.Response(
            200,
            json={"status": "success", "data": {"resultType": "matrix", "result": []}},
        )

    async with httpx.AsyncClient(
        base_url="http://prometheus:9090", transport=httpx.MockTransport(handler)
    ) as client:
        await query_overview_history_rollups(client, plan)
    assert peak == 3
