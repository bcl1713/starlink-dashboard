"""JSON status endpoint handler."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.mission.pop_status import PopStatusService
from app.services.ground_entry_point import get_cached_ground_entry_point
from app.services.pop.continuity_models import CallContinuityProjection

router = APIRouter()

# Global status state
_coordinator: object | None = None
_pop_service: PopStatusService = PopStatusService()


def set_coordinator(coordinator):
    """Set the simulation coordinator reference."""
    global _coordinator
    _coordinator = coordinator


def set_pop_service(service: PopStatusService):
    """Inject the active-route advisory lifecycle alongside the coordinator."""
    global _pop_service
    _pop_service = service


class StatusResponse(BaseModel):
    """Retain telemetry wire fields and publish typed optional call evidence."""

    model_config = ConfigDict(extra="allow")
    call_continuity: CallContinuityProjection | None = None


@router.get("/api/status", response_model=StatusResponse)
async def status():
    """
    Get current telemetry status as JSON.

    Returns current position, network, and obstruction telemetry with human-readable
    fields and the original ISO 8601 acquisition timestamp. Each of the five
    metric values is null unless its metric_availability flag is true.

    Example response:
    ```json
    {
        "timestamp": "2024-10-23T16:30:00.000000",
        "position": {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "altitude": 5000.0,
            "speed": 25.5,
            "heading": 45.0
        },
        "network": {
            "latency_ms": 45.2,
            "throughput_down_mbps": null,
            "throughput_up_mbps": 25.1,
            "packet_loss_percent": 0.5
        },
        "obstruction": {
            "obstruction_percent": 15.0
        },
        "metric_availability": {
            "latency_ms": true,
            "throughput_down_mbps": false,
            "throughput_up_mbps": true,
            "packet_loss_percent": true,
            "obstruction_percent": true
        },
        "environmental": {
            "signal_quality_percent": 85.0,
            "uptime_seconds": 3600.5,
            "temperature_celsius": null
        }
    }
    ```
    """
    if _coordinator is None:
        raise HTTPException(status_code=503, detail="Service not yet initialized")

    try:
        telemetry = _coordinator.get_current_telemetry()
        pop_payload = _pop_service.status_payload(telemetry)
        if pop_payload["pop_observation"]["source"] == "simulation":
            entry = pop_payload["pop_observation"]["entry"]
            ground_entry_position = (
                {"latitude": entry["latitude"], "longitude": entry["longitude"]}
                if entry
                else None
            )
        else:
            ground_entry_point = get_cached_ground_entry_point()
            ground_entry_position = (
                {
                    "latitude": ground_entry_point.latitude,
                    "longitude": ground_entry_point.longitude,
                }
                if ground_entry_point
                else None
            )
        availability = telemetry.metric_availability

        return {
            **pop_payload,
            "timestamp": telemetry.timestamp.isoformat(),
            "position": {
                "latitude": telemetry.position.latitude,
                "longitude": telemetry.position.longitude,
                "altitude": telemetry.position.altitude,
                "speed": telemetry.position.speed,
                "heading": telemetry.position.heading,
            },
            "network": {
                "latency_ms": (
                    telemetry.network.latency_ms if availability.latency_ms else None
                ),
                "throughput_down_mbps": (
                    telemetry.network.throughput_down_mbps
                    if availability.throughput_down_mbps
                    else None
                ),
                "throughput_up_mbps": (
                    telemetry.network.throughput_up_mbps
                    if availability.throughput_up_mbps
                    else None
                ),
                "packet_loss_percent": (
                    telemetry.network.packet_loss_percent
                    if availability.packet_loss_percent
                    else None
                ),
            },
            "obstruction": {
                "obstruction_percent": (
                    telemetry.obstruction.obstruction_percent
                    if availability.obstruction_percent
                    else None
                )
            },
            "metric_availability": availability.model_dump(),
            "environmental": {
                "signal_quality_percent": telemetry.environmental.signal_quality_percent,
                "uptime_seconds": telemetry.environmental.uptime_seconds,
                "temperature_celsius": telemetry.environmental.temperature_celsius,
            },
            "ground_entry_point": ground_entry_position,
        }
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        LookupError,
        ConnectionError,
        TimeoutError,
        ImportError,
        EOFError,
    ) as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {e!s}")
