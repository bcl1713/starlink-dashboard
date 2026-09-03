"""Same-origin weather radar API routes."""

import inspect

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.services.weather_radar import RainViewerRadarService

router = APIRouter(prefix="/api/weather", tags=["weather"])
rainviewer_radar_service = RainViewerRadarService()


def unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail="Weather radar unavailable")


@router.get("/radar/rainviewer/metadata")
async def rainviewer_radar_metadata(request: Request) -> dict[str, bool | str]:
    """Publish only the fixed origin-relative tile template to the browser."""
    service = request.app.state.rainviewer_radar_service
    try:
        frame = service.frame_token()
        if inspect.isawaitable(frame):
            frame = await frame
    except (RuntimeError, TypeError, ValueError):
        raise unavailable() from None
    return {
        "available": True,
        "tile_url": f"/api/weather/radar/rainviewer/{{z}}/{{x}}/{{y}}.png?frame={frame}",
    }


@router.get("/radar/rainviewer/{z}/{x}/{y}.png")
async def rainviewer_radar_tile(request: Request, z: int, x: int, y: int) -> Response:
    """Proxy a bounded PNG tile; never redirect browsers to RainViewer."""
    service = request.app.state.rainviewer_radar_service
    try:
        image = service.tile_bytes(z=z, x=x, y=y)
        if inspect.isawaitable(image):
            image = await image
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid radar tile") from exc
    except (RuntimeError, TypeError):
        raise unavailable() from None
    return Response(
        content=image,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )
