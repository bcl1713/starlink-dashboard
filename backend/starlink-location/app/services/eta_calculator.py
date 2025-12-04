"""
Backward compatibility wrapper for eta_calculator module.

This file maintains backward compatibility by providing the original
ETACalculator class with all methods integrated.

DEPRECATED: Import from app.services.eta instead.
"""

from app.services.eta.calculator import ETACalculator as _ETACalculator
from app.services.eta.projection import ETAProjection
from app.models.poi import POI
from app.models.flight_status import ETAMode, FlightPhase
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.route import ParsedRoute


class ETACalculator(_ETACalculator):
    """
    Calculate ETA and distance to POIs with speed smoothing.

    This class extends the base calculator with projection capabilities
    to maintain backward compatibility with the original implementation.
    """

    def __init__(
        self,
        smoothing_duration_seconds: float = 120.0,
        default_speed_knots: float = 150.0,
    ):
        """Initialize ETA calculator with projection capabilities."""
        super().__init__(smoothing_duration_seconds, default_speed_knots)
        self._projection = ETAProjection(self)

    def calculate_poi_metrics(
        self,
        current_lat: float,
        current_lon: float,
        pois: list[POI],
        speed_knots: Optional[float] = None,
        active_route: Optional["ParsedRoute"] = None,
        eta_mode: ETAMode = ETAMode.ESTIMATED,
        flight_phase: Optional[FlightPhase] = None,
    ) -> dict[str, dict]:
        """
        Calculate distance and ETA metrics for all POIs with dual-mode support.

        Delegates to ETAProjection for route-aware calculations.
        """
        return self._projection.calculate_poi_metrics(
            current_lat,
            current_lon,
            pois,
            speed_knots,
            active_route,
            eta_mode,
            flight_phase,
        )

    def _calculate_route_aware_eta(
        self,
        current_lat: float,
        current_lon: float,
        poi: POI,
        active_route: "ParsedRoute",
    ) -> Optional[float]:
        """
        DEPRECATED: Use _calculate_route_aware_eta_estimated or _calculate_route_aware_eta_anticipated instead.

        This method is kept for backward compatibility but delegates to estimated mode.
        """
        return self._projection._calculate_route_aware_eta_estimated(
            current_lat, current_lon, poi, active_route
        )

    def _calculate_route_aware_eta_estimated(
        self,
        current_lat: float,
        current_lon: float,
        poi: POI,
        active_route: "ParsedRoute",
        current_speed_knots: Optional[float] = None,
    ) -> Optional[float]:
        """Calculate ETA using segment-based speeds with speed blending (estimated/in-flight mode)."""
        return self._projection._calculate_route_aware_eta_estimated(
            current_lat, current_lon, poi, active_route, current_speed_knots
        )

    def _calculate_route_aware_eta_anticipated(
        self,
        current_lat: float,
        current_lon: float,
        poi: POI,
        active_route: "ParsedRoute",
    ) -> Optional[float]:
        """Calculate ETA using expected times from flight plan (anticipated/pre-departure mode)."""
        return self._projection._calculate_route_aware_eta_anticipated(
            current_lat, current_lon, poi, active_route
        )

    def _calculate_on_route_eta_estimated(
        self,
        current_lat: float,
        current_lon: float,
        destination_waypoint: "RouteWaypoint",
        active_route: "ParsedRoute",
        current_speed_knots: Optional[float] = None,
    ) -> Optional[float]:
        """Calculate ETA for a waypoint with speed blending (estimated/in-flight mode)."""
        return self._projection._calculate_on_route_eta_estimated(
            current_lat,
            current_lon,
            destination_waypoint,
            active_route,
            current_speed_knots,
        )

    def _calculate_on_route_eta(
        self,
        current_lat: float,
        current_lon: float,
        destination_waypoint: "RouteWaypoint",
        active_route: "ParsedRoute",
    ) -> Optional[float]:
        """
        Calculate ETA for a waypoint that is on the active route.

        DEPRECATED: This delegates to estimated mode for backward compatibility.
        """
        return self._projection._calculate_on_route_eta_estimated(
            current_lat, current_lon, destination_waypoint, active_route
        )

    def _calculate_off_route_eta_with_projection_estimated(
        self,
        current_lat: float,
        current_lon: float,
        poi: POI,
        active_route: "ParsedRoute",
        current_speed_knots: Optional[float] = None,
    ) -> Optional[float]:
        """Calculate ETA for off-route POI with speed blending (estimated/in-flight mode)."""
        return self._projection._calculate_off_route_eta_with_projection_estimated(
            current_lat, current_lon, poi, active_route, current_speed_knots
        )

    def _calculate_off_route_eta_with_projection(
        self,
        current_lat: float,
        current_lon: float,
        poi: POI,
        active_route: "ParsedRoute",
    ) -> Optional[float]:
        """
        Calculate ETA for a POI that is off-route but has projection data.

        DEPRECATED: This delegates to estimated mode for backward compatibility.
        """
        return self._projection._calculate_off_route_eta_with_projection_estimated(
            current_lat, current_lon, poi, active_route
        )


__all__ = ["ETACalculator"]
