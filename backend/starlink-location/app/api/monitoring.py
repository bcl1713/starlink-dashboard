"""Independent history and ground-entry-point dashboard routes."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.models.dashboard import GroundEntryPointResponse, HistoryResponse
from app.services.ground_entry_point import get_cached_ground_entry_point
from app.services.monitoring_history import HistoryClient, HistoryUnavailable

router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])


def get_history_client(request: Request) -> HistoryClient:
    """Return an optional injected client or a bounded default adapter."""
    return getattr(request.app.state, "history_client", HistoryClient())


@router.get("/history", response_model=HistoryResponse)
async def history(
    response: Response,
    client: Annotated[HistoryClient, Depends(get_history_client)],
    range_seconds: Annotated[int, Query(ge=60, le=1800)] = 1800,
    step_seconds: Annotated[int, Query(ge=1, le=30)] = 1,
) -> HistoryResponse:
    """Return fixed allow-listed series without accepting an upstream target."""
    response.headers["Cache-Control"] = "no-store"
    try:
        return await client.fetch(
            range_seconds=range_seconds, step_seconds=step_seconds
        )
    except HistoryUnavailable as exc:
        raise HTTPException(
            status_code=503, detail={"code": "monitoring_history_unavailable"}
        ) from exc


@router.get("/ground-entry-point", response_model=GroundEntryPointResponse)
async def ground_entry_point() -> GroundEntryPointResponse:
    """Return cached geometry; discovery remains outside the request path."""
    entry = get_cached_ground_entry_point()
    generated_at = datetime.now(timezone.utc)
    if entry is None:
        return GroundEntryPointResponse(
            available=False,
            observed_at=None,
            generated_at=generated_at,
            display=None,
            city=None,
            region=None,
            country=None,
            latitude=None,
            longitude=None,
        )
    return GroundEntryPointResponse(
        available=True,
        observed_at=getattr(entry, "observed_at", None),
        generated_at=generated_at,
        display=entry.label,
        city=entry.city or None,
        region=entry.region or None,
        country=entry.country or None,
        latitude=entry.latitude,
        longitude=entry.longitude,
    )
