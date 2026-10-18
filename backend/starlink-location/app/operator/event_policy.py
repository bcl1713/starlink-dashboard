"""Provisional Operator notification tuning, independent of prediction physics."""

import os
from typing import Annotated

from pydantic import Field

from .common import StrictModel

PositiveSeconds = Annotated[float, Field(gt=0, allow_inf_nan=False)]
CaptureCount = Annotated[int, Field(ge=2, strict=True)]


class EventPolicy(StrictModel):
    model_shift_seconds: PositiveSeconds = 300.0
    model_stable_captures: CaptureCount = 2
    model_capture_spacing_seconds: PositiveSeconds = 15.0
    model_escalation_captures: CaptureCount = 2

    @classmethod
    def from_env(cls):
        values = {}
        for name in cls.model_fields:
            value = os.getenv("OPERATOR_EVENT_" + name.upper())
            if value is not None:
                values[name] = int(value) if name.endswith("captures") else float(value)
        return cls(**values)
