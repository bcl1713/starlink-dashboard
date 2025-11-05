"""Performance benchmarks for ETA timing mode components."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from time import perf_counter

from app.models.flight_status import ETAMode, FlightPhase
from app.models.poi import POI
from app.models.route import (
    ParsedRoute,
    RouteMetadata,
    RoutePoint,
    RouteTimingProfile,
    RouteWaypoint,
)
from app.services.eta_calculator import ETACalculator
from app.services.flight_state_manager import get_flight_state_manager


def _build_large_route(point_count: int = 1200) -> ParsedRoute:
    """Construct a ParsedRoute with timing metadata and many waypoints."""
    departure_time = datetime.now(timezone.utc)
    arrival_time = departure_time + timedelta(minutes=point_count)
    metadata = RouteMetadata(
        name="Performance Route",
        description="Synthetic performance benchmark route",
        file_path="/tmp/perf-route.kml",
        point_count=point_count,
    )

    points: list[RoutePoint] = []
    waypoints: list[RouteWaypoint] = []
    base_lat = 35.0
    base_lon = -120.0

    for idx in range(point_count):
        # Generate a gentle arc to avoid zero-distance segments
        offset = idx * 0.01
        latitude = base_lat + offset
        longitude = base_lon + offset * 0.3

        points.append(
            RoutePoint(
                latitude=latitude,
                longitude=longitude,
                sequence=idx,
                expected_arrival_time=departure_time + timedelta(minutes=idx),
                expected_segment_speed_knots=320.0,
            )
        )
        waypoints.append(
            RouteWaypoint(
                name=f"WPT-{idx}",
                latitude=latitude,
                longitude=longitude,
                order=idx,
                expected_arrival_time=departure_time + timedelta(minutes=idx),
            )
        )

    timing_profile = RouteTimingProfile(
        departure_time=departure_time,
        arrival_time=arrival_time,
        total_expected_duration_seconds=(arrival_time - departure_time).total_seconds(),
        has_timing_data=True,
        segment_count_with_timing=point_count - 1,
    )

    return ParsedRoute(
        metadata=metadata,
        points=points,
        waypoints=waypoints,
        timing_profile=timing_profile,
    )


def _build_route_pois(route: ParsedRoute, count: int = 1100) -> list[POI]:
    """Create POIs aligned with the supplied route for performance testing."""
    pois: list[POI] = []
    base_lat = route.points[0].latitude
    base_lon = route.points[0].longitude

    for idx in range(count):
        # Use deterministic offsets to keep projections aligned without repetition
        offset = idx * 0.009
        latitude = base_lat + offset
        longitude = base_lon + offset * 0.27
        pois.append(
            POI(
                id=f"perf-{idx}",
                name=f"WPT-{idx}",
                latitude=latitude,
                longitude=longitude,
                route_id=route.metadata.file_path,
            )
        )

    return pois


def test_eta_calculator_large_route_and_poi_batch_performance():
    """Executing a large route-aware ETA calculation should stay within targets."""
    route = _build_large_route(point_count=1200)
    pois = _build_route_pois(route, count=1100)

    calculator = ETACalculator()

    start = perf_counter()
    metrics = calculator.calculate_poi_metrics(
        current_lat=route.points[0].latitude,
        current_lon=route.points[0].longitude,
        pois=pois,
        active_route=route,
        eta_mode=ETAMode.ANTICIPATED,
        flight_phase=FlightPhase.PRE_DEPARTURE,
    )
    elapsed = perf_counter() - start

    assert len(metrics) == len(pois)

    avg_per_poi = elapsed / len(pois)
    assert avg_per_poi < 0.05, f"Average ETA computation exceeded 50ms per POI ({avg_per_poi:.4f}s)"


def test_flight_state_manager_check_departure_overhead():
    """check_departure should remain below the 1ms target per invocation."""
    manager = get_flight_state_manager()
    manager.reset()

    iterations = 1000
    start = perf_counter()
    for _ in range(iterations):
        manager.check_departure(25.0)  # Below threshold to avoid state changes
    elapsed = perf_counter() - start

    avg_call_time = elapsed / iterations
    assert avg_call_time < 0.001, f"Average check_departure exceeded 1ms ({avg_call_time:.6f}s)"

    manager.reset()


def test_flight_state_manager_handles_rapid_transitions():
    """Stress-test rapid transition sequences to ensure stability."""
    manager = get_flight_state_manager()
    manager.reset()

    cycles = 50
    for _ in range(cycles):
        assert manager.trigger_departure(reason="perf-cycle")
        assert manager.trigger_arrival(reason="perf-cycle")
        manager.reset()

    final_status = manager.get_status()
    assert final_status.phase == FlightPhase.PRE_DEPARTURE
    assert final_status.eta_mode == ETAMode.ANTICIPATED
