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
        _eta_calculator = ETACalculator()
        logger.info("ETA service initialized successfully")
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
        raise RuntimeError("ETA service not initialized. Call initialize_eta_service() first.")

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
        raise RuntimeError("ETA service not initialized. Call initialize_eta_service() first.")

    return _poi_manager


def update_eta_metrics(latitude: float, longitude: float, speed_knots: float) -> dict:
    """Update ETA metrics for all POIs.

    This function is called by the background update loop on each telemetry cycle.
    It calculates ETA and distance for all available POIs and returns the results.

    Args:
        latitude: Current latitude in decimal degrees
        longitude: Current longitude in decimal degrees
        speed_knots: Current speed in knots

    Returns:
        Dictionary mapping POI IDs to their ETA metrics
    """
    try:
        eta_calculator = get_eta_calculator()
        poi_manager = get_poi_manager()

        # Update speed in calculator (maintains rolling average)
        eta_calculator.update_speed(speed_knots)

        # Get all POIs
        pois = poi_manager.list_pois()

        # Calculate metrics for all POIs
        metrics = eta_calculator.calculate_poi_metrics(
            latitude, longitude, pois, speed_knots
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
        eta_calculator = get_eta_calculator()

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
