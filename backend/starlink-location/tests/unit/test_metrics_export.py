"""Unit tests for Prometheus metrics export endpoint."""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from app.api import metrics_export
from app.models.poi import POI
from app.models.route import (
    ParsedRoute,
    RouteMetadata,
    RoutePoint,
    RouteTimingProfile,
)
from app.models.telemetry import (
    EnvironmentalData,
    NetworkData,
    ObstructionData,
    PositionData,
    TelemetryData,
)


def _make_telemetry(speed_knots: float = 250.0) -> TelemetryData:
    """Helper to create consistent telemetry samples."""
    return TelemetryData(
        timestamp=datetime.now(timezone.utc),
        position=PositionData(
            latitude=40.0,
            longitude=-73.0,
            altitude=10000.0,
            speed=speed_knots,
            heading=180.0,
        ),
        network=NetworkData(
            latency_ms=45.0,
            throughput_down_mbps=120.0,
            throughput_up_mbps=25.0,
            packet_loss_percent=0.5,
        ),
        obstruction=ObstructionData(obstruction_percent=5.0),
        environmental=EnvironmentalData(),
    )


class _DummyCoordinator:
    """Minimal coordinator stub that returns canned telemetry."""

    def __init__(self, telemetry: TelemetryData):
        self._telemetry = telemetry

    def get_current_telemetry(self) -> TelemetryData:
        return self._telemetry


class _DummyPOIManager:
    """Simple in-memory POI manager used for metrics export tests."""

    def __init__(self, *pois: POI):
        self._pois = {poi.id: poi for poi in pois}

    def list_pois(self) -> list[POI]:
        return list(self._pois.values())

    def get_poi(self, poi_id: str) -> POI | None:
        return self._pois.get(poi_id)


class _DummyRouteManager:
    """Route manager stub returning the provided active route."""

    def __init__(self, active_route: ParsedRoute | None):
        self._active_route = active_route

    def get_active_route(self) -> ParsedRoute | None:
        return self._active_route


def _make_parsed_route(has_timing: bool = True) -> ParsedRoute:
    """Create a ParsedRoute fixture with optional timing metadata."""
    metadata = RouteMetadata(
        name="Unit Test Route",
        description="Synthetic route for metrics export tests",
        file_path="/tmp/unit-test-route.kml",
        point_count=2,
    )
    points = [
        RoutePoint(latitude=40.0, longitude=-73.0, sequence=0),
        RoutePoint(latitude=41.0, longitude=-72.0, sequence=1),
    ]
    timing_profile = None
    if has_timing:
        departure_time = datetime.now(timezone.utc)
        arrival_time = departure_time + timedelta(hours=2)
        timing_profile = RouteTimingProfile(
            departure_time=departure_time,
            arrival_time=arrival_time,
            total_expected_duration_seconds=7200.0,
            has_timing_data=True,
            segment_count_with_timing=2,
        )
    return ParsedRoute(
        metadata=metadata,
        points=points,
        waypoints=[],
        timing_profile=timing_profile,
    )


@pytest.mark.anyio("asyncio")
async def test_metrics_export_emits_eta_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    """Metrics export exposes eta_type labels even without an active route."""

    telemetry = _make_telemetry()
    poi = POI(
        id="unit-poi",
        name="Unit Test POI",
        latitude=40.5,
        longitude=-72.5,
        category="test",
    )

    dummy_poi_manager = _DummyPOIManager(poi)
    dummy_route_manager = _DummyRouteManager(active_route=None)

    # metrics_export.set_poi_manager(dummy_poi_manager)
    # metrics_export.set_route_manager(dummy_route_manager)

    def _coordinator_factory(config: Any) -> _DummyCoordinator:
        return _DummyCoordinator(telemetry)

    monkeypatch.setattr(metrics_export, "SimulationCoordinator", _coordinator_factory)

    output = await metrics_export.get_metrics(
        route_manager=dummy_route_manager,
        poi_manager=dummy_poi_manager,
    )

    assert 'starlink_eta_poi_seconds' in output
    assert 'eta_type="' in output
    assert 'starlink_distance_to_poi_meters' in output


@pytest.mark.anyio("asyncio")
async def test_metrics_export_includes_route_timing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Route timing metrics are exported when active route has timing data."""

    telemetry = _make_telemetry()
    poi = POI(
        id="timed-poi",
        name="Timed Route POI",
        latitude=41.1,
        longitude=-71.9,
        category="timed",
        route_id="unit-route",
    )

    dummy_poi_manager = _DummyPOIManager(poi)
    dummy_route_manager = _DummyRouteManager(active_route=_make_parsed_route(has_timing=True))

    # metrics_export.set_poi_manager(dummy_poi_manager)
    # metrics_export.set_route_manager(dummy_route_manager)

    monkeypatch.setattr(
        metrics_export,
        "SimulationCoordinator",
        lambda config: _DummyCoordinator(telemetry),
    )

    output = await metrics_export.get_metrics(
        route_manager=dummy_route_manager,
        poi_manager=dummy_poi_manager,
    )

    assert "starlink_route_has_timing_data" in output
    assert "starlink_route_total_duration_seconds" in output
    assert "starlink_route_departure_time_unix" in output
    assert "starlink_route_arrival_time_unix" in output
    assert "starlink_route_segment_count_with_timing" in output
    assert 'eta_type="' in output
