"""Lease-scoped orbital cache and side-effect-free operator diagnostics."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response

from app.services.orbital_catalog import OrbitalCatalogService

router = APIRouter()
Viewer = Annotated[str, Path(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")]


def _service(request: Request) -> OrbitalCatalogService:
    service = getattr(request.app.state, "orbital_catalog", None)
    if service is None:
        raise HTTPException(503, "Orbital catalog not initialized")
    return service


@router.put("/api/orbital/viewers/{viewer_id}")
async def acquire(request: Request, viewer_id: Viewer):
    try:
        return await _service(request).acquire(viewer_id)
    except OverflowError as error:
        raise HTTPException(429, str(error)) from error


@router.delete("/api/orbital/viewers/{viewer_id}", status_code=204)
async def release(request: Request, viewer_id: Viewer):
    await _service(request).release(viewer_id)
    return Response(status_code=204)


@router.get("/api/orbital/catalog")
async def catalog(
    request: Request, viewer_id: Annotated[str, Query(min_length=1, max_length=128)]
):
    try:
        return await _service(request).get_catalog(viewer_id)
    except LookupError as error:
        raise HTTPException(409, str(error)) from error


@router.get("/api/orbital/status")
async def status(request: Request):
    return await _service(request).get_status()


@router.post("/api/orbital/provider/resume")
async def resume(request: Request):
    return await _service(request).resume_provider()
