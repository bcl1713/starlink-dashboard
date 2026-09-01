"""Typed monitoring API routes."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.models.monitoring import GroundEntryPointResponse, MonitoringHistoryResponse
from app.services.ground_entry_point import (
    GroundEntryPoint,
    get_cached_ground_entry_point,
)
from app.services.prometheus_client import (
    MonitoringPrometheusClient,
    MonitoringPrometheusError,
    MonitoringRateLimitError,
    MonitoringUnavailableError,
)

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_monitoring_client(request: Request) -> MonitoringPrometheusClient:
    """Return the lifespan-owned Prometheus monitoring client."""
    return request.app.state.monitoring_prometheus_client


@router.get(
    "/history",
    response_model=MonitoringHistoryResponse,
    summary="Get allow-listed monitoring history",
)
async def get_monitoring_history(
    response: Response,
    prometheus: Annotated[
        MonitoringPrometheusClient,
        Depends(get_monitoring_client),
    ],
    range_seconds: Annotated[
        int,
        Query(ge=60, le=3600, description="UTC history range in seconds"),
    ] = 1800,
    step_seconds: Annotated[
        int,
        Query(ge=1, le=60, description="Prometheus query step in seconds"),
    ] = 1,
) -> MonitoringHistoryResponse:
    """Return fixed monitoring series for a server-owned UTC time window."""
    response.headers["Cache-Control"] = "no-store"
    try:
        return await prometheus.get_history(
            range_seconds=range_seconds,
            step_seconds=step_seconds,
            client_id="monitoring-history",
        )
    except asyncio.CancelledError:
        raise
    except MonitoringRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "monitoring_rate_limited"},
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except MonitoringUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "monitoring_capacity_unavailable"},
        ) from exc
    except MonitoringPrometheusError as exc:
        if exc.code == "upstream_timeout":
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={"code": "monitoring_upstream_timeout"},
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "monitoring_upstream_error"},
        ) from exc


@router.get(
    "/ground-entry-point",
    response_model=GroundEntryPointResponse,
    summary="Get cached ground entry point",
)
async def get_ground_entry_point() -> GroundEntryPointResponse:
    """Return cached ground-entry point state without triggering discovery."""
    entry_point: GroundEntryPoint | None = get_cached_ground_entry_point()
    generated_at = _utc_now()
    if entry_point is None:
        return GroundEntryPointResponse(
            available=False,
            observed_at=None,
            generated_at=generated_at,
            display=None,
            city=None,
            region=None,
            country=None,
            latitude=None,
            longitude=None,
        )
    return GroundEntryPointResponse(
        available=True,
        observed_at=entry_point.observed_at,
        generated_at=generated_at,
        display=entry_point.label,
        city=entry_point.city,
        region=entry_point.region,
        country=entry_point.country,
        latitude=entry_point.latitude,
        longitude=entry_point.longitude,
    )
