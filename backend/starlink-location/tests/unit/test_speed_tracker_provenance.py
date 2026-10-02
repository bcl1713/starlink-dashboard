"""Measured zero requires a collected interval; reset and gaps lose provenance."""

from app.services.speed_tracker import SpeedTracker


def test_speed_warmup_reset_and_expired_window():
    tracker = SpeedTracker(smoothing_duration_seconds=2)
    assert tracker.update(40, -73, timestamp=100) == 0
    assert not tracker.has_observation()
    assert tracker.update(40, -73, timestamp=100) == 0
    assert not tracker.has_observation()
    assert tracker.update(40, -73, timestamp=101) == 0
    assert tracker.has_observation()
    tracker.update(40, -72.99, timestamp=102)
    assert tracker.get_last_speed() > 0
    # An expired GPS interval cannot renew speed provenance with one sample.
    tracker.update(40, -72.99, timestamp=110)
    assert not tracker.has_observation()
    tracker.update(40, -72.99, timestamp=111)
    assert tracker.has_observation()
    assert tracker.get_last_speed() == 0
    tracker.reset()
    assert not tracker.has_observation()
