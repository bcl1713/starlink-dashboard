"""Normal production inputs can publish and guard significant modeled alerts."""

import json

import pytest

from app.mission import storage
from app.models.config import SimulationConfig
from app.operator.errors import OperatorError
from app.operator.event_eligibility import select_eligible
from app.operator.event_policy import EventPolicy
from app.operator.event_projection import derive_events
from app.operator.event_publication import EventPublication
from app.services.route_manager import RouteManager
from tests.operator.fixtures import pop_inputs


@pytest.fixture
def production(service, clock, tmp_path, monkeypatch):
    from app.operator.production_event_sources import ProductionEventSources

    inputs = pop_inputs(clock)
    monkeypatch.chdir(tmp_path)
    from app.mission import timeline_service
    from app.satellites import catalog as satellite_catalog

    monkeypatch.setattr(timeline_service, "_COVERAGE_SAMPLER", None)
    monkeypatch.setattr(satellite_catalog, "_catalog", None)
    coverage = tmp_path / "data/sat_coverage"
    coverage.mkdir(parents=True)
    (coverage / "commka.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"satellite_id": "AOR"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [[-20, -10], [20, -10], [20, 10], [-20, 10], [-20, -10]]
                            ],
                        },
                    }
                ],
            }
        )
    )
    satellites = tmp_path / "data/satellites"
    satellites.mkdir()
    (satellites / "catalog.yaml").write_text(
        "satellites:\n  - id: X-1\n    transport: X\n    longitude: 90\n"
    )
    path = tmp_path / "pops.json"
    path.write_text(
        json.dumps(
            {"sites": [s.model_dump(mode="json") for s in inputs["catalog"].sites]}
        )
    )
    config = SimulationConfig(mode="live")
    config.pop.catalog_path = path
    mission = storage.load_mission_v2("demo-mission")
    leg = mission.legs[0]
    leg.is_active = True
    leg.transports.starshield_enabled = True
    storage.save_mission_v2(mission)
    routes = RouteManager(tmp_path / "routes")
    route = inputs["route"].model_copy(update={"route_id": leg.route_id}, deep=True)
    routes.add_route(leg.route_id, route)
    state = {"telemetry": inputs["telemetry"], "lifecycle": "run-1"}
    publication = EventPublication()
    adapter = ProductionEventSources(
        service,
        clock=clock,
        publication=publication,
        route_manager=routes,
        config_provider=lambda: config,
        telemetry_provider=lambda: state["telemetry"],
        context_provider=lambda: {
            "source_mode": "live",
            "simulation_run_id": None,
            "lifecycle": state["lifecycle"],
            "active_route_id": leg.route_id,
            "phase": "in_flight",
        },
    )
    return adapter, publication, state, config, routes, leg, path


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
    if change in ("config", "telemetry_stale", "missing_catalog"):
        assert not any(
            s.aligned and s.freshness == "fresh"
            for s in after.sources
            if s.source.startswith("model:")
        )
    else:
        assert after.sources != before.sources
