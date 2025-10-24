"""Metrics export endpoint for integration with Prometheus and monitoring."""

from fastapi import APIRouter, status

from app.core.config import ConfigManager
from app.core.metrics import REGISTRY
from app.models.telemetry import TelemetryData
from app.services.eta_calculator import ETACalculator
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from app.simulation.coordinator import SimulationCoordinator

# Initialize services
config_manager = ConfigManager()
route_manager = RouteManager()
poi_manager = POIManager()

# Create API router
router = APIRouter(tags=["metrics"])


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

        # Update POI metrics if we have active route and POIs
        active_route = route_manager.get_active_route()
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
