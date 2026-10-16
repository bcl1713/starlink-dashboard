"""Real live adapter regression for arrival away from an exact route waypoint."""

from app.services.flight_events.live_adapter import FlightEventRuntime
from app.services.flight_events.store import FlightEventStore
from tests.unit.test_flight_events import observation


def test_live_arrival_away_from_endpoint(tmp_path):
    runtime = FlightEventRuntime(tmp_path)
    for second in range(301):
        runtime.accept(observation(second))
    for second in range(301, 321):
        runtime.accept(observation(second, speed=10))
    for second in range(321, 351):
        runtime.accept(observation(second, speed=120, altitude=500))
    for second in range(351, 361):
        runtime.accept(observation(second, speed=200, altitude=10000))
    for second in range(361, 401):
        runtime.accept(observation(second, speed=25, altitude=100, distance=1000))
    for second in range(401, 710):
        runtime.accept(observation(second, distance=1000))
    status = runtime.status("m", "l")
    assert status["movement_state"] == "parked"
    assert status["on_blocks_at"] is not None
    assert status["movement_uncertain"] is False
    assert FlightEventStore(tmp_path / "events.db").state("m", "l").destination_complete
