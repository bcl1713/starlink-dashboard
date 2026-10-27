"""Status projections use effective routes, provenance, and isolated observation modes."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.api import status as status_api
from app.mission.pop_status import PopStatusService
from app.models.config import SimulationConfig
from app.services.ground_entry_point import GroundEntryPoint
from app.services.pop.models import PopForecast, PopObservation
from tests.conftest import default_mock_telemetry
from tests.unit.test_mission_pop_forecast import route, sites

NOW = datetime(2035, 1, 1, tzinfo=timezone.utc)
CATALOG = sites(("a", 0, -5), ("b", 0, 15))


def telemetry(lon=-5, age=0):
    result = default_mock_telemetry()
    result.timestamp = NOW
    result.position.latitude = 0
    result.position.longitude = lon
    result.position.speed = 300
    result.position.observed_at = NOW - timedelta(seconds=age)
    result.position.speed_observed_at = NOW - timedelta(seconds=age)
    return result


def known(city="a", source="live"):
    return PopObservation(
        ip="203.0.113.1",
        status="known",
        source=source,
        entry=GroundEntryPoint("203.0.113.1", city, "US", 0, -5),
    )


def snapshot(service, **kwargs):
    values = {
        "route": route(),
        "catalog": CATALOG,
        "enabled": True,
        "mode": "live",
        "now": NOW,
    }
    values.update(kwargs)
    return service.snapshot(telemetry(), **values)


@pytest.mark.parametrize("age", [10, 100])
def test_stale_telemetry_cannot_publish_a_current_forecast(age):
    service = PopStatusService(
        observation_provider=lambda mode, telemetry, catalog: known()
    )
    payload = service.snapshot(
        telemetry(age=age),
        route=route(),
        catalog=CATALOG,
        enabled=True,
        mode="live",
        now=NOW,
    )
    assert payload["pop_forecast"]["status"] == "unavailable"
    assert payload["pop_observation"]["status"] == "known"
    assert payload["pop_advisories"] == []


def test_current_speed_provenance_is_required_independently():
    sample = telemetry()
    sample.position.speed_observed_at = None
    payload = PopStatusService().snapshot(
        sample, route=route(), catalog=CATALOG, enabled=True, mode="live", now=NOW
    )
    assert payload["pop_forecast"]["status"] == "unavailable"


@pytest.mark.parametrize(
    "change",
    [
        {"lifecycle_token": "reset"},
        {"mode": "simulation"},
        {"now": NOW - timedelta(seconds=1)},
        {"route": route((-10, 1, 10))},
    ],
)
def test_route_revision_seek_reset_and_mode_rebase_completion(change):
    service = PopStatusService(
        observation_provider=lambda mode, telemetry, catalog: known("b", mode)
    )
    shared_route = route()
    first = snapshot(service, route=shared_route)
    completed = service.state.completed_ids
    assert len(completed) == 1
    second = snapshot(service, route=shared_route, now=NOW + timedelta(seconds=1))
    assert first["pop_forecast"]["revision"] == second["pop_forecast"]["revision"]
    assert service.state.completed_ids == completed
    values = {"route": shared_route}
    values.update(change)
    payload = snapshot(service, **values)
    assert payload["pop_forecast"]["revision"] != first["pop_forecast"]["revision"]
    assert not (service.state.completed_ids & completed)


def test_obsolete_forecast_is_rejected_without_overwriting_current_state():
    service = PopStatusService()
    old = snapshot(service)["pop_forecast"]
    snapshot(service, lifecycle_token="new")
    before = service.state
    accepted = service.reconcile(
        PopForecast.model_validate(old),
        known("b"),
        catalog=CATALOG,
        nearest_id="a",
        next_id="b",
        now=NOW,
    )
    assert accepted is None
    assert service.state == before


def test_default_provider_does_not_use_production_cache_in_simulation(monkeypatch):
    from app.services import ground_entry_point

    monkeypatch.setattr(
        ground_entry_point, "get_cached_pop_observation", lambda: known()
    )
    service = PopStatusService()
    assert snapshot(service)["pop_observation"]["status"] == "known"
    simulated = snapshot(service, mode="simulation")
    assert simulated["pop_observation"] == {
        "ip": None,
        "entry": None,
        "status": "unknown",
        "source": "simulation",
        "sampled_at": None,
        "lookup_at": None,
        "freshness": "unknown",
    }


def test_missing_route_retains_observation_and_disabled_never_advises():
    service = PopStatusService(observation_provider=lambda *args: known())
    assert snapshot(service, route=None)["pop_forecast"]["status"] == "unavailable"
    disabled = snapshot(service, enabled=False)
    assert disabled["pop_forecast"]["status"] == "disabled"
    assert disabled["pop_advisories"] == []


def test_endpoint_adds_fields_without_network_lookup_or_changing_legacy_values(
    test_client, monkeypatch
):
    sample = telemetry()
    coordinator = SimpleNamespace(
        get_current_telemetry=lambda: sample,
        get_config=lambda: SimulationConfig(mode="live"),
    )
    monkeypatch.setattr(status_api, "_coordinator", coordinator)
    monkeypatch.setattr(
        status_api,
        "_pop_service",
        PopStatusService(
            config_provider=lambda: SimulationConfig(mode="live"),
            observation_provider=lambda *args: known(),
        ),
    )
    from app.services import ground_entry_point

    monkeypatch.setattr(
        ground_entry_point,
        "resolve_public_ip",
        lambda: pytest.fail("HTTP status must not discover IP"),
    )
    response = test_client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["pop_forecast"]["status"] == "unavailable"
    assert data["pop_observation"]["status"] == "known"
    assert data["position"]["speed"] == 300
    assert data["network"]["latency_ms"] == sample.network.latency_ms
    assert data["metric_availability"] == sample.metric_availability.model_dump()


def test_active_mission_uses_effective_route_and_starshield_setting(monkeypatch):
    from app.mission import pop_status

    effective = route((-10, 0, 1), (0, 10, 20))  # Never crosses a/b boundary at lon 5.
    leg = SimpleNamespace(transports=SimpleNamespace(starshield_enabled=True))
    context = SimpleNamespace(leg=leg, parent_mission_id="m", route_id="r")
    monkeypatch.setattr(
        pop_status,
        "resolve_active_mission_leg_context",
        lambda manager: SimpleNamespace(context=context, state="available"),
    )
    monkeypatch.setattr(
        pop_status, "prepare_effective_route", lambda got, manager: effective
    )
    config = SimulationConfig(mode="live")
    manager = SimpleNamespace(get_active_route=lambda: route())
    service = PopStatusService(
        manager, lambda: config, observation_provider=lambda *args: known()
    )
    monkeypatch.setattr(pop_status, "load_catalog", lambda path: CATALOG)
    payload = service.status_payload(telemetry(), now=NOW)
    assert payload["pop_forecast"]["status"] == "ready"
    assert payload["pop_forecast"]["transitions"] == []
    leg.transports.starshield_enabled = False
    assert (
        service.status_payload(telemetry(), now=NOW)["pop_forecast"]["status"]
        == "disabled"
    )


def test_catalog_failure_preserves_observation_and_existing_status(monkeypatch):
    from app.mission import pop_status

    def unavailable(path):
        raise ValueError("broken catalog")

    monkeypatch.setattr(pop_status, "load_catalog", unavailable)
    service = PopStatusService(
        config_provider=lambda: SimulationConfig(mode="live"),
        observation_provider=lambda *args: known(),
    )
    payload = service.status_payload(telemetry(), now=NOW)
    assert payload["pop_forecast"]["status"] == "unavailable"
    assert payload["pop_observation"]["status"] == "known"


def test_predeparture_uses_planned_timing_and_route_start_without_fresh_aircraft():
    service = PopStatusService(observation_provider=lambda *args: known())
    payload = service.snapshot(
        telemetry(age=100),
        route=route(),
        catalog=CATALOG,
        enabled=True,
        mode="live",
        now=NOW,
        flight_phase="pre_departure",
    )
    assert payload["pop_forecast"]["status"] == "ready"
    assert (
        payload["pop_forecast"]["transitions"][0]["crossing_utc"]
        == "2035-01-01T00:25:00Z"
    )
    assert payload["pop_advisories"] == []


def test_cached_prior_city_cannot_complete_current_unknown_ip_observation():
    from app.services.ground_entry_point import GroundEntryPointResolver

    old = GroundEntryPoint("203.0.113.1", "b", "US", 0, 15)
    ips = iter([old.ip, "203.0.113.2"])
    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: next(ips),
        geolocator=lambda ip: old if ip == old.ip else None,
        poll_interval_seconds=0,
    )
    resolver.refresh()
    resolver.refresh()
    assert resolver.current() is None
    service = PopStatusService(
        observation_provider=lambda *args: resolver.observation()
    )
    payload = snapshot(service)
    assert not service.state.completed_ids
    assert payload["pop_observation"]["status"] == "unknown"
    assert [a["kind"] for a in payload["pop_advisories"]] == ["observation_unknown"]


def test_mission_clock_does_not_age_real_observation_provenance():
    payload = PopStatusService().snapshot(
        telemetry(),
        route=route(),
        catalog=CATALOG,
        enabled=True,
        mode="simulation",
        now=NOW + timedelta(days=1),
        observed_now=NOW,
    )
    assert payload["pop_forecast"]["status"] == "ready"
