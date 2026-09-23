"""Regression coverage for legacy compatibility re-export modules."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from app.core import metrics as metrics_target
from app.services import route_eta as route_eta_target

METRICS_EXPORTS = (
    "REGISTRY",
    "_current_position",
    "clear_mission_metrics",
    "clear_telemetry_metrics",
    "mission_active_info",
    "mission_comm_state",
    "mission_critical_seconds",
    "mission_degraded_seconds",
    "mission_next_conflict_seconds",
    "mission_phase_state",
    "mission_timeline_generated_timestamp",
    "set_service_info",
    "simulation_errors_total",
    "simulation_updates_total",
    "starlink_connection_attempts_total",
    "starlink_connection_failures_total",
    "starlink_current_waypoint_index",
    "starlink_device_location",
    "starlink_dish_altitude_feet",
    "starlink_dish_heading_degrees",
    "starlink_dish_latitude_degrees",
    "starlink_dish_longitude_degrees",
    "starlink_dish_obstruction_percent",
    "starlink_dish_outage_active",
    "starlink_dish_speed_knots",
    "starlink_dish_thermal_throttle",
    "starlink_dish_uptime_seconds",
    "starlink_distance_to_poi_meters",
    "starlink_distance_to_waypoint_meters",
    "starlink_eta_mode",
    "starlink_eta_poi_seconds",
    "starlink_eta_to_waypoint_seconds",
    "starlink_flight_arrival_time_unix",
    "starlink_flight_departure_time_unix",
    "starlink_flight_phase",
    "starlink_ground_entry_point_info",
    "starlink_ground_entry_point_latitude_degrees",
    "starlink_ground_entry_point_location",
    "starlink_ground_entry_point_longitude_degrees",
    "starlink_metrics_generation_errors_total",
    "starlink_metrics_last_update_timestamp_seconds",
    "starlink_metrics_scrape_duration_seconds",
    "starlink_mode_info",
    "starlink_network_latency_ms",
    "starlink_network_latency_ms_current",
    "starlink_network_packet_loss_percent",
    "starlink_network_throughput_down_mbps",
    "starlink_network_throughput_down_mbps_current",
    "starlink_network_throughput_up_mbps",
    "starlink_network_throughput_up_mbps_current",
    "starlink_outage_events_total",
    "starlink_route_arrival_time_unix",
    "starlink_route_departure_time_unix",
    "starlink_route_has_timing_data",
    "starlink_route_progress_percent",
    "starlink_route_segment_count_with_timing",
    "starlink_route_segment_speed_knots",
    "starlink_route_total_duration_seconds",
    "starlink_service_info",
    "starlink_signal_quality_percent",
    "starlink_thermal_events_total",
    "starlink_time_until_departure_seconds",
    "starlink_uptime_seconds",
    "update_metrics_from_telemetry",
    "update_mission_active_metric",
    "update_mission_comm_state_metric",
    "update_mission_duration_metrics",
    "update_mission_next_conflict_metric",
    "update_mission_phase_metric",
    "update_mission_timeline_timestamp",
)

ROUTE_ETA_EXPORTS = (
    "RouteETACalculator",
    "cleanup_eta_cache",
    "clear_eta_cache",
    "get_eta_accuracy_stats",
    "get_eta_cache_stats",
    "project_point_to_line_segment",
)


def _load_legacy_module(module_name: str, relative_path: str) -> ModuleType:
    """Load a legacy module file whose path is shadowed by its replacement package."""
    path = Path(__file__).resolve().parents[2] / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_compatibility_contract(
    legacy_module: ModuleType,
    target_module: ModuleType,
    expected_exports: tuple[str, ...],
) -> None:
    assert tuple(target_module.__all__) == expected_exports
    assert tuple(legacy_module.__all__) == expected_exports
    for export_name in expected_exports:
        assert getattr(legacy_module, export_name) is getattr(
            target_module, export_name
        )


def test_legacy_metrics_module_preserves_all_public_exports_by_identity():
    """The legacy metrics module must retain the documented 70-name contract."""
    legacy_metrics = _load_legacy_module(
        "legacy_metrics_compatibility_test", "app/core/metrics.py"
    )

    _assert_compatibility_contract(legacy_metrics, metrics_target, METRICS_EXPORTS)


def test_legacy_route_eta_calculator_preserves_all_public_exports_by_identity():
    """The legacy route-ETA module must retain its six-name contract."""
    legacy_route_eta = _load_legacy_module(
        "legacy_route_eta_compatibility_test", "app/services/route_eta_calculator.py"
    )

    _assert_compatibility_contract(
        legacy_route_eta, route_eta_target, ROUTE_ETA_EXPORTS
    )


def test_compatibility_contract_rejects_wrong_export_identity():
    """The characterization fails if a legacy export stops aliasing its target."""
    legacy_metrics = _load_legacy_module(
        "legacy_metrics_identity_sabotage_test", "app/core/metrics.py"
    )
    setattr(legacy_metrics, "REGISTRY", object())

    with pytest.raises(AssertionError):
        _assert_compatibility_contract(legacy_metrics, metrics_target, METRICS_EXPORTS)


def test_compatibility_contract_rejects_wrong_export_order():
    """The characterization fails if a legacy module changes its public order."""
    legacy_route_eta = _load_legacy_module(
        "legacy_route_eta_order_sabotage_test", "app/services/route_eta_calculator.py"
    )
    setattr(legacy_route_eta, "__all__", tuple(reversed(ROUTE_ETA_EXPORTS)))

    with pytest.raises(AssertionError):
        _assert_compatibility_contract(
            legacy_route_eta, route_eta_target, ROUTE_ETA_EXPORTS
        )
