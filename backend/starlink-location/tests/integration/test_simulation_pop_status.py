"""Actual replay emissions and status share spherical geography and mission time."""

import json
from datetime import datetime, timedelta

import main
import pytest
from app.api import status as status_api
from app.core.metrics import REGISTRY
from app.mission.pop_status import PopStatusService
from app.services import ground_entry_point as gep
from app.simulation.pop import SimulationPopObservationProvider
from prometheus_client import generate_latest

from tests.integration.test_simulation_run_api import LEG, api

__all__ = ["api"]


@pytest.fixture
def pop_api(api, monkeypatch, tmp_path):
    client, service, clocks = api
    config = service.coordinator.config
    config.network.packet_loss_min_percent = config.network.packet_loss_max_percent = 0
    path = tmp_path / "pop.json"

    # Equatorial 0 -> 1 -> 2 fixture crosses the A/B boundary at longitude .5,
    # exactly mission second 150, despite later segment's slower speed.
    def set_sites(locations):
        path.write_text(
            json.dumps(
                {
                    "sites": [
                        {
                            "id": name,
                            "city": name.upper(),
                            "country": "US",
                            "latitude": lat,
                            "longitude": lon,
                            "source": "test",
                            "coordinate_source": "test",
                        }
                        for name, lat, lon in locations
                    ]
                }
            )
        )

    set_sites([("a", 0, -0.5), ("b", 0, 1.5)])
    config.pop.catalog_path = path
    monkeypatch.setattr(main, "_coordinator", service.coordinator)
    monkeypatch.setattr(main, "_simulation_config", config)
    monkeypatch.setattr(main, "_route_manager", service.route_manager)
    monkeypatch.setattr(
        main.app.state, "simulation_run_service", service, raising=False
    )
    monkeypatch.setattr(
        main.app.state, "poi_manager", service.poi_manager, raising=False
    )
    pops = PopStatusService(
        service.route_manager,
        lambda: service.coordinator.config,
        observation_provider=SimulationPopObservationProvider(
            main._pop_lifecycle_token
        ),
        snapshot_context_provider=main._simulation_pop_context,
    )
    monkeypatch.setattr(main.app.state, "pop_status_service", pops, raising=False)
    monkeypatch.setattr(status_api, "_coordinator", service.coordinator)
    monkeypatch.setattr(status_api, "_pop_service", pops)
    client.app.include_router(status_api.router)
    service.publish = main._publish_replay_telemetry

    def forbidden(*args, **kwargs):
        raise AssertionError("Synthetic IP must not reach external discovery")

    monkeypatch.setattr(gep, "resolve_public_ip", forbidden)
    monkeypatch.setattr(gep, "geolocate_public_ip", forbidden)
    monkeypatch.setattr(gep, "resolve_public_ip_via_dns", forbidden)
    monkeypatch.setattr(gep, "resolve_public_ip_via_cloudflare_trace", forbidden)
    monkeypatch.setattr(gep._resolver, "_geolocator", forbidden)
    try:
        yield client, service, clocks, pops, set_sites
    finally:
        service.close()
        gep.clear_ground_entry_point_metrics()


def start_paced(client, multiplier):
    pacing = {"mode": "multiplier", "multiplier": multiplier}
    preview = client.post(LEG + "/simulation/preview", json=pacing)
    assert preview.status_code == 200, preview.text
    response = client.post(
        LEG + "/activate",
        json={
            "simulation": {"pacing": pacing, "plan_token": preview.json()["plan_token"]}
        },
    )
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("multiplier", [1, 10, 100])
@pytest.mark.parametrize(
    "center_second, sites, changed_lon",
    [
        (150, [("a", 0, -0.5), ("b", 0, 1.5)], 0.503333333333),
        (750, [("a", 0, 0.5), ("b", 0, 2.5)], 1.501111111111),
    ],
)
def test_first_ip_change_matches_forecast_center_to_one_emitted_frame(
    pop_api, multiplier, center_second, sites, changed_lon
):
    client, service, clocks, pops, set_sites = pop_api
    set_sites(sites)
    start_paced(client, multiplier)
    plan = service.runtime.selected_plan()
    assert plan.artifacts.projector.route_snapshot == plan.artifacts.route.model_dump()
    before = client.get("/api/status").json()
    assert before["pop_forecast"]["status"] == "ready", before["pop_forecast"]
    crossing = before["pop_forecast"]["transitions"][0]
    center = datetime.fromisoformat(crossing["crossing_utc"].replace("Z", "+00:00"))
    assert center == service.status().run.planned_departure + timedelta(
        seconds=center_second
    )
    assert before["pop_observation"]["ip"] == "192.0.2.1"
    # First emit immediately before T, then on T (tie retains A), then after T.
    for target, expected in [
        (center_second - 1, "192.0.2.1"),
        (center_second, "192.0.2.1"),
        (center_second + 1, "192.0.2.2"),
    ]:
        clocks.advance(target / multiplier - clocks.elapsed)
        service.collect(service.coordinator, service.publish)
        result = client.get("/api/status").json()
        assert result["pop_observation"]["ip"] == expected
        assert result["pop_observation"]["entry"]["city"] == (
            "A" if target <= center_second else "B"
        )
        info = next(
            line
            for line in generate_latest(REGISTRY).decode().splitlines()
            if line.startswith("starlink_ground_entry_point_info{")
        )
        assert f'ip="{expected}"' in info
        assert result["pop_forecast"]["revision"] == before["pop_forecast"]["revision"]
        assert (
            plan.artifacts.projector.route_snapshot == plan.artifacts.route.model_dump()
        )
    frame = service.runtime.frame()
    assert (frame.simulation_time - center).total_seconds() == 1
    assert frame.position.longitude == pytest.approx(changed_lon, abs=1e-8)
    assert len(pops.state.completed_ids) == 1
    assert service.status().state == "running"
    if center_second == 750:
        assert result["position"]["speed"] < before["position"]["speed"] / 2
    # A PoP observation is not a network performance measurement.
    assert result["metric_availability"]["packet_loss_percent"] is False
    assert result["network"]["packet_loss_percent"] is None
    assert service.status().run.transport_states["Ku"] == "available"


@pytest.mark.parametrize(
    "start,end,sites,mid_lat,mid_lon",
    [
        ((60, -60), (60, 60), [("a", 60, -60), ("b", 60, 60)], 73.897886248, 0),
        ((0, 170), (0, -170), [("a", 0, 170), ("b", 0, -170)], 0, 180),
    ],
)
def test_curved_and_dateline_replay_centers_follow_emitted_spherical_position(
    pop_api, start, end, sites, mid_lat, mid_lon
):
    client, service, clocks, _, set_sites = pop_api
    set_sites(sites)
    route = service.route_manager.get_route("replay")
    route.points = [route.points[0], route.points[-1]]
    for point, (lat, lon) in zip(route.points, (start, end)):
        point.latitude, point.longitude = lat, lon
    route.metadata.point_count = 2
    start_paced(client, 10)
    first = client.get("/api/status").json()
    assert first["pop_forecast"]["status"] == "ready", first["pop_forecast"]
    transition = first["pop_forecast"]["transitions"][0]
    center = datetime.fromisoformat(transition["crossing_utc"].replace("Z", "+00:00"))
    assert center == service.status().run.planned_departure + timedelta(seconds=600)
    clocks.advance(60)
    service.collect(service.coordinator, service.publish)
    frame = service.runtime.frame()
    assert frame.position.latitude == pytest.approx(mid_lat, abs=1e-8)
    assert abs(frame.position.longitude) == pytest.approx(abs(mid_lon), abs=1e-8)
    at_center = client.get("/api/status").json()
    assert at_center["pop_observation"]["ip"] == "192.0.2.1"
    clocks.advance(0.1)
    service.collect(service.coordinator, service.publish)
    assert client.get("/api/status").json()["pop_observation"]["ip"] == "192.0.2.2"


def test_replay_context_is_ignored_in_live_mode(pop_api):
    client, service, _, pops, _ = pop_api
    start_paced(client, 10)
    called = []
    pops.snapshot_context_provider = lambda: called.append(True)
    service.coordinator.config.mode = "live"
    result = client.get("/api/status").json()
    assert result["pop_observation"]["source"] == "live"
    assert called == []


def test_catalog_failure_clears_current_synthetic_ip_and_metrics(pop_api):
    client, service, clocks, _, _ = pop_api
    start_paced(client, 10)
    assert client.get("/api/status").json()["pop_observation"]["status"] == "known"
    service.coordinator.config.pop.catalog_path.write_text('{"sites": []}')
    clocks.advance(1)
    service.collect(service.coordinator, service.publish)
    result = client.get("/api/status").json()
    assert result["pop_observation"] == {
        "ip": None,
        "entry": None,
        "source": "simulation",
        "status": "unknown",
    }
    assert result["ground_entry_point"] is None
    assert result["pop_forecast"]["status"] == "unavailable"
    assert "starlink_ground_entry_point_info{" not in generate_latest(REGISTRY).decode()


def test_ordinary_metrics_paced_gap_and_return_to_activate(pop_api):
    client, service, _clocks, _pops, _sites = pop_api
    assert client.post(LEG + "/activate").status_code == 200
    main._background_update_tick(service.poi_manager, 10, 0, 0)
    ordinary = client.get("/api/status").json()
    assert ordinary["metric_source"] == "simulated"
    assert all(ordinary["metric_availability"].values())
    assert ordinary["network"]["latency_ms"] > 0
    start_paced(client, 2)
    paced = client.get("/api/status").json()
    assert paced["metric_source"] == "unavailable"
    assert not any(paced["metric_availability"].values())
    assert all(value is None for value in paced["network"].values())
    assert paced["obstruction"]["obstruction_percent"] is None
    assert client.post("/api/v2/missions/mission-1/legs/deactivate").status_code == 200
    assert client.post(LEG + "/activate").status_code == 200
    main._background_update_tick(service.poi_manager, 10, 0, 0)
    restored = client.get("/api/status").json()
    assert restored["metric_source"] == "simulated"
    assert all(restored["metric_availability"].values())
    assert restored["network"]["latency_ms"] > 0
