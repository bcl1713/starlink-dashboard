"""Metrics module - Prometheus metrics registry and update functions."""

# Export REGISTRY for main.py
# Export update functions
from app.core.metrics.metric_updater import (
    clear_mission_metrics,
    clear_telemetry_metrics,
    set_service_info,
    update_metrics_from_telemetry,
    update_mission_active_metric,
    update_mission_comm_state_metric,
    update_mission_duration_metrics,
    update_mission_next_conflict_metric,
    update_mission_phase_metric,
    update_mission_timeline_timestamp,
)

# Export all metric objects for use in other modules
from app.core.metrics.prometheus_metrics import (
    REGISTRY,
    _current_position,
    # Mission planning metrics
    mission_active_info,
    mission_comm_state,
    mission_critical_seconds,
    mission_degraded_seconds,
    mission_next_conflict_seconds,
    mission_phase_state,
    mission_timeline_generated_timestamp,
    simulation_errors_total,
    # Simulation metrics
    simulation_updates_total,
    # Event counters
    starlink_connection_attempts_total,
    starlink_connection_failures_total,
    starlink_current_waypoint_index,
    # Position metrics
    starlink_device_location,
    starlink_dish_altitude_feet,
    starlink_dish_heading_degrees,
    starlink_dish_latitude_degrees,
    starlink_dish_longitude_degrees,
    # Obstruction and signal
    starlink_dish_obstruction_percent,
    starlink_dish_outage_active,
    starlink_dish_speed_knots,
    starlink_dish_thermal_throttle,
    starlink_dish_uptime_seconds,
    starlink_distance_to_poi_meters,
    starlink_distance_to_waypoint_meters,
    starlink_eta_mode,
    # POI and ETA metrics
    starlink_eta_poi_seconds,
    starlink_eta_to_waypoint_seconds,
    starlink_flight_arrival_time_unix,
    starlink_flight_departure_time_unix,
    # Flight Status metrics
    starlink_flight_phase,
    starlink_ground_entry_point_info,
    starlink_ground_entry_point_latitude_degrees,
    starlink_ground_entry_point_location,
    starlink_ground_entry_point_longitude_degrees,
    starlink_metrics_generation_errors_total,
    starlink_metrics_last_update_timestamp_seconds,
    # Meta-metrics
    starlink_metrics_scrape_duration_seconds,
    starlink_mode_info,
    # Network metrics - Histograms
    starlink_network_latency_ms,
    # Network metrics - Current values
    starlink_network_latency_ms_current,
    starlink_network_packet_loss_percent,
    starlink_network_throughput_down_mbps,
    starlink_network_throughput_down_mbps_current,
    starlink_network_throughput_up_mbps,
    starlink_network_throughput_up_mbps_current,
    starlink_outage_events_total,
    starlink_route_arrival_time_unix,
    starlink_route_departure_time_unix,
    # Route timing metrics
    starlink_route_has_timing_data,
    # Route following metrics
    starlink_route_progress_percent,
    starlink_route_segment_count_with_timing,
    starlink_route_segment_speed_knots,
    starlink_route_total_duration_seconds,
    # Status metrics
    starlink_service_info,
    starlink_signal_quality_percent,
    starlink_thermal_events_total,
    starlink_time_until_departure_seconds,
    starlink_uptime_seconds,
)

__all__ = [
    "REGISTRY",
    "_current_position",
    "clear_mission_metrics",
    "clear_telemetry_metrics",
    # Mission planning metrics
    "mission_active_info",
    "mission_comm_state",
    "mission_critical_seconds",
    "mission_degraded_seconds",
    "mission_next_conflict_seconds",
    "mission_phase_state",
    "mission_timeline_generated_timestamp",
    "set_service_info",
    "simulation_errors_total",
    # Simulation metrics
    "simulation_updates_total",
    # Event counters
    "starlink_connection_attempts_total",
    "starlink_connection_failures_total",
    "starlink_current_waypoint_index",
    # Position metrics
    "starlink_device_location",
    "starlink_dish_altitude_feet",
    "starlink_dish_heading_degrees",
    "starlink_dish_latitude_degrees",
    "starlink_dish_longitude_degrees",
    # Obstruction and signal
    "starlink_dish_obstruction_percent",
    "starlink_dish_outage_active",
    "starlink_dish_speed_knots",
    "starlink_dish_thermal_throttle",
    "starlink_dish_uptime_seconds",
    "starlink_distance_to_poi_meters",
    "starlink_distance_to_waypoint_meters",
    "starlink_eta_mode",
    # POI and ETA metrics
    "starlink_eta_poi_seconds",
    "starlink_eta_to_waypoint_seconds",
    "starlink_flight_arrival_time_unix",
    "starlink_flight_departure_time_unix",
    # Flight Status metrics
    "starlink_flight_phase",
    "starlink_ground_entry_point_info",
    "starlink_ground_entry_point_latitude_degrees",
    "starlink_ground_entry_point_location",
    "starlink_ground_entry_point_longitude_degrees",
    "starlink_metrics_generation_errors_total",
    "starlink_metrics_last_update_timestamp_seconds",
    # Meta-metrics
    "starlink_metrics_scrape_duration_seconds",
    "starlink_mode_info",
    # Network metrics - Histograms
    "starlink_network_latency_ms",
    # Network metrics - Current values
    "starlink_network_latency_ms_current",
    "starlink_network_packet_loss_percent",
    "starlink_network_throughput_down_mbps",
    "starlink_network_throughput_down_mbps_current",
    "starlink_network_throughput_up_mbps",
    "starlink_network_throughput_up_mbps_current",
    "starlink_outage_events_total",
    "starlink_route_arrival_time_unix",
    "starlink_route_departure_time_unix",
    # Route timing metrics
    "starlink_route_has_timing_data",
    # Route following metrics
    "starlink_route_progress_percent",
    "starlink_route_segment_count_with_timing",
    "starlink_route_segment_speed_knots",
    "starlink_route_total_duration_seconds",
    # Status metrics
    "starlink_service_info",
    "starlink_signal_quality_percent",
    "starlink_thermal_events_total",
    "starlink_time_until_departure_seconds",
    "starlink_uptime_seconds",
    # Update functions
    "update_metrics_from_telemetry",
    "update_mission_active_metric",
    "update_mission_comm_state_metric",
    "update_mission_duration_metrics",
    "update_mission_next_conflict_metric",
    "update_mission_phase_metric",
    "update_mission_timeline_timestamp",
]
