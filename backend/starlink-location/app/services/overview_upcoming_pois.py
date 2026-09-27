"""Truthful, route-aware projection for Overview upcoming mission POIs."""

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import TYPE_CHECKING

from app.models.overview_upcoming_pois import (
    OverviewUpcomingPoi,
    OverviewUpcomingPoisResponse,
)
from app.models.poi import POI

if TYPE_CHECKING:
    from app.models.route import ParsedRoute
    from app.services.eta_calculator import ETACalculator


RETAINED_AFTER_EXPECTED_ARRIVAL = timedelta(minutes=60)


def calculate_route_aware_eta_results(
    *,
    pois: list[POI],
    calculator: "ETACalculator",
    active_route: "ParsedRoute",
    flight_phase: str,
    latitude: float | None,
    longitude: float | None,
    speed_knots: float | None,
) -> dict[str, float | None]:
    """Calculate route-aware ETA results without endpoint coordinate fallbacks."""
    results: dict[str, float | None] = {}
    in_flight = flight_phase == "in_flight"

    for poi in pois:
        if in_flight:
            if latitude is None or longitude is None or speed_knots is None:
                results[poi.id] = None
                continue
            eta = calculator._calculate_route_aware_eta_estimated(
                latitude, longitude, poi, active_route, speed_knots
            )
        else:
            # The anticipated calculator is schedule/route based; its coordinate
            # arguments are not part of the calculation. Use the route origin,
            # never a generic endpoint coordinate fallback.
            route_origin = active_route.points[0] if active_route.points else None
            if route_origin is None:
                results[poi.id] = None
                continue
            eta = calculator._calculate_route_aware_eta_anticipated(
                route_origin.latitude, route_origin.longitude, poi, active_route
            )
        results[poi.id] = eta
    return results


def _is_valid_coordinate(latitude: float, longitude: float) -> bool:
    return (
        isfinite(latitude)
        and isfinite(longitude)
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


def project_overview_upcoming_pois(
    *,
    pois: list[POI],
    eta_results: dict[str, float | None],
    flight_phase: str,
    current_progress: float | None,
    calculated_at: datetime,
) -> OverviewUpcomingPoisResponse:
    """Project generated POIs with route-relative in-flight eligibility."""
    if calculated_at.tzinfo is None:
        calculated_at = calculated_at.replace(tzinfo=timezone.utc)
    else:
        calculated_at = calculated_at.astimezone(timezone.utc)

    eta_type = "estimated" if flight_phase == "in_flight" else "anticipated"
    projected: list[OverviewUpcomingPoi] = []
    for poi in pois:
        if poi.kind is None or not _is_valid_coordinate(poi.latitude, poi.longitude):
            continue

        eta_seconds = eta_results.get(poi.id)
        estimated_arrival_time = (
            calculated_at + timedelta(seconds=eta_seconds)
            if eta_seconds is not None
            else None
        )
        ahead_on_route = (
            current_progress is not None
            and poi.projected_route_progress is not None
            and 0 <= poi.projected_route_progress <= 100
            and poi.projected_route_progress > current_progress
        )
        if flight_phase == "in_flight":
            upcoming = ahead_on_route
        elif flight_phase == "post_arrival":
            upcoming = False
        else:
            upcoming = True

        if (
            poi.kind in {"departure", "arrival"}
            or upcoming
            or estimated_arrival_time is None
        ):
            map_retained = True
        else:
            map_retained = (
                calculated_at
                <= estimated_arrival_time + RETAINED_AFTER_EXPECTED_ARRIVAL
            )

        projected.append(
            OverviewUpcomingPoi(
                poi_id=poi.id,
                name=poi.name,
                kind=poi.kind,
                latitude=poi.latitude,
                longitude=poi.longitude,
                projected_route_progress=poi.projected_route_progress,
                expected_arrival_time=poi.expected_arrival_time,
                eta_seconds=eta_seconds,
                estimated_arrival_time=estimated_arrival_time,
                eta_type=eta_type,
                flight_phase=flight_phase,
                upcoming=upcoming,
                map_retained=map_retained,
            )
        )

    if flight_phase == "in_flight":
        projected.sort(
            key=lambda poi: (
                not poi.upcoming,
                poi.eta_seconds is None,
                poi.eta_seconds if poi.eta_seconds is not None else float("inf"),
                (
                    poi.projected_route_progress
                    if poi.projected_route_progress is not None
                    else float("inf")
                ),
                poi.poi_id,
            )
        )
    else:
        projected.sort(
            key=lambda poi: (
                not poi.upcoming,
                (
                    poi.projected_route_progress
                    if poi.projected_route_progress is not None
                    else float("inf")
                ),
                poi.poi_id,
            )
        )
    state = (
        "available" if any(poi.upcoming for poi in projected) else "no_upcoming_pois"
    )
    return OverviewUpcomingPoisResponse(
        state=state,
        calculated_at=calculated_at,
        pois=projected,
    )
