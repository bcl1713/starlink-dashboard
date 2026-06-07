"""Tests for ground entry point discovery and metric formatting."""

from __future__ import annotations

from prometheus_client import generate_latest

from app.core.metrics import REGISTRY
from app.services import ground_entry_point as gep
from app.services.ground_entry_point import (
    GroundEntryPoint,
    maybe_refresh_ground_entry_point_metrics,
    publish_ground_entry_point_metrics,
    refresh_ground_entry_point_metrics,
)


def setup_function() -> None:
    gep.invalidate_cached_ground_entry_point()
    gep.clear_ground_entry_point_metrics()
    gep._last_ground_entry_point_refresh_monotonic = None


def test_publish_ground_entry_point_metrics_exposes_location_and_info_labels() -> None:
    entry_point = GroundEntryPoint(
        ip="203.0.113.10",
        city="Omaha",
        country="US",
        latitude=41.2565,
        longitude=-95.9345,
    )

    publish_ground_entry_point_metrics(entry_point)

    output = generate_latest(REGISTRY).decode("utf-8")
    assert "starlink_ground_entry_point_location" in output
    assert 'city="Omaha"' in output
    assert 'country="US"' in output
    assert 'ip="203.0.113.10"' in output
    assert 'lat="41.2565"' in output
    assert 'lon="-95.9345"' in output
    assert "starlink_ground_entry_point_latitude_degrees 41.2565" in output
    assert "starlink_ground_entry_point_longitude_degrees -95.9345" in output


def test_refresh_ground_entry_point_metrics_invalidates_cache_and_replaces_labels(
    monkeypatch,
) -> None:
    discoveries = iter(
        [
            GroundEntryPoint(
                ip="203.0.113.10",
                city="Omaha",
                country="US",
                latitude=41.2565,
                longitude=-95.9345,
            ),
            GroundEntryPoint(
                ip="198.51.100.20",
                city="Tokyo",
                country="JP",
                latitude=35.6764,
                longitude=139.65,
            ),
        ]
    )

    monkeypatch.setattr(
        gep,
        "discover_ground_entry_point",
        lambda timeout_seconds=5.0: next(discoveries),
    )

    first = refresh_ground_entry_point_metrics(now_monotonic=10.0)
    second = refresh_ground_entry_point_metrics(now_monotonic=20.0)

    assert first is not None
    assert second is not None
    assert first.city == "Omaha"
    assert second.city == "Tokyo"

    output = generate_latest(REGISTRY).decode("utf-8")
    assert 'city="Tokyo"' in output
    assert 'country="JP"' in output
    assert 'ip="198.51.100.20"' in output
    assert "starlink_ground_entry_point_latitude_degrees 35.6764" in output
    assert "starlink_ground_entry_point_longitude_degrees 139.65" in output
    assert 'city="Omaha"' not in output
    assert 'ip="203.0.113.10"' not in output


def test_maybe_refresh_ground_entry_point_metrics_honors_refresh_interval(
    monkeypatch,
) -> None:
    refresh_times: list[float] = []

    def fake_refresh(now_monotonic: float | None = None) -> GroundEntryPoint:
        refresh_times.append(-1.0 if now_monotonic is None else now_monotonic)
        gep._last_ground_entry_point_refresh_monotonic = now_monotonic
        return GroundEntryPoint(
            ip="203.0.113.10",
            city="Omaha",
            country="US",
            latitude=41.2565,
            longitude=-95.9345,
        )

    monkeypatch.setattr(gep, "refresh_ground_entry_point_metrics", fake_refresh)
    monkeypatch.setattr(
        gep,
        "get_cached_ground_entry_point",
        lambda: GroundEntryPoint(
            ip="203.0.113.10",
            city="Omaha",
            country="US",
            latitude=41.2565,
            longitude=-95.9345,
        ),
    )

    maybe_refresh_ground_entry_point_metrics(
        refresh_interval_seconds=300.0,
        now_monotonic=100.0,
    )
    maybe_refresh_ground_entry_point_metrics(
        refresh_interval_seconds=300.0,
        now_monotonic=200.0,
    )
    maybe_refresh_ground_entry_point_metrics(
        refresh_interval_seconds=300.0,
        now_monotonic=401.0,
    )

    assert refresh_times == [100.0, 401.0]


def test_maybe_refresh_ground_entry_point_metrics_falls_back_from_nan_interval(
    monkeypatch,
) -> None:
    refresh_times: list[float] = []

    def fake_refresh(now_monotonic: float | None = None) -> GroundEntryPoint:
        refresh_times.append(-1.0 if now_monotonic is None else now_monotonic)
        gep._last_ground_entry_point_refresh_monotonic = now_monotonic
        return GroundEntryPoint(
            ip="203.0.113.10",
            city="Omaha",
            country="US",
            latitude=41.2565,
            longitude=-95.9345,
        )

    monkeypatch.setattr(gep, "refresh_ground_entry_point_metrics", fake_refresh)
    monkeypatch.setattr(
        gep,
        "get_cached_ground_entry_point",
        lambda: GroundEntryPoint(
            ip="203.0.113.10",
            city="Omaha",
            country="US",
            latitude=41.2565,
            longitude=-95.9345,
        ),
    )

    maybe_refresh_ground_entry_point_metrics(
        refresh_interval_seconds=float("nan"),
        now_monotonic=100.0,
    )
    maybe_refresh_ground_entry_point_metrics(
        refresh_interval_seconds=float("nan"),
        now_monotonic=401.0,
    )

    assert refresh_times == [100.0, 401.0]
