"""Serialize replay planning, collection, and lifecycle with leg activation."""

from collections.abc import Callable

from fastapi import HTTPException

from app.core.metrics.frames import GaugeFrame
from app.core.metrics.source_admission import replay_input_identity
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
from app.simulation.run_wakeup import ReplayWakeup


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
        self.publish: Callable[[TelemetryData, RunTick], GaugeFrame | None] | None = (
            None
        )
        self.wakeup: ReplayWakeup | None = None

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
        publish: Callable[[TelemetryData, RunTick], GaugeFrame | None],
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
            from app.core.metrics.prometheus_metrics import FRAME_STORE

            expected = FRAME_STORE.read()
            from app.core.metrics.frame_builder import coordinator_identity

            config = (
                coordinator_identity(coordinator),
                coordinator.get_config().model_dump_json(),
            )
            checkpoint = coordinator.checkpoint_telemetry()
            flight = get_flight_state_manager()
            flight_checkpoint = flight.checkpoint()
            try:
                telemetry = coordinator.update(replay_frame=tick.frame)
                flight.apply_simulation_frame(tick.plan, tick.frame)
                expected = FRAME_STORE.read()
                inputs = replay_input_identity(self, tick)
                frame = publish(telemetry, tick)
                if advancing:
                    self.runtime.commit_tick(tick)
                self.publish_committed_metrics(
                    expected, frame, tick, coordinator, config, telemetry, inputs
                )
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
                FRAME_STORE.fail(expected, "replay collection failed")
                self.runtime.fail(
                    "collection_error",
                    "Replay collection failed; stop and restart the run",
                )
                raise

    def publish_committed_metrics(
        self, expected, frame, tick, coordinator, config, telemetry, inputs
    ):
        """Publish only an admitted, committed replay candidate; caller holds admission.

        The existing repository gate excludes config/route/POI/mission writers
        through preparation and commit. Runtime and source are rechecked directly
        before the pointer swap. A stale CAS cannot mask or replace a newer head.
        Legacy callbacks returning None do not produce coupled metrics.
        """
        if frame is None:
            return False
        from app.core.metrics.frame_builder import coordinator_identity
        from app.core.metrics.prometheus_metrics import FRAME_STORE

        status = self.status()
        identity = frame.identity
        if (
            self.runtime.selected_plan() is not tick.plan
            or self.runtime.frame() is not tick.frame
            or identity.replay_runtime_id != status.runtime_id
            or identity.replay_revision != str(status.revision)
            or status.run is None
            or identity.replay_run_id != status.run.run_id
            or identity.replay_mission_time != status.run.simulation_time.timestamp()
            or (
                coordinator_identity(coordinator),
                coordinator.get_config().model_dump_json(),
            )
            != config
            or coordinator.get_current_telemetry() is not telemetry
            or telemetry.timestamp.timestamp() != identity.observation_timestamp
            or replay_input_identity(self, tick) != inputs
            or (
                identity.coordinator_id is not None
                and identity.coordinator_id != coordinator_identity(coordinator)
            )
        ):
            FRAME_STORE.fail(expected, "replay source superseded")
            return False
        return FRAME_STORE.publish(expected, frame)

    def cancel_owned(self, mission_id: str, leg_id: str | None, reason: str) -> None:
        with get_active_leg_lock():
            run = self.status().run
            if (
                run
                and run.mission_id == mission_id
                and (leg_id is None or run.leg_id == leg_id)
            ):
                previous_revision = self.status().revision
                self.runtime.cancel(reason)
                if self.status().revision != previous_revision:
                    from app.core.metrics.prometheus_metrics import FRAME_STORE

                    head = FRAME_STORE.read()
                    identity = head.frame.identity if head.frame else None
                    if (
                        identity is not None
                        and identity.replay_runtime_id == self.status().runtime_id
                        and identity.replay_run_id == run.run_id
                    ):
                        FRAME_STORE.invalidate("replay source cancelled")

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
