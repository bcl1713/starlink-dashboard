"""Metrics export endpoint for integration with Prometheus and monitoring."""

from typing import Optional

from fastapi import APIRouter, status

from app.core.config import ConfigManager
from app.core.metrics import (
    REGISTRY,
    starlink_route_has_timing_data,
    starlink_route_total_duration_seconds,
    starlink_route_departure_time_unix,
    starlink_route_arrival_time_unix,
    starlink_route_segment_count_with_timing,
)
from app.models.telemetry import TelemetryData
from app.services.eta_calculator import ETACalculator
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from app.simulation.coordinator import SimulationCoordinator

# Initialize services
config_manager = ConfigManager()

# Global manager instances (set by main.py)
route_manager: Optional[RouteManager] = None
poi_manager: Optional[POIManager] = None

# Create API router
router = APIRouter(tags=["metrics"])


def set_route_manager(manager: RouteManager) -> None:
    """Set the route manager instance (called by main.py during startup)."""
    global route_manager
    route_manager = manager


def set_poi_manager(manager: POIManager) -> None:
    """Set the POI manager instance (called by main.py during startup)."""
    global poi_manager
    poi_manager = manager


@router.get("/metrics", status_code=status.HTTP_200_OK)
async def get_metrics() -> str:
    """
    Get Prometheus metrics in OpenMetrics text format.

    This endpoint is scraped by Prometheus to collect metrics.
    Includes position, network, obstruction, and POI/ETA metrics.

    Returns:
    - Prometheus OpenMetrics format text
    """
    try:
        # Get current telemetry to update POI metrics
        coordinator = SimulationCoordinator(config=config_manager.get_config())
        telemetry = coordinator.get_current_telemetry()

        # Update route timing metrics if we have an active route with timing data
        active_route = route_manager.get_active_route()
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
                departure_unix = time_module.mktime(timing_profile.departure_time.timetuple())
                starlink_route_departure_time_unix.labels(route_name=route_name).set(
                    departure_unix
                )

            if timing_profile.arrival_time:
                import time as time_module
                arrival_unix = time_module.mktime(timing_profile.arrival_time.timetuple())
                starlink_route_arrival_time_unix.labels(route_name=route_name).set(
                    arrival_unix
                )

            # Export segment count
            starlink_route_segment_count_with_timing.labels(route_name=route_name).set(
                timing_profile.segment_count_with_timing
            )

        # Update POI metrics if we have active route and POIs
        pois = poi_manager.list_pois()

        if telemetry and active_route and pois:
            eta_calc = ETACalculator()
            eta_calc.update_speed(telemetry.position.speed)

            metrics = eta_calc.calculate_poi_metrics(
                telemetry.position.latitude,
                telemetry.position.longitude,
                pois,
                telemetry.position.speed,
            )

            # Update Prometheus gauges with POI metrics
            for poi_id, metric in metrics.items():
                poi = poi_manager.get_poi(poi_id)
                if poi:
                    # Set POI distance gauge
                    distance_gauge = REGISTRY._names_to_collectors.get(
                        "starlink_distance_to_poi_meters"
                    )
                    if distance_gauge:
                        distance_gauge.labels(name=poi.name, id=poi_id).set(
                            metric["distance_meters"]
                        )

                    # Set POI ETA gauge
                    eta_gauge = REGISTRY._names_to_collectors.get("starlink_eta_poi_seconds")
                    if eta_gauge:
                        eta_seconds = metric["eta_seconds"]
                        # ETA of -1 means no speed; Prometheus doesn't like negative values
                        # Store as special value or skip
                        if eta_seconds >= 0:
                            eta_gauge.labels(name=poi.name, id=poi_id).set(eta_seconds)

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
