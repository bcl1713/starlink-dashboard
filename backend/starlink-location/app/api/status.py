"""Typed cache-only JSON status endpoint."""

from datetime import datetime, timezone
from typing import Any, Literal, Protocol

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.models.dashboard import (
    StatusEnvironmental,
    StatusNetwork,
    StatusObstruction,
    StatusPosition,
    StatusResponse,
    utc,
)

router = APIRouter()


class TelemetryCoordinator(Protocol):
    def get_current_telemetry(self) -> Any: ...


_coordinator: TelemetryCoordinator | None = None


def set_coordinator(coordinator: TelemetryCoordinator) -> None:
    """Set the coordinator whose last sample backs the hot path."""
    global _coordinator
    _coordinator = coordinator


@router.get("/api/status", response_model=StatusResponse)
async def status() -> StatusResponse:
    """Return the coordinator's already-observed sample without I/O."""
    if _coordinator is None:
        raise HTTPException(status_code=503, detail={"code": "status_unavailable"})
    try:
        telemetry: Any = _coordinator.get_current_telemetry()
        observed_at = utc(telemetry.timestamp)
        return StatusResponse(
            source=_source_name(_coordinator),
            timestamp=observed_at,
            observed_at=observed_at,
            received_at=datetime.now(timezone.utc),
            position=StatusPosition(
                latitude=telemetry.position.latitude,
                longitude=_normalize_longitude(telemetry.position.longitude),
                altitude=telemetry.position.altitude,
                speed=telemetry.position.speed,
                heading=telemetry.position.heading,
            ),
            network=StatusNetwork(
                latency_ms=telemetry.network.latency_ms,
                throughput_down_mbps=telemetry.network.throughput_down_mbps,
                throughput_up_mbps=telemetry.network.throughput_up_mbps,
                packet_loss_percent=telemetry.network.packet_loss_percent,
            ),
            obstruction=StatusObstruction(
                obstruction_percent=telemetry.obstruction.obstruction_percent
            ),
            environmental=StatusEnvironmental(
                signal_quality_percent=telemetry.environmental.signal_quality_percent,
                uptime_seconds=telemetry.environmental.uptime_seconds,
                temperature_celsius=telemetry.environmental.temperature_celsius,
            ),
        )
    except HTTPException:
        raise
    except (AttributeError, TypeError, ValueError, ValidationError) as exc:
        raise HTTPException(
            status_code=503, detail={"code": "status_unavailable"}
        ) from exc


def _normalize_longitude(longitude: float) -> float:
    """Represent equivalent finite longitudes in the public IDL-safe range."""
    return (longitude + 180.0) % 360.0 - 180.0


def _source_name(
    coordinator: TelemetryCoordinator,
) -> Literal["simulation", "live"]:
    return "live" if type(coordinator).__name__ == "LiveCoordinator" else "simulation"
