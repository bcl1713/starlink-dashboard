"""JSON status endpoint handler."""

from typing import Optional

from fastapi import APIRouter, HTTPException

router = APIRouter()

# Global status state
_coordinator: Optional[object] = None


def set_coordinator(coordinator):
    """Set the simulation coordinator reference."""
    global _coordinator
    _coordinator = coordinator


@router.get("/api/status")
async def status():
    """
    Get current telemetry status as JSON.

    Returns current position, network, and obstruction telemetry with human-readable
    fields and ISO 8601 formatted timestamp.

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
            "throughput_down_mbps": 125.3,
            "throughput_up_mbps": 25.1,
            "packet_loss_percent": 0.5
        },
        "obstruction": {
            "obstruction_percent": 15.0
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
        raise HTTPException(
            status_code=503,
            detail="Service not yet initialized"
        )

    try:
        telemetry = _coordinator.get_current_telemetry()

        return {
            "timestamp": telemetry.timestamp.isoformat(),
            "position": {
                "latitude": telemetry.position.latitude,
                "longitude": telemetry.position.longitude,
                "altitude": telemetry.position.altitude,
                "speed": telemetry.position.speed,
                "heading": telemetry.position.heading
            },
            "network": {
                "latency_ms": telemetry.network.latency_ms,
                "throughput_down_mbps": telemetry.network.throughput_down_mbps,
                "throughput_up_mbps": telemetry.network.throughput_up_mbps,
                "packet_loss_percent": telemetry.network.packet_loss_percent
            },
            "obstruction": {
                "obstruction_percent": telemetry.obstruction.obstruction_percent
            },
            "environmental": {
                "signal_quality_percent": telemetry.environmental.signal_quality_percent,
                "uptime_seconds": telemetry.environmental.uptime_seconds,
                "temperature_celsius": telemetry.environmental.temperature_celsius
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get status: {str(e)}"
        )
