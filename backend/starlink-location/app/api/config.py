"""Configuration management endpoint handler."""

from typing import Optional

from fastapi import APIRouter, HTTPException

from app.core.config import ConfigManager
from app.models.config import SimulationConfig

router = APIRouter()

# Global config manager reference
_coordinator: Optional[object] = None


def set_coordinator(coordinator):
    """Set the simulation coordinator reference."""
    global _coordinator
    _coordinator = coordinator


@router.get("/api/config")
async def get_config():
    """
    Get current configuration.

    Returns the current simulation configuration as JSON.

    Example response:
    ```json
    {
        "mode": "simulation",
        "update_interval_seconds": 1.0,
        "route": {
            "pattern": "circular",
            "latitude_start": 40.7128,
            "longitude_start": -74.0060,
            "radius_km": 100.0,
            "distance_km": 500.0
        },
        "network": {
            "latency_min_ms": 20.0,
            "latency_typical_ms": 50.0,
            "latency_max_ms": 80.0,
            "latency_spike_max_ms": 200.0,
            "spike_probability": 0.05,
            "throughput_down_min_mbps": 50.0,
            "throughput_down_max_mbps": 200.0,
            "throughput_up_min_mbps": 10.0,
            "throughput_up_max_mbps": 40.0,
            "packet_loss_min_percent": 0.0,
            "packet_loss_max_percent": 5.0
        },
        "obstruction": {
            "min_percent": 0.0,
            "max_percent": 30.0,
            "variation_rate": 0.5
        },
        "position": {
            "speed_min_knots": 0.0,
            "speed_max_knots": 100.0,
            "altitude_min_meters": 100.0,
            "altitude_max_meters": 10000.0,
            "heading_variation_rate": 5.0
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
        config = _coordinator.get_config()
        return config.model_dump()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get configuration: {str(e)}"
        )


@router.post("/api/config")
async def update_config(new_config: SimulationConfig):
    """
    Update configuration.

    Accepts a new configuration JSON and applies it to the running simulator.
    This triggers a reset of all simulators with the new parameters.

    Request body should be a complete SimulationConfig object.

    Returns the updated configuration.
    """
    if _coordinator is None:
        raise HTTPException(
            status_code=503,
            detail="Service not yet initialized"
        )

    try:
        # Validate the new config (Pydantic will do this automatically)
        _coordinator.update_config(new_config)
        return new_config.model_dump()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to update configuration: {str(e)}"
        )


@router.put("/api/config")
async def replace_config(new_config: SimulationConfig):
    """
    Replace entire configuration.

    Equivalent to POST /api/config. Accepts a new configuration JSON and
    applies it to the running simulator.

    Returns the updated configuration.
    """
    if _coordinator is None:
        raise HTTPException(
            status_code=503,
            detail="Service not yet initialized"
        )

    try:
        # Validate the new config (Pydantic will do this automatically)
        _coordinator.update_config(new_config)
        return new_config.model_dump()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to update configuration: {str(e)}"
        )
