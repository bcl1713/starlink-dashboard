"""Evidence contracts must reject invented altitude provenance."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.services.flight_events.models import FlightObservation, FlightEvent


def test_altitude_requires_own_freshness():
    now = datetime.now(timezone.utc)
    sample = FlightObservation(observed_at=now, position_observed_at=now,
        speed_observed_at=now, latitude=40, longitude=-70, speed_knots=100,
        altitude_feet=1000, altitude_usable=True, source_mode="live",
        mission_id="mission", leg_id="leg", route_id="route")
    assert not sample.usable_altitude


def test_events_require_aware_times():
    with pytest.raises(ValidationError):
        FlightEvent(kind="takeoff", occurred_at=datetime(2026, 1, 1),
                    detected_at=datetime.now(timezone.utc), source="manual",
                    mission_id="mission", leg_id="leg")
