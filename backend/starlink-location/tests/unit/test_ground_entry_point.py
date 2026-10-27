"""Tests for ground entry point discovery and metric formatting."""

from __future__ import annotations

from dataclasses import asdict, replace

import pytest
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


def test_environment_ground_entry_point_rejects_invalid_coordinates(
    monkeypatch,
) -> None:
    invalid_coordinates = [
        ("91", "-95.9345"),  # latitude range
        ("41.2565", "181"),  # longitude range
        ("nan", "-95.9345"),  # non-finite latitude
        ("41.2565", "inf"),  # non-finite longitude
    ]

    for latitude, longitude in invalid_coordinates:
        monkeypatch.setenv("STARLINK_GROUND_ENTRY_LATITUDE", latitude)
        monkeypatch.setenv("STARLINK_GROUND_ENTRY_LONGITUDE", longitude)

        assert gep._entry_point_from_environment() is None


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


def test_invalid_latitude_returns_none(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {
                "ip": "203.0.113.10",
                "city": "Omaha",
                "region": "Nebraska",
                "country": "US",
                "loc": "91,-95.9345",
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

    assert gep.geolocate_public_ip("203.0.113.10") is None


def test_invalid_longitude_returns_none(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {
                "ip": "203.0.113.10",
                "city": "Omaha",
                "region": "Nebraska",
                "country": "US",
                "loc": "41.2565,181",
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

    assert gep.geolocate_public_ip("203.0.113.10") is None


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
    assert second.ip == first.ip and second.lookup_at == first.lookup_at
    assert third.ip == first.ip and third.lookup_at == first.lookup_at
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
    assert second.ip == first.ip and second.lookup_at == first.lookup_at
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
    assert third.ip == first.ip and third.lookup_at == first.lookup_at
    assert geolocate_calls == ["203.0.113.10", "198.51.100.24"]


def test_resolver_ignores_environment_override_by_default(monkeypatch) -> None:
    monkeypatch.setenv("STARLINK_GROUND_ENTRY_LATITUDE", "41.2565")
    monkeypatch.setenv("STARLINK_GROUND_ENTRY_LONGITUDE", "-95.9345")

    resolver = gep.GroundEntryPointResolver()

    assert resolver.current() is None
    configured = resolver.current(include_environment_override=True)

    assert configured is not None
    assert configured.latitude == 41.2565
    assert configured.longitude == -95.9345


def test_resolver_refresh_ignores_environment_override_by_default(
    monkeypatch,
) -> None:
    monkeypatch.setenv("STARLINK_GROUND_ENTRY_LATITUDE", "41.2565")
    monkeypatch.setenv("STARLINK_GROUND_ENTRY_LONGITUDE", "-95.9345")

    discovered = GroundEntryPoint(
        ip="203.0.113.10",
        city="Omaha",
        region="Nebraska",
        country="US",
        latitude=41.2565,
        longitude=-95.9345,
    )
    resolver = gep.GroundEntryPointResolver(
        ip_resolver=lambda: "203.0.113.10",
        geolocator=lambda _: discovered,
    )

    assert resolver.refresh().provider_geoip.city == discovered.city


def test_observation_marks_changed_ip_unknown_until_retry_succeeds() -> None:
    old = GroundEntryPoint("203.0.113.1", "Dallas", "US", 32, -96)
    new = GroundEntryPoint("203.0.113.2", "Tokyo", "JP", 35, 139)
    ips = iter([old.ip, new.ip, new.ip, old.ip])
    entries = iter([old, None, new])
    now = 0.0
    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: next(ips),
        geolocator=lambda ip: next(entries),
        poll_interval_seconds=0,
        time_source=lambda: now,
    )
    resolver.refresh()
    assert resolver.observation().entry.ip == old.ip
    resolver.refresh()
    assert resolver.current() is None
    current = resolver.observation()
    assert (
        current.status == "unknown" and current.ip == new.ip and current.entry is None
    )
    now = 60.0
    resolver.refresh()
    assert resolver.observation().entry.ip == new.ip
    resolver.refresh()
    assert resolver.observation().entry.ip == old.ip


def test_observation_same_ip_revalidates_aged_lookup() -> None:
    entry = GroundEntryPoint("203.0.113.1", "Dallas", "US", 32, -96)
    now = 0
    calls = []

    def geolocate(ip):
        calls.append(ip)
        return entry

    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: entry.ip, geolocator=geolocate, time_source=lambda: now
    )
    resolver.refresh()
    now = 10**9
    resolver.refresh()
    assert resolver.observation().entry.ip == entry.ip
    assert resolver.observation().entry.freshness == "fresh"
    assert calls == [entry.ip, entry.ip]


def test_changed_ip_http_timeout_clears_display_and_observation():
    old = GroundEntryPoint("203.0.113.1", "Dallas", "US", 32, -96)
    ips = iter([old.ip, "203.0.113.2"])

    def geolocate(ip):
        if ip != old.ip:
            raise gep.httpx.ReadTimeout("geolocation unavailable")
        return old

    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: next(ips), geolocator=geolocate, poll_interval_seconds=0
    )
    resolver.refresh()
    assert resolver.refresh() is None
    assert resolver.observation().status == "unknown"
    assert resolver.observation().entry is None


def test_real_http_failure_uses_dns_fallback(monkeypatch):
    def trace(timeout_seconds):
        raise gep.httpx.ConnectError("trace unavailable")

    monkeypatch.setattr(gep, "resolve_public_ip_via_cloudflare_trace", trace)
    monkeypatch.setattr(
        gep, "resolve_public_ip_via_dns", lambda **kwargs: "203.0.113.7"
    )
    assert gep.resolve_public_ip() == "203.0.113.7"


@pytest.mark.parametrize(
    "prefix,pop_id,city,latitude,longitude",
    [
        ("216.255.176", "los-angeles", "Los Angeles", 34.05223, -118.24368),
        ("216.255.182", "los-angeles", "Los Angeles", 34.05223, -118.24368),
        ("216.255.177", "ashburn", "Ashburn", 39.04372, -77.48749),
        ("216.255.183", "ashburn", "Ashburn", 39.04372, -77.48749),
        ("216.255.178", "dallas", "Dallas", 32.78306, -96.80667),
        ("75.78.128", "dallas", "Dallas", 32.78306, -96.80667),
        ("216.255.179", "sydney", "Sydney", -33.86785, 151.20732),
        ("216.255.180", "frankfurt", "Frankfurt", 50.11552, 8.68417),
        ("216.255.181", "tokyo", "Tokyo", 35.6895, 139.69171),
    ],
)
@pytest.mark.parametrize("host", [0, 127, 255])
def test_static_identity_uses_exact_cidr_and_catalog_without_geoip(
    prefix, pop_id, city, latitude, longitude, host
):
    ip = f"{prefix}.{host}"
    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: ip, geolocator=lambda _: None
    )
    entry = resolver.refresh()
    assert entry is not None
    assert (entry.pop_id, entry.city, entry.latitude, entry.longitude) == (
        pop_id,
        city,
        latitude,
        longitude,
    )
    assert entry.identity_source == "operator_static_cidr"
    assert entry.matched_cidr == f"{prefix}.0/24"
    assert entry.provider_geoip is None and not entry.discrepancy
    assert entry.freshness == "fresh"
    assert entry.sampled_at.endswith("+00:00")
    assert resolver.observation().entry == resolver.current() == entry


@pytest.mark.parametrize(
    "ip",
    [
        "216.255.175.255",
        "216.255.184.0",
        "75.78.127.255",
        "75.78.129.0",
        "bad",
        "216.255.176.999",
        "2001:db8::1",
    ],
)
def test_nonmember_and_malformed_ips_never_gain_static_identity(ip):
    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: ip, geolocator=lambda _: None
    )
    assert resolver.refresh() is None
    assert resolver.current() is None
    assert resolver.observation().status == "unknown"


def test_static_identity_keeps_conflicting_geoip_as_serializable_evidence():
    raw = GroundEntryPoint("216.255.176.5", "New York", "US", 40.7, -74, "New York")
    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: raw.ip, geolocator=lambda _: raw
    )
    entry = resolver.refresh()
    assert entry.city == "Los Angeles" and entry.latitude == 34.05223
    assert entry.discrepancy
    assert asdict(entry.provider_geoip)["city"] == "New York"
    assert entry.provider_geoip.latitude == 40.7
    publish_ground_entry_point_metrics(entry)
    metrics = generate_latest(REGISTRY).decode()
    assert 'pop_id="los-angeles"' in metrics
    assert 'identity_source="operator_static_cidr"' in metrics
    assert 'city="Los Angeles"' in metrics
    assert 'city="New York"' not in metrics


def test_same_ip_geoip_is_revalidated_and_can_correct_location():
    now = 0.0
    entries = iter(
        [
            GroundEntryPoint("203.0.113.1", "Dallas", "US", 32, -96),
            GroundEntryPoint("203.0.113.1", "Tokyo", "JP", 35, 139),
        ]
    )
    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: "203.0.113.1",
        geolocator=lambda _: next(entries),
        time_source=lambda: now,
    )
    assert resolver.refresh().city == "Dallas"
    now = 899
    assert resolver.refresh().city == "Dallas"
    now = 900
    entry = resolver.refresh()
    assert entry.city == "Tokyo" and entry.freshness == "fresh"
    assert entry.pop_id is None and entry.identity_source == "geoip"
    assert entry.matched_cidr is None


def test_readers_expire_sample_without_network_and_preserve_one_stale_view():
    now = 0.0
    raw = GroundEntryPoint("203.0.113.1", "Dallas", "US", 32, -96)
    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: raw.ip, geolocator=lambda _: raw, time_source=lambda: now
    )
    resolver.refresh()
    now = 30
    entry = resolver.current()
    assert entry.freshness == "stale"
    assert resolver.observation().status == "unknown"
    assert resolver.observation().entry == entry
    now = 31
    assert resolver.refresh().freshness == "fresh"


def test_failed_changed_ip_clears_current_and_retries_after_sixty_seconds(monkeypatch):
    now = 0.0
    ip = "216.255.176.1"
    answers = iter(
        [None, None, GroundEntryPoint("203.0.113.1", "Dallas", "US", 32, -96)]
    )
    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: ip,
        geolocator=lambda _: next(answers),
        time_source=lambda: now,
    )
    assert resolver.refresh().pop_id == "los-angeles"
    ip = "203.0.113.1"
    now = 1
    monkeypatch.setattr(gep, "_resolver", resolver)
    assert refresh_ground_entry_point_metrics() is None
    assert resolver.current() is resolver.observation().entry is None
    assert (
        "starlink_ground_entry_point_latitude_degrees NaN"
        in generate_latest(REGISTRY).decode()
    )
    now = 60
    assert resolver.refresh() is None
    now = 61
    assert resolver.refresh().city == "Dallas"


def test_static_identity_survives_provider_exception_and_stale_provider_evidence():
    now = 0.0

    def unavailable(_):
        raise gep.httpx.ReadTimeout("unavailable")

    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: "216.255.181.1",
        geolocator=unavailable,
        time_source=lambda: now,
    )
    assert resolver.refresh().pop_id == "tokyo"
    now = 900
    assert resolver.refresh().freshness == "fresh"
    assert resolver.observation().status == "known"


def test_failed_geoip_revalidation_expires_uncertainty_and_retries_bounded():
    now = 0.0
    raw = GroundEntryPoint("203.0.113.1", "Dallas", "US", 32, -96)
    answers = iter([raw, None, raw])
    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: raw.ip,
        geolocator=lambda _: next(answers),
        time_source=lambda: now,
    )
    first = resolver.refresh()
    now = 900
    entry = resolver.refresh()
    assert entry.lookup_at == first.lookup_at
    assert entry.freshness == entry.provider_geoip.freshness == "stale"
    assert resolver.observation().status == "unknown"
    now = 959
    assert resolver.refresh().freshness == "stale"
    now = 960
    assert resolver.refresh().freshness == "fresh"


def test_static_identity_freshness_is_independent_of_expired_provider():
    now = 0.0
    raw = GroundEntryPoint("216.255.176.1", "New York", "US", 40.7, -74)
    answers = iter([raw, None])
    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: raw.ip,
        geolocator=lambda _: next(answers),
        time_source=lambda: now,
    )
    resolver.refresh()
    now = 900
    entry = resolver.refresh()
    assert entry.freshness == "fresh"
    assert entry.provider_geoip.freshness == "stale"
    assert entry.pop_id == "los-angeles" and entry.discrepancy
    assert resolver.observation().status == "known"


@pytest.mark.parametrize("initial_ip", [None, "203.0.113.1", "216.255.181.1"])
def test_static_identity_is_readable_while_provider_lookup_is_in_progress(initial_ip):
    ip = initial_ip

    def lookup(sampled_ip):
        if sampled_ip != "216.255.176.5":
            return GroundEntryPoint(sampled_ip, "Tokyo", "JP", 35, 139)
        current = resolver.current()
        observation = resolver.observation()
        assert current is not None
        assert current.ip == observation.ip == sampled_ip
        assert current.pop_id == "los-angeles"
        assert current.latitude == 34.05223
        assert current.provider_geoip is None
        assert observation.status == "known"
        assert observation.entry == current
        return GroundEntryPoint(sampled_ip, "New York", "US", 40.7, -74)

    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: ip, geolocator=lookup, poll_interval_seconds=0
    )
    if initial_ip:
        resolver.refresh()
    ip = "216.255.176.5"
    result = resolver.refresh()
    assert result.pop_id == "los-angeles"
    assert result.provider_geoip.city == "New York"
    assert result.provider_geoip.source == "ipinfo.io"
    assert result.discrepancy


def test_stale_metrics_remove_location_but_preserve_explicit_stale_identity():
    entry = GroundEntryPoint(
        "216.255.176.5",
        "Los Angeles",
        "US",
        34.05223,
        -118.24368,
        pop_id="los-angeles",
        identity_source="operator_static_cidr",
        matched_cidr="216.255.176.0/24",
    )
    publish_ground_entry_point_metrics(entry)
    live = generate_latest(REGISTRY).decode()
    assert "starlink_ground_entry_point_location{" in live
    publish_ground_entry_point_metrics(replace(entry, freshness="stale"))
    stale = generate_latest(REGISTRY).decode()
    assert "starlink_ground_entry_point_latitude_degrees NaN" in stale
    assert "starlink_ground_entry_point_longitude_degrees NaN" in stale
    assert "starlink_ground_entry_point_location{" not in stale
    info = [
        line
        for line in stale.splitlines()
        if line.startswith("starlink_ground_entry_point_info{")
    ]
    assert len(info) == 1
    assert 'freshness="stale"' in info[0]
    assert 'pop_id="los-angeles"' in info[0]
    publish_ground_entry_point_metrics(None)
    assert "starlink_ground_entry_point_info{" not in generate_latest(REGISTRY).decode()
