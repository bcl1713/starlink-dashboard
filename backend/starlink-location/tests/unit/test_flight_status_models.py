"""Unit tests for flight status models."""

from datetime import datetime, timedelta, timezone

from app.models.flight_status import (
    ETAMode,
    FlightPhase,
    FlightStatus,
    FlightStatusResponse,
)


def test_flight_status_defaults():
    """Verify FlightStatus default values match PRE_DEPARTURE semantics."""
    status = FlightStatus()

    assert status.phase == FlightPhase.PRE_DEPARTURE
    assert status.eta_mode == ETAMode.ANTICIPATED
    assert status.active_route_id is None
    assert status.has_timing_data is False
    assert status.scheduled_departure_time is None
    assert status.departure_time is None
    assert status.time_until_departure_seconds is None
    assert status.time_since_departure_seconds is None


def test_flight_status_with_custom_metadata():
    """Ensure FlightStatus accepts full metadata when provided."""
    departure = datetime(2025, 10, 27, 16, 45, tzinfo=timezone.utc)
    arrival = datetime(2025, 10, 28, 2, 5, tzinfo=timezone.utc)

    status = FlightStatus(
        phase=FlightPhase.IN_FLIGHT,
        eta_mode=ETAMode.ESTIMATED,
        active_route_id="leg-1",
        active_route_name="Leg 1",
        has_timing_data=True,
        scheduled_departure_time=departure,
        scheduled_arrival_time=arrival,
        departure_time=departure + timedelta(minutes=5),
        arrival_time=None,
        speed_persistence_seconds=12.0,
    )

    assert status.phase == FlightPhase.IN_FLIGHT
    assert status.eta_mode == ETAMode.ESTIMATED
    assert status.active_route_id == "leg-1"
    assert status.has_timing_data is True
    assert status.departure_time == departure + timedelta(minutes=5)
    assert status.arrival_time is None

    serialized = status.model_dump(mode="json")
    assert serialized["phase"] == "in_flight"
    assert serialized["eta_mode"] == "estimated"
    assert serialized["scheduled_departure_time"] == "2025-10-27T16:45:00Z"
    assert serialized["departure_time"] == "2025-10-27T16:50:00Z"
    assert serialized["time_until_departure_seconds"] is None


def test_flight_status_response_timestamp_auto_populates():
    """FlightStatusResponse should generate a timestamp when omitted."""
    before = datetime.now(timezone.utc)
    response = FlightStatusResponse(
        phase=FlightPhase.PRE_DEPARTURE,
        eta_mode=ETAMode.ANTICIPATED,
        active_route_id=None,
        time_until_departure_seconds=600.0,
    )
    after = datetime.now(timezone.utc)

    assert isinstance(response.timestamp, datetime)
    assert before <= response.timestamp <= after
    assert response.time_since_departure_seconds is None

    json_payload = response.model_dump(mode="json")
    assert json_payload["phase"] == "pre_departure"
    assert json_payload["eta_mode"] == "anticipated"
    assert json_payload["time_until_departure_seconds"] == 600.0


def test_flight_status_response_allows_optional_fields():
    """Optional fields should accept None without validation errors."""
    response = FlightStatusResponse(
        phase=FlightPhase.POST_ARRIVAL,
        eta_mode=ETAMode.ESTIMATED,
        active_route_id="leg-1",
        active_route_name="Leg 1",
        has_timing_data=True,
        scheduled_departure_time=None,
        scheduled_arrival_time=None,
        departure_time=None,
        arrival_time=None,
        time_until_departure_seconds=0.0,
        time_since_departure_seconds=3600.0,
    )

    assert response.phase == FlightPhase.POST_ARRIVAL
    assert response.eta_mode == ETAMode.ESTIMATED
    assert response.time_since_departure_seconds == 3600.0
