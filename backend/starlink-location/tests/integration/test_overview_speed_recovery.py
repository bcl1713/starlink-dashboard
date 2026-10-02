"""Exercise actual live speed tracking through the Overview ETA endpoint."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import starlink_grpc

from app.live.coordinator import LiveCoordinator
from app.mission.dependencies import get_poi_manager
from app.models.config import SimulationConfig
from tests.conftest import default_mock_telemetry
from tests.integration.test_overview_upcoming_pois_api import (
    NOW,
    arrange_active_v2_context,
    scheduled_poi,
)


@pytest.mark.parametrize("recovery", ["restart", "gps_loss", "rpc_loss"])
@pytest.mark.parametrize("moving", [False, True])
def test_eta_waits_for_measured_speed_after_recovery(
    client, monkeypatch, recovery, moving
):
    clock = [NOW]
    monkeypatch.setattr("app.api.overview_upcoming_pois._utc_now", lambda: clock[0])
    monkeypatch.setattr(
        "app.live.coordinator.datetime", SimpleNamespace(now=lambda tz: clock[0])
    )
    monkeypatch.setattr(
        "app.api.overview_upcoming_pois.get_flight_state_manager",
        lambda: SimpleNamespace(
            get_status=lambda: SimpleNamespace(phase=SimpleNamespace(value="in_flight"))
        ),
    )
    dish = MagicMock()
    dish.connect.return_value = False
    monkeypatch.setattr("app.live.coordinator.StarlinkClient", lambda **kwargs: dish)
    coordinator = LiveCoordinator(SimulationConfig())
    arrange_active_v2_context(client)
    client.app.dependency_overrides[get_poi_manager] = lambda: SimpleNamespace(
        list_pois=lambda mission_id=None: [scheduled_poi()]
    )
    client.app.state.coordinator = coordinator

    def collect(longitude=-73):
        telemetry = default_mock_telemetry()
        telemetry.position.latitude = 40
        telemetry.position.longitude = longitude
        telemetry.position.observed_at = clock[0]
        dish.get_telemetry.return_value = telemetry
        return coordinator.update()

    try:
        if recovery != "restart":
            collect()
            clock[0] += timedelta(seconds=1)
            assert collect(-72.99).position.speed_observed_at is not None
            clock[0] += timedelta(seconds=1)
            if recovery == "gps_loss":
                missing = default_mock_telemetry()
                missing.position.observed_at = None
                dish.get_telemetry.return_value = missing
                coordinator.update()
            else:
                dish.get_telemetry.side_effect = starlink_grpc.GrpcError(
                    "GPS disconnected"
                )
                assert coordinator.update() is None
                dish.get_telemetry.side_effect = None
            clock[0] += timedelta(seconds=1)

        first = collect()
        assert first.position.speed == 0
        assert first.position.speed_observed_at is None
        payload = client.get("/api/overview/upcoming-pois").json()
        assert payload["position_state"] == "fresh"
        assert payload["state"] == "unavailable"
        assert payload["pois"][0]["map_retained"] is True
        assert payload["pois"][0]["estimated_arrival_time"] is None

        # Duplicate timestamps cannot establish speed; a new collected interval can.
        assert collect().position.speed_observed_at is None
        clock[0] += timedelta(seconds=1)
        measured = collect(-72.99 if moving else -73)
        assert measured.position.speed_observed_at == clock[0]
        assert (measured.position.speed > 0) == moving
        payload = client.get("/api/overview/upcoming-pois").json()
        assert payload["state"] == "available"
        assert payload["pois"][0]["eta_seconds"] > 0
    finally:
        client.app.dependency_overrides.clear()
        del client.app.state.coordinator
