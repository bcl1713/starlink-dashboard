"""Typed mission settings and operational action API, independent of Operator storage."""

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.mission.availability_models import Transport
from app.mission.availability_service import AvailabilityService
from app.mission.planning.errors import PlanningFailure

router = APIRouter()


class AvailabilityCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0)
    command_id: str = Field(min_length=1, max_length=200)


class AvailabilitySettings(AvailabilityCommand):
    defaults: dict[Transport, StrictBool] | None = None
    leg_overrides: dict[str, dict[Transport, StrictBool]] | None = None


class AvailabilityAction(AvailabilityCommand):
    transport: Transport
    action: Literal["unavailable", "restore"]
    reason: str | None = Field(default=None, max_length=2000)


def service_for(request):
    from app.mission import storage
    from app.mission.planning.store import PlanningStore

    state = request.app.state
    planning = getattr(state, "planning_service", None)
    store = planning.store if planning else None
    if store is None or store.root != storage.MISSIONS_DIR.resolve():
        store = PlanningStore(
            storage.MISSIONS_DIR, state.route_manager, state.poi_manager
        )

    def current_mode():
        mode = getattr(state, "availability_source_mode", None)
        if mode is not None:
            return mode
        # The source coordinator remains authoritative with Operator storage disabled.
        coordinator = getattr(state, "coordinator", None)
        config = coordinator.get_config() if coordinator is not None else None
        if config is not None:
            return config.mode
        runtime = getattr(state, "operator_runtime", None)
        if runtime is not None:
            return runtime.health().source_mode
        run_service = getattr(state, "simulation_run_service", None)
        return (
            getattr(run_service.status(), "service_mode", "live")
            if run_service
            else "live"
        )

    return AvailabilityService(
        store,
        clock=getattr(state, "availability_clock", None),
        run_service=lambda: getattr(state, "simulation_run_service", None),
        source_mode=current_mode,
    )


async def invoke(function, *args, **kwargs):
    try:
        return await asyncio.to_thread(function, *args, **kwargs)
    except PlanningFailure as exc:
        raise HTTPException(
            exc.status_code, detail=exc.error.model_dump(mode="json")
        ) from exc


@router.get("/{mission_id}/availability")
async def read(mission_id: str, request: Request):
    return await invoke(service_for(request).read, mission_id)


@router.put("/{mission_id}/availability")
async def settings(mission_id: str, command: AvailabilitySettings, request: Request):
    return await invoke(service_for(request).command, mission_id, command)


@router.post("/{mission_id}/availability/actions")
async def action(mission_id: str, command: AvailabilityAction, request: Request):
    return await invoke(service_for(request).command, mission_id, command, action=True)
