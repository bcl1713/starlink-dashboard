"""Operator commands use the application's existing restricted-access boundary."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import AwareDatetime, BaseModel, Field

from app.mission.storage import load_mission_v2

router = APIRouter(prefix="/api/v2/missions", tags=["Flight events"])


class ManualEventRequest(BaseModel):
    kind: Literal["off_blocks", "takeoff", "landed", "on_blocks"]
    occurred_at: AwareDatetime
    reason: str = Field(min_length=1, max_length=1000)


class CorrectionRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    occurred_at: AwareDatetime
    reason: str = Field(min_length=1, max_length=1000)


class StopClassificationRequest(BaseModel):
    classification: Literal["intermediate", "destination_complete"]
    reason: str = Field(min_length=1, max_length=1000)


def runtime_for(request: Request, mission_id: str, leg_id: str):
    mission = load_mission_v2(mission_id)
    if not mission or not any(leg.id == leg_id for leg in mission.legs):
        raise HTTPException(404, "Mission leg not found")
    run_service = getattr(request.app.state, "simulation_run_service", None)
    if run_service and run_service.status().run:
        run_service.assert_plan_edit_allowed(mission_id, leg_id)
    runtime = getattr(request.app.state, "flight_event_runtime", None)
    if runtime is None:
        raise HTTPException(503, "Live flight-event recording is unavailable")
    return runtime


def actor_for(request: Request) -> str:
    # No built-in authentication exists in this application. Do not trust actor
    # headers or pretend a caller-supplied name establishes an authenticated user.
    return "restricted-access operator"


def event_error(error: ValueError):
    return HTTPException(409 if "revision" in str(error) else 422, str(error))


@router.get("/{mission_id}/legs/{leg_id}/flight-events")
def read_events(request: Request, mission_id: str, leg_id: str):
    runtime = runtime_for(request, mission_id, leg_id)
    return {
        "status": runtime.status(mission_id, leg_id),
        "events": runtime.events.events(mission_id, leg_id),
        "capture": {
            key: value
            for key, value in (
                runtime.archive.capture_summary(mission_id, leg_id) or {}
            ).items()
            if key not in ("samples", "events")
        },
    }


@router.post("/{mission_id}/legs/{leg_id}/flight-events")
def create_event(
    request: Request, mission_id: str, leg_id: str, body: ManualEventRequest
):
    runtime = runtime_for(request, mission_id, leg_id)
    try:
        event = runtime.events.record_manual_event(
            mission_id,
            leg_id,
            body.kind,
            body.occurred_at,
            body.reason,
            actor_for(request),
        )
        runtime.changed(mission_id, leg_id)
        return event
    except ValueError as error:
        raise event_error(error)


@router.patch("/{mission_id}/legs/{leg_id}/flight-events/{event_id}")
def correct_event(
    request: Request,
    mission_id: str,
    leg_id: str,
    event_id: str,
    body: CorrectionRequest,
):
    runtime = runtime_for(request, mission_id, leg_id)
    try:
        event = runtime.events.correct_event(
            event_id,
            body.occurred_at,
            body.reason,
            actor_for(request),
            body.expected_revision,
            mission_id,
            leg_id,
        )
        runtime.changed(mission_id, leg_id)
        return event
    except ValueError as error:
        raise event_error(error)


@router.post("/{mission_id}/legs/{leg_id}/stops/{stop_id}/classification")
def classify_stop(
    request: Request,
    mission_id: str,
    leg_id: str,
    stop_id: str,
    body: StopClassificationRequest,
):
    runtime = runtime_for(request, mission_id, leg_id)
    try:
        event = runtime.events.classify_stop(
            mission_id,
            leg_id,
            stop_id,
            body.classification,
            body.reason,
            actor_for(request),
        )
        runtime.changed(mission_id, leg_id)
        return event
    except ValueError as error:
        raise event_error(error)
