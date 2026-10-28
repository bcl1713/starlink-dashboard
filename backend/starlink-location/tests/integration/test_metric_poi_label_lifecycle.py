"""Real CRUD notifications replace the entire current POI/route label set."""

from math import isnan

import main
import pytest
from app.core.metrics import prometheus_metrics as metrics
from app.models.flight_status import FlightPhase
from app.models.poi import POICreate, POIUpdate

from tests.integration.test_live_background_route import background_runtime

__all__ = ["background_runtime"]


def samples(name):
    return next(f.samples for f in metrics.REGISTRY.collect() if f.name == name)


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_200_poi_edits_and_route_renames_do_not_accumulate(background_runtime):
    manager = main.app.state.poi_manager
    routes = background_runtime.route_manager
    owner = main.app.state.metrics_refresh_owner
    routes.activate_route("first")
    poi = manager.create_poi(POICreate(name="Before", latitude=1, longitude=1))
    for i in range(200):
        name, category = f"POI {i}", f"category-{i % 3}"
        manager.update_poi(poi.id, POIUpdate(name=name, category=category))
        route = routes.get_active_route().model_copy(deep=True)
        route.metadata.name = f"Route {i}"
        routes.add_route("first", route)
        await owner.refresh_without_collection()
        for metric in ("starlink_eta_poi_seconds", "starlink_distance_to_poi_meters"):
            current = samples(metric)
            assert len(current) == 1
            assert current[0].labels == {
                "name": name,
                "category": category,
                "eta_type": "anticipated",
            }
            # No accepted aircraft location/speed: no invented zero measurement.
            assert isnan(current[0].value)
        timing = samples("starlink_route_has_timing_data")
        assert len(timing) == 1
        assert timing[0].labels == {"route_name": f"Route {i}"}
        assert timing[0].value == 0  # genuine absence of embedded timing

    background_runtime.flight_state.transition_phase(FlightPhase.IN_FLIGHT)
    await owner.refresh_without_collection()
    assert {s.labels["eta_type"] for s in samples("starlink_eta_poi_seconds")} == {
        "estimated"
    }
    manager.delete_poi(poi.id)
    routes.deactivate_route()
    await owner.refresh_without_collection()
    assert samples("starlink_eta_poi_seconds") == []
    assert samples("starlink_distance_to_poi_meters") == []
    for definition in metrics.COUPLED_SCHEMA:
        if definition.labelnames == ("route_name",):
            assert samples(definition.name) == []
