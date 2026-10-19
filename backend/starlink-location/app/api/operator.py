"""Gated public Operator API on the existing restricted LAN boundary."""

import sqlite3
from time import perf_counter
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import Field, ValidationError
from starlette.concurrency import run_in_threadpool

from app.operator.api_models import JournalTransition, PublicCreate, PublicUpdate
from app.operator.catalog import Catalog, CatalogStore
from app.operator.common import Identifier, RecordId, SchemaVersion, StrictModel
from app.operator.errors import OperatorError
from app.operator.models import (
    CreateRecord,
    RecordFilter,
    RecordType,
    RemoveRecord,
    RestoreRecord,
    Scope,
    UpdateRecord,
)
from app.operator.read_metadata import read_page, read_record
from app.operator.runtime import enabled, runtime_for


def error_response(error):
    code = error.code
    status = (
        404
        if code in ("operator_disabled", "record_not_found")
        else (
            422
            if code in ("validation_error", "invalid_cursor")
            else (
                409
                if code
                in (
                    "version_conflict",
                    "idempotency_conflict",
                    "dependency_conflict",
                    "invalid_transition",
                    "store_epoch_changed",
                    "event_snapshot_changed",
                    "store_context_changed",
                    "simulation_run_required",
                )
                else 503
            )
        )
    )
    body = {
        "code": code,
        "message": {
            404: "Operator resource not found",
            422: "Invalid Operator input",
            409: "Operator state requires reconciliation",
            503: "Operator store unavailable",
        }[status],
        "retryable": error.retryable,
    }
    for name in ("fields", "current_version", "record_ids"):
        if (value := getattr(error, name)) is not None:
            body[name] = value
    headers = {"Cache-Control": "no-store"}
    if code == "store_busy":
        headers["Retry-After"] = "1"
    return JSONResponse(
        {"error": body, "request_id": str(uuid4())}, status_code=status, headers=headers
    )


def gate(request):
    with runtime_for(request) as runtime:
        if runtime is None or not enabled(runtime):
            raise OperatorError("operator_disabled")


class OperatorRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handle(request):
            started = perf_counter()
            gate_finished = started
            try:
                await run_in_threadpool(gate, request)
                gate_finished = perf_counter()
                if request.method in ("POST", "PUT"):
                    chunks, size = [], 0
                    async for chunk in request.stream():
                        size += len(chunk)
                        if size > 65536:
                            raise OperatorError(
                                "validation_error",
                                fields={"body": "Body exceeds 64 KiB"},
                            )
                        chunks.append(chunk)
                    request._body = b"".join(chunks)
                response = await original(request)
            except (RequestValidationError, ValidationError) as error:
                # Pydantic's default response echoes inputs and exception text.
                fields = {}
                for item in error.errors():
                    # Unknown JSON keys are caller content too; do not reflect
                    # their names in validation responses.
                    location = (
                        item["loc"][:-1]
                        if item["type"] == "extra_forbidden"
                        else item["loc"]
                    )
                    fields[".".join(map(str, location)) or "body"] = "Invalid value"
                response = error_response(
                    OperatorError("validation_error", fields=fields)
                )
            except OperatorError as error:
                response = error_response(error)
            except (sqlite3.Error, OSError):
                response = error_response(OperatorError("store_unavailable"))
            response.headers["Server-Timing"] = ", ".join(
                filter(
                    None,
                    [
                        response.headers.get("Server-Timing"),
                        f"operator_gate;dur={(gate_finished - started) * 1000:.3f}",
                        f"operator_request;dur={(perf_counter() - started) * 1000:.3f}",
                    ],
                )
            )
            response.headers["Cache-Control"] = "no-store"
            return response

        return handle


router = APIRouter(
    prefix="/api/v2/operator", tags=["Operator"], route_class=OperatorRoute
)


def require_service(runtime):
    if runtime is None or not enabled(runtime):
        raise OperatorError("operator_disabled")
    if runtime.service is None:
        raise OperatorError(runtime.health().error_code or "store_unavailable")
    return runtime.service


def mutate(request, command, key, epoch):
    started = perf_counter()
    with runtime_for(request) as runtime:
        admitted = perf_counter()
        result = require_service(runtime).execute_result(
            command,
            key=key,
            epoch=epoch,
            expected_replay=(
                (request.headers.get("X-Operator-Replay-Id") or "missing")
                if runtime.settings.mission_journal
                else None
            ),
            writable_types={
                "journal_entry",
                "call",
                "conference",
                "participation",
                "issue",
                "transport_decision",
            },
        )
        return JSONResponse(
            result.receipt.canonical_response,
            status_code=result.receipt.response_status,
            headers={
                "Idempotency-Replayed": str(result.replayed).lower(),
                "Server-Timing": (
                    f"operator_binding;dur={(admitted - started) * 1000:.3f}, "
                    f"operator_command;dur={(perf_counter() - admitted) * 1000:.3f}"
                ),
            },
        )


@router.get("/health")
def health(request: Request):
    with runtime_for(request) as runtime:
        if runtime is None or not enabled(runtime):
            raise OperatorError("operator_disabled")
        state = runtime.health()
        return JSONResponse(
            dict(state.model_dump(mode="json"), enabled=True),
            status_code=200 if state.ready else 503,
        )


@router.get("/context")
def operating_context(request: Request):
    """Project the existing mission/flight authorities; owns no mission state."""
    from app.mission.active_context import resolve_active_mission_leg_context
    from app.services.flight_state import get_flight_state_manager

    manager = getattr(request.app.state, "route_manager", None)
    resolution = resolve_active_mission_leg_context(manager) if manager else None
    context = resolution.context if resolution else None
    with runtime_for(request) as runtime:
        state = runtime.health()
        flight = get_flight_state_manager().get_status()
        run_service = getattr(request.app.state, "simulation_run_service", None)
        status = run_service.status() if run_service else None
        run = (
            status.run if status and status.state in ("running", "completed") else None
        )
        if (
            context
            and state.source_mode == "simulation"
            and run
            and (
                run.mission_id != context.parent_mission_id
                or run.leg_id != context.leg.id
            )
        ):
            context = None
        return {
            "state": (
                "available"
                if context
                else (
                    resolution.state
                    if resolution and resolution.context is None
                    else "unavailable"
                )
            ),
            "mission_id": context.parent_mission_id if context else None,
            "mission_name": context.parent_mission.name if context else None,
            "leg_id": context.leg.id if context else None,
            "leg_name": context.leg.name if context else None,
            "phase": (
                (
                    run.phase
                    if run and state.source_mode == "simulation"
                    else flight.phase.value
                )
                if context
                else None
            ),
            "source_mode": state.source_mode,
            "replay_run_id": state.replay_run_id,
            "operating_context_id": state.operating_context_id,
        }


class ProvisionRequest(StrictModel):
    schema_version: SchemaVersion = 1
    expected_source_mode: Literal["live", "simulation"]
    expected_simulation_run_id: str | None = Field(default=None, max_length=200)


@router.post("/provision")
def provision(request: Request, body: ProvisionRequest):
    with runtime_for(request) as runtime:
        if runtime is None or not enabled(runtime):
            raise OperatorError("operator_disabled")
        state = runtime.provision(
            expected_mode=body.expected_source_mode,
            expected_run=body.expected_simulation_run_id,
        )
        return dict(state.model_dump(mode="json"), enabled=True)


@router.post("/records")
def create(
    request: Request,
    body: PublicCreate,
    key: str = Header(alias="Idempotency-Key"),
    epoch: str = Header(alias="X-Operator-Store-Epoch"),
):
    return mutate(request, CreateRecord(**body.model_dump()), key, epoch)


@router.put("/records/{record_id}")
def update(
    request: Request,
    record_id: RecordId,
    body: PublicUpdate,
    key: str = Header(alias="Idempotency-Key"),
    epoch: str = Header(alias="X-Operator-Store-Epoch"),
):
    return mutate(
        request, UpdateRecord(record_id=record_id, **body.model_dump()), key, epoch
    )


@router.post("/records/{record_id}/remove")
def remove(
    request: Request,
    record_id: RecordId,
    body: JournalTransition,
    key: str = Header(alias="Idempotency-Key"),
    epoch: str = Header(alias="X-Operator-Store-Epoch"),
):
    return mutate(
        request, RemoveRecord(record_id=record_id, **body.model_dump()), key, epoch
    )


@router.post("/records/{record_id}/restore")
def restore(
    request: Request,
    record_id: RecordId,
    body: JournalTransition,
    key: str = Header(alias="Idempotency-Key"),
    epoch: str = Header(alias="X-Operator-Store-Epoch"),
):
    return mutate(
        request, RestoreRecord(record_id=record_id, **body.model_dump()), key, epoch
    )


@router.get("/records")
def records(
    request: Request,
    mission_id: Identifier,
    scope: Scope | None = None,
    leg_id: Identifier | None = None,
    record_type: RecordType | None = None,
    include_removed: bool = False,
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None, max_length=8192),
):
    with runtime_for(request) as runtime:
        service = require_service(runtime)
        filters = RecordFilter(
            mission_id=mission_id,
            scope=scope,
            leg_id=leg_id,
            record_type=record_type,
            include_removed=include_removed,
        )
        return read_page(service.list(filters, limit=limit, cursor=cursor), runtime)


@router.get("/records/{record_id}")
def record(request: Request, record_id: RecordId):
    with runtime_for(request) as runtime:
        return read_record(require_service(runtime).get(record_id), runtime)


@router.get("/records/{record_id}/history")
def history(
    request: Request,
    record_id: RecordId,
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None, max_length=8192),
):
    with runtime_for(request) as runtime:
        return read_page(
            require_service(runtime).history(record_id, limit=limit, cursor=cursor),
            runtime,
        )


@router.get("/journal")
def journal(
    request: Request,
    mission_id: Identifier,
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None, max_length=8192),
):
    with runtime_for(request) as runtime:
        return read_page(
            require_service(runtime).journal(mission_id, limit=limit, cursor=cursor),
            runtime,
        )


from .operator_events import make_router

router.include_router(make_router())


@router.get("/transport-catalog")
def read_transport_catalog(request: Request):
    with runtime_for(request) as runtime:
        return CatalogStore(runtime.settings.root / "transport-catalog.json").read()


@router.put("/transport-catalog")
def save_transport_catalog(request: Request, catalog: Catalog):
    with runtime_for(request) as runtime:
        return CatalogStore(runtime.settings.root / "transport-catalog.json").update(
            catalog
        )
