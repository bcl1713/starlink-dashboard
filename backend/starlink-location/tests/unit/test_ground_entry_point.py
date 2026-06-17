"""Tests for ground entry point discovery and metric formatting."""

from __future__ import annotations

from prometheus_client import generate_latest

from app.core.metrics import REGISTRY
from app.services import ground_entry_point as gep
from app.services.ground_entry_point import (
    GroundEntryPoint,
    GroundEntryPointResolver,
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


def test_refresh_ground_entry_point_metrics_replaces_labels(monkeypatch) -> None:
    entries = iter(
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

    monkeypatch.setattr(gep._resolver, "refresh", lambda force=False: next(entries))

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

    def fake_refresh(
        now_monotonic: float | None = None,
        force: bool = False,
    ) -> GroundEntryPoint:
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
        refresh_interval_seconds=1.0,
        now_monotonic=100.0,
    )
    maybe_refresh_ground_entry_point_metrics(
        refresh_interval_seconds=1.0,
        now_monotonic=100.5,
    )
    maybe_refresh_ground_entry_point_metrics(
        refresh_interval_seconds=1.0,
        now_monotonic=101.0,
    )

    assert refresh_times == [100.0, 101.0]


def test_maybe_refresh_ground_entry_point_metrics_falls_back_from_nan_interval(
    monkeypatch,
) -> None:
    refresh_times: list[float] = []

    def fake_refresh(
        now_monotonic: float | None = None,
        force: bool = False,
    ) -> GroundEntryPoint:
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
        now_monotonic=100.5,
    )
    maybe_refresh_ground_entry_point_metrics(
        refresh_interval_seconds=float("nan"),
        now_monotonic=101.0,
    )

    assert refresh_times == [100.0, 101.0]


def test_resolver_suppresses_dns_polling_until_interval_elapses() -> None:
    now = 10.0
    resolve_calls: list[float] = []

    def resolve_ip() -> str:
        resolve_calls.append(now)
        return "203.0.113.10"

    def geolocate_ip(ip: str) -> GroundEntryPoint:
        return GroundEntryPoint(
            ip=ip,
            city="Omaha",
            country="US",
            latitude=41.2565,
            longitude=-95.9345,
        )

    resolver = GroundEntryPointResolver(
        ip_resolver=resolve_ip,
        geolocator=geolocate_ip,
        poll_interval_seconds=1.0,
        time_source=lambda: now,
    )

    first = resolver.refresh()
    now = 10.5
    second = resolver.refresh()
    now = 11.0
    third = resolver.refresh()

    assert first is not None
    assert second is first
    assert third is first
    assert resolve_calls == [10.0, 11.0]


def test_resolver_geolocates_only_when_public_ip_changes() -> None:
    resolved_ips = iter(["203.0.113.10", "203.0.113.10", "198.51.100.24"])
    geolocate_calls: list[str] = []

    def resolve_ip() -> str:
        return next(resolved_ips)

    def geolocate_ip(ip: str) -> GroundEntryPoint:
        geolocate_calls.append(ip)
        if ip == "203.0.113.10":
            return GroundEntryPoint(
                ip=ip,
                city="Omaha",
                country="US",
                latitude=41.2565,
                longitude=-95.9345,
            )
        return GroundEntryPoint(
            ip=ip,
            city="Dallas",
            country="US",
            latitude=32.7767,
            longitude=-96.797,
        )

    resolver = GroundEntryPointResolver(
        ip_resolver=resolve_ip,
        geolocator=geolocate_ip,
        poll_interval_seconds=0.0,
    )

    first = resolver.refresh()
    second = resolver.refresh()
    third = resolver.refresh()

    assert first is not None
    assert second is first
    assert third is not None
    assert third.ip == "198.51.100.24"
    assert geolocate_calls == ["203.0.113.10", "198.51.100.24"]


def test_resolver_reuses_cached_geolocation_when_prior_ip_returns() -> None:
    resolved_ips = iter(["203.0.113.10", "198.51.100.24", "203.0.113.10"])
    geolocate_calls: list[str] = []

    def resolve_ip() -> str:
        return next(resolved_ips)

    def geolocate_ip(ip: str) -> GroundEntryPoint:
        geolocate_calls.append(ip)
        city = "Omaha" if ip == "203.0.113.10" else "Dallas"
        latitude = 41.2565 if ip == "203.0.113.10" else 32.7767
        longitude = -95.9345 if ip == "203.0.113.10" else -96.797
        return GroundEntryPoint(
            ip=ip,
            city=city,
            country="US",
            latitude=latitude,
            longitude=longitude,
        )

    resolver = GroundEntryPointResolver(
        ip_resolver=resolve_ip,
        geolocator=geolocate_ip,
        poll_interval_seconds=0.0,
    )

    first = resolver.refresh()
    second = resolver.refresh()
    third = resolver.refresh()

    assert first is not None
    assert second is not None
    assert third is first
    assert geolocate_calls == ["203.0.113.10", "198.51.100.24"]
