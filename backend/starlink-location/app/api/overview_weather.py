"""Same-origin buffered weather routes; provider details never become API errors."""

import re

from fastapi import APIRouter, HTTPException, Request, Response

from app.models.overview_weather import WeatherSettingsUpdate
from app.services.overview_weather.protocol import WeatherUnavailable
from app.services.overview_weather.request import (
    WeatherRequestDisconnected,
    await_weather_request,
)
from app.services.overview_weather.service import DAY_MS, WeatherTileError

router = APIRouter(prefix="/api/overview-weather")


def store(request):
    value = getattr(request.app.state, "overview_weather_settings_store", None)
    if value is None:
        raise HTTPException(503, "Weather settings unavailable")
    return value


def service(request):
    value = getattr(request.app.state, "overview_weather_service", None)
    if value is None:
        raise HTTPException(503, "Weather unavailable", headers={"Retry-After": "30"})
    return value


@router.get("/settings")
async def get_settings(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        return store(request).get()
    except (OSError, ValueError, TypeError):
        raise HTTPException(503, "Weather settings unavailable") from None


@router.put("/settings")
async def put_settings(
    changes: WeatherSettingsUpdate, request: Request, response: Response
):
    response.headers["Cache-Control"] = "no-store"
    try:
        settings = store(request).update(changes.model_dump())
    except (OSError, ValueError, TypeError):
        raise HTTPException(503, "Weather settings could not be saved") from None
    runtime = getattr(request.app.state, "overview_weather_service", None)
    if runtime is not None:
        await runtime.settings_changed(settings)
    return settings


async def guarded(request, operation):
    try:
        return await await_weather_request(request, operation)
    except WeatherRequestDisconnected:
        return Response(status_code=499)
    except WeatherTileError as error:
        raise HTTPException(error.status_code, "Weather tile unavailable") from None
    except WeatherUnavailable as error:
        raise HTTPException(
            503,
            "Weather unavailable",
            headers={"Retry-After": str(error.retry_after_seconds)},
        ) from None


@router.get("/frame")
async def get_frame(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    runtime = service(request)
    return await guarded(request, runtime.read_frame)


@router.get("/radar/{frame}/{z}/{x}/{y}.png")
async def get_radar(
    frame: str, z: str, x: str, y: str, request: Request, product_id: str | None = None
):
    frame, z, x, y = canonical_coordinates(frame, z, x, y)
    runtime = service(request)
    require_product(product_id)
    payload = await guarded(
        request, lambda: runtime.radar_tile(frame, z, x, y, product_id)
    )
    if isinstance(payload, Response):
        return payload
    return Response(
        payload.body,
        media_type="image/png",
        headers={
            "Cache-Control": "private, max-age=600, immutable",
        },
    )


@router.get("/coverage/{coverage}/{z}/{x}/{y}.png")
async def get_coverage(
    coverage: str,
    z: str,
    x: str,
    y: str,
    request: Request,
    product_id: str | None = None,
):
    coverage, z, x, y = canonical_coordinates(coverage, z, x, y)
    runtime = service(request)
    require_product(product_id)
    payload = await guarded(
        request, lambda: runtime.coverage_tile(coverage, z, x, y, product_id)
    )
    if isinstance(payload, Response):
        return payload
    seconds = max(
        0, min(300, ((coverage + 1) * DAY_MS - runtime.clock.utc_ms()) // 1000)
    )
    return Response(
        payload.body,
        media_type="image/png",
        headers={
            "Cache-Control": f"private, max-age={seconds}, must-revalidate",
        },
    )


def canonical_coordinates(token, z, x, y):
    if any(
        not re.fullmatch(r"0|[1-9][0-9]{0,15}", value) for value in (token, z, x, y)
    ):
        raise HTTPException(400, "Invalid weather coordinates")
    values = tuple(map(int, (token, z, x, y)))
    try:
        from app.services.overview_weather.service import WeatherService

        WeatherService._coordinates(*values[1:])
    except WeatherTileError:
        raise HTTPException(400, "Invalid weather coordinates") from None
    return values


def require_product(product_id):
    if product_id is None or not re.fullmatch(r"[a-f0-9]{64}", product_id):
        raise HTTPException(404, "Weather product unavailable")
