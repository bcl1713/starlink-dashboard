"""Durable mission eligibility commands use one guarded publication."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.mission import storage
from app.mission.availability_models import MissionAvailability
from app.mission.models import Mission, MissionLeg, Transport, TransportConfig
from app.mission.planning.service import PlanningService
from app.mission.planning.store import PlanningStore
from app.mission.routes_v2 import router
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint, RouteTimingProfile
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager

NOW = datetime(2035, 3, 1, 12, tzinfo=timezone.utc)


@pytest.fixture
def availability_api(tmp_path, monkeypatch):
    routes = RouteManager(tmp_path / "routes")
    pois = POIManager(tmp_path / "pois.json")
    store = PlanningStore(storage.MISSIONS_DIR, routes, pois)
    route = ParsedRoute(
        metadata=RouteMetadata(
            name="availability", file_path="owned.kml", point_count=2
        ),
        points=[
            RoutePoint(
                latitude=n,
                longitude=0,
                altitude=1000,
                sequence=n,
                expected_arrival_time=NOW + timedelta(hours=n),
            )
            for n in (0, 1)
        ],
        timing_profile=RouteTimingProfile(
            departure_time=NOW,
            arrival_time=NOW + timedelta(hours=1),
            has_timing_data=True,
        ),
    )
    routes.add_route("route-one", route)
    routes.activate_route("route-one")
    mission = Mission(
        id="availability-mission",
        name="Availability",
        availability=MissionAvailability(defaults={"X": False}),
        legs=[
            MissionLeg(
                id=f"leg-{n}",
                name=f"Leg {n}",
                route_id="route-one",
                is_active=n == 1,
                transports=TransportConfig(initial_x_satellite_id=""),
            )
            for n in (1, 2)
        ],
    )
    storage.save_mission_v2(mission)
    app = FastAPI()
    app.state.route_manager = routes
    app.state.poi_manager = pois
    app.state.planning_service = PlanningService(store)
    app.state.availability_clock = SimpleNamespace(
        now=lambda: NOW + timedelta(minutes=10)
    )
    app.state.availability_source_mode = "live"
    app.include_router(router)
    with TestClient(
        app,
        raise_server_exceptions=False,
        client=(f"availability-{uuid4()}", 50000),
    ) as client:
        yield client, app, store, mission


def command(
    client,
    *,
    revision=0,
    command_id="failure-one",
    transport="Ka",
    action="unavailable",
):
    return client.post(
        "/api/v2/missions/availability-mission/availability/actions",
        json={
            "expected_revision": revision,
            "command_id": command_id,
            "transport": transport,
            "action": action,
        },
    )


def test_stale_revision_rejected(availability_api):
    client, _, _, _ = availability_api
    assert command(client).status_code == 200
    stale = command(client, command_id="other")
    assert stale.status_code == 409
    assert (
        len(storage.load_mission_v2("availability-mission").availability.history) == 1
    )


def test_duplicate_action_is_idempotent(availability_api):
    client, _, _, _ = availability_api
    first = command(client)
    assert first.status_code == 200
    retry = command(client)
    assert retry.status_code == 200 and retry.json() == first.json()
    assert retry.json()["revision"] == 1
    assert retry.json()["history"][0]["effective_at"] == "2035-03-01T12:10:00Z"
    assert retry.json()["effective"]["Ka"] is False
    assert retry.json()["operator_actions_allowed"] is True
    assert command(client, transport="Ku").status_code == 409


def test_regeneration_failure_does_not_publish_partial_change(
    availability_api, monkeypatch
):
    client, _, store, mission = availability_api
    before = storage.load_mission_v2(mission.id).model_dump_json()
    from app.mission import timeline_preparation

    original = timeline_preparation.prepare_mission_timeline
    calls = []

    def fail_second(*args, **kwargs):
        calls.append(args[0].id)
        if len(calls) == 2:
            raise ValueError("second profile failed")
        return original(*args, **kwargs)

    monkeypatch.setattr(timeline_preparation, "prepare_mission_timeline", fail_second)
    assert command(client).status_code == 422
    assert storage.load_mission_v2(mission.id).model_dump_json() == before
    assert not storage.get_leg_timeline_path("leg-1", mission.id).exists()
    assert not list(store.journal.directory.glob("*.json"))


def test_restart_and_leg_change_keep_failure(availability_api):
    client, app, _, mission = availability_api
    assert command(client).status_code == 200
    stored = storage.load_mission_v2(mission.id)
    stored.legs[0].is_active, stored.legs[1].is_active = False, True
    storage.save_mission_v2(stored)
    assert (
        client.get(f"/api/v2/missions/{mission.id}/availability").json()["effective"][
            "Ka"
        ]
        is False
    )
    app.state.availability_clock = SimpleNamespace(
        now=lambda: NOW + timedelta(minutes=30)
    )
    restored = command(client, revision=1, command_id="restore-one", action="restore")
    assert restored.status_code == 200
    assert restored.json()["effective"]["Ka"] is True
    assert len(storage.load_mission_v2(mission.id).availability.history) == 2


def test_defaults_preserve_partial_leg_overrides(availability_api):
    client, _, _, mission = availability_api
    path = f"/api/v2/missions/{mission.id}/availability"
    first = client.put(
        path,
        json={
            "expected_revision": 0,
            "command_id": "defaults",
            "defaults": {"Ka": False},
            "leg_overrides": {"leg-2": {"Ka": True}},
        },
    )
    assert first.status_code == 200
    second = client.put(
        path,
        json={
            "expected_revision": 1,
            "command_id": "defaults-two",
            "defaults": {"Ku": False},
        },
    )
    assert second.status_code == 200
    stored = storage.load_mission_v2(mission.id)
    assert stored.availability.defaults == {"X": False, "Ka": False, "Ku": False}
    assert stored.legs[1].transports.availability_overrides == {"Ka": True}
    assert second.json()["legs"][1]["planned"] == {"X": False, "Ka": True, "Ku": False}
    assert (
        client.put(
            path,
            json={
                "expected_revision": 1,
                "command_id": "defaults-two",
                "defaults": {"Ku": False},
            },
        ).status_code
        == 200
    )


def test_legacy_editor_does_not_erase_availability(availability_api):
    client, _, _, mission = availability_api
    stored = storage.load_mission_v2(mission.id)
    stored.legs[0].transports.availability_overrides = {Transport.KA: False}
    storage.save_mission_v2(stored)
    payload = stored.legs[0].model_dump(mode="json")
    payload["transports"].pop("availability_overrides")
    response = client.put(f"/api/v2/missions/{mission.id}/legs/leg-1", json=payload)
    assert response.status_code == 200
    assert storage.load_mission_v2(mission.id).legs[
        0
    ].transports.availability_overrides == {"Ka": False}


def test_simulation_failure_does_not_affect_live_mission(availability_api):
    client, app, _, mission = availability_api
    app.state.availability_source_mode = "simulation"
    run = SimpleNamespace(
        run_id="run-one", mission_id=mission.id, leg_id="leg-1", simulation_time=NOW
    )
    app.state.simulation_run_service = SimpleNamespace(
        status=lambda: SimpleNamespace(state="running", run=run)
    )
    response = command(client)
    assert response.status_code == 200
    assert response.json()["simulation_run_id"] == "run-one"
    assert response.json()["effective"]["Ka"] is False
    stored = storage.load_mission_v2(mission.id)
    assert stored.availability.simulation_run_id is None
    timeline = storage.load_mission_timeline("leg-1", mission.id)
    assert timeline.statistics["_transport_availability"]["simulation_run_id"] is None
    assert all(segment.ka_state != "offline" for segment in timeline.segments)
    app.state.availability_source_mode = "live"
    assert (
        client.get(f"/api/v2/missions/{mission.id}/availability").json()["effective"][
            "Ka"
        ]
        is True
    )


def test_expected_simulation_without_clock_rejects_action(availability_api):
    client, app, _, _ = availability_api
    app.state.availability_source_mode = "simulation"
    assert command(client).status_code == 409
    assert storage.load_mission_v2("availability-mission").availability.revision == 0


def test_inactive_actions_rejected_but_settings_allowed(availability_api):
    client, _, _, mission = availability_api
    for leg in mission.legs:
        leg.is_active = False
    storage.save_mission_v2(mission)
    path = f"/api/v2/missions/{mission.id}/availability"
    assert client.get(path).json()["operator_actions_allowed"] is False
    assert command(client).status_code == 409
    assert (
        client.put(
            path,
            json={
                "expected_revision": 0,
                "command_id": "inactive-plan",
                "defaults": {"Ka": False},
            },
        ).status_code
        == 200
    )


def test_itinerary_revision_preserves_availability(availability_api):
    from app.mission.availability import resolved_leg_availability
    from app.mission.itinerary_import.revisions import prepare_revision

    client, _, _, mission = availability_api
    assert command(client).status_code == 200
    current = storage.load_mission_v2(mission.id)
    from app.mission.models import Transport

    current.legs[0].transports.availability_overrides = {Transport.KU: False}
    incoming = mission.model_copy(deep=True)
    incoming.legs.append(
        MissionLeg(
            id="new-leg",
            name="new",
            route_id="route-one",
            transports=TransportConfig(initial_x_satellite_id=""),
        )
    )
    revised = prepare_revision(None, current, mission, incoming).mission
    assert revised.availability.history == current.availability.history
    assert revised.legs[0].transports.availability_overrides == {"Ku": False}
    assert revised.legs[-1].transports.availability_overrides is None
    assert (
        resolved_leg_availability(revised, revised.legs[-1]).resolve(
            NOW + timedelta(hours=1)
        )["Ka"]
        is False
    )


def test_package_roundtrip_keeps_state_and_import_inactive(availability_api):
    import io
    from zipfile import ZipFile

    from app.mission.planning.packages import commit_package, stage_package

    client, _, store, mission = availability_api
    assert command(client).status_code == 200
    source = storage.load_mission_v2(mission.id)
    # Exercise the package machinery without exporting unrelated rendering assets.
    for leg in source.legs:
        leg.route_id = ""
    data = io.BytesIO()
    with ZipFile(data, "w") as archive:
        archive.writestr("mission.json", source.model_dump_json())
    with ZipFile(data) as archive:
        imported = commit_package(
            stage_package(archive, None, store.sources), None
        ).mission
    assert imported.id != mission.id
    assert imported.availability == source.availability
    assert (
        imported.metadata["transport_availability_commands"]
        == source.metadata["transport_availability_commands"]
    )
    assert not any(leg.is_active for leg in imported.legs)
    assert storage.load_mission_v2(mission.id).legs[0].is_active


def test_operator_journal_disabled_does_not_prevent_commands(availability_api):
    client, app, _, _ = availability_api
    app.state.operator_runtime = SimpleNamespace(
        settings=SimpleNamespace(enabled=False),
        health=lambda: SimpleNamespace(source_mode="live"),
    )
    assert command(client).status_code == 200


def test_publication_write_failure_compensates_all_owned_state(
    availability_api, monkeypatch
):
    client, _, store, _mission = availability_api
    before = {p: p.read_bytes() for p in store.root.rglob("*.json")}
    before_pois = store.poi_manager.pois_file.read_bytes()
    original = store.journal.commit

    def fail_after_first(files, **kwargs):
        def fail(index, path):
            if index == 0:
                raise OSError("injected write failure")

        return original(files, **kwargs, after_write=fail)

    monkeypatch.setattr(store.journal, "commit", fail_after_first)
    assert command(client).status_code == 500
    assert {p: p.read_bytes() for p in store.root.rglob("*.json")} == before
    import json

    assert json.loads(store.poi_manager.pois_file.read_bytes()) == json.loads(
        before_pois
    )


def test_active_route_mismatch_rejects_operator_actions(availability_api):
    client, _, store, _ = availability_api
    store.route_manager.deactivate_route()
    assert command(client).status_code == 409
    assert storage.load_mission_v2("availability-mission").availability.revision == 0


def test_new_leg_and_manual_preview_inherit_parent_failure(availability_api):
    client, _, _, mission = availability_api
    assert command(client).status_code == 200
    payload = MissionLeg(
        id="added-leg",
        name="Added",
        route_id="route-one",
        transports=TransportConfig(initial_x_satellite_id=""),
    ).model_dump(mode="json")
    path = f"/api/v2/missions/{mission.id}"
    assert client.post(path + "/legs", json=payload).status_code == 201
    saved = storage.load_mission_timeline("added-leg", mission.id)
    assert all(
        segment.ka_state == "offline"
        for segment in saved.segments
        if segment.start_time >= NOW + timedelta(minutes=10)
    )
    response = client.post(path + "/legs/added-leg/timeline/preview", json={})
    assert response.status_code == 200
    assert all(
        segment["ka_state"] == "offline"
        for segment in response.json()["segments"]
        if segment["start_time"] >= "2035-03-01T12:10:00Z"
    )


def test_create_profiles_use_saved_parent_settings(availability_api):
    client, _, _, mission = availability_api
    payload = mission.model_dump(mode="json")
    payload["id"] = "second-mission"
    payload["availability"]["defaults"] = {"X": False, "Ka": False}
    response = client.post("/api/v2/missions", json=payload)
    assert response.status_code == 201
    timeline = storage.load_mission_timeline("leg-1", "second-mission")
    assert timeline is not None
    assert all(segment.ka_state == "offline" for segment in timeline.segments)


def test_stale_explicit_editor_payload_cannot_rollback_owned_leg_settings(
    availability_api,
):
    client, _, _, mission = availability_api
    stale = mission.legs[0].model_dump(mode="json")
    path = f"/api/v2/missions/{mission.id}"
    assert (
        client.put(
            path + "/availability",
            json={
                "expected_revision": 0,
                "command_id": "own-leg",
                "leg_overrides": {"leg-1": {"Ka": False}},
            },
        ).status_code
        == 200
    )
    stale["description"] = "An ordinary stale editor save"
    response = client.put(path + "/legs/leg-1", json=stale)
    assert response.status_code == 200
    current = storage.load_mission_v2(mission.id)
    assert current.legs[0].description == stale["description"]
    assert current.legs[0].transports.availability_overrides == {"Ka": False}
    assert response.json()["leg"]["transports"]["availability_overrides"] == {
        "Ka": False
    }


def test_stale_explicit_mission_save_cannot_rollback_owned_availability(
    availability_api,
):
    client, _, _, mission = availability_api
    stale = mission.model_copy(deep=True)
    assert command(client).status_code == 200
    stale.description = "Ordinary mission save"
    storage.save_mission_v2(stale)
    current = storage.load_mission_v2(mission.id)
    assert current.description == "Ordinary mission save"
    assert current.availability.revision == 1
    assert len(current.availability.history) == 1


def test_restore_keeps_underlying_planned_unavailable(availability_api):
    client, _, _, mission = availability_api
    path = f"/api/v2/missions/{mission.id}/availability"
    assert (
        client.put(
            path,
            json={
                "expected_revision": 0,
                "command_id": "planned-Ka",
                "defaults": {"Ka": False},
            },
        ).status_code
        == 200
    )
    assert command(client, revision=1).status_code == 200
    restored = command(client, revision=2, command_id="restored", action="restore")
    assert restored.status_code == 200
    assert restored.json()["effective"]["Ka"] is False


def test_source_mode_is_rechecked_when_command_is_admitted(availability_api):
    from app.mission.availability_routes import AvailabilityAction, service_for
    from app.mission.planning.errors import PlanningFailure

    _, app, _, _ = availability_api
    service = service_for(SimpleNamespace(app=app))
    app.state.availability_source_mode = "simulation"
    with pytest.raises(PlanningFailure) as failure:
        service.command(
            "availability-mission",
            AvailabilityAction(
                expected_revision=0,
                command_id="raced-mode",
                transport="Ka",
                action="unavailable",
            ),
            action=True,
        )
    assert failure.value.status_code == 409
    assert storage.load_mission_v2("availability-mission").availability.revision == 0


def test_simulation_command_retry_after_restart_remains_idempotent(availability_api):
    client, app, _, mission = availability_api
    app.state.availability_source_mode = "simulation"
    run = SimpleNamespace(
        run_id="run-before-restart",
        mission_id=mission.id,
        leg_id="leg-1",
        simulation_time=NOW,
    )
    app.state.simulation_run_service = SimpleNamespace(
        status=lambda: SimpleNamespace(state="running", run=run)
    )
    assert command(client).status_code == 200
    app.state.availability_source_mode = "live"
    app.state.simulation_run_service = None
    replayed = command(client)
    assert replayed.status_code == 200
    assert replayed.json()["effective"]["Ka"] is True
    assert replayed.json()["revision"] == 1
    assert len(replayed.json()["history"]) == 1


def test_metrics_invalidate_only_after_committed_availability(
    availability_api, monkeypatch
):
    from app.mission import timeline_preparation
    from app.services.metrics_changes import mission_metrics_changes

    client, _, _, _ = availability_api
    notifications = []
    monkeypatch.setattr(
        mission_metrics_changes, "_metrics_change_callback", notifications.append
    )
    original = timeline_preparation.prepare_mission_timeline

    def unavailable(*args, **kwargs):
        raise ValueError("profile is not ready")

    monkeypatch.setattr(timeline_preparation, "prepare_mission_timeline", unavailable)
    assert command(client).status_code == 422
    assert notifications == []
    monkeypatch.setattr(timeline_preparation, "prepare_mission_timeline", original)
    assert command(client).status_code == 200
    assert len(notifications) == 1
    assert command(client).status_code == 200
    assert len(notifications) == 1


@pytest.mark.parametrize("restored", [False, True])
def test_x_configuration_requirement_uses_actual_leg_window(availability_api, restored):
    from app.mission.availability_models import AvailabilityChange

    client, _, _, mission = availability_api
    stored = storage.load_mission_v2(mission.id)
    history = [
        AvailabilityChange(
            id="failure",
            transport="X",
            unavailable=True,
            effective_at=NOW + timedelta(minutes=10),
        )
    ]
    if restored:
        history.append(
            AvailabilityChange(
                id="restore",
                transport="X",
                unavailable=False,
                effective_at=NOW + timedelta(hours=2, minutes=30),
            )
        )
    stored.availability = MissionAvailability(defaults={"X": True}, history=history)
    stored.legs[1].adjusted_departure_time = NOW + timedelta(hours=2)
    storage.save_mission_v2(stored)
    response = client.get(f"/api/v2/missions/{mission.id}/availability")
    assert response.status_code == 200
    rows = response.json()["legs"]
    assert rows[0]["planned"]["X"] is True
    assert rows[0]["effective"]["X"] is False
    assert rows[0]["x_configuration_required"] is True
    assert rows[1]["x_configuration_required"] is restored


def test_action_run_guard_rejects_changed_run_but_preserves_accepted_retry(
    availability_api,
):
    client, app, _, mission = availability_api
    app.state.availability_source_mode = "simulation"
    run = SimpleNamespace(
        run_id="run-a", mission_id=mission.id, leg_id="leg-1", simulation_time=NOW
    )
    app.state.simulation_run_service = SimpleNamespace(
        status=lambda: SimpleNamespace(state="running", run=run)
    )
    path = f"/api/v2/missions/{mission.id}/availability/actions"
    request = {
        "expected_revision": 0,
        "command_id": "guarded-run",
        "transport": "Ka",
        "action": "unavailable",
        "expected_simulation_run_id": "run-a",
    }
    first = client.post(path, json=request)
    assert first.status_code == 200
    run.run_id = "run-b"
    repeated = client.post(path, json=request)
    assert repeated.status_code == 200
    assert repeated.json()["effective"]["Ka"] is True
    rejected = client.post(
        path, json={**request, "command_id": "new-stale-run", "expected_revision": 1}
    )
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "availability_action_unavailable"
    assert len(storage.load_mission_v2(mission.id).availability.history) == 1
    accepted = client.post(
        path,
        json={
            **request,
            "command_id": "new-current-run",
            "expected_revision": 1,
            "expected_simulation_run_id": "run-b",
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["effective"]["Ka"] is False


@pytest.mark.parametrize("failure_run", [None, "run-a"])
def test_simulation_failure_keeps_canonical_live_X_configuration_required(
    availability_api, failure_run
):
    from app.mission.availability_models import AvailabilityChange

    client, app, _, mission = availability_api
    stored = storage.load_mission_v2(mission.id)
    stored.availability = MissionAvailability(
        defaults={"X": True},
        history=[
            AvailabilityChange(
                id="simulation-X",
                transport="X",
                unavailable=True,
                effective_at=NOW - timedelta(minutes=1),
                simulation_run_id=failure_run,
            )
        ],
    )
    storage.save_mission_v2(stored)
    app.state.availability_source_mode = "simulation"
    run = SimpleNamespace(
        run_id="run-a", mission_id=mission.id, leg_id="leg-1", simulation_time=NOW
    )
    app.state.simulation_run_service = SimpleNamespace(
        status=lambda: SimpleNamespace(state="running", run=run)
    )
    response = client.get(f"/api/v2/missions/{mission.id}/availability")
    assert response.status_code == 200
    row = response.json()["legs"][0]
    assert row["effective"]["X"] is (failure_run != "run-a")
    assert row["planning_effective"]["X"] is (failure_run is not None)
    assert row["x_configuration_required"] is (failure_run is not None)


@pytest.fixture
def manual_archive(availability_api):
    from app.mission.package.__main__ import export_mission_package

    client, _app, store, mission = availability_api
    path = store.route_manager.routes_dir / "route-one.kml"
    path.write_text(
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
        "<Placemark><name>Departure</name><description>"
        "Time Over Waypoint: 2035-03-01 12:00:00Z</description>"
        "<Point><coordinates>0,0,1000</coordinates></Point></Placemark>"
        "<Placemark><name>Arrival</name><description>"
        "Time Over Waypoint: 2035-03-01 13:00:00Z</description>"
        "<Point><coordinates>0,1,1000</coordinates></Point></Placemark>"
        "<Placemark><LineString><coordinates>0,0,1000 0,1,1000</coordinates>"
        "</LineString></Placemark></Document></kml>"
    )
    with export_mission_package(
        mission.id, store.route_manager, store.poi_manager
    ) as handle:
        package = handle.read()
    return client, store, mission, package


def import_manual(client, package):
    return client.post(
        "/api/v2/missions/import",
        files={"file": ("earlier.zip", package, "application/zip")},
    )


@pytest.mark.parametrize("change", ["failure", "defaults", "leg_override"])
def test_older_manual_archive_clones_to_preserve_availability(manual_archive, change):
    client, _store, mission, package = manual_archive
    if change == "failure":
        assert command(client).status_code == 200
    else:
        update = (
            {"defaults": {"Ka": False}}
            if change == "defaults"
            else {"leg_overrides": {"leg-2": {"Ka": False}}}
        )
        response = client.put(
            f"/api/v2/missions/{mission.id}/availability",
            json={"expected_revision": 0, "command_id": "planned", **update},
        )
        assert response.status_code == 200
    stored = storage.load_mission_v2(mission.id)
    for leg in stored.legs:
        leg.is_active = False
    storage.save_mission_v2(stored)
    before = storage.load_mission_v2(mission.id).model_dump(mode="json")
    response = import_manual(client, package)
    assert response.status_code == 200, response.text
    assert response.json()["mission_id"] != mission.id
    assert storage.load_mission_v2(mission.id).model_dump(mode="json") == before
    imported = storage.load_mission_v2(response.json()["mission_id"])
    assert imported.availability.revision == 0
    assert imported.availability.history == ()
    assert all(not leg.is_active for leg in imported.legs)


def test_untouched_manual_archive_still_replaces_same_id(manual_archive):
    client, _, mission, package = manual_archive
    stored = storage.load_mission_v2(mission.id)
    for leg in stored.legs:
        leg.is_active = False
    storage.save_mission_v2(stored)
    response = import_manual(client, package)
    assert response.status_code == 200, response.text
    assert response.json()["mission_id"] == mission.id


def test_active_manual_archive_still_rejected(manual_archive):
    client, _, mission, package = manual_archive
    assert command(client).status_code == 200
    before = storage.load_mission_v2(mission.id).model_dump(mode="json")
    response = import_manual(client, package)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ACTIVE_MISSION_IMPORT_FORBIDDEN"
    assert storage.load_mission_v2(mission.id).model_dump(mode="json") == before
