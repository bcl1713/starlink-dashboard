"""Metric update functions for telemetry and mission data."""

# FR-004: File exceeds 300 lines (604 lines) because metric updates coordinate
# across telemetry calculations, mission timeline state, flight phase logic, and
# POI ETA projections. Refactoring would split interdependent calculations into
# separate modules creating circular dependencies. Deferred to v0.4.0.

import logging
import math
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from app.mission.input_admission import model_input_write
from app.services.position_freshness import position_observation, speed_is_fresh

if TYPE_CHECKING:
    from app.core.config import ConfigManager
    from app.core.metrics.frames import GaugeFrame
    from app.models.mission_time import MissionTimeContext
    from app.models.route import ParsedRoute
    from app.models.telemetry import TelemetryData
    from app.services.poi_manager import POIManager
    from app.simulation.run_plan import PreparedMissionRun
    from app.simulation.run_replay import ReplayFrame

from app.core.metrics.prometheus_metrics import (
    mission_active_info,
    mission_comm_state,
    mission_critical_seconds,
    mission_degraded_seconds,
    mission_next_conflict_seconds,
    mission_phase_state,
    mission_timeline_generated_timestamp,
    simulation_updates_total,
    starlink_dish_outage_active,
    starlink_dish_thermal_throttle,
    starlink_dish_uptime_seconds,
    starlink_network_latency_ms,
    starlink_network_throughput_down_mbps,
    starlink_network_throughput_up_mbps,
)

logger = logging.getLogger(__name__)


def _observe_flight_status(
    telemetry,
    active_route,
    flight_events_managed,
    mission_context,
    simulation_plan,
    simulation_frame,
):
    flight_state = None
    flight_status = None
    try:
        from app.services.flight_state import get_flight_state_manager

        flight_state = get_flight_state_manager()
        if mission_context is not None:
            flight_state.apply_simulation_frame(simulation_plan, simulation_frame)
        now = datetime.now(UTC)
        observed_at, position_state = position_observation(
            telemetry.position.latitude,
            telemetry.position.longitude,
            telemetry.position.observed_at,
            now,
        )
        detection_ready = position_state == "fresh" and speed_is_fresh(
            telemetry.position.speed, telemetry.position.speed_observed_at, now
        )
        if mission_context is not None or flight_events_managed:
            detection_ready = False
        if not detection_ready:
            flight_state.reset_detection()
        else:
            detection_ready = flight_state.observe_detection(observed_at)

        # Automatic departure detection (speed-based)
        try:
            if detection_ready:
                flight_state.check_departure(
                    telemetry.position.speed, observed_at=observed_at
                )
        except (
            RuntimeError,
            ValueError,
            OSError,
            KeyError,
            TypeError,
            AttributeError,
            LookupError,
            ConnectionError,
            TimeoutError,
            ImportError,
            EOFError,
        ) as departure_error:  # pragma: no cover - defensive guard
            logger.warning(f"Departure detection error: {departure_error}")

        # Automatic arrival detection when an active route is available
        if active_route and active_route.points and detection_ready:
            try:
                from app.services.kml.geometry import haversine_distance

                # Projected route remainder can be zero far beyond or beside
                # the final endpoint. Arrival requires actual proximity to it.
                destination = active_route.points[-1]
                distance_to_destination = haversine_distance(
                    telemetry.position.latitude,
                    telemetry.position.longitude,
                    destination.latitude,
                    destination.longitude,
                )
                flight_state.check_arrival(
                    distance_to_destination,
                    telemetry.position.speed,
                    observed_at=observed_at,
                )
            except (
                RuntimeError,
                ValueError,
                OSError,
                KeyError,
                TypeError,
                AttributeError,
                LookupError,
                ConnectionError,
                TimeoutError,
                ImportError,
                EOFError,
            ) as arrival_error:  # pragma: no cover - defensive guard
                logger.debug(f"Arrival detection skipped: {arrival_error}")

        flight_status = (
            flight_state.get_status(mission_now=mission_context.simulation_time)
            if mission_context
            else flight_state.get_status()
        )
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        LookupError,
        ConnectionError,
        TimeoutError,
        ImportError,
        EOFError,
    ) as state_error:  # pragma: no cover - defensive guard
        if mission_context is not None:
            raise
        logger.warning(f"Flight state manager unavailable: {state_error}")

    if flight_status is None:
        from app.services.flight_state import get_flight_state_manager

        flight_status = (
            get_flight_state_manager().get_status(
                mission_now=mission_context.simulation_time
            )
            if mission_context
            else get_flight_state_manager().get_status()
        )
    if active_route is not None:
        from app.models.route import RouteTimingProfile

        if active_route.timing_profile is None:
            active_route.timing_profile = RouteTimingProfile()
        active_route.timing_profile.flight_status = flight_status.phase.value
        active_route.timing_profile.actual_departure_time = flight_status.departure_time
        active_route.timing_profile.actual_arrival_time = flight_status.arrival_time
    return flight_status


def _observe_independent_metrics(telemetry, config, simulation_plan, simulation_frame):
    from app.core.labels import get_mode_label, get_telemetry_status_label

    mode = get_mode_label(config) if config else "unknown"
    status = get_telemetry_status_label(telemetry)
    for field, histogram in (
        ("latency_ms", starlink_network_latency_ms),
        ("throughput_down_mbps", starlink_network_throughput_down_mbps),
        ("throughput_up_mbps", starlink_network_throughput_up_mbps),
    ):
        if getattr(getattr(telemetry, "metric_availability", None), field, False):
            histogram.labels(mode=mode, status=status).observe(
                getattr(telemetry.network, field)
            )
    if simulation_plan is not None and simulation_frame is not None:
        plan, frame = simulation_plan, simulation_frame
        mission_phase_state.labels(mission_id=plan.mission_id).set(
            2 if frame.phase.value == "post_arrival" else 1
        )
        for transport, state in frame.transport_states.items():
            mission_comm_state.labels(
                mission_id=plan.mission_id, transport=transport.value
            ).set({"available": 0, "degraded": 1, "offline": 2}[state.value])
        conflict = next(
            (
                event
                for event in plan.replay_events[frame.processed_event_count :]
                if event.severity in ("warning", "critical")
            ),
            None,
        )
        mission_next_conflict_seconds.labels(mission_id=plan.mission_id).set(
            (conflict.timestamp - frame.simulation_time).total_seconds()
            if conflict
            else -1
        )


@model_input_write
def prepare_metrics_from_telemetry(
    telemetry: Optional["TelemetryData"],
    config: Optional["ConfigManager"] = None,
    active_route: Optional["ParsedRoute"] = None,
    poi_manager: Optional["POIManager"] = None,
    *,
    flight_events_managed: bool = False,
    mission_context: Optional["MissionTimeContext"] = None,
    simulation_plan: Optional["PreparedMissionRun"] = None,
    simulation_frame: Optional["ReplayFrame"] = None,
    route_progress: tuple[float, int] | None = None,
    coordinator_id: str | None = None,
    _captured_head=None,
) -> "GaugeFrame | None":
    """Account for one accepted observation and return a private complete frame.

    The producer owns repository admission and publication. Replay owners defer
    publication until runtime commit. No retry or derived refresh calls this API.
    """
    return _prepare_metrics_from_telemetry_admitted(
        telemetry,
        config,
        active_route,
        poi_manager,
        flight_events_managed=flight_events_managed,
        mission_context=mission_context,
        simulation_plan=simulation_plan,
        simulation_frame=simulation_frame,
        route_progress=route_progress,
        coordinator_id=coordinator_id,
        _captured_head=_captured_head,
    )


def _prepare_metrics_from_telemetry_admitted(
    telemetry: Optional["TelemetryData"],
    config: Optional["ConfigManager"] = None,
    active_route: Optional["ParsedRoute"] = None,
    poi_manager: Optional["POIManager"] = None,
    *,
    flight_events_managed: bool = False,
    mission_context: Optional["MissionTimeContext"] = None,
    simulation_plan: Optional["PreparedMissionRun"] = None,
    simulation_frame: Optional["ReplayFrame"] = None,
    route_progress: tuple[float, int] | None = None,
    coordinator_id: str | None = None,
    _captured_head=None,
) -> "GaugeFrame | None":
    """Account for one accepted observation and return a private complete frame.

    The producer owns repository admission and publication. Replay owners defer
    publication until runtime commit. No retry or derived refresh calls this API.
    """
    from app.core import eta_service
    from app.core.metrics.frame_builder import FrameInputs, prepare_frame
    from app.core.metrics.prometheus_metrics import FRAME_STORE

    if telemetry is None:
        from app.services.flight_state import get_flight_state_manager

        get_flight_state_manager().reset_detection()
        return
    try:
        _observe_independent_metrics(
            telemetry, config, simulation_plan, simulation_frame
        )
        flight_status = _observe_flight_status(
            telemetry,
            active_route,
            flight_events_managed,
            mission_context,
            simulation_plan,
            simulation_frame,
        )
        manager = (
            poi_manager if poi_manager is not None else eta_service.get_poi_manager()
        )
        pois = manager.list_pois()
        replay_eta = None
        if simulation_plan is not None and simulation_frame is not None:
            from app.simulation.run_timing import planned_poi_metrics

            replay_eta = planned_poi_metrics(simulation_plan, simulation_frame, pois)
            count = len(simulation_plan.artifacts.route.points)
            route_progress = (
                simulation_frame.progress_percent,
                min(
                    int(simulation_frame.progress_percent / 100 * (count - 1)),
                    count - 1,
                ),
            )
        expected = FRAME_STORE.read()
        if _captured_head is not None:
            _captured_head(expected)
        inputs = FrameInputs(
            expected,
            telemetry=telemetry,
            config=config,
            active_route=active_route,
            pois=pois,
            flight_status=flight_status,
            mission_context=mission_context,
            progress=route_progress,
            replay_eta_metrics=replay_eta,
            now=datetime.now(UTC),
            coordinator_id=coordinator_id,
        )
        return prepare_frame(inputs, admit_observation=True)
    finally:
        # Independent accounting belongs to acceptance, even if optional frame
        # preparation fails or its eventual CAS loses. Never repeat it on retry.
        simulation_updates_total.inc()


def update_metrics_from_telemetry(
    telemetry: Optional["TelemetryData"],
    config: Optional["ConfigManager"] = None,
    active_route: Optional["ParsedRoute"] = None,
    poi_manager: Optional["POIManager"] = None,
    *,
    flight_events_managed: bool = False,
    mission_context: Optional["MissionTimeContext"] = None,
    simulation_plan: Optional["PreparedMissionRun"] = None,
    simulation_frame: Optional["ReplayFrame"] = None,
    route_progress: tuple[float, int] | None = None,
    coordinator_id: str | None = None,
    source_is_current: Callable[[], bool] | None = None,
) -> None:
    """Publish one admitted observation; source writers use the same admission.

    Only the FrameStore reference operations take its short pointer mutex.
    Repository admission serializes accepted calculation with model/source writes;
    Prometheus readers never enter it. Independent observations are not rolled back.
    """
    from app.core.metrics.source_admission import frame_inputs_are_current
    from app.mission.storage import get_active_leg_lock

    with get_active_leg_lock():
        if source_is_current is not None and not source_is_current():
            return

        def final_validation(frame):
            return (
                source_is_current is None or source_is_current()
            ) and frame_inputs_are_current(frame, active_route, poi_manager)

        _update_metrics_from_telemetry_admitted(
            telemetry,
            config,
            active_route,
            poi_manager,
            flight_events_managed=flight_events_managed,
            mission_context=mission_context,
            simulation_plan=simulation_plan,
            simulation_frame=simulation_frame,
            route_progress=route_progress,
            coordinator_id=coordinator_id,
            final_validation=final_validation,
        )


def _update_metrics_from_telemetry_admitted(
    telemetry: Optional["TelemetryData"],
    config: Optional["ConfigManager"] = None,
    active_route: Optional["ParsedRoute"] = None,
    poi_manager: Optional["POIManager"] = None,
    *,
    flight_events_managed: bool = False,
    mission_context: Optional["MissionTimeContext"] = None,
    simulation_plan: Optional["PreparedMissionRun"] = None,
    simulation_frame: Optional["ReplayFrame"] = None,
    route_progress: tuple[float, int] | None = None,
    coordinator_id: str | None = None,
    final_validation: Callable[["GaugeFrame"], bool],
) -> None:
    """Update under caller-held canonical admission after immediate entry validation."""
    from app.core.metrics.prometheus_metrics import FRAME_STORE

    expected = FRAME_STORE.read()

    def captured(head):
        nonlocal expected
        expected = head

    try:
        frame = _prepare_metrics_from_telemetry_admitted(
            telemetry,
            config,
            active_route,
            poi_manager,
            flight_events_managed=flight_events_managed,
            mission_context=mission_context,
            simulation_plan=simulation_plan,
            simulation_frame=simulation_frame,
            route_progress=route_progress,
            coordinator_id=coordinator_id,
            _captured_head=captured,
        )
        if frame is None:
            return
        # Recheck immediately before the CAS, under repository admission.
        if not final_validation(frame):
            FRAME_STORE.fail(expected, "telemetry source superseded")
            return
        FRAME_STORE.publish(expected, frame)
    except Exception:
        FRAME_STORE.fail(expected, "telemetry preparation failed")
        if mission_context is not None:
            raise
        logger.exception("Complete metric frame preparation failed")


@model_input_write
def clear_telemetry_metrics(
    *,
    config=None,
    active_route=None,
    poi_manager=None,
    coordinator_id=None,
) -> None:
    """Publish an unavailable observation atomically, retaining service/planned state."""
    from dataclasses import replace

    from app.core.metrics.frame_builder import FrameInputs, prepare_unavailable_frame
    from app.core.metrics.frames import GaugeFrame
    from app.core.metrics.prometheus_metrics import COUPLED_SCHEMA, FRAME_STORE

    expected = FRAME_STORE.read()
    if config is not None or poi_manager is not None:
        from app.services.flight_state import get_flight_state_manager

        try:
            frame = prepare_unavailable_frame(
                FrameInputs(
                    expected,
                    config=config,
                    active_route=active_route,
                    pois=poi_manager.list_pois() if poi_manager is not None else (),
                    flight_status=get_flight_state_manager().get_status(),
                    coordinator_id=coordinator_id,
                    now=datetime.now(UTC),
                )
            )
        except Exception:
            FRAME_STORE.fail(expected, "unavailable frame preparation failed")
            raise
    elif expected.frame is None:
        frame = prepare_unavailable_frame(FrameInputs(expected))
    else:
        old = expected.frame
        observed = {
            "starlink_dish_latitude_degrees",
            "starlink_dish_longitude_degrees",
            "starlink_dish_altitude_feet",
            "starlink_dish_speed_knots",
            "starlink_dish_heading_degrees",
            "starlink_network_latency_ms_current",
            "starlink_network_throughput_down_mbps_current",
            "starlink_network_throughput_up_mbps_current",
            "starlink_network_packet_loss_percent",
            "starlink_dish_obstruction_percent",
            "starlink_signal_quality_percent",
            "starlink_eta_poi_seconds",
            "starlink_distance_to_poi_meters",
        }
        frame = GaugeFrame(
            replace(
                old.identity,
                observation_id=None,
                observation_timestamp=None,
                input_revision=expected.input_revision,
            ),
            tuple(
                tuple(
                    (labels, math.nan if definition.name in observed else value)
                    for labels, value in family
                )
                for definition, family in zip(COUPLED_SCHEMA, old.families)
            ),
            old.last_observation_publication_time,
        )
    FRAME_STORE.publish(expected, frame)
    clear_independent_dish_metrics()


def clear_independent_dish_metrics() -> None:
    """Retain the existing disconnect/failure clears for dormant dish gauges."""
    for gauge in (
        starlink_dish_uptime_seconds,
        starlink_dish_thermal_throttle,
        starlink_dish_outage_active,
    ):
        gauge.set(math.nan)


def set_service_info(version: str, mode: str) -> None:
    """Source configuration producer; never reuse observations from an old mode."""
    from types import SimpleNamespace

    from app.core.metrics.frame_builder import FrameInputs, prepare_unavailable_frame
    from app.core.metrics.prometheus_metrics import FRAME_STORE

    expected = FRAME_STORE.invalidate("service source changed")
    try:
        frame = prepare_unavailable_frame(
            FrameInputs(expected, config=SimpleNamespace(mode=mode), version=version)
        )
        FRAME_STORE.publish(expected, frame)
    except Exception:
        FRAME_STORE.fail(expected, "service metadata preparation failed")
        raise


def update_mission_active_metric(mission_id: str, route_id: str) -> None:
    """Update mission active info metric when a mission is activated.

    This function sets the mission_active_info gauge to 1 for the specified mission
    and route combination, indicating that this mission is currently active. Only one
    mission should be active at a time; activating a new mission should deactivate
    the previous one (handled by caller).

    Args:
        mission_id: Unique identifier of the activated mission.
        route_id: Unique identifier of the route associated with this mission.

    Returns:
        None. The function updates Prometheus metrics in-place as a side effect.

    Raises:
        Does not raise exceptions. Failures are logged and ignored to prevent
        disrupting mission activation workflows.
    """
    try:
        mission_active_info.labels(mission_id=mission_id, route_id=route_id).set(1)
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        LookupError,
        ConnectionError,
        TimeoutError,
        ImportError,
        EOFError,
    ) as e:  # pragma: no cover - defensive guard
        logger.warning(f"Failed to update mission active metric: {e}")


def clear_mission_metrics(mission_id: str) -> None:
    """Clear mission metrics when a mission is deactivated or deleted.

    This function resets all mission-related metrics to NaN or 0 to indicate they
    are no longer active. Prometheus doesn't support deleting label combinations
    directly, so we use NaN for gauges (making them absent in queries) and 0 for
    the active info metric (explicitly showing inactive state).

    Args:
        mission_id: Unique identifier of the mission to clear metrics for.

    Returns:
        None. The function updates Prometheus metrics in-place as a side effect.

    Raises:
        Does not raise exceptions. Failures are logged and ignored to prevent
        disrupting mission deactivation workflows.
    """
    try:
        # Clear all mission metrics with this mission_id label
        # Note: Prometheus doesn't have a direct way to delete labels,
        # so we set them to NaN or 0 to indicate they're not active
        mission_phase_state.labels(mission_id=mission_id).set(math.nan)
        mission_next_conflict_seconds.labels(mission_id=mission_id).set(math.nan)
        mission_timeline_generated_timestamp.labels(mission_id=mission_id).set(math.nan)

        # For mission_active_info, we need to set to 0 for all label combinations
        # Since we don't track all combinations, we'll just set to 0 with empty route_id
        mission_active_info.labels(mission_id=mission_id, route_id="").set(0)
        for transport in ["X", "Ka", "Ku"]:
            mission_comm_state.labels(mission_id=mission_id, transport=transport).set(
                math.nan
            )
        mission_degraded_seconds.labels(mission_id=mission_id).set(math.nan)
        mission_critical_seconds.labels(mission_id=mission_id).set(math.nan)
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        LookupError,
        ConnectionError,
        TimeoutError,
        ImportError,
        EOFError,
    ) as e:  # pragma: no cover - defensive guard
        logger.warning(f"Failed to clear mission metrics: {e}")


def update_mission_phase_metric(mission_id: str, phase: str) -> None:
    """Update mission phase state metric.

    This function encodes the mission phase as a numeric value for Prometheus
    gauges. The encoding allows time series queries to track phase transitions
    and calculate time spent in each phase.

    Args:
        mission_id: Unique identifier of the mission.
        phase: Mission phase as a string. Valid values are 'pre_departure' (0),
            'in_flight' (1), or 'post_arrival' (2). Unknown phases default to 0.

    Returns:
        None. The function updates Prometheus metrics in-place as a side effect.

    Raises:
        Does not raise exceptions. Failures are logged and ignored.
    """
    try:
        phase_map = {"pre_departure": 0, "in_flight": 1, "post_arrival": 2}
        phase_value = phase_map.get(phase, 0)
        mission_phase_state.labels(mission_id=mission_id).set(phase_value)
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        LookupError,
        ConnectionError,
        TimeoutError,
        ImportError,
        EOFError,
    ) as e:  # pragma: no cover - defensive guard
        logger.warning(f"Failed to update mission phase metric: {e}")


def update_mission_timeline_timestamp(mission_id: str, timestamp: float) -> None:
    """Update mission timeline generation timestamp.

    This function records when the mission's communication timeline was last computed,
    allowing operators to track timeline freshness and identify when recomputation
    may be needed.

    Args:
        mission_id: Unique identifier of the mission.
        timestamp: Unix timestamp (seconds since epoch) of timeline generation.

    Returns:
        None. The function updates Prometheus metrics in-place as a side effect.

    Raises:
        Does not raise exceptions. Failures are logged and ignored.
    """
    try:
        mission_timeline_generated_timestamp.labels(mission_id=mission_id).set(
            timestamp
        )
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        LookupError,
        ConnectionError,
        TimeoutError,
        ImportError,
        EOFError,
    ) as e:  # pragma: no cover - defensive guard
        logger.warning(f"Failed to update mission timeline timestamp metric: {e}")


def update_mission_comm_state_metric(
    mission_id: str, transport: str, state_value: int
) -> None:
    """Update mission communication state metric for a given transport.

    This function tracks the planned state of each communication transport (X, Ka, Ku)
    throughout the mission timeline. States are encoded numerically to allow queries
    that track availability windows and identify degraded/offline periods.

    Args:
        mission_id: Unique identifier of the mission.
        transport: Transport band identifier ('X', 'Ka', or 'Ku').
        state_value: Numeric state encoding: 0=available, 1=degraded, 2=offline.

    Returns:
        None. The function updates Prometheus metrics in-place as a side effect.

    Raises:
        Does not raise exceptions. Failures are logged and ignored.
    """
    try:
        mission_comm_state.labels(mission_id=mission_id, transport=transport).set(
            state_value
        )
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        LookupError,
        ConnectionError,
        TimeoutError,
        ImportError,
        EOFError,
    ) as e:  # pragma: no cover
        logger.warning(f"Failed to update mission comm state metric: {e}")


def update_mission_duration_metrics(
    mission_id: str, degraded_seconds: float, critical_seconds: float
) -> None:
    """Update degraded/critical mission duration gauges.

    This function publishes the total planned durations for degraded and critical
    communication states in the mission timeline. These metrics help operators
    understand mission risk profile and assess whether communication constraints
    are acceptable.

    Args:
        mission_id: Unique identifier of the mission.
        degraded_seconds: Total seconds when one or more transports are degraded.
        critical_seconds: Total seconds when all transports are offline (critical state).

    Returns:
        None. The function updates Prometheus metrics in-place as a side effect.

    Raises:
        Does not raise exceptions. Failures are logged and ignored.
    """
    try:
        mission_degraded_seconds.labels(mission_id=mission_id).set(degraded_seconds)
        mission_critical_seconds.labels(mission_id=mission_id).set(critical_seconds)
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        LookupError,
        ConnectionError,
        TimeoutError,
        ImportError,
        EOFError,
    ) as e:  # pragma: no cover
        logger.warning(f"Failed to update mission duration metrics: {e}")


def update_mission_next_conflict_metric(mission_id: str, seconds: float) -> None:
    """Update countdown to next degraded/critical event.

    This function tracks the time remaining until the next communication degradation
    or outage in the mission timeline. This allows real-time alerting and helps
    operators prepare for upcoming communication constraints.

    Args:
        mission_id: Unique identifier of the mission.
        seconds: Seconds until next degraded/critical event. Set to -1 if no
            upcoming events are scheduled in the timeline.

    Returns:
        None. The function updates Prometheus metrics in-place as a side effect.

    Raises:
        Does not raise exceptions. Failures are logged and ignored.
    """
    try:
        mission_next_conflict_seconds.labels(mission_id=mission_id).set(seconds)
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        LookupError,
        ConnectionError,
        TimeoutError,
        ImportError,
        EOFError,
    ) as e:  # pragma: no cover
        logger.warning(f"Failed to update mission next conflict metric: {e}")
