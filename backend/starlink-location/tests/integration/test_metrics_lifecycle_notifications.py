"""Bulk and file-backed notification boundaries, including config APIs."""

import httpx
import pytest

import main
from app.core.metrics import prometheus_metrics as metrics
from app.models.poi import POICreate
from tests.integration.test_live_background_route import background_runtime

__all__ = ["background_runtime"]


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
@pytest.mark.parametrize(
    "method,args",
    [
        ("delete_route_pois", ("first",)),
        ("delete_mission_pois", ("mission",)),
        ("delete_mission_pois_by_category", ("mission", {"test"})),
        ("delete_mission_pois_by_name_prefixes", ("mission", ["Bulk"])),
        ("delete_route_mission_pois_with_prefixes", ("first", ["Bulk"])),
        ("delete_leg_pois", ("first", "mission")),
        ("delete_scoped_pois_by_names", ({"Bulk 0", "Bulk 1", "Bulk 2"},)),
    ],
)
async def test_bulk_deletion_notifies_once_without_observations(
    background_runtime, method, args
):
    manager = main.app.state.poi_manager
    owner = main.app.state.metrics_refresh_owner
    for i in range(3):
        manager.create_poi(
            POICreate(
                name=f"Bulk {i}",
                latitude=1,
                longitude=1,
                route_id="first",
                mission_id="mission",
                category="test",
            )
        )
    await owner.refresh_without_collection()
    before = metrics.REGISTRY.get_sample_value("simulation_updates_total")
    revision = metrics.FRAME_STORE.read().input_revision
    assert getattr(manager, method)(*args) == 3
    assert metrics.FRAME_STORE.read().status == "pending"
    assert metrics.FRAME_STORE.read().input_revision == revision + 1
    await owner.refresh_without_collection()
    assert metrics.FRAME_STORE.read().status == "ready"

    family = next(
        f for f in metrics.REGISTRY.collect() if f.name == "starlink_eta_poi_seconds"
    )
    assert not family.samples
    assert metrics.REGISTRY.get_sample_value("simulation_updates_total") == before


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
@pytest.mark.parametrize("failure", ["parse", "profile"])
async def test_route_read_failure_preserves_confirmed_flight_phase(
    background_runtime, failure
):
    from app.models.flight_status import FlightPhase
    from app.services.kml_parser import KMLParseError

    routes = background_runtime.route_manager
    routes.activate_route("first")
    flight = background_runtime.flight_state
    flight.trigger_departure(background_runtime.origin)
    before = flight.get_status()
    if failure == "parse":
        path = routes.routes_dir / "first.kml"
        path.write_text("broken KML")
        routes._load_route_file(str(path))
    else:

        def invalid(_):
            raise KMLParseError("profile unavailable")

        routes._profile_resolver = invalid
        assert routes.get_active_route() is None
    assert flight.get_status().phase == FlightPhase.IN_FLIGHT
    assert flight.get_status().departure_time == before.departure_time
    assert flight.get_status().active_route_id is None


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_projection_publication_notifies_without_collecting(background_runtime):
    manager = main.app.state.poi_manager
    owner = main.app.state.metrics_refresh_owner
    manager.create_poi(POICreate(name="Projection", latitude=1, longitude=1))
    await owner.refresh_without_collection()
    assert manager.calculate_poi_projections(background_runtime.route) == 1
    assert metrics.FRAME_STORE.read().status == "pending"
    await owner.refresh_without_collection()
    assert metrics.FRAME_STORE.read().status == "ready"


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
@pytest.mark.parametrize("method", ["POST", "PUT"])
async def test_config_api_replacement_masks_previous_source(background_runtime, method):
    main._background_update_tick(main.app.state.poi_manager, 1, 0, 0)
    before = metrics.REGISTRY.get_sample_value("simulation_updates_total")
    old_identity = metrics.FRAME_STORE.read().frame.identity.coordinator_id
    config = main._coordinator.get_config().model_dump(mode="json")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url="http://test"
    ) as client:
        response = await client.request(method, "/api/config", json=config)
    assert response.status_code == 200
    await main.app.state.metrics_refresh_owner.refresh_without_collection()
    frame = metrics.FRAME_STORE.read().frame
    assert frame.identity.coordinator_id != old_identity
    assert frame.identity.observation_id is None
    assert metrics.REGISTRY.get_sample_value("simulation_updates_total") == before


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_external_active_route_reload_is_visible_without_telemetry(
    background_runtime,
):
    routes = background_runtime.route_manager
    routes.activate_route("first")
    owner = main.app.state.metrics_refresh_owner
    await owner.refresh_without_collection()
    main._coordinator._last_valid_telemetry = None
    path = routes.routes_dir / "first.kml"
    path.write_text("""<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
      <name>External route</name><Placemark><LineString><coordinates>
      0,0,1000 1,1,1000</coordinates></LineString></Placemark></Document></kml>""")
    routes._load_route_file(str(path))
    assert metrics.FRAME_STORE.read().status == "pending"
    await owner.refresh_without_collection()
    assert (
        metrics.REGISTRY.get_sample_value(
            "starlink_route_has_timing_data", {"route_name": "External route"}
        )
        == 0
    )
    assert (
        metrics.REGISTRY.get_sample_value(
            "starlink_route_has_timing_data", {"route_name": "first"}
        )
        is None
    )
    assert metrics.FRAME_STORE.read().frame.identity.observation_id is None


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_persisted_mission_change_notifies_without_new_enumeration(
    background_runtime, isolate_mission_storage, monkeypatch
):
    from app.mission import storage
    from app.mission.models import Mission

    storage.save_mission_v2(Mission(id="lifecycle-mission", name="Lifecycle", legs=[]))
    assert metrics.FRAME_STORE.read().status == "pending"

    def forbidden(*args, **kwargs):
        raise AssertionError("A lifecycle refresh enumerated missions")

    monkeypatch.setattr(storage, "list_mission_metadata_v2", forbidden)
    await main.app.state.metrics_refresh_owner.refresh_without_collection()
    assert metrics.FRAME_STORE.read().status == "ready"
