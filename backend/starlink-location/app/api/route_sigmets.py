"""Bounded installation-wide route advisory reads and exact acknowledgements."""

import asyncio

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute

from app.models.route_sigmets import NoticeMutation, NoticeSelection
from app.services.aviation_weather.route_state import (
    NoticeConflict,
    NoticeStoreUnavailable,
)
from app.services.overview_weather.protocol import WeatherUnavailable
from app.services.overview_weather.request import (
    WeatherRequestDisconnected,
    await_weather_request,
)

HEADERS = {"Cache-Control": "no-store"}
REQUEST_SECONDS = 10


class NoStoreRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request):
            try:
                return await original(request)
            except RequestValidationError:
                raise HTTPException(
                    422, "Invalid route SIGMET request", headers=HEADERS
                ) from None

        return handler


router = APIRouter(
    prefix="/api/aviation-weather/v1/route-sigmets", route_class=NoStoreRoute
)


async def guarded(request, operation):
    service = getattr(request.app.state, "route_sigmet_service", None)
    if service is None:
        raise HTTPException(503, "Route SIGMET service unavailable", headers=HEADERS)

    async def bounded():
        async with asyncio.timeout(REQUEST_SECONDS):
            return await operation(service)

    try:
        return await await_weather_request(request, bounded)
    except WeatherRequestDisconnected:
        return Response(status_code=499, headers=HEADERS)
    except NoticeConflict:
        raise HTTPException(
            409, "Route SIGMET notice is no longer current", headers=HEADERS
        ) from None
    except (
        NoticeStoreUnavailable,
        WeatherUnavailable,
        TimeoutError,
        OSError,
        ValueError,
        TypeError,
    ):
        raise HTTPException(
            503,
            "Route SIGMET service unavailable",
            headers={**HEADERS, "Retry-After": "5"},
        ) from None


@router.get("")
async def get_route_sigmets(request: Request, response: Response):
    response.headers.update(HEADERS)
    return await guarded(request, lambda service: service.read())


@router.put("/acknowledgement")
async def put_acknowledgement(
    change: NoticeMutation, request: Request, response: Response
):
    response.headers.update(HEADERS)
    return await guarded(request, lambda service: service.acknowledge(change))


@router.put('/selection')
async def put_selection(change: NoticeSelection, request: Request, response: Response):
    response.headers.update(HEADERS)
    return await guarded(request, lambda service: service.select(change))
