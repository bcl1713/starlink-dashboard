"""Single-owner transactional monotonic replay with read-only snapshots."""

import copy
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from app.models.simulation_run import RunError, RunSnapshot, SimulationRunStatus
from app.simulation.run_plan import PreparedMissionRun
from app.simulation.run_replay import ReplayFrame, project_run_frame


@dataclass(frozen=True)
class RunTick:
    expected_revision: int
    plan: PreparedMissionRun
    frame: ReplayFrame
    status: SimulationRunStatus
    start_monotonic: float


class SimulationRunRuntime:
    def __init__(
        self,
        monotonic: Callable[[], float],
        utc_now: Callable[[], datetime],
        service_mode: Literal["simulation", "live"],
    ):
        self._monotonic = monotonic
        self._utc_now = utc_now
        self._status = SimulationRunStatus(
            runtime_id=str(uuid.uuid4()),
            revision=0,
            service_mode=service_mode,
            state="idle",
            served_at=utc_now(),
        )
        self._plan: PreparedMissionRun | None = None
        self._frame: ReplayFrame | None = None
        self._start_monotonic = 0.0

    def prepare_start(self, plan: PreparedMissionRun) -> RunTick:
        if self._status.service_mode != "simulation":
            raise ValueError("Paced runs require simulation mode")
        plan = copy.deepcopy(plan)
        frame = project_run_frame(plan, plan.preview.planned_departure, None)
        now = self._utc_now()
        run = RunSnapshot(
            **plan.normalized.model_dump(),
            run_id=str(uuid.uuid4()),
            mission_id=plan.mission_id,
            leg_id=plan.leg_id,
            route_id=plan.route_id,
            plan_token=plan.preview.plan_token,
            planned_departure=plan.preview.planned_departure,
            planned_arrival=plan.preview.planned_arrival,
            simulation_time=frame.simulation_time,
            started_at=now,
            observed_at=now,
            elapsed_real_seconds=0,
            progress_percent=frame.progress_percent,
            phase=frame.phase.value,
            processed_event_count=frame.processed_event_count,
            transport_states={
                t.value: s.value for t, s in frame.transport_states.items()
            }
        )
        proposed = self._status.model_copy(
            update={
                "revision": self._status.revision + 1,
                "state": "running",
                "served_at": now,
                "run": run,
            }
        )
        return RunTick(self._status.revision, plan, frame, proposed, self._monotonic())

    def prepare_tick(self) -> RunTick | None:
        if self._status.state != "running":
            return None
        plan, previous, run = self._plan, self._frame, self._status.run
        elapsed = max(
            run.elapsed_real_seconds, self._monotonic() - self._start_monotonic, 0
        )
        seconds = min(
            plan.normalized.flight_duration_seconds,
            elapsed * plan.normalized.effective_multiplier,
        )
        frame = project_run_frame(
            plan, plan.preview.planned_departure + timedelta(seconds=seconds), previous
        )
        complete = frame.simulation_time == plan.preview.planned_arrival
        now = self._utc_now()
        candidate = run.model_copy(
            update={
                "simulation_time": frame.simulation_time,
                "observed_at": now,
                "finished_at": now if complete else None,
                "elapsed_real_seconds": elapsed,
                "completion_lateness_seconds": (
                    max(0, elapsed - run.expected_runtime_seconds) if complete else None
                ),
                "progress_percent": frame.progress_percent,
                "phase": frame.phase.value,
                "processed_event_count": frame.processed_event_count,
                "transport_states": {
                    t.value: s.value for t, s in frame.transport_states.items()
                },
            }
        )
        proposed = self._status.model_copy(
            update={
                "revision": self._status.revision + 1,
                "state": "completed" if complete else "running",
                "served_at": now,
                "run": candidate,
            }
        )
        return RunTick(
            self._status.revision, plan, frame, proposed, self._start_monotonic
        )

    def commit_tick(self, tick: RunTick) -> SimulationRunStatus:
        if tick.expected_revision != self._status.revision:
            raise ValueError("Replay tick was superseded")
        new_run = (
            self._status.run is None
            or self._status.run.run_id != tick.status.run.run_id
        )
        now = self._utc_now()
        status = tick.status
        if new_run:
            start = self._monotonic()
            status = status.model_copy(
                update={
                    "run": status.run.model_copy(
                        update={"started_at": now, "observed_at": now}
                    )
                }
            )
        else:
            start = tick.start_monotonic
            if status.state == "completed":
                elapsed = max(
                    status.run.elapsed_real_seconds, self._monotonic() - start
                )
                status = status.model_copy(
                    update={
                        "run": status.run.model_copy(
                            update={
                                "finished_at": now,
                                "elapsed_real_seconds": elapsed,
                                "completion_lateness_seconds": max(
                                    0, elapsed - status.run.expected_runtime_seconds
                                ),
                            }
                        )
                    }
                )
        self._start_monotonic = start
        self._plan = tick.plan
        self._frame = tick.frame
        self._status = status
        return self.status()

    def status(self) -> SimulationRunStatus:
        return self._status.model_copy(deep=True, update={"served_at": self._utc_now()})

    def frame(self) -> ReplayFrame | None:
        return self._frame if self._status.state in ("running", "completed") else None

    def selected_plan(self) -> PreparedMissionRun | None:
        return self._plan if self._status.state in ("running", "completed") else None

    def cancel(self, reason: str) -> SimulationRunStatus:
        if self._status.state in ("running", "completed"):
            self._terminal("cancelled", RunError(code="cancelled", message=reason))
        return self.status()

    def fail(self, code: str, message: str) -> SimulationRunStatus:
        if self._status.state == "running":
            self._terminal("failed", RunError(code=code, message=message))
        return self.status()

    def _terminal(self, state: str, error: RunError) -> None:
        run = self._status.run.model_copy(
            update={"error": error, "finished_at": self._utc_now()}
        )
        self._status = self._status.model_copy(
            update={"revision": self._status.revision + 1, "state": state, "run": run}
        )
        self._plan = None
        self._frame = None

    def clear_selection(self) -> None:
        self._plan = None
        self._frame = None
        self._status = self._status.model_copy(
            update={"revision": self._status.revision + 1, "state": "idle", "run": None}
        )

    def set_service_mode(self, mode: Literal["simulation", "live"]) -> None:
        if mode != self._status.service_mode:
            self.cancel("Service mode changed")
            self._status = self._status.model_copy(
                update={"revision": self._status.revision + 1, "service_mode": mode}
            )

    def seconds_until_next_tick(self) -> float:
        if self._status.state != "running":
            return 1.0
        remaining = self._status.run.expected_runtime_seconds - (
            self._monotonic() - self._start_monotonic
        )
        return min(1.0, max(0, remaining))
