"""HTTP regressions for server-owned V2 lifecycle state and route replacement."""

import io
import json
import threading
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
from app.mission import storage
from app.mission.storage import load_mission_v2
from app.mission.timeline_service import TimelineSummary
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
from fastapi.testclient import TestClient
import pytest

KML = b"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><LineString>
<coordinates>-120.0,35.0,0 -121.0,36.0,0</coordinates>
</LineString></Placemark></Document></kml>"""


@pytest.fixture(autouse=True)
def isolate_lifecycle_roots(client: TestClient, monkeypatch, tmp_path: Path):
    """Keep lifecycle assertions away from shared test mission resources."""
    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    storage._active_leg_locks.clear()

    route_manager = client.app.state.route_manager
    route_manager.routes_dir = tmp_path / "routes"
    route_manager.routes_dir.mkdir()
    route_manager._routes = {}
    route_manager._active_route_id = None

    poi_manager = client.app.state.poi_manager
    poi_manager.pois_file = tmp_path / "pois" / "pois.json"
    poi_manager.lock_file = str(poi_manager.pois_file) + ".lock"
    poi_manager._pois = {}
    poi_manager._load_pois()


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


def _add_route(
    client: TestClient, leg: MissionLeg, routes_dir: Path | None = None
) -> None:
    client.app.state.route_manager.add_route(
        leg.route_id,
        ParsedRoute(
            metadata=RouteMetadata(
                name=leg.route_id,
                file_path=str((routes_dir or Path("/tmp")) / f"{leg.route_id}.kml"),
                point_count=2,
            ),
            points=[
                RoutePoint(latitude=0.0, longitude=0.0),
                RoutePoint(latitude=1.0, longitude=1.0),
            ],
        ),
    )


def _activate(client: TestClient, mission: Mission) -> None:
    _add_route(client, mission.legs[0])
    with patch(
        "app.mission.routes_v2.build_mission_timeline",
        side_effect=lambda mission, **_: _timeline(mission.id),
    ):
        response = client.post(
            f"/api/v2/missions/{mission.id}/legs/{mission.legs[0].id}/activate"
        )
    assert response.status_code == 200


def _active_snapshot(client: TestClient, mission: Mission) -> tuple[bool, str | None]:
    stored = load_mission_v2(mission.id)
    assert stored is not None
    return (
        stored.legs[0].is_active,
        client.app.state.route_manager.get_active_route_id(),
    )


def _package(mission: Mission) -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("mission.json", json.dumps(mission.model_dump(mode="json")))
    return payload.getvalue()


class TestV2LifecycleWriteGuards:
    def test_create_normalizes_client_active_flags_without_disturbing_active_context(
        self, client: TestClient
    ):
        active_parent = _mission("active")
        assert (
            client.post(
                "/api/v2/missions", json=active_parent.model_dump(mode="json")
            ).status_code
            == 201
        )
        _activate(client, active_parent)
        before = _active_snapshot(client, active_parent)
        candidate = _mission("created", active=True)

        response = client.post(
            "/api/v2/missions", json=candidate.model_dump(mode="json")
        )

        assert response.status_code == 201
        assert response.json()["legs"][0]["is_active"] is False
        assert load_mission_v2(candidate.id).legs[0].is_active is False
        assert _active_snapshot(client, active_parent) == before

    def test_add_leg_normalizes_client_active_flag_without_disturbing_active_context(
        self, client: TestClient
    ):
        active_parent = _mission("active")
        inactive_parent = _mission("inactive")
        assert (
            client.post(
                "/api/v2/missions", json=active_parent.model_dump(mode="json")
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/v2/missions", json=inactive_parent.model_dump(mode="json")
            ).status_code
            == 201
        )
        _activate(client, active_parent)
        before = _active_snapshot(client, active_parent)
        incoming = _mission("incoming", active=True).legs[0]

        response = client.post(
            f"/api/v2/missions/{inactive_parent.id}/legs",
            json=incoming.model_dump(mode="json"),
        )

        assert response.status_code == 201
        assert response.json()["is_active"] is False
        assert load_mission_v2(inactive_parent.id).legs[-1].is_active is False
        assert _active_snapshot(client, active_parent) == before

    def test_import_normalizes_client_active_flags_without_disturbing_external_active_context(
        self, client: TestClient
    ):
        active_parent = _mission("active")
        assert (
            client.post(
                "/api/v2/missions", json=active_parent.model_dump(mode="json")
            ).status_code
            == 201
        )
        _activate(client, active_parent)
        before = _active_snapshot(client, active_parent)
        imported = _mission("imported", active=True)

        response = client.post(
            "/api/v2/missions/import",
            files={"file": ("mission.zip", _package(imported), "application/zip")},
        )

        assert response.status_code == 200
        assert load_mission_v2(imported.id).legs[0].is_active is False
        assert _active_snapshot(client, active_parent) == before

    def test_import_over_active_parent_is_conflict_before_any_mutation(
        self, client: TestClient
    ):
        active_parent = _mission("active")
        assert (
            client.post(
                "/api/v2/missions", json=active_parent.model_dump(mode="json")
            ).status_code
            == 201
        )
        _activate(client, active_parent)
        before_mission = load_mission_v2(active_parent.id).model_dump(mode="json")
        before_route = client.app.state.route_manager.get_active_route_id()
        replacement = active_parent.model_copy(deep=True)
        replacement.name = "replacement should not persist"
        replacement.legs[0].is_active = True

        response = client.post(
            "/api/v2/missions/import",
            files={"file": ("mission.zip", _package(replacement), "application/zip")},
        )

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "ACTIVE_MISSION_IMPORT_FORBIDDEN"
        assert (
            load_mission_v2(active_parent.id).model_dump(mode="json") == before_mission
        )
        assert client.app.state.route_manager.get_active_route_id() == before_route

    def test_active_leg_route_upload_is_strict_noop_with_actionable_code(
        self, client: TestClient, tmp_path: Path
    ):
        mission = _mission("active")
        assert (
            client.post(
                "/api/v2/missions", json=mission.model_dump(mode="json")
            ).status_code
            == 201
        )
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
            files={
                "file": ("replacement.kml", KML, "application/vnd.google-earth.kml+xml")
            },
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

    def test_inactive_leg_route_upload_retains_success_behavior(
        self, client: TestClient, tmp_path: Path
    ):
        mission = _mission("inactive")
        assert (
            client.post(
                "/api/v2/missions", json=mission.model_dump(mode="json")
            ).status_code
            == 201
        )
        response = client.put(
            f"/api/v2/missions/{mission.id}/legs/{mission.legs[0].id}/route",
            files={
                "file": (
                    "inactive-replacement.kml",
                    KML,
                    "application/vnd.google-earth.kml+xml",
                )
            },
        )

        assert response.status_code == 200
        assert response.json()["leg"]["route_id"].startswith("inactive-replacement")

    def test_import_holds_active_coordination_through_route_side_effect(
        self, client: TestClient, monkeypatch, tmp_path: Path
    ):
        """Activation cannot enter after import persists but before routes import."""
        imported = _mission("serialized")
        _add_route(client, imported.legs[0])
        side_effect_entered = threading.Event()
        release_import = threading.Event()
        activation_attempted = threading.Event()
        import_result: list[object] = []
        activation_result: list[object] = []

        def pause_route_import(*_args, **_kwargs):
            side_effect_entered.set()
            assert release_import.wait(timeout=2)
            return 0, []

        monkeypatch.setattr(
            "app.mission.routes_v2._import_routes_from_zip", pause_route_import
        )
        monkeypatch.setattr(
            "app.mission.routes_v2.build_mission_timeline",
            lambda mission, **_: _timeline(mission.id),
        )

        def run_import():
            import_result.append(
                client.post(
                    "/api/v2/missions/import",
                    files={
                        "file": (
                            "mission.zip",
                            _package(imported),
                            "application/zip",
                        )
                    },
                )
            )

        def run_activation():
            activation_attempted.set()
            activation_result.append(
                client.post(
                    f"/api/v2/missions/{imported.id}/legs/{imported.legs[0].id}/activate"
                )
            )

        importer = threading.Thread(target=run_import)
        importer.start()
        assert side_effect_entered.wait(timeout=2)
        activator = threading.Thread(target=run_activation)
        activator.start()
        assert activation_attempted.wait(timeout=2)
        assert not activation_result
        release_import.set()
        importer.join(timeout=2)
        activator.join(timeout=2)

        assert not importer.is_alive()
        assert not activator.is_alive()
        assert import_result[0].status_code == 200
        assert activation_result[0].status_code == 200

    def test_ordinary_writers_take_active_lock_before_parent_lock(
        self, client: TestClient, monkeypatch, tmp_path: Path
    ):
        """The four direct save writers share route-upload's lock ordering."""
        mission = _mission("ordered")
        assert (
            client.post(
                "/api/v2/missions", json=mission.model_dump(mode="json")
            ).status_code
            == 201
        )

        entries: list[str] = []

        class RecordedLock:
            def __init__(self, name: str):
                self.name = name

            def __enter__(self):
                entries.append(self.name)
                return self

            def __exit__(self, *_args):
                return False

        monkeypatch.setattr(
            "app.mission.routes_v2.get_active_leg_lock", lambda: RecordedLock("active")
        )
        monkeypatch.setattr(
            "app.mission.routes_v2.get_mission_lock",
            lambda _mission_id: RecordedLock("mission"),
        )

        updated = mission.model_copy(deep=True)
        updated.legs[0].name = "updated"
        cases = [
            (
                lambda: client.patch(
                    f"/api/v2/missions/{mission.id}", json={"name": "renamed"}
                ),
                200,
            ),
            (
                lambda: client.post(
                    f"/api/v2/missions/{mission.id}/legs",
                    json=_mission("added").legs[0].model_dump(mode="json"),
                ),
                201,
            ),
            (
                lambda: client.put(
                    f"/api/v2/missions/{mission.id}/legs/{mission.legs[0].id}",
                    json=updated.legs[0].model_dump(mode="json"),
                ),
                200,
            ),
            (
                lambda: client.delete(
                    f"/api/v2/missions/{mission.id}/legs/{mission.legs[0].id}"
                ),
                204,
            ),
        ]
        for request, expected_status in cases:
            entries.clear()
            response = request()
            assert response.status_code == expected_status
            assert entries[:2] == ["active", "mission"]
