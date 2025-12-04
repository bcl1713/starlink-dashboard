"""Metric update functions for telemetry and mission data."""

# FR-004: File exceeds 300 lines (604 lines) because metric updates coordinate
# across telemetry calculations, mission timeline state, flight phase logic, and
# POI ETA projections. Refactoring would split interdependent calculations into
# separate modules creating circular dependencies. Deferred to v0.4.0.

import logging
import math
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.telemetry import TelemetryData
    from app.models.route import ParsedRoute
    from app.services.poi_manager import POIManager
    from app.core.config import ConfigManager

from app.core.metrics.prometheus_metrics import (
    _current_position,
    starlink_dish_latitude_degrees,
    starlink_dish_longitude_degrees,
    starlink_dish_altitude_feet,
    starlink_dish_speed_knots,
    starlink_dish_heading_degrees,
    starlink_network_latency_ms_current,
    starlink_network_throughput_down_mbps_current,
    starlink_network_throughput_up_mbps_current,
    starlink_network_packet_loss_percent,
    starlink_network_latency_ms,
    starlink_network_throughput_down_mbps,
    starlink_network_throughput_up_mbps,
    starlink_dish_obstruction_percent,
    starlink_signal_quality_percent,
    starlink_uptime_seconds,
    starlink_flight_phase,
    starlink_eta_mode,
    starlink_flight_departure_time_unix,
    starlink_flight_arrival_time_unix,
    starlink_time_until_departure_seconds,
    starlink_eta_poi_seconds,
    starlink_distance_to_poi_meters,
    simulation_updates_total,
    starlink_dish_uptime_seconds,
    starlink_dish_thermal_throttle,
    starlink_dish_outage_active,
    starlink_service_info,
    starlink_mode_info,
    mission_active_info,
    mission_phase_state,
    mission_next_conflict_seconds,
    mission_timeline_generated_timestamp,
    mission_comm_state,
    mission_degraded_seconds,
    mission_critical_seconds,
)

logger = logging.getLogger(__name__)


def update_metrics_from_telemetry(
    telemetry: Optional["TelemetryData"],
    config: Optional["ConfigManager"] = None,
    active_route: Optional["ParsedRoute"] = None,
    poi_manager: Optional["POIManager"] = None,
) -> None:
    """Update all Prometheus metrics from telemetry data.

    This is the primary function for publishing telemetry data to Prometheus. It updates
    position, network, obstruction, and flight status metrics, and optionally calculates
    POI/ETA metrics if a route and POI manager are provided. The function performs
    automatic flight phase transitions (departure/arrival detection) based on speed and
    position relative to the active route.

    Args:
        telemetry: TelemetryData instance containing current sensor readings. If None,
            the function returns early to prevent publishing invalid/stale data.
        config: Optional ConfigManager for computing mode and status labels applied to
            histogram metrics (e.g., "simulation" vs "live", "normal" vs "degraded").
        active_route: Optional ParsedRoute with timing profile for route-aware ETA
            calculations and automatic arrival detection.
        poi_manager: Optional POIManager for calculating distances and ETAs to all
            configured points of interest.

    Returns:
        None. The function updates Prometheus metrics in-place as a side effect.

    Raises:
        Does not raise exceptions. All errors are logged and handled gracefully to
        ensure metrics collection continues even if individual updates fail.
    """
    # Defensive check: do not publish metrics if telemetry is None
    # This prevents pollution of Prometheus with zero/invalid values
    if telemetry is None:
        return

    from app.core.labels import get_mode_label, get_status_label

    # Compute labels if config provided
    mode_label = get_mode_label(config) if config else "unknown"
    status_label = get_status_label(
        telemetry.network.latency_ms, telemetry.network.packet_loss_percent
    )

    # Position metrics
    # Update custom collector's position data
    global _current_position
    _current_position["latitude"] = telemetry.position.latitude
    _current_position["longitude"] = telemetry.position.longitude
    _current_position["altitude"] = telemetry.position.altitude

    # Also set individual metrics for backward compatibility
    starlink_dish_latitude_degrees.set(telemetry.position.latitude)
    starlink_dish_longitude_degrees.set(telemetry.position.longitude)
    starlink_dish_altitude_feet.set(telemetry.position.altitude)
    starlink_dish_speed_knots.set(telemetry.position.speed)
    starlink_dish_heading_degrees.set(telemetry.position.heading)

    # Network metrics - Current values (Gauges)
    starlink_network_latency_ms_current.set(telemetry.network.latency_ms)
    starlink_network_throughput_down_mbps_current.set(
        telemetry.network.throughput_down_mbps
    )
    starlink_network_throughput_up_mbps_current.set(
        telemetry.network.throughput_up_mbps
    )
    starlink_network_packet_loss_percent.set(telemetry.network.packet_loss_percent)

    # Network metrics - Histograms (for percentile analysis)
    # Record observations for histogram buckets with labels
    starlink_network_latency_ms.labels(mode=mode_label, status=status_label).observe(
        telemetry.network.latency_ms
    )
    starlink_network_throughput_down_mbps.labels(
        mode=mode_label, status=status_label
    ).observe(telemetry.network.throughput_down_mbps)
    starlink_network_throughput_up_mbps.labels(
        mode=mode_label, status=status_label
    ).observe(telemetry.network.throughput_up_mbps)

    # Obstruction and signal metrics
    starlink_dish_obstruction_percent.set(telemetry.obstruction.obstruction_percent)
    starlink_signal_quality_percent.set(telemetry.environmental.signal_quality_percent)

    # Status metrics
    starlink_uptime_seconds.set(telemetry.environmental.uptime_seconds)

    # Evaluate automatic flight phase transitions and cache current status
    flight_state = None
    flight_status = None
    try:
        from app.services.flight_state_manager import get_flight_state_manager

        flight_state = get_flight_state_manager()

        # Automatic departure detection (speed-based)
        try:
            flight_state.check_departure(telemetry.position.speed)
        except Exception as departure_error:  # pragma: no cover - defensive guard
            logger.warning(f"Departure detection error: {departure_error}")

        # Automatic arrival detection when an active route is available
        if active_route:
            try:
                from app.services.route_eta_calculator import RouteETACalculator

                route_calculator = RouteETACalculator(active_route)
                progress_info = route_calculator.get_route_progress(
                    telemetry.position.latitude,
                    telemetry.position.longitude,
                )
                distance_remaining = progress_info.get("distance_remaining_meters")
                if distance_remaining is not None:
                    flight_state.check_arrival(
                        distance_remaining, telemetry.position.speed
                    )
            except Exception as arrival_error:  # pragma: no cover - defensive guard
                logger.debug(f"Arrival detection skipped: {arrival_error}")

        flight_status = flight_state.get_status()
    except Exception as state_error:  # pragma: no cover - defensive guard
        logger.warning(f"Flight state manager unavailable: {state_error}")

    # Update Flight Status metrics
    try:
        if flight_status is None:
            if flight_state is None:
                from app.services.flight_state_manager import get_flight_state_manager

                flight_state = get_flight_state_manager()
            flight_status = flight_state.get_status()

        # Map phase to numeric value
        phase_value = {"pre_departure": 0, "in_flight": 1, "post_arrival": 2}.get(
            flight_status.phase.value, 0
        )

        # Map ETA mode to numeric value
        mode_value = {"anticipated": 0, "estimated": 1}.get(
            flight_status.eta_mode.value, 0
        )

        starlink_flight_phase.set(phase_value)
        starlink_eta_mode.set(mode_value)

        # Set timestamp metrics (0 if not set)
        if flight_status.departure_time:
            starlink_flight_departure_time_unix.set(
                flight_status.departure_time.timestamp()
            )
        else:
            starlink_flight_departure_time_unix.set(0)

        if flight_status.arrival_time:
            starlink_flight_arrival_time_unix.set(
                flight_status.arrival_time.timestamp()
            )
        else:
            starlink_flight_arrival_time_unix.set(0)

        # Synchronize active route timing profile with live flight status
        if active_route is not None and flight_status is not None:
            try:
                from app.models.route import (
                    RouteTimingProfile,
                )  # Local import to avoid cycle

                timing_profile = active_route.timing_profile
                if timing_profile is None:
                    timing_profile = RouteTimingProfile()
                    active_route.timing_profile = timing_profile

                timing_profile.flight_status = flight_status.phase.value
                timing_profile.actual_departure_time = flight_status.departure_time
                timing_profile.actual_arrival_time = flight_status.arrival_time
            except Exception as sync_error:  # pragma: no cover - defensive guard
                logger.debug(
                    f"Failed to sync route timing profile with flight status: {sync_error}"
                )

        # Update time-until-departure gauge
        time_until_departure = 0.0
        if flight_status is not None:
            now = datetime.now(timezone.utc)

            departure_time = getattr(flight_status, "departure_time", None)
            if departure_time:
                departure_time = (
                    departure_time.astimezone(timezone.utc)
                    if departure_time.tzinfo
                    else departure_time.replace(tzinfo=timezone.utc)
                )
                delta = (departure_time - now).total_seconds()
                time_until_departure = max(0.0, delta)
            elif (
                active_route
                and active_route.timing_profile
                and active_route.timing_profile.departure_time
            ):
                scheduled_departure = active_route.timing_profile.departure_time
                if scheduled_departure:
                    scheduled_departure = (
                        scheduled_departure.astimezone(timezone.utc)
                        if scheduled_departure.tzinfo
                        else scheduled_departure.replace(tzinfo=timezone.utc)
                    )
                    delta = (scheduled_departure - now).total_seconds()
                    time_until_departure = delta

        starlink_time_until_departure_seconds.set(time_until_departure)

    except Exception as e:
        logger.warning(f"Error updating flight status metrics: {e}")

    # Update POI/ETA metrics
    try:
        from app.core.eta_service import update_eta_metrics
        from app.models.flight_status import ETAMode

        if flight_status is None:
            if flight_state is None:
                from app.services.flight_state_manager import get_flight_state_manager

                flight_state = get_flight_state_manager()
            flight_status = flight_state.get_status()

        current_eta_mode = (
            flight_status.eta_mode if flight_status else ETAMode.ESTIMATED
        )

        eta_metrics = update_eta_metrics(
            telemetry.position.latitude,
            telemetry.position.longitude,
            telemetry.position.speed,
            active_route=active_route,
            eta_mode=current_eta_mode,
            flight_phase=flight_status.phase if flight_status else None,
            poi_manager=poi_manager,
        )

        # Update Prometheus gauges with ETA data
        for poi_id, metrics_data in eta_metrics.items():
            poi_name = metrics_data.get("poi_name", "unknown")
            poi_category = metrics_data.get("poi_category", "")
            eta_seconds = metrics_data.get("eta_seconds", -1)
            distance_meters = metrics_data.get("distance_meters", 0)
            eta_type = metrics_data.get(
                "eta_type", current_eta_mode.value if current_eta_mode else "estimated"
            )

            # Only set valid ETA values (skip -1 which means no speed)
            if eta_seconds >= 0:
                starlink_eta_poi_seconds.labels(
                    name=poi_name, category=poi_category, eta_type=eta_type
                ).set(eta_seconds)
            starlink_distance_to_poi_meters.labels(
                name=poi_name, category=poi_category, eta_type=eta_type
            ).set(distance_meters)

    except Exception as e:
        logger.warning(f"Error updating POI/ETA metrics: {e}")

    # Increment update counter
    simulation_updates_total.inc()


def clear_telemetry_metrics() -> None:
    """Clear all telemetry metrics by setting them to NaN.

    This is called when the Starlink dish is disconnected in live mode to prevent
    publishing stale or zero values to Prometheus. Setting metrics to NaN causes
    Prometheus to treat them as absent, effectively removing them from the time series
    database until new valid data arrives.

    Note: Service info, uptime, and counter metrics are intentionally NOT cleared
    because they represent the backend service state rather than dish telemetry.
    Counters are monotonic and should never decrease, so they continue tracking
    lifetime totals even during disconnections.

    Args:
        None

    Returns:
        None. The function updates Prometheus metrics in-place as a side effect.

    Raises:
        Does not raise exceptions. This is a fire-and-forget operation.
    """
    # Position metrics
    starlink_dish_latitude_degrees.set(math.nan)
    starlink_dish_longitude_degrees.set(math.nan)
    starlink_dish_altitude_feet.set(math.nan)
    starlink_dish_speed_knots.set(math.nan)
    starlink_dish_heading_degrees.set(math.nan)

    # Network metrics (current values)
    starlink_network_latency_ms_current.set(math.nan)
    starlink_network_throughput_down_mbps_current.set(math.nan)
    starlink_network_throughput_up_mbps_current.set(math.nan)
    starlink_network_packet_loss_percent.set(math.nan)

    # Obstruction and signal metrics
    starlink_dish_obstruction_percent.set(math.nan)
    starlink_signal_quality_percent.set(math.nan)

    # Dish status metrics
    starlink_dish_uptime_seconds.set(math.nan)
    starlink_dish_thermal_throttle.set(math.nan)
    starlink_dish_outage_active.set(math.nan)

    # Clear route metrics when no active route (handled separately by simulator)
    # Route metrics are only cleared when route is deactivated

    # Clear custom position collector data
    global _current_position
    _current_position["latitude"] = math.nan
    _current_position["longitude"] = math.nan
    _current_position["altitude"] = math.nan


def set_service_info(version: str, mode: str) -> None:
    """Set service info metrics for backend service identification.

    This function publishes metadata about the backend service to Prometheus for
    monitoring and debugging purposes. It sets two related metrics: a composite
    service info metric with version and mode as labels, and individual mode
    indicator metrics that can be easily filtered in queries.

    The mode indicators use a binary encoding where only the active mode is set
    to 1, and all other modes are set to 0. This allows Prometheus queries like
    `starlink_mode_info{mode="simulation"} == 1` to efficiently filter time series.

    Args:
        version: Service version string (e.g., "1.0.0" or git commit hash).
        mode: Operating mode, either "simulation" (synthetic data) or "live"
            (connected to real Starlink dish).

    Returns:
        None. The function updates Prometheus metrics in-place as a side effect.

    Raises:
        Does not raise exceptions. Failures are silently ignored to prevent
        disrupting service startup.
    """
    # Set composite service info metric with version and mode labels
    starlink_service_info.labels(version=version, mode=mode).set(1)

    # Set mode indicator metric - only the active mode will be set to 1
    # This allows easy filtering by mode in Prometheus queries
    for possible_mode in ["simulation", "live"]:
        if possible_mode == mode:
            starlink_mode_info.labels(mode=possible_mode).set(1)
        else:
            starlink_mode_info.labels(mode=possible_mode).set(0)


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
    except Exception as e:  # pragma: no cover - defensive guard
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
    except Exception as e:  # pragma: no cover - defensive guard
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
    except Exception as e:  # pragma: no cover - defensive guard
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
    except Exception as e:  # pragma: no cover - defensive guard
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
    except Exception as e:  # pragma: no cover
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
    except Exception as e:  # pragma: no cover
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
    except Exception as e:  # pragma: no cover
        logger.warning(f"Failed to update mission next conflict metric: {e}")
