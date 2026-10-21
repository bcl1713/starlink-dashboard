"""Reuse frozen synthetic inputs; add only the read-only acceptance adapter."""

from strict_performance.fixture import app, main

from app.core.metrics import prometheus_metrics
from app.mission.storage import get_active_leg_lock
from performance.state import capture


@app.get("/api/_acceptance/availability/state")
def availability_state():
    with get_active_leg_lock():
        return capture(main, prometheus_metrics)
