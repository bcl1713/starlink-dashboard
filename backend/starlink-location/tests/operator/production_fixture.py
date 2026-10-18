"""Real raw route/catalog inputs shared by production-source regressions."""

import json

import pytest

from app.mission import storage
from app.models.config import SimulationConfig
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
    routes.activate_route(leg.route_id)
    clock.advance(600)
    inputs["telemetry"].position.observed_at = clock.now()
    inputs["telemetry"].position.speed_observed_at = clock.now()
    inputs["telemetry"].position.longitude = -9.5
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
            "active_route_id": routes.get_active_route_id(),
            "phase": "in_flight",
        },
    )
    return adapter, publication, state, config, routes, leg, path
