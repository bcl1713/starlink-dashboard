"""Prometheus metrics registry and definitions."""

# FR-004: File exceeds 300 lines (451 lines) because metrics registry defines
# 40+ metric instances with type-specific exports (gauges, counters, histograms)
# and accessor functions. Splitting would fragment metric definitions reducing
# discoverability. Deferred to v0.4.0.

import logging
from typing import Dict, Generator

from prometheus_client import (
    Gauge,
    Counter,
    Histogram,
    CollectorRegistry,
)
from prometheus_client.core import GaugeMetricFamily

logger = logging.getLogger(__name__)

# Create a dedicated registry for our metrics
REGISTRY: CollectorRegistry = CollectorRegistry()

# Current position data for custom collector
# This is updated by metric_updater functions and read by PositionCollector
_current_position: Dict[str, float] = {
    "latitude": 0.0,
    "longitude": 0.0,
    "altitude": 0.0,
}


class PositionCollector:
    """Custom collector that exports position as a single metric with all values.

    This collector is registered with Prometheus and yields a GaugeMetricFamily
    containing the current aircraft position with three dimensions (latitude,
    longitude, altitude). The position data is read from the module-level
    _current_position dictionary which is updated by metric_updater functions.
    """

    def collect(self) -> Generator[GaugeMetricFamily, None, None]:
        """Collect and yield position metrics for Prometheus scraping.

        Returns:
            Generator[GaugeMetricFamily, None, None]: A generator yielding a single
                GaugeMetricFamily with position data labeled by dimension.
        """
        # Create a gauge metric with the position data
        position_metric = GaugeMetricFamily(
            "starlink_aircraft_position",
            "Current aircraft position with latitude, longitude, and altitude",
            labels=["dimension"],
        )

        position_metric.add_metric(["latitude"], _current_position["latitude"])
        position_metric.add_metric(["longitude"], _current_position["longitude"])
        position_metric.add_metric(["altitude"], _current_position["altitude"])

        yield position_metric


# Register the custom collector
REGISTRY.register(PositionCollector())

# ============================================================================
# Position metrics
# ============================================================================
# Composite location metric for Grafana geomap compatibility
# This single metric with latitude/longitude as labels is what Grafana
# expects for rendering geographic positions
starlink_device_location = Gauge(
    "starlink_device_location",
    "Device location with latitude and longitude as labels",
    labelnames=["lat", "lon", "altitude"],
    registry=REGISTRY,
)

starlink_dish_latitude_degrees = Gauge(
    "starlink_dish_latitude_degrees",
    "Dish latitude in decimal degrees",
    registry=REGISTRY,
)

starlink_dish_longitude_degrees = Gauge(
    "starlink_dish_longitude_degrees",
    "Dish longitude in decimal degrees",
    registry=REGISTRY,
)

starlink_dish_altitude_feet = Gauge(
    "starlink_dish_altitude_feet",
    "Dish altitude in feet above sea level",
    registry=REGISTRY,
)

starlink_dish_speed_knots = Gauge(
    "starlink_dish_speed_knots", "Dish speed in knots", registry=REGISTRY
)

starlink_dish_heading_degrees = Gauge(
    "starlink_dish_heading_degrees",
    "Dish heading in degrees (0=North, 90=East)",
    registry=REGISTRY,
)

# ============================================================================
# Network metrics - Current values (Gauges)
# ============================================================================
starlink_network_latency_ms_current = Gauge(
    "starlink_network_latency_ms_current",
    "Network round-trip latency in milliseconds (current value)",
    registry=REGISTRY,
)

starlink_network_throughput_down_mbps_current = Gauge(
    "starlink_network_throughput_down_mbps_current",
    "Download throughput in Megabits per second (current value)",
    registry=REGISTRY,
)

starlink_network_throughput_up_mbps_current = Gauge(
    "starlink_network_throughput_up_mbps_current",
    "Upload throughput in Megabits per second (current value)",
    registry=REGISTRY,
)

starlink_network_packet_loss_percent = Gauge(
    "starlink_network_packet_loss_percent",
    "Packet loss as percentage (0-100)",
    registry=REGISTRY,
)

# ============================================================================
# Network metrics - Histograms for percentile analysis
# ============================================================================
# Latency histogram: buckets chosen to capture Starlink typical performance
# Starlink latency typically ranges 25-150ms (median ~50ms)
# Buckets: 20, 40, 60, 80, 100, 150, 200, 500 capture low/normal/degraded/poor ranges
starlink_network_latency_ms = Histogram(
    "starlink_network_latency_ms",
    "Network round-trip latency in milliseconds (histogram for percentile analysis)",
    labelnames=["mode", "status"],
    buckets=[20, 40, 60, 80, 100, 150, 200, 500],
    registry=REGISTRY,
)

# Download throughput histogram: buckets for typical Starlink speeds
# Starlink download typically 50-300 Mbps depending on conditions
# Buckets: 50, 100, 150, 200, 250, 300 capture performance ranges
starlink_network_throughput_down_mbps = Histogram(
    "starlink_network_throughput_down_mbps",
    "Download throughput in Megabits per second (histogram for percentile analysis)",
    labelnames=["mode", "status"],
    buckets=[50, 100, 150, 200, 250, 300],
    registry=REGISTRY,
)

# Upload throughput histogram: buckets for typical Starlink upload speeds
# Starlink upload typically 10-50 Mbps depending on conditions
# Buckets: 10, 20, 30, 40, 50 capture the typical performance range
starlink_network_throughput_up_mbps = Histogram(
    "starlink_network_throughput_up_mbps",
    "Upload throughput in Megabits per second (histogram for percentile analysis)",
    labelnames=["mode", "status"],
    buckets=[10, 20, 30, 40, 50],
    registry=REGISTRY,
)

# ============================================================================
# Obstruction and signal metrics
# ============================================================================
starlink_dish_obstruction_percent = Gauge(
    "starlink_dish_obstruction_percent",
    "Dish obstruction as percentage (0-100)",
    registry=REGISTRY,
)

starlink_signal_quality_percent = Gauge(
    "starlink_signal_quality_percent",
    "Signal quality as percentage (0-100)",
    registry=REGISTRY,
)

# ============================================================================
# Status metrics
# ============================================================================
starlink_service_info = Gauge(
    "starlink_service_info",
    "Starlink service information",
    ["version", "mode"],
    registry=REGISTRY,
)

starlink_mode_info = Gauge(
    "starlink_mode_info",
    "Starlink operating mode indicator",
    labelnames=["mode"],
    registry=REGISTRY,
)

starlink_uptime_seconds = Gauge(
    "starlink_uptime_seconds", "Service uptime in seconds", registry=REGISTRY
)

starlink_dish_uptime_seconds = Gauge(
    "starlink_dish_uptime_seconds", "Dish uptime in seconds", registry=REGISTRY
)

starlink_dish_thermal_throttle = Gauge(
    "starlink_dish_thermal_throttle",
    "Dish thermal throttle state (0=normal, 1=throttled)",
    registry=REGISTRY,
)

starlink_dish_outage_active = Gauge(
    "starlink_dish_outage_active",
    "Dish outage state (0=connected, 1=outage)",
    registry=REGISTRY,
)

# ============================================================================
# Event counters
# ============================================================================
starlink_connection_attempts_total = Counter(
    "starlink_connection_attempts_total",
    "Total number of connection attempts",
    registry=REGISTRY,
)

starlink_connection_failures_total = Counter(
    "starlink_connection_failures_total",
    "Total number of failed connection attempts",
    registry=REGISTRY,
)

starlink_outage_events_total = Counter(
    "starlink_outage_events_total", "Total number of outage events", registry=REGISTRY
)

starlink_thermal_events_total = Counter(
    "starlink_thermal_events_total",
    "Total number of thermal throttle events",
    registry=REGISTRY,
)

# ============================================================================
# POI and ETA metrics
# ============================================================================
starlink_eta_poi_seconds = Gauge(
    "starlink_eta_poi_seconds",
    "Estimated time of arrival to point of interest in seconds (anticipated or estimated)",
    labelnames=["name", "category", "eta_type"],
    registry=REGISTRY,
)

starlink_distance_to_poi_meters = Gauge(
    "starlink_distance_to_poi_meters",
    "Distance to point of interest in meters",
    labelnames=["name", "category", "eta_type"],
    registry=REGISTRY,
)

# ============================================================================
# Flight Status metrics (Phase 0 - ETA Timing Modes)
# ============================================================================
starlink_flight_phase = Gauge(
    "starlink_flight_phase",
    "Current flight phase (0=pre_departure, 1=in_flight, 2=post_arrival)",
    registry=REGISTRY,
)

starlink_eta_mode = Gauge(
    "starlink_eta_mode",
    "Current ETA calculation mode (0=anticipated, 1=estimated)",
    registry=REGISTRY,
)

starlink_flight_departure_time_unix = Gauge(
    "starlink_flight_departure_time_unix",
    "Detected departure time (Unix timestamp), 0 if not yet departed",
    registry=REGISTRY,
)

starlink_flight_arrival_time_unix = Gauge(
    "starlink_flight_arrival_time_unix",
    "Detected arrival time (Unix timestamp), 0 if not yet arrived",
    registry=REGISTRY,
)

starlink_time_until_departure_seconds = Gauge(
    "starlink_time_until_departure_seconds",
    "Seconds remaining until scheduled or detected departure (0 once departed, negative if scheduled time is in the past and departure not detected)",
    registry=REGISTRY,
)

# ============================================================================
# Route following metrics (Phase 5 - Simulation mode route following)
# ============================================================================
starlink_route_progress_percent = Gauge(
    "starlink_route_progress_percent",
    "Current progress along active KML route (0-100%)",
    labelnames=["route_name"],
    registry=REGISTRY,
)

starlink_current_waypoint_index = Gauge(
    "starlink_current_waypoint_index",
    "Index of current waypoint in active route (0-indexed)",
    labelnames=["route_name"],
    registry=REGISTRY,
)

# ============================================================================
# Route timing metrics (Phase 3 - ETA Route Timing)
# ============================================================================
starlink_route_has_timing_data = Gauge(
    "starlink_route_has_timing_data",
    "Binary flag indicating if route has embedded timing data (1=has timing, 0=no timing)",
    labelnames=["route_name"],
    registry=REGISTRY,
)

starlink_route_total_duration_seconds = Gauge(
    "starlink_route_total_duration_seconds",
    "Expected total flight duration for active route in seconds",
    labelnames=["route_name"],
    registry=REGISTRY,
)

starlink_route_departure_time_unix = Gauge(
    "starlink_route_departure_time_unix",
    "Expected departure time for active route (Unix timestamp)",
    labelnames=["route_name"],
    registry=REGISTRY,
)

starlink_route_arrival_time_unix = Gauge(
    "starlink_route_arrival_time_unix",
    "Expected arrival time for active route (Unix timestamp)",
    labelnames=["route_name"],
    registry=REGISTRY,
)

starlink_route_segment_count_with_timing = Gauge(
    "starlink_route_segment_count_with_timing",
    "Number of route segments with calculated expected speeds",
    labelnames=["route_name"],
    registry=REGISTRY,
)

starlink_eta_to_waypoint_seconds = Gauge(
    "starlink_eta_to_waypoint_seconds",
    "Estimated time to arrival at specific waypoint in seconds",
    labelnames=["route_name", "waypoint_name"],
    registry=REGISTRY,
)

starlink_distance_to_waypoint_meters = Gauge(
    "starlink_distance_to_waypoint_meters",
    "Distance to specific waypoint in meters",
    labelnames=["route_name", "waypoint_name"],
    registry=REGISTRY,
)

starlink_route_segment_speed_knots = Gauge(
    "starlink_route_segment_speed_knots",
    "Expected speed for route segment in knots",
    labelnames=["route_name", "segment_index"],
    registry=REGISTRY,
)

# ============================================================================
# Meta-metrics for monitoring the monitoring system
# ============================================================================
starlink_metrics_scrape_duration_seconds = Histogram(
    "starlink_metrics_scrape_duration_seconds",
    "Time spent collecting metrics in seconds",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
    registry=REGISTRY,
)

starlink_metrics_generation_errors_total = Counter(
    "starlink_metrics_generation_errors_total",
    "Total number of metric generation errors",
    registry=REGISTRY,
)

starlink_metrics_last_update_timestamp_seconds = Gauge(
    "starlink_metrics_last_update_timestamp_seconds",
    "Timestamp of last successful metric update (Unix epoch)",
    registry=REGISTRY,
)

# ============================================================================
# Mission planning metrics (Phase 1 Continuation)
# ============================================================================
mission_active_info = Gauge(
    "mission_active_info",
    "Currently active mission information (1 when active, 0 when not)",
    labelnames=["mission_id", "route_id"],
    registry=REGISTRY,
)

mission_phase_state = Gauge(
    "mission_phase_state",
    "Current mission phase state (0=pre_departure, 1=in_flight, 2=post_arrival)",
    labelnames=["mission_id"],
    registry=REGISTRY,
)

mission_next_conflict_seconds = Gauge(
    "mission_next_conflict_seconds",
    "Seconds until next degraded/critical event in mission timeline (-1 if none)",
    labelnames=["mission_id"],
    registry=REGISTRY,
)

mission_timeline_generated_timestamp = Gauge(
    "mission_timeline_generated_timestamp",
    "Unix timestamp of last mission timeline computation",
    labelnames=["mission_id"],
    registry=REGISTRY,
)

mission_comm_state = Gauge(
    "mission_comm_state",
    "Planned state per transport (0=available, 1=degraded, 2=offline)",
    labelnames=["mission_id", "transport"],
    registry=REGISTRY,
)

mission_degraded_seconds = Gauge(
    "mission_degraded_seconds",
    "Planned degraded duration for mission timeline (seconds)",
    labelnames=["mission_id"],
    registry=REGISTRY,
)

mission_critical_seconds = Gauge(
    "mission_critical_seconds",
    "Planned critical duration for mission timeline (seconds)",
    labelnames=["mission_id"],
    registry=REGISTRY,
)

# ============================================================================
# Simulation metrics (only in simulation mode)
# ============================================================================
simulation_updates_total = Counter(
    "simulation_updates_total", "Total number of simulation updates", registry=REGISTRY
)

simulation_errors_total = Counter(
    "simulation_errors_total", "Total number of simulation errors", registry=REGISTRY
)
