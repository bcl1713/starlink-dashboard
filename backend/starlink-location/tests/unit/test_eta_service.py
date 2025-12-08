"""Unit tests for the ETA service singleton helpers."""

from __future__ import annotations

import pytest

from app.core import eta_service
from app.services.eta_calculator import ETACalculator
from app.models.flight_status import ETAMode


@pytest.fixture(autouse=True)
def reset_eta_service_globals():
    """Ensure eta_service globals are reset between tests."""
    eta_service._eta_calculator = None
    eta_service._poi_manager = None
    yield
    eta_service._eta_calculator = None
    eta_service._poi_manager = None


class DummyPOIManager:
    def __init__(self, pois=None):
        self._pois = pois or []
        self.list_calls = 0

    def list_pois(self):
        self.list_calls += 1
        return list(self._pois)


class DummyETACalculator:
    def __init__(self):
        self.speed_updates: list[float] = []
        self.last_call_args = None

    def update_speed(self, speed_knots: float) -> None:
        self.speed_updates.append(speed_knots)

    def calculate_poi_metrics(
        self,
        latitude,
        longitude,
        pois,
        speed_knots,
        *,
        active_route=None,
        eta_mode=None,
        flight_phase=None,
    ):
        self.last_call_args = {
            "latitude": latitude,
            "longitude": longitude,
            "pois": pois,
            "speed_knots": speed_knots,
            "active_route": active_route,
            "eta_mode": eta_mode,
            "flight_phase": flight_phase,
        }
        return {"dummy": {"eta_seconds": 42, "distance_meters": 1000}}


def test_initialize_eta_service_uses_provided_manager():
    manager = DummyPOIManager()
    eta_service.initialize_eta_service(manager)

    calc = eta_service.get_eta_calculator()
    assert isinstance(calc, ETACalculator)
    assert calc.smoothing_duration_seconds == 120.0

    assert eta_service.get_poi_manager() is manager


def test_getters_raise_when_uninitialized():
    with pytest.raises(RuntimeError):
        eta_service.get_eta_calculator()
    with pytest.raises(RuntimeError):
        eta_service.get_poi_manager()


def test_initialize_eta_service_logs_and_raises_on_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    class BoomManager:
        def __init__(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(eta_service, "POIManager", BoomManager)

    with pytest.raises(RuntimeError):
        eta_service.initialize_eta_service()


def test_update_eta_metrics_uses_defaults_and_returns_calculator_output():
    dummy_calc = DummyETACalculator()
    dummy_manager = DummyPOIManager(pois=["poi-a"])
    eta_service._eta_calculator = dummy_calc
    eta_service._poi_manager = dummy_manager

    result = eta_service.update_eta_metrics(
        latitude=40.0,
        longitude=-73.0,
        speed_knots=180.0,
        active_route="route-obj",
        eta_mode=None,
        flight_phase="pre_departure",
    )

    assert result == {"dummy": {"eta_seconds": 42, "distance_meters": 1000}}
    assert dummy_calc.speed_updates == [180.0]
    assert dummy_calc.last_call_args["eta_mode"] == ETAMode.ESTIMATED
    assert dummy_calc.last_call_args["active_route"] == "route-obj"
    assert dummy_manager.list_calls == 1


def test_update_eta_metrics_handles_exceptions(monkeypatch: pytest.MonkeyPatch):
    def boom():
        raise RuntimeError("not initialized")

    monkeypatch.setattr(eta_service, "get_eta_calculator", boom)
    # Ensure POI manager call is not attempted when calculator fetch fails
    monkeypatch.setattr(eta_service, "get_poi_manager", boom)

    result = eta_service.update_eta_metrics(0.0, 0.0, 0.0)
    assert result == {}


def test_shutdown_eta_service_clears_singletons():
    eta_service._eta_calculator = DummyETACalculator()
    eta_service._poi_manager = DummyPOIManager()

    eta_service.shutdown_eta_service()

    with pytest.raises(RuntimeError):
        eta_service.get_eta_calculator()
    with pytest.raises(RuntimeError):
        eta_service.get_poi_manager()


def test_get_nearest_poi_metrics_returns_none_when_initialized():
    eta_service._eta_calculator = DummyETACalculator()
    assert eta_service.get_nearest_poi_metrics() is None


def test_get_nearest_poi_metrics_handles_exception(monkeypatch: pytest.MonkeyPatch):
    def boom():
        raise RuntimeError("no calc")

    monkeypatch.setattr(eta_service, "get_eta_calculator", boom)
    assert eta_service.get_nearest_poi_metrics() is None
