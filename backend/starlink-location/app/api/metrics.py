"""Prometheus metrics endpoint handler."""

import time
from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import generate_latest

from app.core.metrics import REGISTRY

router = APIRouter()

# Module-level state for tracking Prometheus scrapes
_last_scrape_time = None


def get_last_scrape_time():
    """Get the timestamp of the last Prometheus scrape."""
    return _last_scrape_time


def set_last_scrape_time(timestamp):
    """Set the timestamp of the last Prometheus scrape."""
    global _last_scrape_time
    _last_scrape_time = timestamp


@router.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format (application/openmetrics-text).

    This endpoint exposes all registered Prometheus metrics including:
    - Position metrics (latitude, longitude, altitude, speed, heading)
    - Network metrics (latency, throughput, packet loss)
    - Obstruction and signal quality metrics
    - Service info and uptime metrics
    - Simulation counters (updates, errors)
    - Histogram metrics for latency and throughput (percentile analysis)
    - Event counters (connection attempts, failures, outages, thermal events)
    - Meta-metrics (scrape duration, generation errors, last update timestamp)

    Example request:
    ```
    curl http://localhost:8000/metrics
    ```
    """
    # Record scrape time for health endpoint monitoring
    set_last_scrape_time(time.time())

    # Generate metrics and ensure OpenMetrics EOF marker is present
    metrics_output = generate_latest(REGISTRY)

    # Ensure OpenMetrics format compliance with EOF marker
    if not metrics_output.endswith(b"# EOF\n"):
        metrics_output = metrics_output.rstrip() + b"\n# EOF\n"

    return Response(
        content=metrics_output,
        media_type="application/openmetrics-text; version=1.0.0; charset=utf-8"
    )
