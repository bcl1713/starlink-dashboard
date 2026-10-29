"""Preparation is explicit; downloads only open already owned ready files."""

import asyncio
import logging
import sqlite3
from typing import Literal

from fastapi import APIRouter, HTTPException, Request

from app.mission.exporter.snapshot_inputs import SnapshotCaptureError
from app.operator.errors import OperatorError

from .archive_errors import ArchiveCapacityError, ArchiveDeadlineError
from .export_job import download_response, prepare_for_request
from .preparation_store import ExportPreparation

router = APIRouter(prefix="/api/v2/missions", tags=["Mission export preparation"])
logger = logging.getLogger(__name__)


def get_export_preparation_service(request, job_id=None, artifact_kind="planning"):
    if artifact_kind == "telemetry" or (job_id and job_id.startswith("telemetry-")):
        runtime = getattr(request.app.state, "flight_event_runtime", None)
        if runtime is None:
            raise HTTPException(503, "Live telemetry archives are unavailable")
        return runtime.preparations
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
async def start_preparation(
    request: Request,
    mission_id: str,
    artifact_kind: Literal["planning", "telemetry"] = "planning",
    allow_partial: bool = False,
    telemetry_format: Literal["full", "compact"] = "full",
):
    service = get_export_preparation_service(request, artifact_kind=artifact_kind)
    try:
        return (
            await asyncio.to_thread(
                service.start, mission_id, allow_partial=allow_partial
            )
            if artifact_kind == "telemetry"
            else await prepare_for_request(
                request, service, mission_id, telemetry_format=telemetry_format
            )
        )
    except ArchiveCapacityError as error:
        raise HTTPException(413, detail=error.detail) from error
    except ArchiveDeadlineError as error:
        raise HTTPException(504, detail=error.detail) from error
    except (OperatorError, RuntimeError, OSError, sqlite3.Error) as error:
        logger.exception("Mission %s archive capture failed", mission_id)
        raise HTTPException(
            503, detail="Mission archive capture unavailable; retry after recovery"
        ) from error
    except ValueError as error:
        raise HTTPException(409, str(error))
    except KeyError:
        raise HTTPException(404, "Mission not found")
    except SnapshotCaptureError:
        raise HTTPException(404, detail="Mission inputs are unavailable")


@router.get(
    "/{mission_id}/export-preparations/{job_id}", response_model=ExportPreparation
)
def preparation_status(request: Request, mission_id: str, job_id: str):
    return read_job(get_export_preparation_service(request, job_id), mission_id, job_id)


@router.delete(
    "/{mission_id}/export-preparations/{job_id}", response_model=ExportPreparation
)
def cancel_preparation(request: Request, mission_id: str, job_id: str):
    service = get_export_preparation_service(request, job_id)
    read_job(service, mission_id, job_id)
    return service.cancel(mission_id, job_id)


@router.get("/{mission_id}/export-preparations/{job_id}/download")
def download_preparation(request: Request, mission_id: str, job_id: str):
    service = get_export_preparation_service(request, job_id)
    job = read_job(service, mission_id, job_id)
    try:
        download = service.open_download(mission_id, job_id)
    except TimeoutError:
        raise HTTPException(410, detail="Export expired; prepare a new export")
    except ValueError:
        raise HTTPException(409, detail="Export is not ready; check preparation status")
    return download_response(download, mission_id, fingerprint=job.fingerprint)
