"""Prometheus metrics endpoint handler."""

from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import generate_latest

from app.core.metrics import REGISTRY

router = APIRouter()


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

    Example request:
    ```
    curl http://localhost:8000/metrics
    ```
    """
    return Response(
        content=generate_latest(REGISTRY),
        media_type="application/openmetrics-text; version=1.0.0; charset=utf-8"
    )
