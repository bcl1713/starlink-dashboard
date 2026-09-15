from app.services.overview_history_prometheus import (
    OVERVIEW_HISTORY_METRICS,
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


def test_downsamples_a_longer_window_to_at_most_eighteen_hundred_samples():
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
