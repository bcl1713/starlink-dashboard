"""Freshness contract tests for route coordinate overlay endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from app.api import geojson
from app.mission.dependencies import get_route_manager
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
from app.services.route_manager import RouteManager
from fastapi.testclient import TestClient
from main import app

OLD_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Snapshot Route</name>
    <Placemark>
      <LineString>
        <coordinates>
          1.0,2.0,100.0
          3.0,4.0,200.0
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>"""

NEW_KML = OLD_KML.replace("1.0,2.0,100.0", "11.0,12.0,300.0").replace(
    "Snapshot Route", "Reloaded Route"
)


class StaticRouteManager:
    def __init__(self, route: ParsedRoute | None) -> None:
        self.route = route

    def get_active_route(self) -> ParsedRoute | None:
        return self.route

    def get_route(self, route_id: str) -> ParsedRoute | None:
        return self.route


def _route(
    file_path: str,
    source_revision_at: datetime | None = datetime(
        2026, 8, 29, 11, 30, tzinfo=timezone.utc
    ),
) -> ParsedRoute:
    return ParsedRoute(
        metadata=RouteMetadata(
            name="IDL route",
            file_path=file_path,
            point_count=3,
            source_revision_at=source_revision_at,
        ),
        points=[
            RoutePoint(latitude=10.0, longitude=-170.0, altitude=1000.0, sequence=0),
            RoutePoint(latitude=11.0, longitude=-160.0, altitude=1100.0, sequence=1),
            RoutePoint(latitude=12.0, longitude=170.0, altitude=1200.0, sequence=2),
        ],
    )


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_west_and_east_coordinates_include_route_revision_and_generated_at(
    client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "route.kml"
    source.write_text("<kml />")
    generated_at = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(geojson, "_utc_now", lambda: generated_at)
    app.dependency_overrides[get_route_manager] = lambda: StaticRouteManager(
        _route(str(source))
    )

    west = client.get("/api/route/coordinates/west")
    east = client.get("/api/route/coordinates/east")

    assert west.status_code == 200
    assert east.status_code == 200
    assert west.json()["revision_at"] == "2026-08-29T11:30:00Z"
    assert east.json()["revision_at"] == "2026-08-29T11:30:00Z"
    assert west.json()["generated_at"] == "2026-08-29T12:00:00Z"
    assert east.json()["generated_at"] == "2026-08-29T12:00:00Z"
    assert west.json()["coordinates"][0] == {
        "latitude": 10.0,
        "longitude": -170.0,
        "altitude_meters": 1000.0,
        "sequence": 0.0,
    }


def test_unchanged_route_revision_is_stable_while_generated_at_advances(
    client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "route.kml"
    source.write_text("<kml />")
    generated_times = iter(
        [
            datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 8, 29, 12, 1, tzinfo=timezone.utc),
        ]
    )
    monkeypatch.setattr(geojson, "_utc_now", lambda: next(generated_times))
    app.dependency_overrides[get_route_manager] = lambda: StaticRouteManager(
        _route(str(source))
    )

    first = client.get("/api/route/coordinates/west").json()
    second = client.get("/api/route/coordinates/west").json()

    assert first["revision_at"] == second["revision_at"]
    assert first["generated_at"] == "2026-08-29T12:00:00Z"
    assert second["generated_at"] == "2026-08-29T12:01:00Z"


def test_manual_route_without_source_revision_reports_none(
    client: TestClient, tmp_path
) -> None:
    source = tmp_path / "route.kml"
    source.write_text("<kml />")
    revision_epoch = datetime(2026, 8, 29, 11, 30, tzinfo=timezone.utc).timestamp()
    os.utime(source, (revision_epoch, revision_epoch))
    app.dependency_overrides[get_route_manager] = lambda: StaticRouteManager(
        _route(str(source), source_revision_at=None)
    )

    response = client.get("/api/route/coordinates/west")

    assert response.status_code == 200
    assert response.json()["revision_at"] is None


def test_cached_route_revision_and_coordinates_survive_watcher_gap(
    client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "route.kml"
    first_revision = datetime(2026, 1, 1, tzinfo=timezone.utc)
    second_revision = datetime(2026, 1, 2, tzinfo=timezone.utc)
    source.write_text(OLD_KML)
    os.utime(
        source,
        ns=(
            int(first_revision.timestamp() * 1_000_000_000),
            int(first_revision.timestamp() * 1_000_000_000),
        ),
    )
    manager = RouteManager(routes_dir=tmp_path)
    manager._load_route_file(str(source))
    manager.activate_route("route")
    app.dependency_overrides[get_route_manager] = lambda: manager
    monkeypatch.setattr(
        geojson,
        "_utc_now",
        lambda: datetime(2026, 1, 3, tzinfo=timezone.utc),
    )

    source.write_text(NEW_KML)
    os.utime(
        source,
        ns=(
            int(second_revision.timestamp() * 1_000_000_000),
            int(second_revision.timestamp() * 1_000_000_000),
        ),
    )
    stale = client.get("/api/route/coordinates").json()

    assert stale["revision_at"] == "2026-01-01T00:00:00Z"
    assert stale["coordinates"][0]["latitude"] == 2.0
    assert stale["coordinates"][0]["longitude"] == 1.0

    manager._load_route_file(str(source))
    fresh = client.get("/api/route/coordinates").json()

    assert fresh["revision_at"] == "2026-01-02T00:00:00Z"
    assert fresh["coordinates"][0]["latitude"] == 12.0
    assert fresh["coordinates"][0]["longitude"] == 11.0


def test_missing_route_has_no_revision_but_still_reports_generation_time(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        geojson,
        "_utc_now",
        lambda: datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
    )
    app.dependency_overrides[get_route_manager] = lambda: StaticRouteManager(None)

    response = client.get("/api/route/coordinates/west")

    assert response.status_code == 200
    assert response.json() == {
        "coordinates": [],
        "total": 0,
        "route_id": None,
        "route_name": None,
        "revision_at": None,
        "generated_at": "2026-08-29T12:00:00Z",
    }


def test_coordinate_endpoints_use_typed_openapi_responses(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert (
        schema["paths"]["/api/route/coordinates/west"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/RouteCoordinatesResponse"
    )
    assert (
        schema["paths"]["/api/route/coordinates/east"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/RouteCoordinatesResponse"
    )
