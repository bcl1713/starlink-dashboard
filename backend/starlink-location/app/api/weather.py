"""Same-origin weather radar API routes."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.services.weather_radar import RainViewerRadarService

router = APIRouter(prefix="/api/weather", tags=["weather"])
rainviewer_radar_service = RainViewerRadarService()


def unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail="Weather radar unavailable")


@router.get("/radar/rainviewer/metadata")
def rainviewer_radar_metadata() -> dict[str, bool | str]:
    """Publish only the fixed origin-relative tile template to the browser."""
    try:
        frame = rainviewer_radar_service.frame_token()
    except (RuntimeError, ValueError):
        raise unavailable() from None
    return {
        "available": True,
        "tile_url": f"/api/weather/radar/rainviewer/{{z}}/{{x}}/{{y}}.png?frame={frame}",
    }


@router.get("/radar/rainviewer/{z}/{x}/{y}.png")
def rainviewer_radar_tile(z: int, x: int, y: int) -> Response:
    """Proxy a bounded PNG tile; never redirect browsers to RainViewer."""
    try:
        image = rainviewer_radar_service.tile_bytes(z=z, x=x, y=y)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid radar tile") from exc
    except RuntimeError:
        raise unavailable() from None
    return Response(
        content=image,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )