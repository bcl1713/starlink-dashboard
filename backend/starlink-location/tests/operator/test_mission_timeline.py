"""Complete chronology is a read-only projection, separate from alert admission."""

from datetime import timedelta

import pytest

from app.mission import storage
from tests.operator.api_helpers import BASE


def read(api, production, mission_id="demo-mission"):
    api.app.state.operator_runtime.event_source_adapter = production[0]
    response = api.get(
        BASE + "/events/mission-timeline", params={"mission_id": mission_id}
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def x_window(snapshot, leg_id="leg-a"):
    return next(
        e for e in snapshot["events"] if e["transport"] == "X" and e["leg_id"] == leg_id
    )


def test_preflight_without_telemetry_is_current_schedule_and_never_writes_ledger(
    api, production
):
    adapter = production[0]
    context = adapter.context_provider
    adapter.context_provider = lambda: context() | {"phase": "pre_departure"}
    production[2]["telemetry"] = None
    with adapter.service.store.connect() as db:
        before = list(db.iterdump())
    snapshot = read(api, production)
    event = x_window(snapshot)
    assert event["time_basis"] == "planned_utc"
    assert event["due_at"] and event["end_at"]
    assert snapshot["legs"][0]["coverage"] == "available"
    assert not any(
        e["notification"]["eligible"] or e["notification"]["acknowledgment_available"]
        for e in snapshot["events"]
    )
    read(api, production)
    with adapter.service.store.connect() as db:
        assert list(db.iterdump()) == before


def test_all_legs_include_more_than_24_hours_and_missing_leg_is_explicit(
    api, production, clock
):
    mission = storage.load_mission_v2("demo-mission")
    leg = mission.legs[0].model_copy(deep=True)
    leg.id, leg.name, leg.is_active = "leg-b", "Tomorrow", False
    leg.route_id = "route-b"
    route = production[4].get_route("route-a").model_copy(deep=True)
    route.route_id = "route-b"
    for point in route.points:
        if point.expected_arrival_time is not None:
            point.expected_arrival_time += timedelta(days=2)
    route.timing_profile.departure_time += timedelta(days=2)
    route.timing_profile.arrival_time += timedelta(days=2)
    production[4].add_route("route-b", route)
    missing = leg.model_copy(
        update={"id": "leg-c", "name": "Missing route", "route_id": "missing"}
    )
    mission.legs += [leg, missing]
    storage.save_mission_v2(mission)
    snapshot = read(api, production)
    assert (
        x_window(snapshot, "leg-b")["due_at"]
        > (clock.now() + timedelta(days=1)).isoformat()
    )
    assert x_window(snapshot, "leg-b")["time_basis"] == "planned_utc"
    assert [leg["coverage"] for leg in snapshot["legs"]] == [
        "partial",
        "available",
        "unavailable",
    ]
    assert "PoP timing unavailable" in snapshot["legs"][0]["reason"]
    assert snapshot["legs"][2]["reason"]
    assert x_window(snapshot)["time_basis"] == "live_route_eta"


def test_live_eta_moves_and_unavailable_never_falls_back_to_plan(api, production):
    production[2]["telemetry"].position.speed = 1200
    first = x_window(read(api, production))
    production[2]["telemetry"].position.speed = 300
    slower = x_window(read(api, production))
    assert slower["due_at"] > first["due_at"]
    assert slower["event_id"] == first["event_id"]
    production[2]["telemetry"] = None
    unavailable = x_window(read(api, production))
    assert unavailable["time_basis"] == "live_unavailable"
    assert unavailable["due_at"] is None and unavailable["end_at"] is None
    assert unavailable["planned_due_at"] == first["planned_due_at"]


def test_schedule_cache_changes_with_inputs_and_context_isolation(api, production):
    first = read(api, production)
    mission = storage.load_mission_v2("demo-mission")
    mission.legs[0].name = "Revised schedule"
    mission.legs[0].adjusted_departure_time = production[4].get_route(
        "route-a"
    ).timing_profile.departure_time + timedelta(hours=2)
    storage.save_mission_v2(mission)
    changed = read(api, production)
    assert changed["generation"] != first["generation"]
    assert changed["legs"][0]["name"] == "Revised schedule"
    assert x_window(changed)["planned_due_at"] > x_window(first)["planned_due_at"]
    other = read(api, production, "other-mission")
    assert other["mission_id"] == "other-mission"
    assert not any(e["mission_id"] != "other-mission" for e in other["events"])
    assert not any(e["time_basis"] == "live_route_eta" for e in other["events"])


def test_airborne_pop_reads_current_publication_without_advancing_producer(
    api, production, clock
):
    from app.mission.pop_status import PopStatusService

    adapter = production[0]
    adapter.pop_service = PopStatusService(production[4], lambda: production[3])
    adapter.pop_service.status_payload(production[2]["telemetry"], now=clock.now())
    before = adapter.pop_service.read_publication()
    snapshot = read(api, production)
    pop = [e for e in snapshot["events"] if e["kind"] == "pop_advisory"]
    assert pop
    assert all(e["time_basis"] == "live_route_eta" for e in pop if e["due_at"])
    assert adapter.pop_service.read_publication() == before
    clock.advance(31)
    stale = read(api, production)
    pop = [e for e in stale["events"] if e["kind"] == "pop_advisory"]
    assert pop
    assert all(e["freshness"] != "fresh" for e in pop)


def test_missing_ka_coverage_does_not_make_known_x_eta_stale(api, production):
    from pathlib import Path

    Path("data/sat_coverage/commka.geojson").write_text(
        '{"type":"FeatureCollection","features":[]}'
    )
    snapshot = read(api, production)
    event = x_window(snapshot)
    assert snapshot["legs"][0]["coverage"] == "partial"
    assert event["time_basis"] == "live_route_eta"
    assert event["freshness"] == "fresh"


@pytest.mark.parametrize("change", ["route", "config"])
def test_static_preparation_is_cached_but_input_change_during_work_is_rejected(
    api, production, monkeypatch, change
):
    from app.operator.production_event_inputs import ModelInputs

    prepare = ModelInputs.prepare
    prepared = []

    def track(self, leg):
        prepared.append(leg.id)
        return prepare(self, leg)

    monkeypatch.setattr(ModelInputs, "prepare", track)
    read(api, production)
    read(api, production)
    assert prepared == ["leg-a"]
    production[0].mission_timeline_cache.clear()

    def moving(self, leg):
        result = prepare(self, leg)
        if change == "route":
            route = production[4].get_route("route-a").model_copy(deep=True)
            route.points[-1].longitude += 0.2
            production[4].add_route("route-a", route)
        else:
            production[3].pop.catalog_path = production[6].with_name(
                "missing-catalog.json"
            )
        return result

    monkeypatch.setattr(ModelInputs, "prepare", moving)
    response = api.get(
        BASE + "/events/mission-timeline", params={"mission_id": "demo-mission"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "event_snapshot_changed"


@pytest.mark.parametrize("phase", ["pre_departure", "in_flight"])
@pytest.mark.parametrize("failure", ["route_file", "owned_profile"])
def test_unaccepted_route_file_only_marks_its_leg_unavailable(
    api, production, failure, phase
):
    context = production[0].context_provider
    production[0].context_provider = lambda: context() | {"phase": phase}
    mission = storage.load_mission_v2("demo-mission")
    second = mission.legs[0].model_copy(
        update={
            "id": "leg-b",
            "route_id": "route-b",
            "name": "Awaiting route",
            "is_active": False,
        },
        deep=True,
    )
    production[4].add_route(
        "route-b",
        production[4]
        .get_route("route-a")
        .model_copy(update={"route_id": "route-b"}, deep=True),
    )
    mission.legs.append(second)
    storage.save_mission_v2(mission)
    if failure == "route_file":
        (production[4].routes_dir / "route-b.kml").write_text(
            "Unaccepted replacement bytes"
        )
    else:
        inventory = storage.MISSIONS_DIR / ".planning/inventory"
        inventory.mkdir(parents=True, exist_ok=True)
        (inventory / "route-b.json").write_text(
            '{"id":"route-b","content_hash":"broken"}'
        )
    snapshot = read(api, production)
    assert snapshot["legs"][1]["coverage"] == "unavailable"
    event = x_window(snapshot)
    assert event["due_at"] and event["end_at"]
    assert event["time_basis"] == (
        "live_route_eta" if phase == "in_flight" else "planned_utc"
    )
    assert event["freshness"] == "fresh"


def test_pop_publication_uses_observation_clock_and_rejects_old_replay_lifecycle(
    production, clock, monkeypatch
):
    from dataclasses import replace

    from app.mission.pop_status import PopStatusService
    from app.operator.mission_timeline import _current_pop
    from app.operator.production_event_inputs import capture_current

    adapter = production[0]
    inputs = capture_current(adapter, "demo-mission", as_of=clock.now(), scheduled=True)
    inputs = replace(inputs, context=inputs.context | {"lifecycle": "seek-one"})
    health = adapter.service.store.health().model_copy(
        update={"source_mode": "simulation", "simulation_run_id": "replay-a"}
    )
    monkeypatch.setattr(adapter.service.store, "health", lambda: health)
    physical_now = clock.now() + timedelta(days=2)
    monkeypatch.setattr(clock, "observation_now", lambda: physical_now, raising=False)
    telemetry = production[2]["telemetry"]
    telemetry.position.observed_at = telemetry.position.speed_observed_at = physical_now
    adapter.pop_service = PopStatusService()
    adapter.pop_service.snapshot(
        telemetry,
        route=production[4].get_route("route-a"),
        catalog=inputs.pop_catalog,
        enabled=True,
        mode="simulation",
        now=clock.now(),
        observed_now=physical_now,
        mission_id="demo-mission",
        leg_id="leg-a",
        simulation_run_id="replay-a",
        lifecycle_token="seek-one",
    )
    current = _current_pop(
        adapter, inputs, production[5], clock.now(), live_available=True
    )
    assert current is not None
    assert current[2].freshness == "fresh"
    seek = replace(inputs, context=inputs.context | {"lifecycle": "seek-two"})
    assert (
        _current_pop(adapter, seek, production[5], clock.now(), live_available=True)
        is None
    )
    health = health.model_copy(update={"simulation_run_id": "replay-b"})
    assert (
        _current_pop(adapter, inputs, production[5], clock.now(), live_available=True)
        is None
    )


@pytest.mark.parametrize("phase", ["pre_departure", "in_flight"])
def test_schedule_ignores_corrupt_export_archive_but_keeps_per_leg_route_gaps(
    api, production, phase
):
    from app.mission.slide_cache.capture import capture_raw, normalize_capture

    mission = storage.load_mission_v2("demo-mission")
    mission.metadata["itinerary_planning"] = {
        "schema_version": 1,
        "source_revisions": [
            {
                "id": "missing-pdf",
                "owner": mission.id,
                "kind": "itinerary_pdf",
                "filename": "original.pdf",
                "content_hash": "a" * 64,
                "owned_relative_path": "sources/missing-pdf.pdf",
            }
        ],
    }
    mission.legs.append(
        mission.legs[0].model_copy(
            update={
                "id": "leg-b",
                "route_id": "missing-route",
                "name": "Route unavailable",
                "is_active": False,
            }
        )
    )
    # Persist the fixture's accepted manifest under the same repository gate
    # used by planning writes; then its retained PDF is deliberately absent.
    with storage.get_active_leg_lock():
        storage._save_mission_v2_unlocked(mission)
    context = production[0].context_provider
    production[0].context_provider = lambda: context() | {"phase": phase}
    if phase == "pre_departure":
        production[2]["telemetry"] = None
    snapshot = read(api, production)
    assert snapshot["legs"][1]["coverage"] == "unavailable"
    event = x_window(snapshot)
    assert event["time_basis"] == (
        "live_route_eta" if phase == "in_flight" else "planned_utc"
    )
    assert event["due_at"] and event["end_at"]
    assert event["freshness"] == "fresh"
    # Export defaults still enforce the retained archival contract.
    raw = capture_raw("demo-mission", production[4], None)
    with pytest.raises(OSError):
        normalize_capture(raw, persisted=True)


def test_live_pop_uses_effective_manual_splice_geometry(api, production, clock):
    from app.mission.models import (
        ManualAARTrack,
        ManualAARTrackPoint,
        ManualRouteSplice,
    )
    from app.mission.pop_status import PopStatusService
    from app.services.pop.geometry import route_geometry_fingerprint

    mission = storage.load_mission_v2("demo-mission")
    mission.legs[0].transports.manual_aar_tracks = [
        ManualAARTrack(
            id="track",
            name="Diversion",
            points=[
                ManualAARTrackPoint(latitude=0.2, longitude=lon) for lon in (-8, -7)
            ],
        )
    ]
    mission.legs[0].transports.manual_route_splice = ManualRouteSplice(
        enabled_track_id="track", speed_knots=300
    )
    storage.save_mission_v2(mission)
    adapter = production[0]
    adapter.pop_service = PopStatusService(production[4], lambda: production[3])
    adapter.pop_service.status_payload(production[2]["telemetry"], now=clock.now())
    publication = adapter.pop_service.read_publication()
    assert publication["route_geometry_identity"] != route_geometry_fingerprint(
        production[4].get_route("route-a").points
    )
    snapshot = read(api, production)
    assert any(event["kind"] == "pop_advisory" for event in snapshot["events"]), {
        "publication": publication,
        "sources": snapshot["sources"],
        "legs": snapshot["legs"],
    }


def test_position_is_recaptured_after_expensive_preparation(
    api, production, clock, monkeypatch
):
    from app.operator.production_event_inputs import ModelInputs

    original = ModelInputs.prepare

    def moving(self, leg):
        artifacts = original(self, leg)
        clock.advance(11)
        position = production[2]["telemetry"].position
        position.longitude = 10
        position.observed_at = position.speed_observed_at = clock.now()
        return artifacts

    monkeypatch.setattr(ModelInputs, "prepare", moving)
    event = x_window(read(api, production))
    assert event["time_basis"] == "live_route_eta"
    assert event["state"] == "inactive"
    assert not event["active"]


def test_missing_live_pop_is_explicit_without_aging_known_x(api, production):
    snapshot = read(api, production)
    assert snapshot["legs"][0]["coverage"] == "partial"
    assert "PoP timing unavailable" in snapshot["legs"][0]["reason"]
    event = x_window(snapshot)
    assert event["time_basis"] == "live_route_eta" and event["freshness"] == "fresh"
    assert event["due_at"] and event["end_at"]


def test_ready_empty_and_deliberately_disabled_pop_have_no_gap(api, production, clock):
    import json

    from app.mission.pop_status import PopStatusService

    catalog = json.loads(production[6].read_text())
    catalog["sites"] = catalog["sites"][:1]
    production[6].write_text(json.dumps(catalog))
    adapter = production[0]
    adapter.pop_service = PopStatusService(production[4], lambda: production[3])
    adapter.pop_service.status_payload(production[2]["telemetry"], now=clock.now())
    publication = adapter.pop_service.read_publication()
    assert publication["payload"]["pop_forecast"]["status"] == "ready"
    assert not publication["payload"]["pop_forecast"]["transitions"]
    assert read(api, production)["legs"][0]["coverage"] == "available"
    mission = storage.load_mission_v2("demo-mission")
    mission.legs[0].transports.starshield_enabled = False
    storage.save_mission_v2(mission)
    adapter.pop_service = None
    disabled = read(api, production)
    assert disabled["legs"][0]["coverage"] == "available"
    assert any(
        source["freshness"] == "disabled" and source["source"].endswith(":live-pop")
        for source in disabled["sources"]
    )


def test_rejected_seek_publication_reports_current_leg_pop_gap(
    production, clock, monkeypatch
):
    from app.mission.pop_status import PopStatusService
    from app.operator.mission_timeline import build_mission_timeline
    from app.operator.production_event_inputs import capture_current
    from app.operator.runtime import OperatorRuntime

    adapter = production[0]
    inputs = capture_current(adapter, "demo-mission", as_of=clock.now(), scheduled=True)
    health = adapter.service.store.health().model_copy(
        update={"source_mode": "simulation", "simulation_run_id": "replay-a"}
    )
    monkeypatch.setattr(adapter.service.store, "health", lambda: health)
    production[3].mode = "simulation"
    context = adapter.context_provider
    adapter.context_provider = lambda: context() | {
        "source_mode": "simulation",
        "simulation_run_id": "replay-a",
        "lifecycle": "seek-two",
    }
    adapter.pop_service = PopStatusService()
    adapter.pop_service.snapshot(
        production[2]["telemetry"],
        route=production[4].get_route("route-a"),
        catalog=inputs.pop_catalog,
        enabled=True,
        mode="simulation",
        now=clock.now(),
        observed_now=clock.now(),
        mission_id="demo-mission",
        leg_id="leg-a",
        simulation_run_id="replay-a",
        lifecycle_token="seek-one",
    )
    runtime = OperatorRuntime(adapter.service.store.settings, clock)
    runtime.service = adapter.service
    snapshot = build_mission_timeline(runtime, "demo-mission", adapter).model_dump(
        mode="json"
    )
    assert snapshot["legs"][0]["coverage"] == "partial"
    assert "PoP timing unavailable" in snapshot["legs"][0]["reason"]
    assert not any(event["kind"] == "pop_advisory" for event in snapshot["events"])
    assert x_window(snapshot)["freshness"] == "fresh"


@pytest.mark.parametrize("invalid", ["stale", "wrong_route", "ambiguous_active"])
def test_active_timing_rejects_stale_or_wrong_association(
    api, production, clock, invalid
):
    if invalid == "stale":
        clock.advance(31)
    elif invalid == "wrong_route":
        context = production[0].context_provider
        production[0].context_provider = lambda: context() | {
            "active_route_id": "other-route"
        }
    else:
        other = storage.load_mission_v2("other-mission")
        other.legs[0].is_active = True
        storage.save_mission_v2(other)
    event = x_window(read(api, production))
    assert event["time_basis"] == "live_unavailable"
    assert event["due_at"] is None and event["end_at"] is None


def test_active_timing_rejects_store_epoch_change_during_position_capture(
    api, production, monkeypatch
):
    adapter = production[0]
    health = adapter.service.store.health()
    changed = {"value": False}
    monkeypatch.setattr(
        adapter.service.store,
        "health",
        lambda: (
            health.model_copy(update={"api_epoch": "different-epoch"})
            if changed["value"]
            else health
        ),
    )
    telemetry = adapter.telemetry_provider

    def switching():
        changed["value"] = True
        return telemetry()

    adapter.telemetry_provider = switching
    event = x_window(read(api, production))
    assert event["time_basis"] == "live_unavailable"
    assert event["due_at"] is None and event["end_at"] is None
