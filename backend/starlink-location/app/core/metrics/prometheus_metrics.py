"""Prometheus metrics registry and definitions."""

# FR-004: File exceeds 300 lines (451 lines) because metrics registry defines
# 40+ metric instances with type-specific exports (gauges, counters, histograms)
# and accessor functions. Splitting would fragment metric definitions reducing
# discoverability. Deferred to v0.4.0.

import logging
from collections.abc import Mapping

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
)

from app.core.metrics.frames import (
    FrameGaugeView,
    FrameStore,
    GaugeDefinition,
    TelemetryFrameCollector,
)

logger = logging.getLogger(__name__)

# Create a dedicated registry for our metrics
REGISTRY: CollectorRegistry = CollectorRegistry()

COUPLED_SCHEMA = (
    GaugeDefinition(
        "starlink_dish_latitude_degrees", "Dish latitude in decimal degrees", ()
    ),
    GaugeDefinition(
        "starlink_dish_longitude_degrees", "Dish longitude in decimal degrees", ()
    ),
    GaugeDefinition(
        "starlink_dish_altitude_feet", "Dish altitude in feet above sea level", ()
    ),
    GaugeDefinition("starlink_dish_speed_knots", "Dish speed in knots", ()),
    GaugeDefinition(
        "starlink_dish_heading_degrees",
        "Dish heading in degrees (0=North, 90=East)",
        (),
    ),
    GaugeDefinition(
        "starlink_network_latency_ms_current",
        "Network round-trip latency in milliseconds (current value)",
        (),
    ),
    GaugeDefinition(
        "starlink_network_throughput_down_mbps_current",
        "Download throughput in Megabits per second (current value)",
        (),
    ),
    GaugeDefinition(
        "starlink_network_throughput_up_mbps_current",
        "Upload throughput in Megabits per second (current value)",
        (),
    ),
    GaugeDefinition(
        "starlink_network_packet_loss_percent", "Packet loss as percentage (0-100)", ()
    ),
    GaugeDefinition(
        "starlink_dish_obstruction_percent",
        "Dish obstruction as percentage (0-100)",
        (),
    ),
    GaugeDefinition(
        "starlink_signal_quality_percent", "Signal quality as percentage (0-100)", ()
    ),
    GaugeDefinition(
        "starlink_service_info", "Starlink service information", ("version", "mode")
    ),
    GaugeDefinition(
        "starlink_mode_info", "Starlink operating mode indicator", ("mode",)
    ),
    GaugeDefinition("starlink_uptime_seconds", "Service uptime in seconds", ()),
    GaugeDefinition(
        "starlink_eta_poi_seconds",
        "Estimated time of arrival to point of interest in seconds (anticipated or estimated)",
        ("name", "category", "eta_type"),
    ),
    GaugeDefinition(
        "starlink_distance_to_poi_meters",
        "Distance to point of interest in meters",
        ("name", "category", "eta_type"),
    ),
    GaugeDefinition(
        "starlink_flight_phase",
        "Current flight phase (0=pre_departure, 1=in_flight, 2=post_arrival)",
        (),
    ),
    GaugeDefinition(
        "starlink_eta_mode",
        "Current ETA calculation mode (0=anticipated, 1=estimated)",
        (),
    ),
    GaugeDefinition(
        "starlink_flight_departure_time_unix",
        "Detected departure time (Unix timestamp), 0 if not yet departed",
        (),
    ),
    GaugeDefinition(
        "starlink_flight_arrival_time_unix",
        "Detected arrival time (Unix timestamp), 0 if not yet arrived",
        (),
    ),
    GaugeDefinition(
        "starlink_time_until_departure_seconds",
        "Seconds remaining until scheduled or detected departure (0 once departed, negative if scheduled time is in the past and departure not detected)",
        (),
    ),
    GaugeDefinition(
        "starlink_route_progress_percent",
        "Current progress along active KML route (0-100%)",
        ("route_name",),
    ),
    GaugeDefinition(
        "starlink_current_waypoint_index",
        "Index of current waypoint in active route (0-indexed)",
        ("route_name",),
    ),
    GaugeDefinition(
        "starlink_route_has_timing_data",
        "Binary flag indicating if route has embedded timing data (1=has timing, 0=no timing)",
        ("route_name",),
    ),
    GaugeDefinition(
        "starlink_route_total_duration_seconds",
        "Expected total flight duration for active route in seconds",
        ("route_name",),
    ),
    GaugeDefinition(
        "starlink_route_departure_time_unix",
        "Expected departure time for active route (Unix timestamp)",
        ("route_name",),
    ),
    GaugeDefinition(
        "starlink_route_arrival_time_unix",
        "Expected arrival time for active route (Unix timestamp)",
        ("route_name",),
    ),
    GaugeDefinition(
        "starlink_route_segment_count_with_timing",
        "Number of route segments with calculated expected speeds",
        ("route_name",),
    ),
    GaugeDefinition(
        "starlink_metrics_last_update_timestamp_seconds",
        "Timestamp of last successful metric update (Unix epoch)",
        (),
    ),
)
FRAME_STORE = FrameStore(COUPLED_SCHEMA)
(
    starlink_dish_latitude_degrees,
    starlink_dish_longitude_degrees,
    starlink_dish_altitude_feet,
    starlink_dish_speed_knots,
    starlink_dish_heading_degrees,
    starlink_network_latency_ms_current,
    starlink_network_throughput_down_mbps_current,
    starlink_network_throughput_up_mbps_current,
    starlink_network_packet_loss_percent,
    starlink_dish_obstruction_percent,
    starlink_signal_quality_percent,
    starlink_service_info,
    starlink_mode_info,
    starlink_uptime_seconds,
    starlink_eta_poi_seconds,
    starlink_distance_to_poi_meters,
    starlink_flight_phase,
    starlink_eta_mode,
    starlink_flight_departure_time_unix,
    starlink_flight_arrival_time_unix,
    starlink_time_until_departure_seconds,
    starlink_route_progress_percent,
    starlink_current_waypoint_index,
    starlink_route_has_timing_data,
    starlink_route_total_duration_seconds,
    starlink_route_departure_time_unix,
    starlink_route_arrival_time_unix,
    starlink_route_segment_count_with_timing,
    starlink_metrics_last_update_timestamp_seconds,
) = tuple(FrameGaugeView(FRAME_STORE, definition) for definition in COUPLED_SCHEMA)


class _PositionView(Mapping):
    """Read-only compatibility mapping; snapshot captures all dimensions once."""

    def snapshot(self):
        state = FRAME_STORE.read()
        indices = {
            definition.name: index for index, definition in enumerate(COUPLED_SCHEMA)
        }
        return {
            dimension: (
                state.frame.families[indices[name]][0][1]
                if state.frame is not None and state.status == "ready"
                else float("nan")
            )
            for dimension, name in (
                ("latitude", "starlink_dish_latitude_degrees"),
                ("longitude", "starlink_dish_longitude_degrees"),
                ("altitude", "starlink_dish_altitude_feet"),
            )
        }

    def __getitem__(self, key):
        return self.snapshot()[key]

    def __iter__(self):
        return iter(("latitude", "longitude", "altitude"))

    def __len__(self):
        return 3


_current_position = _PositionView()
_FRAME_COLLECTOR = TelemetryFrameCollector(FRAME_STORE, COUPLED_SCHEMA)


class PositionCollector:
    """Compatibility read view; the registered full collector emits this alias."""

    def collect(self):
        for family in _FRAME_COLLECTOR.collect():
            if family.name == "starlink_aircraft_position":
                yield family


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


# ============================================================================
# Network metrics - Current values (Gauges)
# ============================================================================


starlink_ground_entry_point_latitude_degrees = Gauge(
    "starlink_ground_entry_point_latitude_degrees",
    "Ground entry point latitude in decimal degrees",
    registry=REGISTRY,
)

starlink_ground_entry_point_longitude_degrees = Gauge(
    "starlink_ground_entry_point_longitude_degrees",
    "Ground entry point longitude in decimal degrees",
    registry=REGISTRY,
)

starlink_ground_entry_point_location = Gauge(
    "starlink_ground_entry_point_location",
    "Ground entry point location with labels for Grafana geomap display",
    labelnames=["lat", "lon", "city", "region", "country", "ip", "display"],
    registry=REGISTRY,
)

starlink_ground_entry_point_info = Gauge(
    "starlink_ground_entry_point_info",
    "Ground entry point identity information",
    labelnames=["city", "region", "country", "ip", "display"],
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


# ============================================================================
# Status metrics
# ============================================================================


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


# ============================================================================
# Flight Status metrics (Phase 0 - ETA Timing Modes)
# ============================================================================


# ============================================================================
# Route following metrics (Phase 5 - Simulation mode route following)
# ============================================================================


# ============================================================================
# Route timing metrics (Phase 3 - ETA Route Timing)
# ============================================================================


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


INDEPENDENT_GAUGES = tuple(
    value for value in tuple(globals().values()) if isinstance(value, Gauge)
)
REGISTRY.register(_FRAME_COLLECTOR)
