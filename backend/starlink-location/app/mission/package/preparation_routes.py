"""Preparation is explicit; downloads only open already owned ready files."""

from fastapi import APIRouter, HTTPException, Request

from app.mission.exporter.snapshot_inputs import SnapshotCaptureError

from .export_job import download_response
from .preparation_store import ExportPreparation

router = APIRouter(prefix="/api/v2/missions", tags=["Mission export preparation"])


def get_export_preparation_service(request):
    service = getattr(request.app.state, "export_preparation_service", None)
    if service is None:
        raise HTTPException(
            503, detail="Export preparation is unavailable; retry after startup"
        )
    return service


def read_job(service, mission_id, job_id):
    try:
        return service.status(mission_id, job_id)
    except KeyError:
        raise HTTPException(404, detail="Export preparation not found")


@router.post(
    "/{mission_id}/export-preparations",
    response_model=ExportPreparation,
    status_code=202,
)
def start_preparation(request: Request, mission_id: str):
    service = get_export_preparation_service(request)
    try:
        return service.start(mission_id)
    except SnapshotCaptureError:
        raise HTTPException(404, detail="Mission inputs are unavailable")


@router.get(
    "/{mission_id}/export-preparations/{job_id}", response_model=ExportPreparation
)
def preparation_status(request: Request, mission_id: str, job_id: str):
    return read_job(get_export_preparation_service(request), mission_id, job_id)


@router.delete(
    "/{mission_id}/export-preparations/{job_id}", response_model=ExportPreparation
)
def cancel_preparation(request: Request, mission_id: str, job_id: str):
    service = get_export_preparation_service(request)
    read_job(service, mission_id, job_id)
    return service.cancel(mission_id, job_id)


@router.get("/{mission_id}/export-preparations/{job_id}/download")
def download_preparation(request: Request, mission_id: str, job_id: str):
    service = get_export_preparation_service(request)
    job = read_job(service, mission_id, job_id)
    try:
        download = service.open_download(mission_id, job_id)
    except TimeoutError:
        raise HTTPException(410, detail="Export expired; prepare a new export")
    except ValueError:
        raise HTTPException(409, detail="Export is not ready; check preparation status")
    return download_response(download, mission_id, fingerprint=job.fingerprint)
