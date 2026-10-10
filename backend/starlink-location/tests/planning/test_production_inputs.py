"""Exercise acceptance inputs through the real parser and public APIs."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.mission.dependencies import get_poi_manager
from app.mission.planning.extract import extract_itinerary
from app.mission.planning.inputs import resolve_positions
from app.mission.planning.routes import router
from app.satellites.routes import router as satellite_router
from app.services.kml.parser import parse_kml_file

from .test_match import kml_fixture
from .test_store import create
from .test_store import service as service_fixture

service = service_fixture


def test_production_seed_routes_match_extracted_itinerary(tmp_path):
    root = Path(__file__).resolve().parents[4]
    spec = importlib.util.spec_from_file_location(
        "acceptance_seed", root / "tools/acceptance/itinerary-planning/seed.py"
    )
    seed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed)
    itinerary = extract_itinerary(seed.pdf(1)).parsed_values
    for ordinal, leg in enumerate(itinerary.expected_legs, 1):
        path = tmp_path / f"leg-{ordinal}.kml"
        path.write_bytes(seed.kml(ordinal))
        route = parse_kml_file(path, profile="planning_v1")
        assert route.timing_profile is not None
        assert route.timing_profile.departure_time == leg.departure_time
        assert route.timing_profile.arrival_time == leg.arrival_time
        assert route.waypoints[0].name == leg.departure_airport
        assert route.waypoints[-1].name == leg.arrival_airport
        assert all(point.expected_arrival_time for point in route.points)


def test_route_without_timing_profile_returns_actionable_422(service, tmp_path):
    app = FastAPI()
    app.state.planning_service = service
    app.include_router(router)
    view, _ = create(service)
    data = kml_fixture(tmp_path).read_bytes().replace(b"AAAA-BBBB", b"Unnamed route")
    with TestClient(app) as client:
        response = client.post(
            f"/api/v2/missions/planning/missions/{view.mission.id}/legs/card-1/route-previews",
            data={"expected_revision": 1},
            files={"file": ("route.kml", data, "application/xml")},
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "route_timing_required"
    assert response.json()["detail"]["action"] == "replace_route"
    assert service.store.read(view.mission.id) == view


def test_api_created_satellites_are_validated_planning_options(service, monkeypatch):
    from app.satellites import catalog

    static = catalog.SatelliteCatalog()
    static.add_satellite(catalog.Satellite("SYNTH-X", "X", longitude=30))
    monkeypatch.setattr(catalog, "_catalog", static)
    app = FastAPI()
    app.state.planning_service = service
    app.include_router(router)
    app.include_router(satellite_router)
    app.dependency_overrides[get_poi_manager] = lambda: service.store.poi_manager
    with TestClient(app) as client:
        for identifier, transport, longitude in [
            ("SYNTH-X", "X", -100),
            ("SYNTH-KA", "Ka", -30),
        ]:
            response = client.post(
                "/api/satellites",
                json={
                    "satellite_id": identifier,
                    "transport": transport,
                    "longitude": longitude,
                },
            )
            assert response.status_code == 201
        options = client.get("/api/v2/missions/planning/satellite-options").json()[
            "satellites"
        ]
    by_id = {item["id"]: item for item in options}
    assert by_id["SYNTH-X"]["eligible"]
    assert by_id["SYNTH-X"]["longitude"] == -100
    assert not by_id["SYNTH-KA"]["eligible"]
    service.validate_selection(SimpleNamespace(permitted_satellite_ids=["SYNTH-X"]))
    positions = resolve_positions(["SYNTH-X"], service.store.poi_manager)
    assert positions[0].longitude == -100
    with pytest.raises(ValueError):
        resolve_positions(["SYNTH-KA"], service.store.poi_manager)


def test_invalid_or_ambiguous_configured_satellite_never_uses_static_fallback(
    service, monkeypatch
):
    from app.models.poi import POICreate
    from app.satellites import catalog

    static = catalog.SatelliteCatalog()
    static.add_satellite(catalog.Satellite("SYNTH", "X", longitude=30))
    monkeypatch.setattr(catalog, "_catalog", static)
    manager = service.store.poi_manager
    first = manager.create_poi(
        POICreate(
            name="SYNTH", latitude=0, longitude=-40, category="satellite", icon="Ka"
        )
    )
    assert not next(
        s for s in service.satellite_options().satellites if s.id == "SYNTH"
    ).eligible
    with pytest.raises(ValueError):
        resolve_positions(["SYNTH"], manager)
    manager.delete_poi(first.id)
    manager.create_poi(
        POICreate(
            name="SYNTH", latitude=0, longitude=-40, category="satellite", icon="X"
        )
    )
    manager.create_poi(
        POICreate(
            name="synth", latitude=0, longitude=-50, category="satellite", icon="X"
        )
    )
    assert all(not s.eligible for s in service.satellite_options().satellites)
    with pytest.raises(ValueError):
        resolve_positions(["SYNTH"], manager)


def test_arbitrary_poi_is_not_a_configured_satellite(service, monkeypatch):
    from app.models.poi import POICreate
    from app.satellites import catalog

    monkeypatch.setattr(catalog, "_catalog", catalog.SatelliteCatalog())
    service.store.poi_manager.create_poi(
        POICreate(name="ARBITRARY", latitude=0, longitude=-40, icon="X")
    )
    with pytest.raises(ValueError):
        resolve_positions(["ARBITRARY"], service.store.poi_manager)
