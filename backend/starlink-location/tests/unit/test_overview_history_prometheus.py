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
    }
    assert len(requests) == 1
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
