"""Tests for ground entry point discovery and metric formatting."""

from __future__ import annotations

from datetime import datetime, timezone

from prometheus_client import generate_latest
from typing_extensions import Self

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


def test_extract_cloudflare_trace_ipv4_reads_valid_ip_line() -> None:
    trace_body = """fl=123f45
h=1.1.1.1
ip=203.0.113.10
ts=1781950000.123
"""

    assert gep._extract_cloudflare_trace_ipv4(trace_body) == "203.0.113.10"


def test_extract_cloudflare_trace_ipv4_rejects_missing_or_non_ipv4_values() -> None:
    assert gep._extract_cloudflare_trace_ipv4("h=1.1.1.1\nloc=US\n") is None
    assert gep._extract_cloudflare_trace_ipv4("ip=2001:db8::1\n") is None
    assert gep._extract_cloudflare_trace_ipv4("ip=999.0.0.1\n") is None


def test_resolve_public_ip_prefers_cloudflare_trace(monkeypatch) -> None:
    lookup_timeouts: list[float] = []

    def trace_lookup(timeout_seconds: float) -> str:
        lookup_timeouts.append(timeout_seconds)
        return "203.0.113.10"

    def dns_lookup(timeout_seconds: float) -> str:  # pragma: no cover - must not run
        raise AssertionError("OpenDNS fallback should not run after trace succeeds")

    monkeypatch.setattr(gep, "resolve_public_ip_via_cloudflare_trace", trace_lookup)
    monkeypatch.setattr(gep, "resolve_public_ip_via_dns", dns_lookup)

    assert gep.resolve_public_ip(timeout_seconds=1.5) == "203.0.113.10"
    assert lookup_timeouts == [1.5]


def test_resolve_public_ip_falls_back_to_dns_when_trace_has_no_ipv4(
    monkeypatch,
) -> None:
    lookup_order: list[str] = []

    def trace_lookup(timeout_seconds: float) -> None:
        lookup_order.append(f"trace:{timeout_seconds}")

    def dns_lookup(timeout_seconds: float) -> str:
        lookup_order.append(f"dns:{timeout_seconds}")
        return "198.51.100.24"

    monkeypatch.setattr(gep, "resolve_public_ip_via_cloudflare_trace", trace_lookup)
    monkeypatch.setattr(gep, "resolve_public_ip_via_dns", dns_lookup)

    assert gep.resolve_public_ip(timeout_seconds=1.25) == "198.51.100.24"
    assert lookup_order == ["trace:1.25", "dns:1.25"]


def test_resolve_public_ip_returns_none_when_all_sources_fail(monkeypatch) -> None:
    def trace_lookup(timeout_seconds: float) -> None:
        raise RuntimeError("trace unavailable")

    def dns_lookup(timeout_seconds: float) -> None:
        raise RuntimeError("dns unavailable")

    monkeypatch.setattr(gep, "resolve_public_ip_via_cloudflare_trace", trace_lookup)
    monkeypatch.setattr(gep, "resolve_public_ip_via_dns", dns_lookup)

    assert gep.resolve_public_ip() is None


def test_publish_ground_entry_point_metrics_exposes_location_and_info_labels() -> None:
    entry_point = GroundEntryPoint(
        ip="203.0.113.10",
        city="Omaha",
        region="Nebraska",
        country="US",
        latitude=41.2565,
        longitude=-95.9345,
    )

    publish_ground_entry_point_metrics(entry_point)

    output = generate_latest(REGISTRY).decode("utf-8")
    assert "starlink_ground_entry_point_location" in output
    assert 'city="Omaha"' in output
    assert 'region="Nebraska"' in output
    assert 'country="US"' in output
    assert 'display="Omaha, Nebraska"' in output
    assert 'ip="203.0.113.10"' in output
    assert 'lat="41.2565"' in output
    assert 'lon="-95.9345"' in output
    assert "starlink_ground_entry_point_latitude_degrees 41.2565" in output
    assert "starlink_ground_entry_point_longitude_degrees -95.9345" in output


def test_ground_entry_point_label_formats_us_with_region() -> None:
    entry_point = GroundEntryPoint(
        ip="203.0.113.10",
        city="Omaha",
        region="Nebraska",
        country="US",
        latitude=41.2565,
        longitude=-95.9345,
    )

    assert entry_point.label == "Omaha, Nebraska"


def test_ground_entry_point_label_formats_non_us_with_country() -> None:
    entry_point = GroundEntryPoint(
        ip="198.51.100.24",
        city="Tokyo",
        region="Tokyo",
        country="JP",
        latitude=35.6764,
        longitude=139.65,
    )

    assert entry_point.label == "Tokyo, JP"


def test_ground_entry_point_label_omits_empty_and_placeholder_parts() -> None:
    assert (
        GroundEntryPoint(
            ip="203.0.113.10",
            city=" unknown ",
            region="Nebraska",
            country="US",
            latitude=41.2565,
            longitude=-95.9345,
        ).label
        == "Nebraska"
    )
    assert (
        GroundEntryPoint(
            ip="198.51.100.24",
            city="",
            region="None",
            country="JP",
            latitude=35.6764,
            longitude=139.65,
        ).label
        == "JP"
    )
    assert (
        GroundEntryPoint(
            ip="198.51.100.25",
            city="null",
            region="unknown",
            country="n/a",
            latitude=0.0,
            longitude=0.0,
        ).label
        == "Ground Entry Point"
    )


def test_geolocate_public_ip_parses_ipinfo_region(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {
                "ip": "203.0.113.10",
                "city": "Omaha",
                "region": "Nebraska",
                "country": "US",
                "loc": "41.2565,-95.9345",
            }

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, url: str) -> FakeResponse:
            assert url == "https://ipinfo.io/203.0.113.10/json"
            return FakeResponse()

    monkeypatch.setattr(gep.httpx, "Client", FakeClient)

    entry_point = gep.geolocate_public_ip("203.0.113.10")

    assert entry_point is not None
    assert entry_point.region == "Nebraska"
    assert entry_point.label == "Omaha, Nebraska"


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
    assert third is not None
    assert third is not first
    assert third.observed_at is not None
    assert first.observed_at is not None
    assert third.observed_at >= first.observed_at
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
    assert second is not None
    assert second is not first
    assert second.observed_at is not None
    assert first.observed_at is not None
    assert second.observed_at >= first.observed_at
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
    assert third is not None
    assert first.ip == third.ip
    assert third.city == "Omaha"
    assert geolocate_calls == ["203.0.113.10", "198.51.100.24"]


def test_same_ip_successful_revalidation_advances_observed_at_without_regeolocating() -> (
    None
):
    observed_times = iter(
        [
            datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 8, 29, 12, 1, tzinfo=timezone.utc),
        ]
    )
    geolocate_calls: list[str] = []
    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: "203.0.113.10",
        geolocator=lambda ip: (
            geolocate_calls.append(ip)
            or GroundEntryPoint(
                ip=ip,
                city="Omaha",
                country="US",
                latitude=41.2565,
                longitude=-95.9345,
            )
        ),
        poll_interval_seconds=0.0,
        clock=lambda: next(observed_times),
    )

    first = resolver.refresh()
    second = resolver.refresh()

    assert first is not None
    assert second is not None
    assert second.city == first.city
    assert second.latitude == first.latitude
    assert second.observed_at == datetime(2026, 8, 29, 12, 1, tzinfo=timezone.utc)
    assert geolocate_calls == ["203.0.113.10"]


def test_failed_same_ip_revalidation_retains_prior_observation_without_freshening() -> (
    None
):
    observed = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    calls = 0

    def resolve_ip() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            return "203.0.113.10"
        raise TimeoutError("resolver unavailable")

    resolver = GroundEntryPointResolver(
        ip_resolver=resolve_ip,
        geolocator=lambda ip: GroundEntryPoint(
            ip=ip,
            city="Omaha",
            country="US",
            latitude=41.2565,
            longitude=-95.9345,
        ),
        poll_interval_seconds=0.0,
        clock=lambda: observed,
    )

    first = resolver.refresh()
    second = resolver.refresh()

    assert first is not None
    assert second is first
    assert second is not None
    assert second.observed_at == observed


def test_configured_ground_entry_point_success_gets_current_observation(
    monkeypatch,
) -> None:
    observed = datetime(2026, 8, 29, 12, 5, tzinfo=timezone.utc)
    monkeypatch.setenv("STARLINK_GROUND_ENTRY_LATITUDE", "41.2565")
    monkeypatch.setenv("STARLINK_GROUND_ENTRY_LONGITUDE", "-95.9345")
    monkeypatch.setenv("STARLINK_GROUND_ENTRY_CITY", "Omaha")
    monkeypatch.setenv("STARLINK_GROUND_ENTRY_COUNTRY", "US")

    resolver = GroundEntryPointResolver(clock=lambda: observed)

    entry = resolver.refresh(force=True)

    assert entry is not None
    assert entry.city == "Omaha"
    assert entry.observed_at == observed


def test_discover_configured_ground_entry_point_success_gets_observation(
    monkeypatch,
) -> None:
    monkeypatch.setenv("STARLINK_GROUND_ENTRY_LATITUDE", "41.2565")
    monkeypatch.setenv("STARLINK_GROUND_ENTRY_LONGITUDE", "-95.9345")
    monkeypatch.setenv("STARLINK_GROUND_ENTRY_CITY", "Omaha")
    monkeypatch.setenv("STARLINK_GROUND_ENTRY_COUNTRY", "US")

    entry = gep.discover_ground_entry_point()

    assert entry is not None
    assert entry.city == "Omaha"
    assert entry.observed_at is not None


def test_returning_prior_ip_gets_fresh_observation_without_geolocating_again() -> None:
    clocks = iter(
        [
            datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 8, 29, 12, 1, tzinfo=timezone.utc),
            datetime(2026, 8, 29, 12, 2, tzinfo=timezone.utc),
        ]
    )
    resolved_ips = iter(["203.0.113.10", "198.51.100.24", "203.0.113.10"])
    geolocate_calls: list[str] = []

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
        ip_resolver=lambda: next(resolved_ips),
        geolocator=geolocate_ip,
        poll_interval_seconds=0.0,
        clock=lambda: next(clocks),
    )

    first = resolver.refresh()
    second = resolver.refresh()
    third = resolver.refresh()

    assert first is not None
    assert second is not None
    assert third is not None
    assert first.observed_at == datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    assert second.observed_at == datetime(2026, 8, 29, 12, 1, tzinfo=timezone.utc)
    assert third.observed_at == datetime(2026, 8, 29, 12, 2, tzinfo=timezone.utc)
    assert third.ip == first.ip
    assert third is not first
    assert geolocate_calls == ["203.0.113.10", "198.51.100.24"]


def test_resolver_successful_discovery_sets_observed_at() -> None:
    observed = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)

    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: "203.0.113.10",
        geolocator=lambda ip: GroundEntryPoint(
            ip=ip,
            city="Omaha",
            region="Nebraska",
            country="US",
            latitude=41.2565,
            longitude=-95.9345,
        ),
        poll_interval_seconds=0.0,
        clock=lambda: observed,
    )

    entry = resolver.refresh(force=True)

    assert entry is not None
    assert entry.observed_at == observed


def test_cached_read_preserves_observed_at_without_refreshing_request_time() -> None:
    observed = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    now = observed
    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: "203.0.113.10",
        geolocator=lambda ip: GroundEntryPoint(
            ip=ip,
            city="Omaha",
            country="US",
            latitude=41.2565,
            longitude=-95.9345,
        ),
        poll_interval_seconds=60.0,
        time_source=lambda: now.timestamp(),
        clock=lambda: now,
    )

    first = resolver.refresh()
    now = datetime(2026, 8, 29, 12, 5, tzinfo=timezone.utc)
    cached = resolver.current()

    assert first is not None
    assert cached is first
    assert cached.observed_at == observed


def test_actual_refresh_updates_observed_at_when_public_ip_changes() -> None:
    observed_times = iter(
        [
            datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 8, 29, 12, 5, tzinfo=timezone.utc),
        ]
    )
    now = 0.0
    resolved_ips = iter(["203.0.113.10", "198.51.100.24"])
    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: next(resolved_ips),
        geolocator=lambda ip: GroundEntryPoint(
            ip=ip,
            city="Omaha" if ip == "203.0.113.10" else "Dallas",
            country="US",
            latitude=41.2565,
            longitude=-95.9345,
        ),
        poll_interval_seconds=0.0,
        time_source=lambda: now,
        clock=lambda: next(observed_times),
    )

    first = resolver.refresh()
    now = 1.0
    second = resolver.refresh()

    assert first is not None
    assert second is not None
    assert first.observed_at == datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    assert second.observed_at == datetime(2026, 8, 29, 12, 5, tzinfo=timezone.utc)


def test_invalidation_and_unavailable_state_do_not_stamp_stale_cache() -> None:
    observed = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: "203.0.113.10",
        geolocator=lambda ip: GroundEntryPoint(
            ip=ip,
            city="Omaha",
            country="US",
            latitude=41.2565,
            longitude=-95.9345,
        ),
        poll_interval_seconds=0.0,
        clock=lambda: observed,
    )
    assert resolver.refresh() is not None

    resolver.invalidate()

    assert resolver.current() is None
    assert resolver.refresh(force=True) is not None


def test_environment_config_refresh_sets_observed_at(monkeypatch) -> None:
    observed = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setenv("STARLINK_GROUND_ENTRY_LATITUDE", "41.2565")
    monkeypatch.setenv("STARLINK_GROUND_ENTRY_LONGITUDE", "-95.9345")
    monkeypatch.setenv("STARLINK_GROUND_ENTRY_CITY", "Omaha")
    monkeypatch.setenv("STARLINK_GROUND_ENTRY_REGION", "Nebraska")
    monkeypatch.setenv("STARLINK_GROUND_ENTRY_COUNTRY", "US")

    resolver = GroundEntryPointResolver(clock=lambda: observed)

    entry = resolver.refresh(force=True)

    assert entry is not None
    assert entry.observed_at == observed
    assert entry.label == "Omaha, Nebraska"
