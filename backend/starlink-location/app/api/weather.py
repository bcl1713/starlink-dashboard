"""Weather-related API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.services.weather_radar import (
    InvalidRadarTileError,
    RainViewerRadarService,
    RainViewerRadarServiceError,
    RainViewerRadarTimeoutError,
)

router = APIRouter(prefix="/api/weather", tags=["weather"])


def get_rainviewer_radar_service(request: Request) -> RainViewerRadarService:
    """Return the application-owned RainViewer radar service."""
    return request.app.state.rainviewer_radar_service


@router.get("/radar/rainviewer/{z}/{x}/{y}.png")
async def rainviewer_radar_tile(z: int, x: int, y: int, request: Request) -> Response:
    """Return a validated RainViewer PNG radar tile through the backend origin."""
    service = get_rainviewer_radar_service(request)
    try:
        tile = await service.fetch_tile(z, x, y, request.is_disconnected)
    except InvalidRadarTileError as exc:
        raise HTTPException(
            status_code=400, detail={"code": "invalid_radar_tile"}
        ) from exc
    except RainViewerRadarTimeoutError as exc:
        raise HTTPException(
            status_code=504, detail={"code": "rainviewer_timeout"}
        ) from exc
    except RainViewerRadarServiceError as exc:
        raise HTTPException(
            status_code=502, detail={"code": "rainviewer_unavailable"}
        ) from exc

    try:
        body = tile.read()
    finally:
        tile.close()
    return Response(
        content=body,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=60",
            "X-Content-Type-Options": "nosniff",
            "X-Radar-Frame-Timestamp": str(tile.frame_timestamp),
        },
    )
