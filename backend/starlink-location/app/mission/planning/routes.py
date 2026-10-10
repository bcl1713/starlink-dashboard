"""Itinerary-first planning API through draft persistence."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from app.services.kml_parser import KMLParseError

from .deadlines import PlanningDeadlineError, PlanningWorkerError
from .errors import PlanningFailure
from .extract import ItineraryExtractionError
from .match import RouteAnchorError
from .models import (
    AcceptRouteBinding,
    ConfirmItinerary,
    ItineraryPreview,
    PlanningSatelliteOptions,
    PlanningView,
    RouteBindingPreview,
    SaveDraft,
)
from .service import PlanningService

router = APIRouter(prefix="/api/v2/missions/planning", tags=["Planning"])


def get_service(request: Request):
    service = getattr(request.app.state, "planning_service", None)
    if service is None:
        raise HTTPException(503, {"code": "planning_unavailable", "retryable": True})
    return service


async def invoke(fn, *args):
    try:
        return await run_in_threadpool(fn, *args)
    except PlanningFailure as exc:
        raise HTTPException(exc.status_code, exc.error.model_dump(mode="json")) from exc
    except (PlanningDeadlineError, PlanningWorkerError) as exc:
        raise HTTPException(
            503, {"code": exc.code, "message": str(exc), "retryable": exc.retryable}
        ) from exc
    except (
        ItineraryExtractionError,
        RouteAnchorError,
        KMLParseError,
        ValueError,
    ) as exc:
        raise HTTPException(
            422,
            {
                "code": getattr(exc, "code", "invalid_planning_input"),
                "message": str(exc),
                "retryable": False,
            },
        ) from exc


async def upload_bytes(file, *, pdf=False):
    content = await file.read(10 * 1024 * 1024 + 1) if pdf else await file.read()
    if pdf and len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            422,
            {
                "code": "upload_too_large",
                "message": "Upload exceeds 10 MiB",
                "retryable": False,
            },
        )
    return content


@router.post("/itinerary-previews", response_model=ItineraryPreview)
async def preview_itinerary(
    file: Annotated[UploadFile, File()],
    service: Annotated[PlanningService, Depends(get_service)],
):
    return await invoke(
        service.preview_itinerary,
        await upload_bytes(file, pdf=True),
        file.filename or "itinerary.pdf",
    )


@router.get("/satellite-options", response_model=PlanningSatelliteOptions)
async def satellite_options(service: Annotated[PlanningService, Depends(get_service)]):
    return await invoke(service.satellite_options)


@router.post("/missions", response_model=PlanningView, status_code=201)
async def create(
    request: ConfirmItinerary, service: Annotated[PlanningService, Depends(get_service)]
):
    return await invoke(service.create, request)


@router.get("/missions/{mission_id}", response_model=PlanningView)
async def read(
    mission_id: str, service: Annotated[PlanningService, Depends(get_service)]
):
    return await invoke(service.store.read, mission_id)


@router.post(
    "/missions/{mission_id}/legs/{leg_id}/route-previews",
    response_model=RouteBindingPreview,
)
async def preview_route(
    mission_id: str,
    leg_id: str,
    file: Annotated[UploadFile, File()],
    expected_revision: Annotated[int, Form(ge=1)],
    service: Annotated[PlanningService, Depends(get_service)],
):
    return await invoke(
        service.preview_route,
        mission_id,
        leg_id,
        await upload_bytes(file),
        expected_revision,
        file.filename or "route.kml",
    )


@router.post("/missions/{mission_id}/legs/{leg_id}/route", response_model=PlanningView)
async def accept_route(
    mission_id: str,
    leg_id: str,
    request: AcceptRouteBinding,
    service: Annotated[PlanningService, Depends(get_service)],
):
    return await invoke(service.accept_route, mission_id, leg_id, request)


@router.put("/missions/{mission_id}/legs/{leg_id}/draft", response_model=PlanningView)
async def save_draft(
    mission_id: str,
    leg_id: str,
    request: SaveDraft,
    service: Annotated[PlanningService, Depends(get_service)],
):
    await invoke(service.validate_selection, request.draft)
    return await invoke(service.store.save_draft, mission_id, leg_id, request)
