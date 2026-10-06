"""Same-origin aviation catalog, configuration and immutable bulletin payloads."""

import asyncio
import re

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import ValidationError

from app.models.aviation_weather import AviationCatalog
from app.services.aviation_weather.catalog import radar_product
from app.services.aviation_weather.gfs.bridge import FILES, unavailable_products
from app.services.aviation_weather.settings import AviationSettingsUpdate
from app.services.overview_weather.protocol import WeatherUnavailable
from app.services.overview_weather.request import (
    WeatherRequestDisconnected,
    await_weather_request,
)

router = APIRouter(prefix="/api/aviation-weather/v1")


def runtime(request):
    service = getattr(request.app.state, "aviation_weather_service", None)
    if service is None:
        raise HTTPException(
            503,
            "Aviation weather unavailable",
            headers={"Retry-After": "30", "Cache-Control": "no-store"},
        )
    return service


async def guarded(request, operation):
    try:
        return await await_weather_request(request, operation)
    except WeatherRequestDisconnected:
        return Response(status_code=499)
    except (WeatherUnavailable, OSError, ValueError, TypeError, ValidationError):
        raise HTTPException(
            503,
            "Aviation weather unavailable",
            headers={"Retry-After": "30", "Cache-Control": "no-store"},
        ) from None


@router.get("/settings")
async def get_settings(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        store = getattr(request.app.state, "aviation_weather_settings_store", None)
        if store is None:
            raise ValueError()
        return store.get()
    except (OSError, ValueError):
        raise HTTPException(503, "Aviation weather settings unavailable") from None


@router.put("/settings")
async def put_settings(
    changes: AviationSettingsUpdate, request: Request, response: Response
):
    response.headers["Cache-Control"] = "no-store"
    try:
        update = changes.changes()
    except ValueError:
        raise HTTPException(
            422, "Provide at least one boolean weather preference"
        ) from None
    service = runtime(request)

    async def save():
        bridge = getattr(request.app.state, "aviation_gfs_bridge", None)
        settings = await bridge.save(update) if bridge else service.store.update(update)
        operations = [service.settings_changed(settings)]
        if bridge:
            operations.append(bridge.settings_changed(settings))
        await asyncio.gather(*operations)
        return settings

    return await guarded(request, save)


@router.get("/catalog")
async def get_catalog(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    service = runtime(request)
    radar = getattr(request.app.state, "overview_weather_service", None)

    async def read():
        async def radar_frame():
            if radar is None:
                return None
            try:
                return await radar.read_frame()
            except (WeatherUnavailable, OSError, ValueError):
                return None

        products, manifest = await asyncio.gather(service.products(), radar_frame())
        now = service.utc_ms()
        settings = service.store.get()
        bridge = getattr(request.app.state, "aviation_gfs_bridge", None)
        models = (
            await bridge.products(settings, now)
            if bridge
            else unavailable_products(settings, now)
        )
        # Build all envelope states against one admission clock after acquisition.
        products = service.admitted_products(now)
        return AviationCatalog(
            schema="aviation-weather-v1",
            generated_at_ms=now,
            settings_revision=settings.revision,
            products=[radar_product(manifest, now), *products, *models],
        )

    return await guarded(request, read)


@router.get("/products/{instance}/{filename}")
async def get_product(instance: str, filename: str, request: Request):
    if (
        re.fullmatch(r"[a-f0-9]{64}", instance) is None
        or filename
        not in {
            "metar.json",
            "taf.json",
            "sigmet.json",
        }
        | FILES
    ):
        raise HTTPException(404, "Aviation weather product unavailable")
    service = runtime(request)

    # Settings from another process must invalidate payload eligibility too.
    async def read():
        if filename in FILES:
            bridge = getattr(request.app.state, "aviation_gfs_bridge", None)
            model = (
                await bridge.response(
                    instance, filename, service.store.get(), service.utc_ms()
                )
                if bridge
                else None
            )
            if model is None:
                raise HTTPException(404, "Aviation weather product unavailable")
            return model
        await service.settings_changed(service.store.get())
        body = service.payload(instance, filename)
        if body is None:
            raise HTTPException(404, "Aviation weather product unavailable")
        return Response(
            body,
            media_type="application/geo+json",
            headers={"Cache-Control": "private, no-cache", "ETag": f'"{instance}"'},
        )

    return await guarded(request, read)
