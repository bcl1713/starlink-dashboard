import httpx
import pytest

from app.services.overview_history_prometheus import (
    MAX_OVERVIEW_HISTORY_SAMPLES,
    OVERVIEW_HISTORY_METRICS,
    build_overview_history_prometheus_params,
    build_overview_history_promql,
    fetch_overview_history_from_prometheus,
    plan_overview_history_query,
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
