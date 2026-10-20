"""Normal production inputs can publish and guard significant modeled alerts."""

import json

import pytest

from app.mission import storage
from app.operator.errors import OperatorError
from app.operator.event_eligibility import select_eligible
from app.operator.event_policy import EventPolicy
from app.operator.event_projection import derive_events


def test_real_preparation_promotes_normal_sources_and_reuses_revision(
    production, clock
):
    adapter, publication, *_ = production
    first = adapter.capture("demo-mission", as_of=clock.now())
    source = next(s for s in first.sources if s.source.startswith("model:"))
    assert source.aligned and source.guardable and source.freshness == "fresh"
    from app.operator.event_ledger import reconcile

    with adapter.service.store.connect(write=True) as db:
        events = reconcile(
            db,
            derive_events(first, as_of=clock.now(), policy=EventPolicy()),
            as_of=clock.now(),
            policy=EventPolicy(),
        )
    select_eligible(events, as_of=clock.now())
    assert any(
        e.kind == "restriction" and e.transport == "X" and e.notification.eligible
        for e in events
    ), [
        (s["x_state"], s["reasons"], s.get("metadata"))
        for s in first.models["leg-a"]["segments"]
    ]
    assert all(not e.notification.eligible for e in events if e.kind == "pop_advisory")
    second = adapter.capture("demo-mission", as_of=clock.now())
    assert second.models == first.models
    assert second.sources == first.sources
    with publication.guard([source]):
        pass


@pytest.mark.parametrize(
    "change",
    [
        "route",
        "config",
        "catalog",
        "leg",
        "lifecycle",
        "telemetry_stale",
        "missing_catalog",
    ],
)
def test_real_inputs_invalidate_guarded_publication(production, clock, change):
    adapter, publication, state, config, routes, leg, path = production
    before = adapter.capture("demo-mission", as_of=clock.now())
    source = next(s for s in before.sources if s.source.startswith("model:"))
    if change == "route":
        route = routes.get_route(leg.route_id).model_copy(deep=True)
        route.points[-1].longitude += 0.1
        routes.add_route(leg.route_id, route)
    elif change == "config":
        config.pop.catalog_path = path.with_name("other.json")
    elif change == "catalog":
        raw = json.loads(path.read_text())
        raw["sites"][0]["longitude"] += 0.2
        path.write_text(json.dumps(raw))
    elif change == "leg":
        mission = storage.load_mission_v2("demo-mission")
        mission.legs[0].transports.starshield_enabled = False
        storage.save_mission_v2(mission)
    elif change == "lifecycle":
        state["lifecycle"] = "run-2"
    elif change == "telemetry_stale":
        clock.advance(31)
    elif change == "missing_catalog":
        path.unlink()
    with pytest.raises(OperatorError) as raised, publication.guard([source]):
        pass
    assert raised.value.code in ("event_snapshot_changed", "event_source_unavailable")
    after = adapter.capture("demo-mission", as_of=clock.now())
    if change == "telemetry_stale":
        assert not any(
            s.aligned and s.freshness == "fresh"
            for s in after.sources
            if s.source.startswith("model:")
        )
    else:
        assert after.sources != before.sources


def test_normal_router_factory_emits_and_acknowledges_real_restriction(
    api, production, clock
):
    from app.operator.production_event_sources import ProductionEventSources
    from tests.operator.api_helpers import BASE, headers

    adapter, _publication, *_rest = production

    def factory(runtime):
        return ProductionEventSources(
            runtime.service,
            clock=runtime.clock,
            publication=runtime.event_publication,
            route_manager=adapter.route_manager,
            poi_manager=adapter.poi_manager,
            config_provider=adapter.config_provider,
            telemetry_provider=adapter.telemetry_provider,
            context_provider=adapter.context_provider,
        )

    api.app.state.operator_event_source_factory = factory
    response = api.get(BASE + "/events", params={"mission_id": "demo-mission"})
    assert response.status_code == 200
    snapshot = response.json()
    event = next(
        e
        for e in snapshot["events"]
        if e["kind"] == "restriction" and e["transport"] == "X"
    )
    assert (
        event["notification"]["eligible"]
        and event["notification"]["acknowledgment_available"]
    )
    receipt = api.post(
        BASE + "/events/acknowledge",
        headers=headers(api),
        json={
            "schema_version": 1,
            "occurrence_id": event["notification"]["generation"],
            "severity_generation": event["notification"]["severity_generation"],
            "snapshot_token": snapshot["snapshot_token"],
        },
    )
    assert receipt.status_code == 200, receipt.text
    current = api.get(BASE + "/events", params={"mission_id": "demo-mission"}).json()
    acked = next(e for e in current["events"] if e["event_id"] == event["event_id"])
    assert (
        acked["notification"]["acknowledged"] and not acked["notification"]["eligible"]
    )


def test_changed_persisted_satellite_catalog_is_consumed_not_relabelled(
    production, clock
):
    adapter, publication, *_ = production
    first = adapter.capture("demo-mission", as_of=clock.now())
    source = next(
        s for s in first.sources if s.guardable and s.source.startswith("model:")
    )
    # Prime the application cache before replacing its persistent source.
    from app.satellites.catalog import get_satellite_catalog

    get_satellite_catalog()
    from pathlib import Path

    Path("data/satellites/catalog.yaml").write_text(
        "satellites:\n  - id: X-1\n    transport: X\n    longitude: 0\n"
    )
    with pytest.raises(OperatorError), publication.guard([source]):
        pass
    latest = adapter.capture("demo-mission", as_of=clock.now())
    assert latest.sources != first.sources
    assert latest.models != first.models


def test_new_route_file_cannot_relabel_an_older_accepted_route(production, clock):
    adapter, publication, _state, _config, routes, leg, _path = production
    first = adapter.capture("demo-mission", as_of=clock.now())
    source = next(
        s for s in first.sources if s.guardable and s.source.startswith("model:")
    )
    (routes.routes_dir / f"{leg.route_id}.kml").write_text(
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><LineString><coordinates>30,0,0 40,0,0</coordinates></LineString></Placemark></kml>'
    )
    with pytest.raises(OperatorError), publication.guard([source]):
        pass
    latest = adapter.capture("demo-mission", as_of=clock.now())
    assert not any(
        s.aligned and s.freshness == "fresh"
        for s in latest.sources
        if s.source == source.source
    )


def test_missing_transport_inputs_remain_explicit(production, clock):
    from pathlib import Path

    adapter, _publication, *_ = production
    Path("data/satellites/catalog.yaml").unlink()
    captured = adapter.capture("demo-mission", as_of=clock.now())
    assert any(
        "inputs unavailable" in (s.reason or "").lower() for s in captured.sources
    )


def test_missing_ka_inputs_do_not_suppress_current_x_warning(
    production, clock, monkeypatch
):
    from pathlib import Path

    from app.operator.event_feed import build_snapshot
    from app.operator.runtime import OperatorRuntime

    adapter, publication, *_ = production
    Path("data/sat_coverage/commka.geojson").unlink()
    from app.mission import timeline_service

    monkeypatch.setattr(timeline_service, "APP_DIR", Path("unavailable-assets"))
    runtime = OperatorRuntime(adapter.service.store.settings, clock=clock)
    runtime.service = adapter.service
    runtime.event_publication = publication
    snapshot = build_snapshot(runtime, "demo-mission", adapter)
    assert snapshot.coverage == "partial"
    assert any(e.transport == "X" and e.notification.eligible for e in snapshot.events)


def test_explicit_leg_deactivation_retires_model_heads(production, clock):
    from app.operator.event_feed import build_snapshot
    from app.operator.runtime import OperatorRuntime

    adapter, publication, *_ = production
    runtime = OperatorRuntime(adapter.service.store.settings, clock)
    runtime.service, runtime.event_publication = adapter.service, publication
    before = build_snapshot(runtime, "demo-mission", adapter)
    assert any(e.kind == "restriction" and e.active for e in before.events)
    mission = storage.load_mission_v2("demo-mission")
    mission.legs[0].is_active = False
    storage.save_mission_v2(mission)
    after = build_snapshot(runtime, "demo-mission", adapter)
    assert not any(e.kind == "restriction" and e.active for e in after.events)


def test_actual_pop_service_uses_separate_live_eta_source(production, clock):
    from app.mission.pop_status import PopStatusService

    adapter, publication, state, config, routes, *_ = production
    adapter.pop_service = PopStatusService(routes, lambda: config)
    first = adapter.capture("demo-mission", as_of=clock.now())
    live = next(s for s in first.sources if s.source.endswith(":live-pop"))
    assert live.guardable and live.aligned and live.freshness == "fresh"
    events = derive_events(first, as_of=clock.now(), policy=EventPolicy())
    assert any(e.source_ref == live.source and e.kind == "pop_advisory" for e in events)
    assert not any(
        e.source_ref == live.source and e.kind == "restriction" for e in events
    )
    state["telemetry"].position.longitude += 1
    with pytest.raises(OperatorError), publication.guard([live]):
        pass
    latest = adapter.capture("demo-mission", as_of=clock.now())
    assert (
        next(s for s in latest.sources if s.source == live.source).generation
        != live.generation
    )


def test_preparation_result_rejected_after_supported_route_publication(
    production, clock, monkeypatch
):
    from app.operator.production_event_inputs import ModelInputs

    adapter, _publication, _state, _config, routes, leg, *_ = production
    prepare = ModelInputs.prepare

    def changing(self, item):
        result = prepare(self, item)
        route = routes.get_route(leg.route_id).model_copy(deep=True)
        route.points[-1].longitude += 1
        routes.add_route(leg.route_id, route)
        return result

    monkeypatch.setattr(ModelInputs, "prepare", changing)
    captured = adapter.capture("demo-mission", as_of=clock.now())
    assert not any(
        s.guardable for s in captured.sources if s.source.startswith("model:")
    )
    assert not adapter.cache


def test_missing_pop_catalog_does_not_hide_known_x_warning(production, clock):
    from app.operator.event_feed import build_snapshot
    from app.operator.runtime import OperatorRuntime

    adapter, publication, *_rest, path = production
    path.unlink()
    runtime = OperatorRuntime(adapter.service.store.settings, clock)
    runtime.service, runtime.event_publication = adapter.service, publication
    snapshot = build_snapshot(runtime, "demo-mission", adapter)
    assert snapshot.coverage == "partial"
    assert any(e.transport == "X" and e.notification.eligible for e in snapshot.events)


def test_timing_guard_uses_one_coherent_input_capture(production, clock, monkeypatch):
    from time import perf_counter

    from app.operator import production_event_sources as module

    adapter, *_ = production
    inputs = module.capture_current(adapter, "demo-mission", as_of=clock.now())
    capture = module.capture_current
    calls = []

    def measured(*args, **kwargs):
        calls.append(1)
        return capture(*args, **kwargs)

    monkeypatch.setattr(module, "capture_current", measured)
    started = perf_counter()
    adapter._validate_timing("demo-mission", inputs.revision, inputs.sample_revision)
    print(
        {
            "validation_captures": len(calls),
            "validation_ms": round((perf_counter() - started) * 1000, 2),
        }
    )
    assert len(calls) == 1
