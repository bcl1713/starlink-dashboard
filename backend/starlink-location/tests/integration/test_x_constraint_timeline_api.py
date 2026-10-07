"""API round trip using wholly invented route and look-angle fixtures."""

import csv
import io
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.mission import routes_v2
from app.mission.exporter.__main__ import generate_csv_export
from app.mission.models import (
    AARWindow,
    Mission,
    MissionLeg,
    MissionLegTimeline,
    TransportConfig,
)
from app.mission.timeline_builder.stats import summarize_timeline
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint, RouteTimingProfile
from app.satellites.catalog import Satellite, SatelliteCatalog
from app.services.route_manager import RouteManager


@pytest.mark.parametrize("restriction", ["elevation", "ar"])
def test_preview_saved_recomputed_and_csv_agree_on_hard_x_restriction(
    monkeypatch, tmp_path, restriction
):
    start = datetime(2035, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(hours=1)
    route = ParsedRoute(
        metadata=RouteMetadata(
            name="Invented route", file_path="invented.kml", point_count=2
        ),
        points=[
            RoutePoint(
                latitude=0,
                longitude=lon,
                altitude=10000,
                sequence=i,
                expected_arrival_time=ts,
            )
            for i, lon, ts in [(0, 0, start), (1, 6, end)]
        ],
        timing_profile=RouteTimingProfile(
            departure_time=start, arrival_time=end, has_timing_data=True
        ),
    )
    manager = RouteManager(routes_dir=tmp_path / "routes")
    manager.add_route("invented-route", route)
    catalog = SatelliteCatalog()
    catalog.add_satellite(Satellite("X-invented", "X", longitude=0))
    monkeypatch.setattr("app.satellites.catalog._catalog", catalog)

    def angles(lat, lon, alt, sat):
        minute = round(lon * 10, 6)
        relative = 180 if 10 <= minute < 50 else 90
        if restriction == "ar" and 20 <= minute < 40:
            relative = 0
        # Heading along this invented eastbound route is 90 degrees.
        return (relative + 90) % 360, (
            5 if restriction == "elevation" and 20 <= minute < 40 else 20
        )

    monkeypatch.setattr("app.satellites.rules.look_angles", angles)

    class InventedKaCoverage:
        def check_coverage_at_point(self, lat, lon):
            return {"Ka-invented"}

    monkeypatch.setattr(routes_v2, "_coverage_sampler", InventedKaCoverage())
    transports = TransportConfig(initial_x_satellite_id="X-invented")
    if restriction == "ar":
        transports.aar_windows = [
            AARWindow(
                id="invented-ar",
                start_waypoint_name="IN",
                end_waypoint_name="OUT",
                override_start_time=start + timedelta(minutes=20),
                override_end_time=start + timedelta(minutes=39),
            )
        ]
    leg = MissionLeg(
        id="invented-leg",
        name="Invented leg",
        route_id="invented-route",
        transports=transports,
    )
    mission = Mission(id="invented-mission", name="Invented mission", legs=[leg])
    app = FastAPI()
    app.include_router(routes_v2.router)
    app.dependency_overrides[routes_v2.get_route_manager] = lambda: manager
    app.dependency_overrides[routes_v2.get_poi_manager] = lambda: None
    root = "/api/v2/missions/invented-mission"
    leg_root = f"{root}/legs/invented-leg"
    with TestClient(app) as client:
        response = client.post("/api/v2/missions", json=mission.model_dump(mode="json"))
        assert response.status_code == 201, response.text
        preview = client.post(f"{leg_root}/timeline/preview", json={})
        assert preview.status_code == 200, preview.text
        saved = client.get(f"{leg_root}/timeline")
        assert saved.status_code == 200, saved.text
        reloaded = client.get(root)
        assert reloaded.status_code == 200
        updated = client.put(leg_root, json=reloaded.json()["legs"][0])
        assert updated.status_code == 200, updated.text
        recomputed = client.get(f"{leg_root}/timeline")
        assert recomputed.status_code == 200

    assert (
        preview.json()["segments"]
        == saved.json()["segments"]
        == recomputed.json()["segments"]
    )
    timeline = MissionLegTimeline.model_validate(recomputed.json())
    assert preview.json()["statistics"] == timeline.statistics
    for minute, state in [
        (11, "available"),
        (21, "degraded"),
        (31, "degraded"),
        (41, "available"),
    ]:
        timestamp = start + timedelta(minutes=minute)
        segment = next(
            s for s in timeline.segments if s.start_time <= timestamp < s.end_time
        )
        assert segment.x_state.value == state
    hard_seconds = 1200  # One-minute sampling; the inclusive AR end clears at 40.
    assert timeline.statistics["degraded_seconds"] == hard_seconds
    summary = summarize_timeline(timeline, start, end, 61, 60, 0)
    assert summary.degraded_seconds == hard_seconds
    rows = list(
        csv.DictReader(io.StringIO(generate_csv_export(timeline, leg).decode()))
    )
    assert [r["X-Band"] for r in rows] == [
        s.x_state.value.upper() for s in timeline.segments
    ]
    assert "DEGRADED" in [r["X-Band"] for r in rows]
