"""HTTP regressions for server-owned V2 lifecycle state and route replacement."""

import io
import json
import zipfile
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.mission.models import (
    Mission,
    MissionLeg,
    MissionLegTimeline,
    TimelineSegment,
    TimelineStatus,
    TransportConfig,
)
from app.mission.storage import load_mission_v2
from app.mission.timeline_service import TimelineSummary
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
from fastapi.testclient import TestClient


KML = b'''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><LineString>
<coordinates>-120.0,35.0,0 -121.0,36.0,0</coordinates>
</LineString></Placemark></Document></kml>'''


def _timeline(leg_id: str) -> tuple[MissionLegTimeline, TimelineSummary]:
    now = datetime.now(timezone.utc)
    return (
        MissionLegTimeline(
            mission_leg_id=leg_id,
            segments=[
                TimelineSegment(
                    id=f"segment-{leg_id}",
                    start_time=now,
                    end_time=now + timedelta(minutes=1),
                    status=TimelineStatus.NOMINAL,
                )
            ],
        ),
        TimelineSummary(
            mission_start=now,
            mission_end=now + timedelta(minutes=1),
            degraded_seconds=0,
            critical_seconds=0,
            next_conflict_seconds=-1,
            transport_states={},
            sample_count=1,
            sample_interval_seconds=60,
            generation_runtime_ms=1,
        ),
    )


def _mission(prefix: str, *, active: bool = False) -> Mission:
    suffix = uuid4().hex[:8]
    return Mission(
        id=f"{prefix}-mission-{suffix}",
        name=f"{prefix} mission",
        legs=[
            MissionLeg(
                id=f"{prefix}-leg-{suffix}",
                name=f"{prefix} leg",
                route_id=f"{prefix}-route-{suffix}",
                transports=TransportConfig(initial_x_satellite_id="X-1"),
                is_active=active,
            )
        ],
    )


def _add_route(client: TestClient, leg: MissionLeg, routes_dir: Path | None = None) -> None:
    client.app.state.route_manager.add_route(
        leg.route_id,
        ParsedRoute(
            metadata=RouteMetadata(
                name=leg.route_id,
                file_path=str((routes_dir or Path("/tmp")) / f"{leg.route_id}.kml"),
                point_count=2,
            ),
            points=[RoutePoint(latitude=0.0, longitude=0.0), RoutePoint(latitude=1.0, longitude=1.0)],
        ),
    )


def _activate(client: TestClient, mission: Mission) -> None:
    _add_route(client, mission.legs[0])
    with patch("app.mission.routes_v2.build_mission_timeline", side_effect=lambda mission, **_: _timeline(mission.id)):
        response = client.post(f"/api/v2/missions/{mission.id}/legs/{mission.legs[0].id}/activate")
    assert response.status_code == 200


def _active_snapshot(client: TestClient, mission: Mission) -> tuple[bool, str | None]:
    stored = load_mission_v2(mission.id)
    assert stored is not None
    return stored.legs[0].is_active, client.app.state.route_manager.get_active_route_id()


def _package(mission: Mission) -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("mission.json", json.dumps(mission.model_dump(mode="json")))
    return payload.getvalue()


class TestV2LifecycleWriteGuards:
    def test_create_normalizes_client_active_flags_without_disturbing_active_context(self, client: TestClient):
        active_parent = _mission("active")
        assert client.post("/api/v2/missions", json=active_parent.model_dump(mode="json")).status_code == 201
        _activate(client, active_parent)
        before = _active_snapshot(client, active_parent)
        candidate = _mission("created", active=True)

        response = client.post("/api/v2/missions", json=candidate.model_dump(mode="json"))

        assert response.status_code == 201
        assert response.json()["legs"][0]["is_active"] is False
        assert load_mission_v2(candidate.id).legs[0].is_active is False
        assert _active_snapshot(client, active_parent) == before

    def test_add_leg_normalizes_client_active_flag_without_disturbing_active_context(self, client: TestClient):
        active_parent = _mission("active")
        inactive_parent = _mission("inactive")
        assert client.post("/api/v2/missions", json=active_parent.model_dump(mode="json")).status_code == 201
        assert client.post("/api/v2/missions", json=inactive_parent.model_dump(mode="json")).status_code == 201
        _activate(client, active_parent)
        before = _active_snapshot(client, active_parent)
        incoming = _mission("incoming", active=True).legs[0]

        response = client.post(f"/api/v2/missions/{inactive_parent.id}/legs", json=incoming.model_dump(mode="json"))

        assert response.status_code == 201
        assert response.json()["is_active"] is False
        assert load_mission_v2(inactive_parent.id).legs[-1].is_active is False
        assert _active_snapshot(client, active_parent) == before

    def test_import_normalizes_client_active_flags_without_disturbing_external_active_context(self, client: TestClient):
        active_parent = _mission("active")
        assert client.post("/api/v2/missions", json=active_parent.model_dump(mode="json")).status_code == 201
        _activate(client, active_parent)
        before = _active_snapshot(client, active_parent)
        imported = _mission("imported", active=True)

        response = client.post("/api/v2/missions/import", files={"file": ("mission.zip", _package(imported), "application/zip")})

        assert response.status_code == 200
        assert load_mission_v2(imported.id).legs[0].is_active is False
        assert _active_snapshot(client, active_parent) == before

    def test_import_over_active_parent_is_conflict_before_any_mutation(self, client: TestClient):
        active_parent = _mission("active")
        assert client.post("/api/v2/missions", json=active_parent.model_dump(mode="json")).status_code == 201
        _activate(client, active_parent)
        before_mission = load_mission_v2(active_parent.id).model_dump(mode="json")
        before_route = client.app.state.route_manager.get_active_route_id()
        replacement = active_parent.model_copy(deep=True)
        replacement.name = "replacement should not persist"
        replacement.legs[0].is_active = True

        response = client.post("/api/v2/missions/import", files={"file": ("mission.zip", _package(replacement), "application/zip")})

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "ACTIVE_MISSION_IMPORT_FORBIDDEN"
        assert load_mission_v2(active_parent.id).model_dump(mode="json") == before_mission
        assert client.app.state.route_manager.get_active_route_id() == before_route

    def test_active_leg_route_upload_is_strict_noop_with_actionable_code(self, client: TestClient, tmp_path: Path):
        mission = _mission("active")
        assert client.post("/api/v2/missions", json=mission.model_dump(mode="json")).status_code == 201
        _activate(client, mission)
        route_manager = client.app.state.route_manager
        original_routes = deepcopy(route_manager._routes)
        original_route_id = route_manager.get_active_route_id()
        stored_before = load_mission_v2(mission.id).model_dump(mode="json")
        poi_manager = client.app.state.poi_manager
        poi_manager.delete_route_pois = MagicMock(wraps=poi_manager.delete_route_pois)
        routes_dir = Path(route_manager.routes_dir)
        files_before = sorted(path.name for path in routes_dir.glob("*"))

        response = client.put(
            f"/api/v2/missions/{mission.id}/legs/{mission.legs[0].id}/route",
            files={"file": ("replacement.kml", KML, "application/vnd.google-earth.kml+xml")},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == {
            "code": "ACTIVE_LEG_ROUTE_REPLACEMENT_FORBIDDEN",
            "message": "Deactivate the leg before replacing its route.",
            "action": "Deactivate the leg, upload the replacement route, then activate the leg again.",
        }
        assert load_mission_v2(mission.id).model_dump(mode="json") == stored_before
        assert route_manager.get_active_route_id() == original_route_id
        assert route_manager._routes == original_routes
        assert sorted(path.name for path in routes_dir.glob("*")) == files_before
        poi_manager.delete_route_pois.assert_not_called()

    def test_inactive_leg_route_upload_retains_success_behavior(self, client: TestClient, tmp_path: Path):
        mission = _mission("inactive")
        assert client.post("/api/v2/missions", json=mission.model_dump(mode="json")).status_code == 201
        response = client.put(
            f"/api/v2/missions/{mission.id}/legs/{mission.legs[0].id}/route",
            files={"file": ("inactive-replacement.kml", KML, "application/vnd.google-earth.kml+xml")},
        )

        assert response.status_code == 200
        assert response.json()["leg"]["route_id"].startswith("inactive-replacement")
