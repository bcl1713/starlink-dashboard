# ruff: noqa: I001
# Fixture initialization must precede application instrumentation imports.
"""Instrumentation-off control with the same frozen capture and diagnostic URL."""

import time
from performance.fixture import app, main
from performance.state import capture
from app.core.metrics import prometheus_metrics as metrics
from app.mission.storage import get_active_leg_lock


@app.get("/api/_diagnostic/state")
def state():
    with get_active_leg_lock():
        result = capture(main, metrics)
        result["diagnostic_capture_ns"] = time.monotonic_ns()
        return result
