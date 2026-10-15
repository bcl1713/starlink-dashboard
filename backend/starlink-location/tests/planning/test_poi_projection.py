"""Projection uses coherent inputs without holding persistence gates during geometry."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from app.mission import storage
from app.models.poi import POICreate, POIUpdate
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
from app.services.poi_manager import POIManager
from app.services.route_eta_calculator import RouteETACalculator


@pytest.fixture
def projection_context(tmp_path):
    manager = POIManager(tmp_path / "pois.json")
    route = ParsedRoute(
        metadata=RouteMetadata(name="Route", file_path="route.kml", point_count=2),
        points=[
            RoutePoint(latitude=0, longitude=0, sequence=0),
            RoutePoint(latitude=1, longitude=1, sequence=1),
        ],
    )
    return manager, route


@pytest.mark.parametrize("operation", ["create", "calculate"])
def test_projection_computation_does_not_block_persistence_readers(
    projection_context, monkeypatch, operation
):
    manager, route = projection_context
    poi = POICreate(name="Point", latitude=0.5, longitude=0.5)
    if operation == "calculate":
        manager.create_poi(poi)
    entered, release = Event(), Event()
    original = RouteETACalculator.project_poi_to_route

    def blocked(self, *args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(RouteETACalculator, "project_poi_to_route", blocked)
    with ThreadPoolExecutor(max_workers=2) as executor:
        projection = (
            executor.submit(manager.create_poi, poi, route)
            if operation == "create"
            else executor.submit(manager.calculate_poi_projections, route)
        )
        try:
            assert entered.wait(5)
            read = executor.submit(storage.list_mission_metadata_v2)
            assert read.result(timeout=1) == []
        finally:
            release.set()
        result = projection.result(timeout=5)
        assert (
            result.projected_latitude is not None
            if operation == "create"
            else result == 1
        )


@pytest.mark.parametrize("changed_input", ["poi", "route", "clear"])
def test_projection_does_not_publish_stale_inputs(
    projection_context, monkeypatch, changed_input
):
    manager, route = projection_context
    poi = manager.create_poi(POICreate(name="Point", latitude=0.5, longitude=0.5))
    other = POIManager(manager.pois_file)
    original = RouteETACalculator.project_poi_to_route
    changed = False

    def modify_during_computation(self, *args, **kwargs):
        nonlocal changed
        if not changed:
            changed = True
            if changed_input == "poi":
                other.update_poi(poi.id, POIUpdate(latitude=0.8))
            elif changed_input == "route":
                route.points[1].longitude = 2
            else:
                other.clear_poi_projections()
        return original(self, *args, **kwargs)

    monkeypatch.setattr(
        RouteETACalculator, "project_poi_to_route", modify_during_computation
    )
    assert manager.calculate_poi_projections(route) == 0
    stored = other.get_poi(poi.id)
    assert stored.projected_latitude is None
    if changed_input == "poi":
        assert stored.latitude == 0.8


def test_create_projection_preserves_concurrent_write_and_unique_ids(
    projection_context, monkeypatch
):
    manager, route = projection_context
    other = POIManager(manager.pois_file)
    poi = POICreate(name="Point", latitude=0.5, longitude=0.5)
    original = RouteETACalculator.project_poi_to_route

    def concurrent_create(self, *args, **kwargs):
        other.create_poi(poi)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(RouteETACalculator, "project_poi_to_route", concurrent_create)
    created = manager.create_poi(poi, route)
    assert created.id == "point-1"
    assert {p.id for p in other.list_pois()} == {"point", "point-1"}
    assert created.projected_latitude is not None


def test_create_skips_projection_if_route_changes_during_computation(
    projection_context, monkeypatch
):
    manager, route = projection_context
    original = RouteETACalculator.project_poi_to_route

    def changed_route(self, *args, **kwargs):
        route.points[1].longitude = 2
        return original(self, *args, **kwargs)

    monkeypatch.setattr(RouteETACalculator, "project_poi_to_route", changed_route)
    created = manager.create_poi(
        POICreate(name="Point", latitude=0.5, longitude=0.5), route
    )
    assert created.projected_latitude is None
    assert manager.get_poi(created.id).projected_latitude is None
