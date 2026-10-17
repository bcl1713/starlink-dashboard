"""Predeparture PoP predictions remain additive and independent of ground egress."""

from types import SimpleNamespace

import pytest

from app.api import status as status_api
from app.mission import pop_status
from app.mission.models import MissionLeg, TransportConfig
from app.mission.pop_status import PopStatusService
from app.models.config import SimulationConfig
from app.models.flight_status import FlightStatus
from app.services import flight_state
from tests.integration.test_pop_status import CATALOG, NOW, known, telemetry
from tests.unit.test_mission_pop_forecast import route


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("timing", ["missing", "invalid", "missing_route"])
def test_bad_predeparture_timing_preserves_status_response(
    test_client, monkeypatch, enabled, timing
):
    untimed = route()
    untimed.timing_profile = None
    for point in untimed.points:
        point.expected_arrival_time = None if timing == "missing" else NOW
    leg = MissionLeg(
        id="leg",
        name="Fixture",
        route_id="r",
        transports=TransportConfig(
            initial_x_satellite_id="x", starshield_enabled=enabled
        ),
    )
    context = SimpleNamespace(leg=leg, parent_mission_id="m", route_id="r")
    monkeypatch.setattr(
        pop_status,
        "resolve_active_mission_leg_context",
        lambda manager: SimpleNamespace(context=context),
    )
    manager = SimpleNamespace(
        get_route=lambda id: (
            untimed if id == "r" and timing != "missing_route" else None
        )
    )
    service = PopStatusService(
        manager,
        lambda: SimulationConfig(mode="live"),
        observation_provider=lambda *args: known("b"),
    )
    monkeypatch.setattr(pop_status, "load_catalog", lambda path: CATALOG)
    monkeypatch.setattr(
        flight_state,
        "get_flight_state_manager",
        lambda: SimpleNamespace(get_status=lambda: FlightStatus()),
    )
    sample = telemetry()
    monkeypatch.setattr(
        status_api,
        "_coordinator",
        SimpleNamespace(get_current_telemetry=lambda: sample),
    )
    monkeypatch.setattr(status_api, "_pop_service", service)
    response = test_client.get("/api/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["pop_forecast"]["status"] == (
        "unavailable" if enabled else "disabled"
    )
    assert payload["pop_observation"]["entry"]["city"] == "b"
    assert payload["position"]["speed"] == 300
    assert payload["network"]["latency_ms"] == sample.network.latency_ms


@pytest.mark.parametrize("city", ["b", "unrelated suburb"])
def test_predeparture_egress_does_not_complete_or_mismatch_planned_crossing(city):
    service = PopStatusService(observation_provider=lambda *args: known(city))
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
    crossing = payload["pop_forecast"]["transitions"][0]["crossing"]
    assert (crossing["from_pop_id"], crossing["to_pop_id"]) == ("a", "b")
    assert not service.state.completed_ids
    assert payload["pop_advisories"] == []
    assert payload["pop_observation"]["entry"]["city"] == city


def test_disabled_predeparture_never_requires_planned_timing(monkeypatch):
    def forbidden(route):
        pytest.fail("Disabled PoP predictions must not derive route timing")

    monkeypatch.setattr(pop_status, "derive_mission_window", forbidden)
    payload = PopStatusService().snapshot(
        telemetry(),
        route=route(),
        catalog=CATALOG,
        enabled=False,
        mode="live",
        now=NOW,
        flight_phase="pre_departure",
    )
    assert payload["pop_forecast"]["status"] == "disabled"
