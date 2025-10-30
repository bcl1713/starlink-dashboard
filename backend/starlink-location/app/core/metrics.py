"""Prometheus metrics registry and definitions."""

from prometheus_client import CollectorRegistry, Gauge, Counter, Histogram, CollectorRegistry as PrometheusCollectorRegistry
from prometheus_client.core import GaugeMetricFamily

# Create a dedicated registry for our metrics
REGISTRY = CollectorRegistry()

# Current position data for custom collector
_current_position = {
    'latitude': 0.0,
    'longitude': 0.0,
    'altitude': 0.0,
}

class PositionCollector:
    """Custom collector that exports position as a single metric with all values."""

    def collect(self):
        # Create a gauge metric with the position data
        position_metric = GaugeMetricFamily(
            'starlink_aircraft_position',
            'Current aircraft position with latitude, longitude, and altitude',
            labels=['dimension']
        )

        position_metric.add_metric(['latitude'], _current_position['latitude'])
        position_metric.add_metric(['longitude'], _current_position['longitude'])
        position_metric.add_metric(['altitude'], _current_position['altitude'])

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
    'starlink_device_location',
    'Device location with latitude and longitude as labels',
    labelnames=['lat', 'lon', 'altitude'],
    registry=REGISTRY
)

starlink_dish_latitude_degrees = Gauge(
    'starlink_dish_latitude_degrees',
    'Dish latitude in decimal degrees',
    registry=REGISTRY
)

starlink_dish_longitude_degrees = Gauge(
    'starlink_dish_longitude_degrees',
    'Dish longitude in decimal degrees',
    registry=REGISTRY
)

starlink_dish_altitude_feet = Gauge(
    'starlink_dish_altitude_feet',
    'Dish altitude in feet above sea level',
    registry=REGISTRY
)

starlink_dish_speed_knots = Gauge(
    'starlink_dish_speed_knots',
    'Dish speed in knots',
    registry=REGISTRY
)

starlink_dish_heading_degrees = Gauge(
    'starlink_dish_heading_degrees',
    'Dish heading in degrees (0=North, 90=East)',
    registry=REGISTRY
)

# ============================================================================
# Network metrics - Current values (Gauges)
# ============================================================================
starlink_network_latency_ms_current = Gauge(
    'starlink_network_latency_ms_current',
    'Network round-trip latency in milliseconds (current value)',
    registry=REGISTRY
)

starlink_network_throughput_down_mbps_current = Gauge(
    'starlink_network_throughput_down_mbps_current',
    'Download throughput in Megabits per second (current value)',
    registry=REGISTRY
)

starlink_network_throughput_up_mbps_current = Gauge(
    'starlink_network_throughput_up_mbps_current',
    'Upload throughput in Megabits per second (current value)',
    registry=REGISTRY
)

starlink_network_packet_loss_percent = Gauge(
    'starlink_network_packet_loss_percent',
    'Packet loss as percentage (0-100)',
    registry=REGISTRY
)

# ============================================================================
# Network metrics - Histograms for percentile analysis
# ============================================================================
# Latency histogram: buckets chosen to capture Starlink typical performance
# Starlink latency typically ranges 25-150ms (median ~50ms)
# Buckets: 20, 40, 60, 80, 100, 150, 200, 500 capture low/normal/degraded/poor ranges
starlink_network_latency_ms = Histogram(
    'starlink_network_latency_ms',
    'Network round-trip latency in milliseconds (histogram for percentile analysis)',
    labelnames=['mode', 'status'],
    buckets=[20, 40, 60, 80, 100, 150, 200, 500],
    registry=REGISTRY
)

# Download throughput histogram: buckets for typical Starlink speeds
# Starlink download typically 50-300 Mbps depending on conditions
# Buckets: 50, 100, 150, 200, 250, 300 capture performance ranges
starlink_network_throughput_down_mbps = Histogram(
    'starlink_network_throughput_down_mbps',
    'Download throughput in Megabits per second (histogram for percentile analysis)',
    labelnames=['mode', 'status'],
    buckets=[50, 100, 150, 200, 250, 300],
    registry=REGISTRY
)

# Upload throughput histogram: buckets for typical Starlink upload speeds
# Starlink upload typically 10-50 Mbps depending on conditions
# Buckets: 10, 20, 30, 40, 50 capture the typical performance range
starlink_network_throughput_up_mbps = Histogram(
    'starlink_network_throughput_up_mbps',
    'Upload throughput in Megabits per second (histogram for percentile analysis)',
    labelnames=['mode', 'status'],
    buckets=[10, 20, 30, 40, 50],
    registry=REGISTRY
)

# ============================================================================
# Obstruction and signal metrics
# ============================================================================
starlink_dish_obstruction_percent = Gauge(
    'starlink_dish_obstruction_percent',
    'Dish obstruction as percentage (0-100)',
    registry=REGISTRY
)

starlink_signal_quality_percent = Gauge(
    'starlink_signal_quality_percent',
    'Signal quality as percentage (0-100)',
    registry=REGISTRY
)

# ============================================================================
# Status metrics
# ============================================================================
starlink_service_info = Gauge(
    'starlink_service_info',
    'Starlink service information',
    ['version', 'mode'],
    registry=REGISTRY
)

starlink_mode_info = Gauge(
    'starlink_mode_info',
    'Starlink operating mode indicator',
    labelnames=['mode'],
    registry=REGISTRY
)

starlink_uptime_seconds = Gauge(
    'starlink_uptime_seconds',
    'Service uptime in seconds',
    registry=REGISTRY
)

starlink_dish_uptime_seconds = Gauge(
    'starlink_dish_uptime_seconds',
    'Dish uptime in seconds',
    registry=REGISTRY
)

starlink_dish_thermal_throttle = Gauge(
    'starlink_dish_thermal_throttle',
    'Dish thermal throttle state (0=normal, 1=throttled)',
    registry=REGISTRY
)

starlink_dish_outage_active = Gauge(
    'starlink_dish_outage_active',
    'Dish outage state (0=connected, 1=outage)',
    registry=REGISTRY
)

# ============================================================================
# Event counters
# ============================================================================
starlink_connection_attempts_total = Counter(
    'starlink_connection_attempts_total',
    'Total number of connection attempts',
    registry=REGISTRY
)

starlink_connection_failures_total = Counter(
    'starlink_connection_failures_total',
    'Total number of failed connection attempts',
    registry=REGISTRY
)

starlink_outage_events_total = Counter(
    'starlink_outage_events_total',
    'Total number of outage events',
    registry=REGISTRY
)

starlink_thermal_events_total = Counter(
    'starlink_thermal_events_total',
    'Total number of thermal throttle events',
    registry=REGISTRY
)

# ============================================================================
# POI and ETA metrics
# ============================================================================
starlink_eta_poi_seconds = Gauge(
    'starlink_eta_poi_seconds',
    'Estimated time of arrival to point of interest in seconds',
    labelnames=['name'],
    registry=REGISTRY
)

starlink_distance_to_poi_meters = Gauge(
    'starlink_distance_to_poi_meters',
    'Distance to point of interest in meters',
    labelnames=['name'],
    registry=REGISTRY
)

# ============================================================================
# Meta-metrics for monitoring the monitoring system
# ============================================================================
starlink_metrics_scrape_duration_seconds = Histogram(
    'starlink_metrics_scrape_duration_seconds',
    'Time spent collecting metrics in seconds',
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
    registry=REGISTRY
)

starlink_metrics_generation_errors_total = Counter(
    'starlink_metrics_generation_errors_total',
    'Total number of metric generation errors',
    registry=REGISTRY
)

starlink_metrics_last_update_timestamp_seconds = Gauge(
    'starlink_metrics_last_update_timestamp_seconds',
    'Timestamp of last successful metric update (Unix epoch)',
    registry=REGISTRY
)

# ============================================================================
# Simulation metrics (only in simulation mode)
# ============================================================================
simulation_updates_total = Counter(
    'simulation_updates_total',
    'Total number of simulation updates',
    registry=REGISTRY
)

simulation_errors_total = Counter(
    'simulation_errors_total',
    'Total number of simulation errors',
    registry=REGISTRY
)


def update_metrics_from_telemetry(telemetry, config=None):
    """
    Update all Prometheus metrics from telemetry data.

    Args:
        telemetry: TelemetryData instance or None
        config: Optional ConfigManager instance for label computation

    Returns:
        None. Does nothing if telemetry is None (prevents publishing invalid data).
    """
    # Defensive check: do not publish metrics if telemetry is None
    # This prevents pollution of Prometheus with zero/invalid values
    if telemetry is None:
        return

    from app.core.labels import get_mode_label, get_status_label

    # Compute labels if config provided
    mode_label = get_mode_label(config) if config else "unknown"
    status_label = get_status_label(
        telemetry.network.latency_ms,
        telemetry.network.packet_loss_percent
    )

    # Position metrics
    # Update custom collector's position data
    global _current_position
    _current_position['latitude'] = telemetry.position.latitude
    _current_position['longitude'] = telemetry.position.longitude
    _current_position['altitude'] = telemetry.position.altitude

    # Also set individual metrics for backward compatibility
    starlink_dish_latitude_degrees.set(telemetry.position.latitude)
    starlink_dish_longitude_degrees.set(telemetry.position.longitude)
    starlink_dish_altitude_feet.set(telemetry.position.altitude)
    starlink_dish_speed_knots.set(telemetry.position.speed)
    starlink_dish_heading_degrees.set(telemetry.position.heading)

    # Network metrics - Current values (Gauges)
    starlink_network_latency_ms_current.set(telemetry.network.latency_ms)
    starlink_network_throughput_down_mbps_current.set(
        telemetry.network.throughput_down_mbps
    )
    starlink_network_throughput_up_mbps_current.set(
        telemetry.network.throughput_up_mbps
    )
    starlink_network_packet_loss_percent.set(
        telemetry.network.packet_loss_percent
    )

    # Network metrics - Histograms (for percentile analysis)
    # Record observations for histogram buckets with labels
    starlink_network_latency_ms.labels(
        mode=mode_label,
        status=status_label
    ).observe(telemetry.network.latency_ms)
    starlink_network_throughput_down_mbps.labels(
        mode=mode_label,
        status=status_label
    ).observe(telemetry.network.throughput_down_mbps)
    starlink_network_throughput_up_mbps.labels(
        mode=mode_label,
        status=status_label
    ).observe(telemetry.network.throughput_up_mbps)

    # Obstruction and signal metrics
    starlink_dish_obstruction_percent.set(
        telemetry.obstruction.obstruction_percent
    )
    starlink_signal_quality_percent.set(
        telemetry.environmental.signal_quality_percent
    )

    # Status metrics
    starlink_uptime_seconds.set(telemetry.environmental.uptime_seconds)

    # Increment update counter
    simulation_updates_total.inc()


def clear_telemetry_metrics():
    """
    Clear all telemetry metrics by setting them to NaN.

    This is used when the dish is disconnected in live mode to prevent
    publishing stale or zero values to Prometheus. NaN values are not
    stored by Prometheus, effectively removing the metrics from the database.

    Note: Service info, uptime, and counter metrics are NOT cleared as they
    represent the backend service state, not dish telemetry.
    """
    import math

    # Position metrics
    starlink_dish_latitude_degrees.set(math.nan)
    starlink_dish_longitude_degrees.set(math.nan)
    starlink_dish_altitude_feet.set(math.nan)
    starlink_dish_speed_knots.set(math.nan)
    starlink_dish_heading_degrees.set(math.nan)

    # Network metrics (current values)
    starlink_network_latency_ms_current.set(math.nan)
    starlink_network_throughput_down_mbps_current.set(math.nan)
    starlink_network_throughput_up_mbps_current.set(math.nan)
    starlink_network_packet_loss_percent.set(math.nan)

    # Obstruction and signal metrics
    starlink_dish_obstruction_percent.set(math.nan)
    starlink_signal_quality_percent.set(math.nan)

    # Dish status metrics
    starlink_dish_uptime_seconds.set(math.nan)
    starlink_dish_thermal_throttle.set(math.nan)
    starlink_dish_outage_active.set(math.nan)

    # Clear custom position collector data
    global _current_position
    _current_position['latitude'] = math.nan
    _current_position['longitude'] = math.nan
    _current_position['altitude'] = math.nan


def set_service_info(version: str, mode: str):
    """
    Set service info metrics.

    Sets both the composite starlink_service_info metric and the individual
    starlink_mode_info metric for better filtering and observability.

    Args:
        version: Service version string
        mode: Operating mode (simulation or live)
    """
    # Set composite service info metric with version and mode labels
    starlink_service_info.labels(version=version, mode=mode).set(1)

    # Set mode indicator metric - only the active mode will be set to 1
    # This allows easy filtering by mode in Prometheus queries
    for possible_mode in ['simulation', 'live']:
        if possible_mode == mode:
            starlink_mode_info.labels(mode=possible_mode).set(1)
        else:
            starlink_mode_info.labels(mode=possible_mode).set(0)
