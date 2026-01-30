"""Prometheus HTTP API client for querying historical metrics."""

import os
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

# Prometheus URL - internal docker network
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")

# Metrics to export
EXPORT_METRICS = [
    ("starlink_dish_latitude_degrees", "latitude"),
    ("starlink_dish_longitude_degrees", "longitude"),
    ("starlink_dish_altitude_feet", "altitude_feet"),
    ("starlink_dish_speed_knots", "speed_knots"),
    ("starlink_dish_heading_degrees", "heading_degrees"),
    ("starlink_network_latency_ms_current", "latency_ms"),
    ("starlink_network_throughput_down_mbps_current", "throughput_down_mbps"),
    ("starlink_network_throughput_up_mbps_current", "throughput_up_mbps"),
    ("starlink_network_packet_loss_percent", "packet_loss_percent"),
    ("starlink_dish_obstruction_percent", "obstruction_percent"),
    ("starlink_signal_quality_percent", "signal_quality_percent"),
]


def calculate_step(start: datetime, end: datetime, step: Optional[int] = None) -> int:
    """Calculate appropriate step interval based on time range.

    Args:
        start: Start datetime
        end: End datetime
        step: Optional explicit step in seconds

    Returns:
        Step interval in seconds
    """
    if step is not None and step >= 1:
        return step

    # Auto-calculate based on range
    duration = end - start
    hours = duration.total_seconds() / 3600

    if hours <= 2:
        return 1  # 1 second
    elif hours <= 24:
        return 10  # 10 seconds
    elif hours <= 168:  # 7 days
        return 60  # 1 minute
    else:
        return 300  # 5 minutes


async def query_metric_range(
    metric: str,
    start: datetime,
    end: datetime,
    step: int,
) -> list[tuple[float, float]]:
    """Query Prometheus for a metric over a time range.

    Args:
        metric: Prometheus metric name
        start: Start datetime
        end: End datetime
        step: Step interval in seconds

    Returns:
        List of (timestamp, value) tuples
    """
    # Format timestamps for Prometheus (RFC3339 or Unix timestamp)
    # Convert to UTC and use Unix timestamps to avoid timezone issues
    start_ts = (
        start.timestamp()
        if start.tzinfo
        else start.replace(tzinfo=timezone.utc).timestamp()
    )
    end_ts = (
        end.timestamp() if end.tzinfo else end.replace(tzinfo=timezone.utc).timestamp()
    )

    params = {
        "query": metric,
        "start": str(start_ts),
        "end": str(end_ts),
        "step": f"{step}s",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(
            f"{PROMETHEUS_URL}/api/v1/query_range",
            params=params,
        )
        response.raise_for_status()
        data = response.json()

    if data["status"] != "success":
        logger.warning(
            "Prometheus query failed: metric=%s error=%s",
            metric,
            data.get("error", "unknown"),
        )
        return []

    results = data.get("data", {}).get("result", [])
    if not results:
        return []

    # Extract values from first result (should only be one for gauge metrics)
    values = results[0].get("values", [])
    return [(float(ts), float(val)) for ts, val in values]


async def query_all_metrics(
    start: datetime,
    end: datetime,
    step: int,
) -> dict[float, dict[str, float]]:
    """Query all export metrics and join by timestamp.

    Args:
        start: Start datetime
        end: End datetime
        step: Step interval in seconds

    Returns:
        Dict mapping timestamp -> {column_name: value}
    """
    # Collect all data points by timestamp
    data_by_timestamp: dict[float, dict[str, float]] = {}

    for prom_metric, column_name in EXPORT_METRICS:
        try:
            values = await query_metric_range(prom_metric, start, end, step)
            for ts, val in values:
                if ts not in data_by_timestamp:
                    data_by_timestamp[ts] = {}
                data_by_timestamp[ts][column_name] = val
        except Exception as e:
            logger.warning("Failed to query metric %s: %s", prom_metric, str(e))

    return data_by_timestamp
