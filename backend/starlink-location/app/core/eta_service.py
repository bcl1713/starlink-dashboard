"""ETA calculation service with singleton pattern and real-time updates.

This module provides a singleton ETACalculator instance that maintains state
across multiple requests and API calls. It integrates with the background
update loop to ensure ETA metrics are continuously calculated and exposed
to Prometheus.
"""

import logging
from typing import Optional

from app.services.eta_calculator import ETACalculator
from app.services.poi_manager import POIManager

logger = logging.getLogger(__name__)

# Global singleton instance
_eta_calculator: Optional[ETACalculator] = None
_poi_manager: Optional[POIManager] = None


def initialize_eta_service(poi_manager: Optional[POIManager] = None) -> None:
    """Initialize the ETA service with singleton instances.

    Args:
        poi_manager: Optional POI manager instance. If not provided, creates new instance.
    """
    global _eta_calculator, _poi_manager

    try:
        _poi_manager = poi_manager or POIManager()
        _eta_calculator = ETACalculator(smoothing_duration_seconds=120.0)
        logger.info("ETA service initialized successfully (120s speed smoothing)")
    except Exception as e:
        logger.error(f"Failed to initialize ETA service: {e}")
        raise


def get_eta_calculator() -> ETACalculator:
    """Get the singleton ETA calculator instance.

    Returns:
        ETACalculator: The singleton instance

    Raises:
        RuntimeError: If service not initialized
    """
    global _eta_calculator

    if _eta_calculator is None:
        raise RuntimeError(
            "ETA service not initialized. Call initialize_eta_service() first."
        )

    return _eta_calculator


def get_poi_manager() -> POIManager:
    """Get the POI manager instance.

    Returns:
        POIManager: The singleton instance

    Raises:
        RuntimeError: If service not initialized
    """
    global _poi_manager

    if _poi_manager is None:
        raise RuntimeError(
            "ETA service not initialized. Call initialize_eta_service() first."
        )

    return _poi_manager


def update_eta_metrics(
    latitude: float,
    longitude: float,
    speed_knots: float,
    active_route=None,
    eta_mode=None,
    flight_phase=None,
    poi_manager: Optional[POIManager] = None,
) -> dict:
    """Update ETA metrics for all POIs.

    This function is called by the background update loop on each telemetry cycle.
    It calculates ETA and distance for all available POIs and returns the results.

    When an active route with timing data is available, POIs that are waypoints
    on that route will use route-aware ETA calculations (segment-based speeds).
    POIs not on the active route fall back to distance/speed calculation.

    Args:
        latitude: Current latitude in decimal degrees
        longitude: Current longitude in decimal degrees
        speed_knots: Current speed in knots
        active_route: Optional ParsedRoute with timing data for route-aware calculations
        eta_mode: Optional ETAMode for dual-mode calculation (defaults to ESTIMATED)
        flight_phase: Optional flight phase for context
        poi_manager: Optional POIManager instance to use instead of global singleton

    Returns:
        Dictionary mapping POI IDs to their ETA metrics
    """
    try:
        from app.models.flight_status import ETAMode

        eta_calculator = get_eta_calculator()

        # Use provided manager or fall back to singleton
        if poi_manager is None:
            poi_manager = get_poi_manager()

        # Default to estimated mode if not specified
        if eta_mode is None:
            eta_mode = ETAMode.ESTIMATED

        # Update speed in calculator (maintains rolling average)
        safe_speed = None
        if speed_knots is not None and speed_knots >= 0.5:
            safe_speed = speed_knots
            eta_calculator.update_speed(speed_knots)
        else:
            # Seed smoothing window with default cruise speed so pre-departure ETAs stay positive
            eta_calculator.update_speed(eta_calculator.default_speed_knots)

        # Get all POIs
        pois = poi_manager.list_pois()

        # Calculate metrics for all POIs (passing active_route and eta_mode)
        metrics = eta_calculator.calculate_poi_metrics(
            latitude,
            longitude,
            pois,
            safe_speed,
            active_route=active_route,
            eta_mode=eta_mode,
            flight_phase=flight_phase,
        )

        return metrics
    except Exception as e:
        logger.error(f"Error updating ETA metrics: {e}", exc_info=True)
        return {}


def get_nearest_poi_metrics() -> Optional[dict]:
    """Get metrics for the nearest POI.

    Returns:
        Dictionary with nearest POI metrics or None if no POIs available
    """
    try:

        # Get nearest POI from calculator
        # Note: This requires tracking in the ETACalculator
        # For now, this is a placeholder for future enhancement
        return None
    except Exception as e:
        logger.error(f"Error getting nearest POI metrics: {e}", exc_info=True)
        return None


def shutdown_eta_service() -> None:
    """Shutdown the ETA service."""
    global _eta_calculator, _poi_manager

    try:
        logger.info("Shutting down ETA service")
        _eta_calculator = None
        _poi_manager = None
    except Exception as e:
        logger.error(f"Error during ETA service shutdown: {e}")
