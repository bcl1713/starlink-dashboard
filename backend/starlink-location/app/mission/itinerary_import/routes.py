"""HTTP adaptation for automatic import operations."""

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict

router = APIRouter(
    prefix="/api/v2/missions/itinerary-imports", tags=["itinerary-import"]
)


class ResolutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    generation: int
    choices: dict


def service(request):
    result = getattr(request.app.state, "itinerary_import_service", None)
    if result is None:
        raise HTTPException(503, "Itinerary import is unavailable")
    return result


def invoke(fn, *args):
    try:
        return fn(*args)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Import operation not found") from exc
    except OverflowError as exc:
        raise HTTPException(429, "Import queue full; retry later") from exc
    except ValueError as exc:
        code = (
            409
            if any(w in str(exc) for w in ["stale", "different", "finished"])
            else 422
        )
        raise HTTPException(code, str(exc)) from exc


@router.post("", status_code=202)
async def start(
    request: Request,
    pdf: Annotated[UploadFile | None, File()] = None,
    kmls: Annotated[list[UploadFile] | None, File()] = None,
    idempotency_key: str = Form(...),
    mission_id: str | None = Form(None),
):
    kmls = kmls or []
    if not mission_id and not kmls:
        raise HTTPException(422, "Upload route KMLs for a new mission")
    if len(kmls) > 16:
        raise HTTPException(422, "Upload at most 16 KMLs")
    data = await pdf.read(10 * 1024 * 1024 + 1) if pdf else b""
    routes = []
    remaining = 40 * 1024 * 1024
    for file in kmls:
        content = await file.read(remaining + 1)
        remaining -= len(content)
        if remaining < 0:
            raise HTTPException(422, "KML upload exceeds 40 MiB")
        routes.append((file.filename or "route.kml", content))
    return invoke(service(request).start, data, routes, idempotency_key, mission_id)


@router.get("/{operation_id}")
def read(request: Request, operation_id: str):
    return invoke(service(request).read, operation_id)


@router.delete("/{operation_id}")
def cancel(request: Request, operation_id: str):
    return invoke(service(request).cancel, operation_id)


@router.post("/{operation_id}/resolutions", status_code=202)
def resolve(request: Request, operation_id: str, body: ResolutionRequest):
    return invoke(service(request).resolve, operation_id, body.generation, body.choices)


@router.post("/{operation_id}/commit")
def commit(request: Request, operation_id: str, body: ResolutionRequest):
    return invoke(
        service(request).commit_revision, operation_id, body.generation, body.choices
    )
