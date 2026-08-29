"""Regression tests for endpoint POIs restored by mission-package imports."""

import asyncio
import io
import json
import zipfile
from datetime import datetime, timezone

from app.mission.models import Mission, MissionLeg, TransportConfig
from app.mission.routes_v2 import (
    _synchronize_imported_endpoint_pois,
    import_mission,
)
from app.models.poi import POICreate
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from fastapi import UploadFile
from starlette.requests import Request


def _mission() -> Mission:
    return Mission(
        id="imported-mission",
        name="Imported Mission",
        legs=[
            MissionLeg(
                id="imported-leg",
                name="Imported Leg",
                route_id="imported-route",
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            )
        ],
    )


def _route() -> ParsedRoute:
    return ParsedRoute(
        metadata=RouteMetadata(
            name="Imported Route",
            file_path="/tmp/imported-route.kml",
            point_count=2,
            imported_at=datetime.now(timezone.utc),
        ),
        points=[
            RoutePoint(latitude=10.0, longitude=20.0, sequence=0),
            RoutePoint(latitude=30.0, longitude=40.0, sequence=1),
        ],
    )


def test_synchronize_imported_endpoint_pois_restores_persists_and_reconciles(
    tmp_path,
):
    """Imported endpoints are route/mission scoped, durable, and idempotent."""
    mission = _mission()
    route_manager = RouteManager(routes_dir=tmp_path / "routes")
    route_manager.add_route("imported-route", _route())
    poi_manager = POIManager(pois_file=tmp_path / "pois.json")

    unrelated = [
        POICreate(name="User POI", latitude=1.0, longitude=2.0),
        POICreate(
            name="Satellite POI",
            latitude=3.0,
            longitude=4.0,
            category="satellite",
        ),
        POICreate(
            name="Mission event",
            latitude=5.0,
            longitude=6.0,
            category="transition",
            route_id="imported-route",
            mission_id=mission.id,
        ),
    ]
    for poi in unrelated:
        poi_manager.create_poi(poi)

    created, warnings = _synchronize_imported_endpoint_pois(
        mission, route_manager, poi_manager
    )

    assert created == 2
    assert warnings == []
    endpoints = [
        poi
        for poi in poi_manager.list_pois()
        if poi.description and "mission-package endpoint" in poi.description
    ]
    assert {(poi.category, poi.icon) for poi in endpoints} == {
        ("departure", "airport"),
        ("arrival", "flag"),
    }
    assert {(poi.latitude, poi.longitude) for poi in endpoints} == {
        (10.0, 20.0),
        (30.0, 40.0),
    }
    assert all(poi.route_id == "imported-route" for poi in endpoints)
    assert all(poi.mission_id == mission.id for poi in endpoints)

    persisted = POIManager(pois_file=tmp_path / "pois.json").list_pois()
    assert (
        len(
            [
                poi
                for poi in persisted
                if poi.description and "mission-package endpoint" in poi.description
            ]
        )
        == 2
    )

    created, warnings = _synchronize_imported_endpoint_pois(
        mission, route_manager, poi_manager
    )

    assert created == 2
    assert warnings == []
    assert len(poi_manager.list_pois()) == 5
    assert {poi.name for poi in poi_manager.list_pois()} >= {
        "User POI",
        "Satellite POI",
        "Mission event",
    }


def test_synchronize_imported_endpoint_pois_warns_for_missing_route(tmp_path):
    """An unresolved imported leg reports a warning instead of a full success."""
    poi_manager = POIManager(pois_file=tmp_path / "pois.json")
    route_manager = RouteManager(routes_dir=tmp_path / "routes")

    created, warnings = _synchronize_imported_endpoint_pois(
        _mission(), route_manager, poi_manager
    )

    assert created == 0
    assert warnings == [
        "Endpoint POIs not restored for leg imported-leg: route unavailable"
    ]


def test_package_import_restores_endpoint_pois_and_reimport_is_idempotent(
    tmp_path, monkeypatch
):
    """The package-import endpoint restores and safely replaces its endpoint POIs."""
    mission = _mission()
    package = io.BytesIO()
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("mission.json", mission.model_dump_json())
        archive.writestr(
            "routes/imported-route.kml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <kml xmlns="http://www.opengis.net/kml/2.2"><Document>
              <Placemark><LineString><coordinates>
                20.0,10.0,0 40.0,30.0,0
              </coordinates></LineString></Placemark>
            </Document></kml>""",
        )

    route_manager = RouteManager(routes_dir=tmp_path / "routes")
    poi_manager = POIManager(pois_file=tmp_path / "pois.json")
    poi_manager.create_poi(POICreate(name="User POI", latitude=1.0, longitude=2.0))
    monkeypatch.setattr("app.mission.routes_v2.save_mission_v2", lambda mission: None)
    monkeypatch.setattr(
        "app.mission.routes_v2._generate_timelines_for_imported_legs",
        lambda *args: [],
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v2/missions/import",
            "headers": [],
            "client": ("testclient", 50000),
        }
    )

    def run_import():
        return asyncio.run(
            import_mission(
                request=request,
                file=UploadFile(
                    file=io.BytesIO(package.getvalue()), filename="mission.zip"
                ),
                route_manager=route_manager,
                poi_manager=poi_manager,
            )
        )

    first_import = run_import()
    second_import = run_import()

    assert first_import["endpoint_pois_restored"] == 2
    assert second_import["endpoint_pois_restored"] == 2
    endpoints = [
        poi
        for poi in poi_manager.list_pois()
        if poi.description and "mission-package endpoint" in poi.description
    ]
    assert len(endpoints) == 2
    assert {poi.category for poi in endpoints} == {"departure", "arrival"}
    assert {poi.name for poi in poi_manager.list_pois()} >= {"User POI"}
    assert json.loads((tmp_path / "pois.json").read_text())["pois"]
