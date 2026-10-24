"""ETA calculation service with singleton pattern and real-time updates.

This module provides a singleton ETACalculator instance that maintains state
across multiple requests and API calls. It integrates with the background
update loop to ensure ETA metrics are continuously calculated and exposed
to Prometheus.
"""

import logging
from collections import deque
from copy import copy, deepcopy
from datetime import datetime
from threading import Lock

from app.services.eta_calculator import ETACalculator
from app.services.poi_manager import POIManager

logger = logging.getLogger(__name__)

# Global singleton instance
_eta_calculator: ETACalculator | None = None
_poi_manager: POIManager | None = None
_computation_guard = Lock()


def initialize_eta_service(poi_manager: POIManager | None = None) -> None:
    """Initialize the ETA service with singleton instances.

    Args:
        poi_manager: Optional POI manager instance. If not provided, creates new instance.
    """
    global _eta_calculator, _poi_manager

    try:
        _poi_manager = poi_manager or POIManager()
        _eta_calculator = ETACalculator(smoothing_duration_seconds=120.0)
        logger.info("ETA service initialized successfully (120s speed smoothing)")
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
    ):
        logger.exception("Failed to initialize ETA service")
        raise


def get_eta_calculator() -> ETACalculator:
    """Get the singleton ETA calculator instance.

    Returns:
        ETACalculator: The singleton instance

    Raises:
        RuntimeError: If service not initialized
    """
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
    if _poi_manager is None:
        raise RuntimeError(
            "ETA service not initialized. Call initialize_eta_service() first."
        )

    return _poi_manager


def _prepare_eta_metrics(
    latitude,
    longitude,
    speed_knots,
    active_route=None,
    eta_mode=None,
    flight_phase=None,
    poi_manager=None,
    *,
    mission_now=None,
    pois=None,
    admit_observation=False,
):
    """Strict preparation: capture manager inputs before singleton computation."""
    from app.models.flight_status import ETAMode
    from app.services.eta.projection import ETAProjection

    calculator = get_eta_calculator()
    if pois is None:
        manager = poi_manager if poi_manager is not None else get_poi_manager()
        pois = manager.list_pois()
    pois = tuple(deepcopy(poi) for poi in pois)
    safe_speed = speed_knots if speed_knots is not None and speed_knots >= 0.5 else None
    mode = eta_mode if eta_mode is not None else ETAMode.ESTIMATED
    clock = {"mission_now": mission_now} if mission_now is not None else {}
    with _computation_guard:
        if admit_observation:
            calculator.update_speed(
                (
                    safe_speed
                    if safe_speed is not None
                    else calculator.default_speed_knots
                ),
                **(
                    {"sample_time_seconds": mission_now.timestamp()}
                    if mission_now is not None
                    else {}
                ),
            )
            return calculator.calculate_poi_metrics(
                latitude,
                longitude,
                pois,
                safe_speed,
                active_route=active_route,
                eta_mode=mode,
                flight_phase=flight_phase,
                **clock,
            )
        # Clone only our calculator state, never managers or registry instruments.
        detached = copy(calculator)
        detached._speed_history = deque(calculator._speed_history)
        detached._passed_pois = calculator._passed_pois.copy()
        detached._projection = ETAProjection(detached)
    return detached.calculate_poi_metrics(
        latitude,
        longitude,
        pois,
        safe_speed,
        active_route=active_route,
        eta_mode=mode,
        flight_phase=flight_phase,
        track_passage=False,
        **clock,
    )


def derive_eta_metrics(
    latitude: float,
    longitude: float,
    speed_knots: float | None,
    active_route=None,
    eta_mode=None,
    flight_phase=None,
    poi_manager=None,
    *,
    mission_now: datetime | None = None,
    pois=None,
) -> dict:
    """Read-only derivation; failures propagate to complete-frame preparation."""
    return _prepare_eta_metrics(
        latitude,
        longitude,
        speed_knots,
        active_route,
        eta_mode,
        flight_phase,
        poi_manager,
        mission_now=mission_now,
        pois=pois,
        admit_observation=False,
    )


def update_eta_metrics(
    latitude: float,
    longitude: float,
    speed_knots: float | None,
    active_route=None,
    eta_mode=None,
    flight_phase=None,
    poi_manager=None,
    *,
    mission_now: datetime | None = None,
    pois=None,
) -> dict:
    """Legacy accepted-observation API; retain its logged empty-result fallback."""
    try:
        return _prepare_eta_metrics(
            latitude,
            longitude,
            speed_knots,
            active_route,
            eta_mode,
            flight_phase,
            poi_manager,
            mission_now=mission_now,
            pois=pois,
            admit_observation=True,
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
    ):
        logger.exception("Error updating ETA metrics")
        return {}


def get_nearest_poi_metrics() -> dict | None:
    """Get metrics for the nearest POI.

    Returns:
        Dictionary with nearest POI metrics or None if no POIs available
    """
    try:

        # Get nearest POI from calculator
        # Note: This requires tracking in the ETACalculator
        # For now, this is a placeholder for future enhancement
        return None
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
    ):
        logger.exception("Error getting nearest POI metrics")
        return None


def shutdown_eta_service() -> None:
    """Shutdown the ETA service."""
    global _eta_calculator, _poi_manager

    try:
        logger.info("Shutting down ETA service")
        _eta_calculator = None
        _poi_manager = None
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
    ):
        logger.exception("Error during ETA service shutdown")
