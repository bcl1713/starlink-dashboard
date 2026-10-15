"""Explicit mission clock, independent of real observation/response timestamps."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class MissionTimeContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    runtime_id: str
    run_id: str
    revision: int
    simulation_time: datetime
    observed_at: datetime
    phase: Literal["in_flight", "post_arrival"]
    effective_multiplier: float
