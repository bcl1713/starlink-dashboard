"""Closed wire contracts for ephemeral, backend-owned mission replay."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


StrictNumber = Annotated[FiniteFloat, Field(strict=True)]


class MultiplierPacing(ClosedModel):
    mode: Literal["multiplier"]
    multiplier: Annotated[StrictNumber, Field(ge=0.1, le=1000)]


class TargetRuntimePacing(ClosedModel):
    mode: Literal["target_runtime"]
    runtime_seconds: Annotated[StrictNumber, Field(ge=1)]


PacingInput = Annotated[
    MultiplierPacing | TargetRuntimePacing, Field(discriminator="mode")
]


class NormalizedPacing(ClosedModel):
    pacing: PacingInput
    effective_multiplier: StrictNumber
    flight_duration_seconds: StrictNumber
    expected_runtime_seconds: StrictNumber


class PacingLimits(ClosedModel):
    min_multiplier: Literal[0.1] = 0.1
    max_multiplier: Literal[1000] = 1000
    min_runtime_seconds: Literal[1] = 1


class SimulationPreview(NormalizedPacing):
    plan_token: str
    planned_departure: datetime
    planned_arrival: datetime
    limits: PacingLimits = PacingLimits()


class SimulationStart(ClosedModel):
    pacing: PacingInput
    plan_token: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


class ActivationRequest(ClosedModel):
    simulation: SimulationStart | None = None


class RunError(ClosedModel):
    code: str
    message: str


class RunSnapshot(NormalizedPacing):
    run_id: str
    mission_id: str
    leg_id: str
    route_id: str
    plan_token: str
    planned_departure: datetime
    planned_arrival: datetime
    simulation_time: datetime
    started_at: datetime
    observed_at: datetime
    finished_at: datetime | None = None
    elapsed_real_seconds: float
    completion_lateness_seconds: float | None = None
    progress_percent: float
    phase: Literal["in_flight", "post_arrival"]
    processed_event_count: int
    transport_states: dict[str, Literal["available", "degraded", "offline"]]
    error: RunError | None = None


class SimulationRunStatus(ClosedModel):
    runtime_id: str
    revision: int
    service_mode: Literal["simulation", "live"]
    state: Literal["idle", "running", "completed", "cancelled", "failed"]
    served_at: datetime
    run: RunSnapshot | None = None
