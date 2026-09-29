import asyncio

import httpx
import pytest

from app.services.overview_history_prometheus import (
    MAX_OVERVIEW_HISTORY_SAMPLES,
    OVERVIEW_HISTORY_METRICS,
    OverviewHistoryBundleSingleFlight,
    OverviewHistoryPrometheusResponseError,
    OverviewHistoryReader,
    build_overview_history_prometheus_params,
    build_overview_history_promql,
    fetch_overview_history_from_prometheus,
    plan_overview_history_query,
    project_overview_history_matrix,
    query_overview_history_bundle,
    resolve_overview_history_prometheus_url,
)
from app.services.overview_history_rollups import ROLLUP_METRICS


def matrix(*entries):
    return {"status": "success", "data": {"resultType": "matrix", "result": list(entries)}}


def raw_entry(metric, values):
    return {"metric": {"__name__": metric}, "values": values}


def rollup_entry(values):
    return {"metric": {}, "values": values}


def test_plans_one_second_samples_for_the_default_thirty_minute_window():
    plan = plan_overview_history_query(
        end_timestamp_seconds=1_782_000_000,
        window_seconds=1800,
    )
    assert plan.start_timestamp_seconds == 1_781_998_200
    assert plan.end_timestamp_seconds == 1_782_000_000
    assert plan.step_seconds == 1
    assert plan.metric_names == OVERVIEW_HISTORY_METRICS


def test_downsamples_a_longer_window_to_at_most_eighteen_hundred_intervals():
    plan = plan_overview_history_query(
        end_timestamp_seconds=1_782_000_000,
        window_seconds=3600,
    )
    assert plan.step_seconds == 2
    assert plan.metric_names == (
        "starlink_dish_latitude_degrees",
        "starlink_dish_longitude_degrees",
        "starlink_dish_altitude_feet",
        "starlink_dish_speed_knots",
        "starlink_dish_heading_degrees",
        "starlink_network_latency_ms_current",
        "starlink_network_throughput_down_mbps_current",
        "starlink_network_throughput_up_mbps_current",
        "starlink_network_packet_loss_percent",
        "starlink_dish_obstruction_percent",
        "starlink_signal_quality_percent",
    )


def test_allows_the_inclusive_thirty_minute_range_to_return_eighteen_hundred_one_samples():
    plan = plan_overview_history_query(
        end_timestamp_seconds=1_782_000_000,
        window_seconds=1800,
    )
    returned_samples = (
        (plan.end_timestamp_seconds - plan.start_timestamp_seconds) // plan.step_seconds
    ) + 1
    assert MAX_OVERVIEW_HISTORY_SAMPLES == 1801
    assert returned_samples == MAX_OVERVIEW_HISTORY_SAMPLES


def test_builds_one_name_matcher_for_the_entire_overview_metric_allowlist():
    plan = plan_overview_history_query(
        end_timestamp_seconds=1_782_000_000,
        window_seconds=1800,
    )
    assert build_overview_history_promql(plan) == (
        '{__name__=~"'
        "starlink_dish_latitude_degrees|"
        "starlink_dish_longitude_degrees|"
        "starlink_dish_altitude_feet|"
        "starlink_dish_speed_knots|"
        "starlink_dish_heading_degrees|"
        "starlink_network_latency_ms_current|"
        "starlink_network_throughput_down_mbps_current|"
        "starlink_network_throughput_up_mbps_current|"
        "starlink_network_packet_loss_percent|"
        "starlink_dish_obstruction_percent|"
        'starlink_signal_quality_percent"}'
    )


def test_builds_range_query_parameters_from_the_shared_overview_plan():
    plan = plan_overview_history_query(
        end_timestamp_seconds=1_782_000_000,
        window_seconds=1800,
    )
    assert build_overview_history_prometheus_params(plan) == {
        "query": build_overview_history_promql(plan),
        "start": "1781998200",
        "end": "1782000000",
        "step": "1",
    }


@pytest.mark.asyncio
async def test_fetches_the_whole_overview_bundle_with_one_prometheus_range_request():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [],
                },
            },
        )

    plan = plan_overview_history_query(
        end_timestamp_seconds=1_782_000_000,
        window_seconds=1800,
    )
    async with httpx.AsyncClient(
        base_url="http://prometheus:9090",
        transport=httpx.MockTransport(handler),
    ) as client:
        payload = await fetch_overview_history_from_prometheus(client, plan)
    assert payload == {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [],
        },
    }
    assert len(requests) == 1
    assert requests[0].url.path == "/api/v1/query_range"
    assert dict(requests[0].url.params) == build_overview_history_prometheus_params(
        plan
    )


def test_projects_prometheus_matrix_samples_by_metric_name():
    payload = {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {
                        "__name__": "starlink_dish_latitude_degrees",
                    },
                    "values": [
                        [1781999999.0, "41.2565"],
                        [1782000000.0, "41.2566"],
                    ],
                },
                {
                    "metric": {
                        "__name__": "starlink_network_latency_ms_current",
                    },
                    "values": [
                        [1782000000.0, "25.4"],
                    ],
                },
            ],
        },
    }

    assert project_overview_history_matrix(payload) == {
        "starlink_dish_latitude_degrees": [
            [1781999999.0, 41.2565],
            [1782000000.0, 41.2566],
        ],
        "starlink_network_latency_ms_current": [
            [1782000000.0, 25.4],
        ],
    }


@pytest.mark.parametrize("reverse", [False, True])
def test_ambiguous_usable_raw_series_omits_only_that_metric(reverse):
    latitude = [
        raw_entry("starlink_dish_latitude_degrees", [[1782000000, "10"]]),
        raw_entry("starlink_dish_latitude_degrees", [[1782000000, "41.2566"]]),
    ]
    if reverse:
        latitude.reverse()
    plan = plan_overview_history_query(end_timestamp_seconds=1782000000, window_seconds=1800)
    assert project_overview_history_matrix(matrix(
        *latitude,
        raw_entry("starlink_dish_longitude_degrees", [[1782000000, "-95.9345"]]),
    ), plan) == {
        "starlink_dish_longitude_degrees": [[1782000000.0, -95.9345]],
    }


def test_unusable_duplicate_raw_series_does_not_hide_usable_series():
    plan = plan_overview_history_query(end_timestamp_seconds=1782000000, window_seconds=1800)
    assert project_overview_history_matrix(matrix(
        raw_entry("starlink_dish_latitude_degrees", [[1782000000, "nan"]]),
        raw_entry("starlink_dish_latitude_degrees", [[1782000000, "41.2566"]]),
        raw_entry("starlink_dish_latitude_degrees", [[1781998199, "10"]]),
    ), plan) == {
        "starlink_dish_latitude_degrees": [[1782000000.0, 41.2566]],
    }


@pytest.mark.parametrize("reverse", [False, True])
def test_raw_cap_keeps_newest_distinct_in_window_samples_chronologically(reverse):
    plan = plan_overview_history_query(end_timestamp_seconds=1782000000, window_seconds=86400)
    values = [[plan.end_timestamp_seconds - i, str(i)] for i in range(1900)]
    if reverse:
        values.reverse()
    projected = project_overview_history_matrix(matrix(
        raw_entry("starlink_dish_latitude_degrees", values),
    ), plan)["starlink_dish_latitude_degrees"]
    assert len(projected) == MAX_OVERVIEW_HISTORY_SAMPLES
    assert projected[0] == [float(plan.end_timestamp_seconds - 1800), 1800.0]
    assert projected[-1] == [float(plan.end_timestamp_seconds), 0.0]
    assert [point[0] for point in projected] == sorted(point[0] for point in projected)


def test_ignores_unapproved_or_non_finite_prometheus_samples():
    payload = {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {
                        "__name__": "starlink_dish_latitude_degrees",
                    },
                    "values": [
                        [1781999999.0, "nan"],
                        [1781999999.5, "not-a-number"],
                        [1782000000.0, "41.2566"],
                    ],
                },
                {
                    "metric": {
                        "__name__": "unrelated_internal_metric",
                    },
                    "values": [
                        [1782000000.0, "123.4"],
                    ],
                },
            ],
        },
    }
    assert project_overview_history_matrix(payload) == {
        "starlink_dish_latitude_degrees": [
            [1782000000.0, 41.2566],
        ],
    }


def test_rejects_a_failed_prometheus_query_response():
    payload = {
        "status": "error",
        "errorType": "timeout",
        "error": "query timed out",
    }
    with pytest.raises(
        OverviewHistoryPrometheusResponseError,
        match="Prometheus history query failed: query timed out",
    ):
        project_overview_history_matrix(payload)


def test_rejects_a_successful_non_matrix_prometheus_response():
    payload = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [],
        },
    }
    with pytest.raises(
        OverviewHistoryPrometheusResponseError,
        match="Prometheus history query did not return a matrix",
    ):
        project_overview_history_matrix(payload)


@pytest.mark.asyncio
async def test_queries_and_projects_one_bounded_overview_history_bundle():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/query_range"
        if not request.url.params["query"].startswith("{__name__"):
            return httpx.Response(200, json=matrix())
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [
                        {
                            "metric": {
                                "__name__": "starlink_dish_longitude_degrees",
                            },
                            "values": [
                                [1782000000.0, "-95.9345"],
                            ],
                        },
                    ],
                },
            },
        )

    async with httpx.AsyncClient(
        base_url="http://prometheus:9090",
        transport=httpx.MockTransport(handler),
    ) as client:
        bundle = await query_overview_history_bundle(
            client,
            end_timestamp_seconds=1_782_000_000,
            window_seconds=1800,
        )
    assert bundle == {
        "window_seconds": 1800,
        "start_timestamp_seconds": 1_781_998_200,
        "end_timestamp_seconds": 1_782_000_000,
        "step_seconds": 1,
        "series": {
            "starlink_dish_longitude_degrees": [
                [1782000000.0, -95.9345],
            ],
        },
        "rolling_5m": {
            metric: {"state": "available", "min": [], "avg": [], "max": []}
            for metric in ROLLUP_METRICS
        },
    }


@pytest.mark.asyncio
async def test_shares_one_in_flight_bundle_query_for_identical_windows():
    calls = 0
    fetch_started = asyncio.Event()
    release_fetch = asyncio.Event()

    async def fetch_bundle(
        *,
        end_timestamp_seconds: int,
        window_seconds: int,
    ) -> dict:
        nonlocal calls
        calls += 1
        fetch_started.set()
        await release_fetch.wait()
        return {
            "end_timestamp_seconds": end_timestamp_seconds,
            "window_seconds": window_seconds,
        }

    single_flight = OverviewHistoryBundleSingleFlight(fetch_bundle)
    requests = asyncio.gather(
        single_flight.get(
            end_timestamp_seconds=1_782_000_000,
            window_seconds=1800,
        ),
        single_flight.get(
            end_timestamp_seconds=1_782_000_000,
            window_seconds=1800,
        ),
    )
    await fetch_started.wait()
    assert calls == 1
    release_fetch.set()
    first, second = await requests
    assert (
        first
        == second
        == {
            "end_timestamp_seconds": 1_782_000_000,
            "window_seconds": 1800,
        }
    )


def test_resolves_the_prometheus_url_from_environment_or_docker_default(
    monkeypatch,
):
    monkeypatch.delenv("STARLINK_PROMETHEUS_URL", raising=False)
    assert resolve_overview_history_prometheus_url() == "http://prometheus:9090"
    monkeypatch.setenv(
        "STARLINK_PROMETHEUS_URL",
        "http://prometheus-test:9090",
    )
    assert resolve_overview_history_prometheus_url() == "http://prometheus-test:9090"


@pytest.mark.asyncio
async def test_reader_uses_the_selected_window_and_current_time_for_one_bundle():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if not request.url.params["query"].startswith("{__name__"):
            return httpx.Response(200, json=matrix())
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [
                        {
                            "metric": {
                                "__name__": "starlink_dish_latitude_degrees",
                            },
                            "values": [
                                [1782000000.0, "41.2566"],
                            ],
                        },
                    ],
                },
            },
        )

    async with httpx.AsyncClient(
        base_url="http://prometheus:9090",
        transport=httpx.MockTransport(handler),
    ) as client:
        reader = OverviewHistoryReader(
            client,
            get_window_seconds=lambda: 900,
            time_source=lambda: 1_782_000_000.75,
        )
        bundle = await reader.read()
    assert bundle == {
        "window_seconds": 900,
        "start_timestamp_seconds": 1_781_999_100,
        "end_timestamp_seconds": 1_782_000_000,
        "step_seconds": 1,
        "series": {
            "starlink_dish_latitude_degrees": [
                [1782000000.0, 41.2566],
            ],
        },
        "rolling_5m": {
            metric: {"state": "available", "min": [], "avg": [], "max": []}
            for metric in ROLLUP_METRICS
        },
    }
    assert len(requests) == 16
    assert dict(requests[0].url.params) == {
        "query": build_overview_history_promql(
            plan_overview_history_query(
                end_timestamp_seconds=1_782_000_000,
                window_seconds=900,
            )
        ),
        "start": "1781999100",
        "end": "1782000000",
        "step": "1",
    }


@pytest.mark.asyncio
async def test_bundle_preserves_raw_trail_and_exposes_five_rolling_traces():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.params["query"].startswith("{__name__"):
            return httpx.Response(200, json=matrix(
                raw_entry("starlink_dish_latitude_degrees", [[1782000000, "41.2566"]]),
                raw_entry("starlink_dish_longitude_degrees", [[1782000000, "-95.9345"]]),
            ))
        stat = request.url.params["query"].split("_over_time(", 1)[0]
        value = {"min": "24.0", "avg": "25.0", "max": "26.0"}[stat]
        return httpx.Response(200, json=matrix(rollup_entry([[1782000000, value]])))

    async with httpx.AsyncClient(base_url="http://prometheus:9090",
                                 transport=httpx.MockTransport(handler)) as client:
        bundle = await query_overview_history_bundle(
            client, end_timestamp_seconds=1782000000, window_seconds=1800
        )
    assert bundle["series"] == {
        "starlink_dish_latitude_degrees": [[1782000000.0, 41.2566]],
        "starlink_dish_longitude_degrees": [[1782000000.0, -95.9345]],
    }
    assert bundle["rolling_5m"]["starlink_network_latency_ms_current"]["min"] == [[1782000000.0, 24.0]]
    assert bundle["rolling_5m"]["starlink_network_latency_ms_current"]["avg"] == [[1782000000.0, 25.0]]
    assert bundle["rolling_5m"]["starlink_network_latency_ms_current"]["max"] == [[1782000000.0, 26.0]]
    assert bundle["step_seconds"] == plan_overview_history_query(
        end_timestamp_seconds=1782000000, window_seconds=1800
    ).step_seconds
    assert len(requests) == 16


@pytest.mark.asyncio
async def test_custom_window_bounds_all_raw_and_aggregate_traces_in_one_plan():
    plan = plan_overview_history_query(end_timestamp_seconds=1782000000, window_seconds=86400)
    requests = []
    raw_values = [[plan.start_timestamp_seconds + i * plan.step_seconds, "1"]
                  for i in range(2000)]
    raw_values += [[plan.end_timestamp_seconds, "9"], [plan.start_timestamp_seconds, "8"]]

    def handler(request):
        requests.append(request)
        if request.url.params["query"].startswith("{__name__"):
            return httpx.Response(200, json=matrix(*(
                raw_entry(metric, raw_values) for metric in OVERVIEW_HISTORY_METRICS
            )))
        return httpx.Response(200, json=matrix(rollup_entry(raw_values)))

    async with httpx.AsyncClient(base_url="http://prometheus:9090",
                                 transport=httpx.MockTransport(handler)) as client:
        bundle = await query_overview_history_bundle(
            client, end_timestamp_seconds=1782000000, window_seconds=86400
        )
    assert len(requests) == 16
    assert all({key: request.url.params[key] for key in ("start", "end", "step")} == {
        "start": str(plan.start_timestamp_seconds), "end": str(plan.end_timestamp_seconds),
        "step": str(plan.step_seconds),
    } for request in requests)
    traces = list(bundle["series"].values()) + [
        entry[stat] for entry in bundle["rolling_5m"].values()
        for stat in ("min", "avg", "max")
    ]
    assert len(bundle["series"]) == 11
    assert len(traces) == 26
    assert all(len(trace) <= MAX_OVERVIEW_HISTORY_SAMPLES for trace in traces)
    assert sum(map(len, traces)) <= 46_826
    assert all(len({sample[0] for sample in trace}) == len(trace) for trace in traces)
    assert all(plan.start_timestamp_seconds <= sample[0] <= plan.end_timestamp_seconds
               for trace in traces for sample in trace)
    assert bundle["series"]["starlink_dish_latitude_degrees"][0] == [float(plan.start_timestamp_seconds), 1.0]


@pytest.mark.asyncio
async def test_one_aggregate_error_preserves_raw_coordinates_and_isolates_its_metric():
    def handler(request):
        query = request.url.params["query"]
        if query.startswith("{__name__"):
            return httpx.Response(200, json=matrix(
                raw_entry("starlink_dish_latitude_degrees", [[1782000000, "41.2566"]]),
                raw_entry("starlink_dish_longitude_degrees", [[1782000000, "-95.9345"]]),
            ))
        if query == "min_over_time(starlink_network_latency_ms_current[5m])":
            return httpx.Response(503)
        return httpx.Response(200, json=matrix(rollup_entry([[1782000000, "24"]])))

    async with httpx.AsyncClient(base_url="http://prometheus:9090",
                                 transport=httpx.MockTransport(handler)) as client:
        bundle = await query_overview_history_bundle(
            client, end_timestamp_seconds=1782000000, window_seconds=1800
        )
    assert bundle["series"] == {
        "starlink_dish_latitude_degrees": [[1782000000.0, 41.2566]],
        "starlink_dish_longitude_degrees": [[1782000000.0, -95.9345]],
    }
    assert bundle["rolling_5m"]["starlink_network_latency_ms_current"] == {
        "state": "unavailable", "min": [], "avg": [], "max": [],
    }
    assert all(bundle["rolling_5m"][metric]["state"] == "available"
               for metric in ROLLUP_METRICS if metric != "starlink_network_latency_ms_current")


@pytest.mark.asyncio
async def test_raw_http_error_propagates_without_querying_aggregates():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(503)

    async with httpx.AsyncClient(base_url="http://prometheus:9090",
                                 transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await query_overview_history_bundle(
                client, end_timestamp_seconds=1782000000, window_seconds=1800
            )
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_reader_coalesces_identical_reads_through_aggregate_queries():
    requests = []
    aggregate_started = asyncio.Event()
    release_aggregate = asyncio.Event()

    async def handler(request):
        requests.append(request)
        if request.url.params["query"].startswith("{__name__"):
            return httpx.Response(200, json=matrix())
        aggregate_started.set()
        await release_aggregate.wait()
        return httpx.Response(200, json=matrix())

    async with httpx.AsyncClient(base_url="http://prometheus:9090",
                                 transport=httpx.MockTransport(handler)) as client:
        reader = OverviewHistoryReader(client, get_window_seconds=lambda: 1800,
                                       time_source=lambda: 1782000000.5)
        first = asyncio.create_task(reader.read())
        await aggregate_started.wait()
        second = asyncio.create_task(reader.read())
        await asyncio.sleep(0)
        release_aggregate.set()
        a, b = await asyncio.gather(first, second)
    assert a is b
    assert len(requests) == 16
