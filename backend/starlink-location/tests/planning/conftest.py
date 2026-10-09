"""Planning tests own their stores, including inherited ETA setup."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def planning_storage(tmp_path: Path, monkeypatch):
    from app.services import poi_manager, route_manager

    inherited_poi_init = poi_manager.POIManager.__init__
    inherited_route_init = route_manager.RouteManager.__init__

    def poi_init(self, pois_file=None):
        inherited_poi_init(self, pois_file or tmp_path / "pois.json")

    def route_init(self, routes_dir=None):
        inherited_route_init(self, routes_dir or tmp_path / "routes")

    monkeypatch.setattr(poi_manager.POIManager, "__init__", poi_init)
    monkeypatch.setattr(route_manager.RouteManager, "__init__", route_init)
    yield tmp_path


@pytest.fixture(autouse=True)
def ensure_eta_service_initialized(planning_storage):
    """Override the parent's setup so dependencies use owned paths first."""
    from app.core import eta_service
    from app.services.poi_manager import POIManager

    original = eta_service._eta_calculator
    eta_service._eta_calculator = None
    eta_service.initialize_eta_service(POIManager())
    yield
    eta_service._eta_calculator = original
