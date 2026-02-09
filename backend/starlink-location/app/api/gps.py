"""GPS configuration endpoint handler."""

from typing import Optional

from fastapi import APIRouter, HTTPException

from app.models.gps import GPSConfigRequest, GPSConfigResponse

router = APIRouter()

# Global client reference (set during startup for live mode)
_starlink_client: Optional[object] = None


def set_starlink_client(client):
    """Set the Starlink client reference for GPS operations."""
    global _starlink_client
    _starlink_client = client


@router.get("/api/v2/gps/config", response_model=GPSConfigResponse)
async def get_gps_config():
    """Get current GPS configuration and status from Starlink dish.

    Returns:
        GPSConfigResponse with enabled, ready, and satellites fields

    Raises:
        HTTPException 503: If the Starlink dish is unavailable
    """
    if _starlink_client is None:
        raise HTTPException(
            status_code=503,
            detail="GPS configuration not available in simulation mode",
        )

    try:
        config = _starlink_client.get_gps_config()
        return GPSConfigResponse(**config)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to Starlink dish: {str(e)}",
        )


@router.post("/api/v2/gps/config", response_model=GPSConfigResponse)
async def set_gps_config(request: GPSConfigRequest):
    """Update GPS configuration on Starlink dish.

    Args:
        request: GPSConfigRequest with enabled field

    Returns:
        GPSConfigResponse with updated configuration

    Raises:
        HTTPException 403: If the dish denies GPS configuration changes
        HTTPException 503: If the Starlink dish is unavailable
    """
    if _starlink_client is None:
        raise HTTPException(
            status_code=503,
            detail="GPS configuration not available in simulation mode",
        )

    try:
        config = _starlink_client.set_gps_config(enable=request.enabled)
        return GPSConfigResponse(**config)
    except PermissionError as e:
        raise HTTPException(
            status_code=403,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to Starlink dish: {str(e)}",
        )
