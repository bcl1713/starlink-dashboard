"""Unit tests for ETACache and ETAHistoryTracker."""

from datetime import datetime, timedelta, timezone

import pytest

from app.services.eta_cache import ETACache, ETAHistoryTracker


def _cache_key_args():
    """Helper returning consistent key args."""
    return (
        "route-123",
        40.12345,
        -73.98765,
        40.54321,
        -74.12345,
        152.34,
    )


def test_cache_hit_and_expiration(monkeypatch):
    """Cache should return stored value until TTL expires."""
    base_time = 1_700_000_000.0
    monkeypatch.setattr("app.services.eta_cache.time.time", lambda: base_time)
    cache = ETACache(ttl_seconds=0.5)

    cache.set(*_cache_key_args(), value={"eta_seconds": 123})
    assert cache.get(*_cache_key_args()) == {"eta_seconds": 123}

    # Advance beyond TTL to force eviction on next access.
    monkeypatch.setattr("app.services.eta_cache.time.time", lambda: base_time + 0.6)
    assert cache.get(*_cache_key_args()) is None


def test_cache_key_rounding():
    """Coordinates close within rounding precision should reuse the same cache entry."""
    cache = ETACache(ttl_seconds=5)
    args = ("route-xyz", 40.121, -73.989, 40.551, -74.111, 150.0)
    cache.set(*args, value={"eta": 10})

    # Adjust lat/lon/speed within rounding tolerance (0.01 for coords, 0.1 for speed)
    adjusted_args = (
        "route-xyz",
        40.124,   # rounds to 40.12
        -73.986,  # rounds to -73.99
        40.547,   # rounds to 40.55
        -74.114,  # rounds to -74.11
        150.04,   # rounds to 150.0
    )
    assert cache.get(*adjusted_args) == {"eta": 10}


def test_cleanup_and_stats(monkeypatch):
    """Expired entries should be removed by cleanup and reflected in stats."""
    base_time = 1_700_000_000.0
    monkeypatch.setattr("app.services.eta_cache.time.time", lambda: base_time)
    cache = ETACache(ttl_seconds=1.0)

    cache.set(*_cache_key_args(), value={"eta": 1})
    # Advance time slightly before storing the second entry so it is newer.
    monkeypatch.setattr("app.services.eta_cache.time.time", lambda: base_time + 0.25)
    cache.set("route-999", 10.0, 20.0, 11.0, 21.0, 120.0, {"eta": 2})

    # Advance time so first entry expires while second stays valid.
    monkeypatch.setattr("app.services.eta_cache.time.time", lambda: base_time + 1.2)
    removed = cache.cleanup_expired()
    assert removed == 1
    assert cache.stats()["cached_entries"] == 1


def test_eta_history_tracks_accuracy():
    """ETAHistoryTracker should compute accuracy metrics after recording arrival."""
    tracker = ETAHistoryTracker(max_history=3)

    prediction_time = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    tracker.record_prediction(
        waypoint_id="wp-1",
        predicted_eta_seconds=300,
        current_position=(40.0, -74.0),
        current_speed=150.0,
        timestamp=prediction_time,
    )
    tracker.record_prediction(
        waypoint_id="wp-2",
        predicted_eta_seconds=120,
        current_position=(41.0, -75.0),
        current_speed=140.0,
        timestamp=prediction_time,
    )

    # Arrival 60 seconds later than predicted for wp-1, exact for wp-2.
    tracker.record_arrival("wp-1", prediction_time + timedelta(seconds=360))
    tracker.record_arrival("wp-2", prediction_time + timedelta(seconds=120))

    stats = tracker.get_accuracy_stats()
    assert stats["total_predictions"] == 2
    assert stats["completed_arrivals"] == 2
    # Average of +60s error and 0s error -> 30s.
    assert pytest.approx(stats["average_error_seconds"], rel=1e-3) == 30.0
    assert stats["max_error_seconds"] == 60.0
    assert stats["min_error_seconds"] == 0.0
    assert pytest.approx(stats["accuracy_percentage"], rel=1e-6) == 100.0


def test_eta_history_respects_max_history():
    """History tracker keeps only the most recent records."""
    tracker = ETAHistoryTracker(max_history=2)
    tracker.record_prediction("a", 10, (0, 0), 100.0)
    tracker.record_prediction("b", 20, (0, 0), 100.0)
    tracker.record_prediction("c", 30, (0, 0), 100.0)

    assert len(tracker._history) == 2
    assert tracker._history[0]["waypoint_id"] == "b"
    assert tracker._history[1]["waypoint_id"] == "c"
