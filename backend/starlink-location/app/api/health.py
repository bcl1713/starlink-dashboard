"""Health check endpoint handler."""

from typing import Optional

from fastapi import APIRouter, HTTPException

router = APIRouter()

# Global health state
_coordinator: Optional[object] = None


def set_coordinator(coordinator):
    """Set the simulation coordinator reference."""
    global _coordinator
    _coordinator = coordinator


@router.get("/health")
async def health():
    """
    Health check endpoint.

    Returns JSON with service status, uptime, and operating mode.

    Example response:
    ```json
    {
        "status": "ok",
        "uptime_seconds": 123.45,
        "mode": "simulation",
        "version": "0.2.0",
        "timestamp": "2024-10-23T16:30:00.000000"
    }
    ```
    """
    if _coordinator is None:
        raise HTTPException(
            status_code=503,
            detail="Service not yet initialized"
        )

    from datetime import datetime

    try:
        config = _coordinator.get_config()
        uptime = _coordinator.get_uptime_seconds()

        return {
            "status": "ok",
            "uptime_seconds": uptime,
            "mode": config.mode,
            "version": "0.2.0",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )
