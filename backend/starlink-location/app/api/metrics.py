"""Prometheus metrics endpoint handler."""

import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, Response

from app.api import metrics_export
from app.core.metrics import (
    _current_position,
    starlink_metrics_generation_errors_total,
    starlink_metrics_scrape_duration_seconds,
)

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
async def metrics(
    route_manager=None,
    poi_manager=None,
):
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format (application/openmetrics-text).

    This endpoint exposes all registered Prometheus metrics including:
    - Position metrics (latitude, longitude, altitude, speed, heading)
    - Network metrics (latency, throughput, packet loss)
    - Obstruction and signal quality metrics
    - Service info and uptime metrics
    - POI distance/ETA gauges including the `eta_type` label for anticipated vs estimated mode
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

    try:
        with starlink_metrics_scrape_duration_seconds.time():
            metrics_output = await metrics_export.get_metrics(
                route_manager, poi_manager
            )
    except Exception as exc:
        # Exporter faults must not be hidden by a second, unvalidated scrape.
        starlink_metrics_generation_errors_total.inc()
        raise HTTPException(
            status_code=503, detail="Metrics exposition failed"
        ) from exc

    return Response(
        content=metrics_output,
        media_type="application/openmetrics-text; version=1.0.0; charset=utf-8",
    )


@router.get("/position-table")
async def position_table():
    """
    Position data as a simple table for Grafana.

    Returns the current position as a JSON array suitable for Grafana's JSON API
    data source or TestData data source format.

    Example request:
    ```
    curl http://localhost:8000/position-table
    ```

    Example response:
    ```json
    {
      "columns": [
        {"text": "aircraft_id", "type": "string"},
        {"text": "latitude", "type": "number"},
        {"text": "longitude", "type": "number"},
        {"text": "altitude", "type": "number"}
      ],
      "rows": [
        ["starlink-dish", 41.612122, -74.006000, 5134.94]
      ]
    }
    ```
    """
    position = _current_position.snapshot()
    return JSONResponse(
        {
            "columns": [
                {"text": "aircraft_id", "type": "string"},
                {"text": "latitude", "type": "number"},
                {"text": "longitude", "type": "number"},
                {"text": "altitude", "type": "number"},
            ],
            "rows": [
                [
                    "starlink-dish",
                    position["latitude"],
                    position["longitude"],
                    position["altitude"],
                ]
            ],
        }
    )
