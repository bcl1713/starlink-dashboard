"""Derived-only capture and admission, without source collection or detection."""

import logging
from datetime import UTC, datetime

from app.core.metrics import frame_builder
from app.core.metrics.prometheus_metrics import FRAME_STORE
from app.core.metrics.source_admission import (
    frame_inputs_are_current,
    replay_input_identity,
    route_source_identity,
)
from app.mission.storage import get_active_leg_lock
from app.services.flight_state import get_flight_state_manager
from app.simulation.run_timing import mission_time_context, planned_poi_metrics

logger = logging.getLogger(__name__)


def refresh_current_metrics(sources, *, initial=False, now=None):
    """The callback returns current (coordinator, config, routes, POIs, replay).

    One admission covers capture/calculation/revalidation, as for the accepted
    producer. Scrapes never take this guard. Retain no manager or second numeric
    gauge store. A refresh may reuse only this source's last published acquisition;
    reset/cancelled/uncommitted source defaults are not new observations.
    """
    now = now or datetime.now(UTC)
    with get_active_leg_lock():
        expected = FRAME_STORE.read()
        try:
            coordinator, config, routes, manager, service = sources()
            identity = frame_builder.coordinator_identity(coordinator)
            config_key = config.model_dump_json()
            route = routes.get_active_route() if routes else None
            route_key = route_source_identity(route)
            status = service.status() if service else None
            plan = service.runtime.selected_plan() if service else None
            replay_frame = service.runtime.frame() if service else None
            context = mission_time_context(status) if status else None
            flight = get_flight_state_manager().get_status(
                mission_now=context.simulation_time if context else None
            )
            pois = manager.list_pois()
            # Reads above can detect an external file reload and invalidate the
            # old head. Stage against the resulting complete input revision.
            expected = FRAME_STORE.read()
            previous = expected.frame
            telemetry = getattr(coordinator, "_last_valid_telemetry", None)
            observation_key = frame_builder.model_identity(telemetry)
            if not initial and not (
                previous is not None
                and previous.identity.coordinator_id == identity
                and telemetry is not None
                and previous.identity.observation_id == observation_key
                and bool(previous.identity.replay_runtime_id) == bool(context)
                and (
                    context is None
                    or (
                        previous.identity.replay_runtime_id == context.runtime_id
                        and previous.identity.replay_run_id == context.run_id
                        and previous.identity.replay_revision == str(context.revision)
                    )
                )
            ):
                telemetry = None
            if config.mode == "live" and not coordinator.is_connected():
                telemetry = None
            from app.services.position_freshness import observation_time

            if (
                telemetry is not None
                and observation_time(telemetry.timestamp, now)[1] == "stale"
            ):
                telemetry = None
                if (
                    expected.status == "ready"
                    and expected.frame.identity.observation_id is not None
                ):
                    expected = FRAME_STORE.invalidate("source expired")
            progress = None
            replay_key = None
            replay_eta = None
            if context and plan and replay_frame:
                from app.simulation.run_runtime import RunTick

                tick = RunTick(status.revision, plan, replay_frame, status, 0)
                replay_key = replay_input_identity(service, tick)
                # The committed run owns a normalized/retimed route. Its times
                # legitimately differ from the file-backed route; do not compare
                # those models for equality or rebase the replay mission clock.
                if routes.get_active_route_id() != plan.route_id:
                    raise ValueError("Replay route is no longer active")
                route = plan.artifacts.route
                replay_eta = planned_poi_metrics(plan, replay_frame, pois)
                count = len(route.points)
                progress = (
                    replay_frame.progress_percent,
                    min(
                        int(replay_frame.progress_percent / 100 * (count - 1)),
                        count - 1,
                    ),
                )
            elif (
                telemetry is not None
                and previous is not None
                and previous.identity.route_id == frame_builder.model_identity(route)
            ):
                progress = getattr(
                    coordinator, "route_progress_snapshot", lambda: None
                )()
            inputs = frame_builder.FrameInputs(
                expected,
                telemetry=telemetry,
                config=config,
                active_route=route,
                pois=pois,
                flight_status=flight,
                mission_context=context,
                progress=progress,
                replay_eta_metrics=replay_eta,
                coordinator_id=identity,
                now=now,
            )
            frame = frame_builder.prepare_frame(inputs, admit_observation=False)
            current = sources()
            if (
                current[0] is not coordinator
                or current[1] is not config
                or current[2] is not routes
                or current[3] is not manager
                or current[4] is not service
                or frame_builder.coordinator_identity(coordinator) != identity
                or config.model_dump_json() != config_key
                or frame_builder.model_identity(
                    getattr(coordinator, "_last_valid_telemetry", None)
                )
                != observation_key
                or route_source_identity(routes.get_active_route() if routes else None)
                != route_key
                or not frame_inputs_are_current(frame, route, manager)
                or (
                    service is not None and service.status().revision != status.revision
                )
                or (
                    replay_key is not None
                    and replay_input_identity(service, tick) != replay_key
                )
            ):
                FRAME_STORE.fail(expected, "derived source superseded")
                return False
            if expected.status == "ready" and frame == expected.frame:
                return True
            return FRAME_STORE.publish(expected, frame)
        except Exception:
            FRAME_STORE.fail(expected, "derived preparation failed")
            logger.exception("Derived metric refresh failed")
            return False
