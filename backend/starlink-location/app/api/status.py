"""Typed cache-only JSON status endpoint."""

from datetime import datetime
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
    mode: str

    def get_current_telemetry_snapshot(self) -> tuple[Any, datetime]: ...


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
        telemetry, received_at = _coordinator.get_current_telemetry_snapshot()
        observed_at = utc(telemetry.timestamp)
        received_at = utc(received_at)
        if received_at < observed_at:
            raise ValueError("receipt precedes observation")
        return StatusResponse(
            source=_source_name(_coordinator),
            timestamp=observed_at,
            observed_at=observed_at,
            received_at=received_at,
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
    except (
        AttributeError,
        RuntimeError,
        TypeError,
        ValueError,
        ValidationError,
    ) as exc:
        raise HTTPException(
            status_code=503, detail={"code": "status_unavailable"}
        ) from exc


def _normalize_longitude(longitude: float) -> float:
    """Represent equivalent finite longitudes in the public IDL-safe range."""
    return (longitude + 180.0) % 360.0 - 180.0


def _source_name(
    coordinator: TelemetryCoordinator,
) -> Literal["simulation", "live"]:
    return "live" if coordinator.mode == "live" else "simulation"
