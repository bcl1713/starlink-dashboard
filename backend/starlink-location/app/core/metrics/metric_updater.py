"""Metric update functions for telemetry and mission data."""

import logging
import math
from datetime import datetime, timezone

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
    telemetry, config=None, active_route=None, poi_manager=None
):
    """
    Update all Prometheus metrics from telemetry data.

    Args:
        telemetry: TelemetryData instance or None
        config: Optional ConfigManager instance for label computation
        active_route: Optional ParsedRoute with timing data for route-aware ETA calculations
        poi_manager: Optional POIManager instance for POI calculations

    Returns:
        None. Does nothing if telemetry is None (prevents publishing invalid data).
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


def clear_telemetry_metrics():
    """
    Clear all telemetry metrics by setting them to NaN.

    This is used when the dish is disconnected in live mode to prevent
    publishing stale or zero values to Prometheus. NaN values are not
    stored by Prometheus, effectively removing the metrics from the database.

    Note: Service info, uptime, and counter metrics are NOT cleared as they
    represent the backend service state, not dish telemetry.
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


def set_service_info(version: str, mode: str):
    """
    Set service info metrics.

    Sets both the composite starlink_service_info metric and the individual
    starlink_mode_info metric for better filtering and observability.

    Args:
        version: Service version string
        mode: Operating mode (simulation or live)
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


def update_mission_active_metric(mission_id: str, route_id: str):
    """
    Update mission active info metric when a mission is activated.

    Args:
        mission_id: ID of the activated mission
        route_id: Route ID associated with the mission
    """
    try:
        mission_active_info.labels(mission_id=mission_id, route_id=route_id).set(1)
    except Exception as e:  # pragma: no cover - defensive guard
        logger.warning(f"Failed to update mission active metric: {e}")


def clear_mission_metrics(mission_id: str):
    """
    Clear mission metrics when a mission is deactivated or deleted.

    Args:
        mission_id: ID of the mission to clear metrics for
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


def update_mission_phase_metric(mission_id: str, phase: str):
    """
    Update mission phase state metric.

    Args:
        mission_id: ID of the mission
        phase: Mission phase ('pre_departure', 'in_flight', 'post_arrival')
    """
    try:
        phase_map = {"pre_departure": 0, "in_flight": 1, "post_arrival": 2}
        phase_value = phase_map.get(phase, 0)
        mission_phase_state.labels(mission_id=mission_id).set(phase_value)
    except Exception as e:  # pragma: no cover - defensive guard
        logger.warning(f"Failed to update mission phase metric: {e}")


def update_mission_timeline_timestamp(mission_id: str, timestamp: float):
    """
    Update mission timeline generation timestamp.

    Args:
        mission_id: ID of the mission
        timestamp: Unix timestamp of timeline generation
    """
    try:
        mission_timeline_generated_timestamp.labels(mission_id=mission_id).set(
            timestamp
        )
    except Exception as e:  # pragma: no cover - defensive guard
        logger.warning(f"Failed to update mission timeline timestamp metric: {e}")


def update_mission_comm_state_metric(mission_id: str, transport: str, state_value: int):
    """Update mission communication state metric for a given transport."""
    try:
        mission_comm_state.labels(mission_id=mission_id, transport=transport).set(
            state_value
        )
    except Exception as e:  # pragma: no cover
        logger.warning(f"Failed to update mission comm state metric: {e}")


def update_mission_duration_metrics(
    mission_id: str, degraded_seconds: float, critical_seconds: float
):
    """Update degraded/critical mission duration gauges."""
    try:
        mission_degraded_seconds.labels(mission_id=mission_id).set(degraded_seconds)
        mission_critical_seconds.labels(mission_id=mission_id).set(critical_seconds)
    except Exception as e:  # pragma: no cover
        logger.warning(f"Failed to update mission duration metrics: {e}")


def update_mission_next_conflict_metric(mission_id: str, seconds: float):
    """Update countdown to next degraded/critical event (-1 if none)."""
    try:
        mission_next_conflict_seconds.labels(mission_id=mission_id).set(seconds)
    except Exception as e:  # pragma: no cover
        logger.warning(f"Failed to update mission next conflict metric: {e}")
