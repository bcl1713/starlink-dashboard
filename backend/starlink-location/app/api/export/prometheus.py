"""Prometheus HTTP API client for querying historical metrics."""

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

# Prometheus URL - internal docker network
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")


@dataclass(frozen=True)
class ExportMetric:
    """Prometheus metric to include in historical CSV exports."""

    metric: str
    column: str | None = None
    label_columns: dict[str, str] | None = None


# Metrics to export
EXPORT_METRICS = [
    ExportMetric("starlink_dish_latitude_degrees", "latitude"),
    ExportMetric("starlink_dish_longitude_degrees", "longitude"),
    ExportMetric("starlink_dish_altitude_feet", "altitude_feet"),
    ExportMetric("starlink_dish_speed_knots", "speed_knots"),
    ExportMetric("starlink_dish_heading_degrees", "heading_degrees"),
    ExportMetric("starlink_network_latency_ms_current", "latency_ms"),
    ExportMetric(
        "starlink_network_throughput_down_mbps_current", "throughput_down_mbps"
    ),
    ExportMetric(
        "starlink_network_throughput_up_mbps_current", "throughput_up_mbps"
    ),
    ExportMetric("starlink_network_packet_loss_percent", "packet_loss_percent"),
    ExportMetric("starlink_dish_obstruction_percent", "obstruction_percent"),
    ExportMetric("starlink_signal_quality_percent", "signal_quality_percent"),
    ExportMetric(
        "starlink_ground_entry_point_latitude_degrees",
        "ground_entry_latitude",
    ),
    ExportMetric(
        "starlink_ground_entry_point_longitude_degrees",
        "ground_entry_longitude",
    ),
    ExportMetric(
        "starlink_ground_entry_point_location",
        label_columns={
            "city": "ground_entry_city",
            "country": "ground_entry_country",
            "ip": "ground_entry_ip",
        },
    ),
]


def export_columns() -> list[str]:
    """Return ordered CSV columns for all configured export metrics."""
    columns: list[str] = []
    for metric in EXPORT_METRICS:
        if metric.column:
            columns.append(metric.column)
        if metric.label_columns:
            columns.extend(metric.label_columns.values())
    return columns


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
) -> list[dict[str, Any]]:
    """Query Prometheus for a metric over a time range.

    Args:
        metric: Prometheus metric name
        start: Start datetime
        end: End datetime
        step: Step interval in seconds

    Returns:
        Raw Prometheus result series for the requested metric
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

    return data.get("data", {}).get("result", [])


async def query_all_metrics(
    start: datetime,
    end: datetime,
    step: int,
) -> dict[float, dict[str, float | str]]:
    """Query all export metrics and join by timestamp.

    Args:
        start: Start datetime
        end: End datetime
        step: Step interval in seconds

    Returns:
        Dict mapping timestamp -> {column_name: value}
    """
    data_by_timestamp: dict[float, dict[str, float | str]] = {}

    for export_metric in EXPORT_METRICS:
        try:
            results = await query_metric_range(export_metric.metric, start, end, step)
            for result in results:
                labels = result.get("metric", {})
                values = result.get("values", [])
                for ts, val in values:
                    timestamp = float(ts)
                    if timestamp not in data_by_timestamp:
                        data_by_timestamp[timestamp] = {}
                    if export_metric.column:
                        data_by_timestamp[timestamp][export_metric.column] = float(val)
                    if export_metric.label_columns:
                        for label_name, column_name in export_metric.label_columns.items():
                            data_by_timestamp[timestamp][column_name] = labels.get(
                                label_name, ""
                            )
        except Exception as e:
            logger.warning(
                "Failed to query metric %s: %s", export_metric.metric, str(e)
            )

    return data_by_timestamp
