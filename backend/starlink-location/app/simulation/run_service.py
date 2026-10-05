"""Serialize replay planning, collection, and lifecycle with leg activation."""

from collections.abc import Callable

from fastapi import HTTPException

from app.mission.models import MissionLeg
from app.mission.storage import get_active_leg_lock, load_mission_v2
from app.models.simulation_run import PacingInput, SimulationStart
from app.models.telemetry import TelemetryData
from app.satellites.coverage import CoverageSampler
from app.services.flight_state import get_flight_state_manager
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from app.simulation.coordinator import SimulationCoordinator
from app.simulation.run_plan import (
    PreparedMissionRun,
    SimulationValidationError,
    prepare_mission_run,
)
from app.simulation.run_runtime import RunTick, SimulationRunRuntime


class SimulationRunService:
    def __init__(
        self,
        runtime: SimulationRunRuntime,
        route_manager: RouteManager,
        poi_manager: POIManager,
        coverage_sampler: CoverageSampler | None = None,
    ):
        self.runtime = runtime
        self.route_manager = route_manager
        self.poi_manager = poi_manager
        self.coverage_sampler = coverage_sampler
        self.coordinator: SimulationCoordinator | None = None
        self.publish: Callable[[TelemetryData, RunTick], None] | None = None

    def _assert_mode(self):
        if self.runtime.status().service_mode != "simulation" or (
            self.coordinator is not None and self.coordinator.mode != "simulation"
        ):
            raise HTTPException(
                409,
                detail={
                    "message": "Paced runs require simulation mode",
                    "simulation_run": self.status().model_dump(mode="json"),
                },
            )

    def prepare_plan(
        self, mission_id: str, leg: MissionLeg, pacing: PacingInput
    ) -> PreparedMissionRun:
        self._assert_mode()
        try:
            return prepare_mission_run(
                mission_id,
                leg,
                pacing,
                self.route_manager,
                self.poi_manager,
                self.coverage_sampler,
            )
        except SimulationValidationError as exc:
            raise HTTPException(
                422,
                detail=[
                    {"loc": ["body", exc.field], "msg": str(exc), "type": "value_error"}
                ],
            ) from exc

    def preview(self, mission_id: str, leg_id: str, pacing: PacingInput):
        with get_active_leg_lock():
            mission = load_mission_v2(mission_id)
            if mission is None:
                raise HTTPException(404, "Mission not found")
            leg = next((leg for leg in mission.legs if leg.id == leg_id), None)
            if leg is None:
                raise HTTPException(404, "Leg not found")
            return self.prepare_plan(mission_id, leg, pacing).preview

    def prepare_start(
        self, mission_id: str, leg: MissionLeg, request: SimulationStart
    ) -> RunTick:
        plan = self.prepare_plan(mission_id, leg, request.pacing)
        if plan.preview.plan_token != request.plan_token:
            raise HTTPException(
                409,
                detail={
                    "message": "Plan changed; refresh the preview before starting",
                    "simulation_run": self.status().model_dump(mode="json"),
                },
            )
        return self.runtime.prepare_start(plan)

    def collect(
        self,
        coordinator: SimulationCoordinator,
        publish: Callable[[TelemetryData, RunTick], None],
    ) -> TelemetryData | None:
        with get_active_leg_lock():
            plan = self.runtime.selected_plan()
            if plan is None:
                return None
            tick = self.runtime.prepare_tick()
            advancing = tick is not None
            if tick is None:
                tick = RunTick(
                    self.status().revision, plan, self.runtime.frame(), self.status(), 0
                )
            checkpoint = coordinator.checkpoint_telemetry()
            flight = get_flight_state_manager()
            flight_checkpoint = flight.checkpoint()
            try:
                telemetry = coordinator.update(replay_frame=tick.frame)
                publish(telemetry, tick)
                if advancing:
                    self.runtime.commit_tick(tick)
                return telemetry
            except (
                RuntimeError,
                ValueError,
                OSError,
                TypeError,
                AttributeError,
                KeyError,
                LookupError,
            ):
                coordinator.restore_telemetry(checkpoint)
                flight.restore_checkpoint(flight_checkpoint)
                from app.core.metrics import clear_telemetry_metrics

                clear_telemetry_metrics()
                self.runtime.fail(
                    "collection_error",
                    "Replay collection failed; stop and restart the run",
                )
                raise

    def cancel_owned(self, mission_id: str, leg_id: str | None, reason: str) -> None:
        with get_active_leg_lock():
            run = self.status().run
            if (
                run
                and run.mission_id == mission_id
                and (leg_id is None or run.leg_id == leg_id)
            ):
                self.runtime.cancel(reason)

    def assert_plan_edit_allowed(self, mission_id: str, leg_id: str | None) -> None:
        run = self.status().run
        if (
            self.status().state == "running"
            and run.mission_id == mission_id
            and (leg_id is None or run.leg_id == leg_id)
        ):
            raise HTTPException(
                409,
                detail={
                    "message": "Stop the paced run before editing its plan",
                    "simulation_run": self.status().model_dump(mode="json"),
                },
            )

    def status(self):
        return self.runtime.status()

    def close(self):
        with get_active_leg_lock():
            self.runtime.cancel("Service stopped")
