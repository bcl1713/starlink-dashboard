"""Metrics export endpoint for integration with Prometheus and monitoring."""

from fastapi import APIRouter, status, Depends

from app.core.config import ConfigManager
from app.core.metrics import (
    REGISTRY,
    starlink_route_has_timing_data,
    starlink_route_total_duration_seconds,
    starlink_route_departure_time_unix,
    starlink_route_arrival_time_unix,
    starlink_route_segment_count_with_timing,
)
from app.models.flight_status import ETAMode
from app.services.eta_calculator import ETACalculator
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from app.simulation.coordinator import SimulationCoordinator
from app.mission.dependencies import get_route_manager, get_poi_manager

# Initialize services
config_manager = ConfigManager()

# Create API router
router = APIRouter(tags=["metrics"])


@router.get("/metrics", status_code=status.HTTP_200_OK)
async def get_metrics(
    route_manager: RouteManager = Depends(get_route_manager),
    poi_manager: POIManager = Depends(get_poi_manager),
) -> str:
    """
    Get Prometheus metrics in OpenMetrics text format.

    This endpoint is scraped by Prometheus to collect metrics.
    Includes position, network, obstruction, and POI/ETA metrics (with `eta_type`
    labels to distinguish anticipated vs estimated timelines). When live speed is
    unavailable pre-departure, the exporter seeds a default cruise speed to keep
    ETA gauges non-negative.

    Returns:
    - Prometheus OpenMetrics format text
    """
    try:
        # Get current telemetry to update POI metrics
        coordinator = SimulationCoordinator(config=config_manager.get_config())
        telemetry = coordinator.get_current_telemetry()

        # Update route timing metrics if we have an active route with timing data
        active_route = route_manager.get_active_route() if route_manager else None
        if active_route and active_route.timing_profile:
            route_name = active_route.metadata.name
            timing_profile = active_route.timing_profile

            # Export route timing presence
            starlink_route_has_timing_data.labels(route_name=route_name).set(
                1 if timing_profile.has_timing_data else 0
            )

            # Export route timing metrics if available
            if timing_profile.total_expected_duration_seconds:
                starlink_route_total_duration_seconds.labels(route_name=route_name).set(
                    timing_profile.total_expected_duration_seconds
                )

            if timing_profile.departure_time:
                import time as time_module

                departure_unix = time_module.mktime(
                    timing_profile.departure_time.timetuple()
                )
                starlink_route_departure_time_unix.labels(route_name=route_name).set(
                    departure_unix
                )

            if timing_profile.arrival_time:
                import time as time_module

                arrival_unix = time_module.mktime(
                    timing_profile.arrival_time.timetuple()
                )
                starlink_route_arrival_time_unix.labels(route_name=route_name).set(
                    arrival_unix
                )

            # Export segment count
            starlink_route_segment_count_with_timing.labels(route_name=route_name).set(
                timing_profile.segment_count_with_timing
            )

        # Update POI metrics if we have telemetry samples and POIs
        pois = poi_manager.list_pois() if poi_manager else []

        if telemetry and pois:
            eta_calc = ETACalculator()
            raw_speed = telemetry.position.speed if telemetry.position else None
            speed_knots = None

            if raw_speed is not None and raw_speed >= 0.5:
                eta_calc.update_speed(raw_speed)
                speed_knots = raw_speed
            else:
                # Prime smoothing window with default cruise speed so ETAs stay positive pre-departure
                eta_calc.update_speed(eta_calc.default_speed_knots)

            status_snapshot = None
            try:
                from app.services.flight_state import get_flight_state_manager

                status_snapshot = get_flight_state_manager().get_status()
            except Exception:
                status_snapshot = None

            eta_mode = (
                status_snapshot.eta_mode if status_snapshot else ETAMode.ESTIMATED
            )
            flight_phase = status_snapshot.phase if status_snapshot else None

            metrics = eta_calc.calculate_poi_metrics(
                telemetry.position.latitude,
                telemetry.position.longitude,
                pois,
                speed_knots,
                active_route=active_route,
                eta_mode=eta_mode,
                flight_phase=flight_phase,
            )

            # Update Prometheus gauges with POI metrics
            for poi_id, metric in metrics.items():
                poi = poi_manager.get_poi(poi_id)
                if poi:
                    # Set POI distance gauge
                    distance_gauge = REGISTRY._names_to_collectors.get(
                        "starlink_distance_to_poi_meters"
                    )
                    eta_gauge = REGISTRY._names_to_collectors.get(
                        "starlink_eta_poi_seconds"
                    )

                    label_kwargs = {
                        "name": poi.name,
                        "category": poi.category or "",
                        "eta_type": metric.get("eta_type", "estimated"),
                    }

                    if distance_gauge:
                        distance_gauge.labels(**label_kwargs).set(
                            metric["distance_meters"]
                        )

                    if eta_gauge:
                        eta_seconds = metric["eta_seconds"]
                        if eta_seconds >= 0:
                            eta_gauge.labels(**label_kwargs).set(eta_seconds)

    except Exception:
        # Gracefully handle errors in POI metric calculation
        pass

    # Generate and return metrics in OpenMetrics format
    from prometheus_client import generate_latest

    metrics_output = generate_latest(REGISTRY).decode("utf-8")

    # Ensure OpenMetrics format compliance with EOF marker
    if not metrics_output.endswith("# EOF\n"):
        metrics_output = metrics_output.rstrip() + "\n# EOF\n"

    return metrics_output
