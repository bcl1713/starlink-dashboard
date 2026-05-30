"""Weather-related API routes."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.services.weather_radar import RainViewerRadarService

router = APIRouter(prefix="/api/weather", tags=["weather"])
rainviewer_radar_service = RainViewerRadarService()


@router.get("/radar/rainviewer/{z}/{x}/{y}.png")
def rainviewer_radar_tile(z: int, x: int, y: int) -> RedirectResponse:
    """Redirect Grafana XYZ tile requests to the latest RainViewer radar frame."""
    try:
        tile_url = rainviewer_radar_service.tile_url(z=z, x=x, y=y)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return RedirectResponse(
        url=tile_url,
        status_code=307,
        headers={"Cache-Control": "public, max-age=300"},
    )
