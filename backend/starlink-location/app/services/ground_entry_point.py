"""Ground entry point discovery and Prometheus publication."""

from __future__ import annotations

import logging
import math
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from ipaddress import AddressValueError, IPv4Address
from threading import RLock
from typing import TYPE_CHECKING, Literal

import dns.resolver
import httpx

from app.core.metrics.prometheus_metrics import (
    starlink_ground_entry_point_info,
    starlink_ground_entry_point_latitude_degrees,
    starlink_ground_entry_point_location,
    starlink_ground_entry_point_longitude_degrees,
)
from app.services.egress_identity import EgressIdentity, resolve_egress_identity

if TYPE_CHECKING:
    from app.services.pop.models import PopObservation

logger = logging.getLogger(__name__)

_DEFAULT_REFRESH_INTERVAL_SECONDS = 1.0
_GEOIP_REFRESH_SECONDS = 900.0
_GEOIP_FAILURE_RETRY_SECONDS = 60.0
_SAMPLE_EXPIRY_SECONDS = 30.0
_CLOUDFLARE_TRACE_URL = "https://1.1.1.1/cdn-cgi/trace"
_OPENDNS_RESOLVERS = ["208.67.222.222", "208.67.220.220"]
_last_ground_entry_point_location_labels: (
    tuple[str, str, str, str, str, str, str] | None
) = None
_last_ground_entry_point_info_labels: tuple[str, ...] | None = None
_last_ground_entry_point_refresh_monotonic: float | None = None


def _has_valid_geographic_coordinates(
    latitude: float,
    longitude: float,
) -> bool:
    return (
        math.isfinite(latitude)
        and math.isfinite(longitude)
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


@dataclass(frozen=True, slots=True)
class ProviderGeoIP:
    """Raw provider evidence; never replaces an operator-supplied identity."""

    ip: str
    city: str
    country: str
    latitude: float
    longitude: float
    region: str = ""
    lookup_at: str | None = None
    freshness: Literal["fresh", "stale"] = "fresh"
    source: str = "ipinfo.io"


@dataclass(frozen=True, slots=True)
class GroundEntryPoint:
    """Current public egress location with identity and separate GeoIP evidence."""

    ip: str
    city: str
    country: str
    latitude: float
    longitude: float
    region: str = ""
    pop_id: str | None = None
    identity_source: Literal["operator_static_cidr", "geoip"] = "geoip"
    matched_cidr: str | None = None
    sampled_at: str | None = None
    lookup_at: str | None = None
    freshness: Literal["fresh", "stale"] = "fresh"
    provider_geoip: ProviderGeoIP | None = None
    discrepancy: bool = False

    @property
    def label(self) -> str:
        """Return compact, punctuation-safe display text for dashboards."""
        parts = _display_location_parts(
            city=self.city,
            region=self.region,
            country=self.country,
        )
        return ", ".join(parts) if parts else "Ground Entry Point"


@dataclass(slots=True)
class _GeoIPCache:
    entry: GroundEntryPoint | None = None
    attempted_at: float | None = None
    succeeded_at: float | None = None
    lookup_at: str | None = None
    failed: bool = False


class GroundEntryPointResolver:
    """Sample public IP frequently with bounded provider refresh and retry."""

    def __init__(
        self,
        ip_resolver: Callable[[], str | None] | None = None,
        geolocator: Callable[[str], GroundEntryPoint | None] | None = None,
        poll_interval_seconds: float = _DEFAULT_REFRESH_INTERVAL_SECONDS,
        time_source: Callable[[], float] | None = None,
        wall_time_source: Callable[[], datetime] | None = None,
    ) -> None:
        self._lock = RLock()
        self._ip_resolver = ip_resolver or resolve_public_ip
        self._geolocator = geolocator or geolocate_public_ip
        self._poll_interval_seconds = poll_interval_seconds
        self._time_source = time_source or time.monotonic
        self._wall_time_source = wall_time_source or (lambda: datetime.now(UTC))
        self._last_lookup_at: float | None = None
        self._sampled_monotonic: float | None = None
        self._sampled_at: str | None = None
        self._current_ip: str | None = None
        self._current_entry: GroundEntryPoint | None = None
        self._entry_cache: dict[str, _GeoIPCache] = {}

    def _timestamp(self) -> str:
        return self._wall_time_source().astimezone(UTC).isoformat()

    def current(
        self, *, include_environment_override: bool = False
    ) -> GroundEntryPoint | None:
        """Return current-IP evidence, expiring confidence without network I/O."""
        with self._lock:
            if include_environment_override:
                configured = _entry_point_from_environment()
                if configured is not None:
                    return configured
            entry = self._current_entry
            if entry is None:
                return None
            now = self._time_source()
            cache = self._entry_cache.get(entry.ip)
            provider_stale = (
                cache is None
                or cache.succeeded_at is None
                or now - cache.succeeded_at >= _GEOIP_REFRESH_SECONDS
            )
            sample_stale = (
                self._sampled_monotonic is None
                or now - self._sampled_monotonic >= _SAMPLE_EXPIRY_SECONDS
            )
            freshness = (
                "stale"
                if sample_stale or (entry.identity_source == "geoip" and provider_stale)
                else "fresh"
            )
            provider = entry.provider_geoip
            if provider is not None:
                provider = replace(
                    provider, freshness="stale" if provider_stale else "fresh"
                )
            self._current_entry = replace(
                entry, freshness=freshness, provider_geoip=provider
            )
            return self._current_entry

    def observation(self) -> PopObservation:
        """Read the same current-IP view used by map and metrics."""
        with self._lock:
            from app.services.pop.models import PopObservation

            entry = self.current()
            return PopObservation(
                ip=self._current_ip,
                entry=entry,
                status=(
                    "known"
                    if entry is not None and entry.freshness == "fresh"
                    else "unknown"
                ),
                source="live",
                sampled_at=self._sampled_at,
                lookup_at=entry.lookup_at if entry else None,
                freshness=entry.freshness if entry else "unknown",
            )

    def invalidate(self, clear_geolocation_cache: bool = False) -> None:
        with self._lock:
            self._last_lookup_at = None
            self._sampled_monotonic = None
            self._sampled_at = None
            self._current_ip = None
            self._current_entry = None
            if clear_geolocation_cache:
                self._entry_cache.clear()

    def refresh(self, force: bool = False) -> GroundEntryPoint | None:
        """Sample IP; resolve identity even if provider lookup fails."""
        now = self._time_source()
        if (
            not force
            and self._last_lookup_at is not None
            and now - self._last_lookup_at < self._poll_interval_seconds
        ):
            return self.current()
        self._last_lookup_at = now
        try:
            ip = self._ip_resolver()
        except (
            httpx.HTTPError,
            dns.exception.DNSException,
            RuntimeError,
            ValueError,
            OSError,
            KeyError,
            TypeError,
            AttributeError,
            LookupError,
            ConnectionError,
            TimeoutError,
            ImportError,
            EOFError,
        ) as exc:
            logger.warning("Failed to resolve public IP: %s", exc)
            return self.current()
        if not ip:
            return self.current()
        ip = _normalize_ipv4_address(ip)
        identity = resolve_egress_identity(ip) if ip is not None else None
        with self._lock:
            if ip is None:
                self._current_ip = None
                self._current_entry = None
                self._sampled_monotonic = None
                self._sampled_at = None
                return None
            self._current_ip = ip
            self._sampled_monotonic = now
            self._sampled_at = self._timestamp()
            cache = self._entry_cache.setdefault(ip, _GeoIPCache())
            # Publish the new IP and its static identity together, before waiting
            # for optional provider evidence. Readers hold the same short lock.
            self._current_entry = self._entry_from_evidence(ip, cache, identity)
            retry = (
                _GEOIP_FAILURE_RETRY_SECONDS if cache.failed else _GEOIP_REFRESH_SECONDS
            )
            needs_lookup = (
                cache.attempted_at is None or now - cache.attempted_at >= retry
            )
            if needs_lookup:
                cache.attempted_at = now
                cache.failed = True
        if needs_lookup:
            try:
                provider = self._geolocator(ip)
            except (
                httpx.HTTPError,
                dns.exception.DNSException,
                RuntimeError,
                ValueError,
                OSError,
                KeyError,
                TypeError,
                AttributeError,
                LookupError,
                ConnectionError,
                TimeoutError,
                ImportError,
                EOFError,
            ) as exc:
                logger.warning("Failed to geolocate public IP %s: %s", ip, exc)
                provider = None
            with self._lock:
                if (
                    provider is not None
                    and provider.ip == ip
                    and _has_valid_geographic_coordinates(
                        provider.latitude, provider.longitude
                    )
                ):
                    cache.entry = provider
                    cache.succeeded_at = now
                    cache.lookup_at = self._timestamp()
                    cache.failed = False
        with self._lock:
            # Another sample may arrive while this provider request is running.
            # Cache its evidence, but never overwrite the newer IP's entry.
            if self._current_ip == ip:
                self._current_entry = self._entry_from_evidence(ip, cache, identity)
            return self.current()

    def _entry_from_evidence(
        self, ip: str, cache: _GeoIPCache, identity: EgressIdentity | None
    ) -> GroundEntryPoint | None:
        raw = cache.entry
        provider_geoip = (
            ProviderGeoIP(
                ip=raw.ip,
                city=raw.city,
                region=raw.region,
                country=raw.country,
                latitude=raw.latitude,
                longitude=raw.longitude,
                lookup_at=cache.lookup_at,
            )
            if raw is not None
            else None
        )
        if identity is not None:
            discrepancy = False
            if raw is not None:
                names = {name.casefold() for name in (identity.city, *identity.aliases)}
                discrepancy = (
                    raw.city.casefold() not in names
                    or raw.country.casefold() != identity.country.casefold()
                    or _location_distance_km(
                        raw.latitude,
                        raw.longitude,
                        identity.latitude,
                        identity.longitude,
                    )
                    > 100
                )
            return GroundEntryPoint(
                ip=ip,
                city=identity.city,
                country=identity.country,
                latitude=identity.latitude,
                longitude=identity.longitude,
                pop_id=identity.pop_id,
                identity_source="operator_static_cidr",
                matched_cidr=identity.matched_cidr,
                sampled_at=self._sampled_at,
                lookup_at=cache.lookup_at,
                provider_geoip=provider_geoip,
                discrepancy=discrepancy,
            )
        elif raw is not None:
            return replace(
                raw,
                ip=ip,
                pop_id=None,
                identity_source="geoip",
                matched_cidr=None,
                sampled_at=self._sampled_at,
                lookup_at=cache.lookup_at,
                provider_geoip=provider_geoip,
                discrepancy=False,
            )
        else:
            return None


def _location_distance_km(
    lat_a: float, lon_a: float, lat_b: float, lon_b: float
) -> float:
    """Use distance only to flag provider disagreement, never assign identity."""
    lat_a, lon_a, lat_b, lon_b = map(math.radians, (lat_a, lon_a, lat_b, lon_b))
    haversine = (
        math.sin((lat_b - lat_a) / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin((lon_b - lon_a) / 2) ** 2
    )
    return 6371 * 2 * math.asin(min(1.0, math.sqrt(haversine)))


def resolve_public_ip(timeout_seconds: float = 2.0) -> str | None:
    """Resolve the current public IPv4, preferring Cloudflare trace."""
    try:
        ip = resolve_public_ip_via_cloudflare_trace(timeout_seconds=timeout_seconds)
    except (
        httpx.HTTPError,
        dns.exception.DNSException,
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        LookupError,
        ConnectionError,
        TimeoutError,
        ImportError,
        EOFError,
    ) as exc:  # pragma: no cover - defensive network guard
        logger.warning("Cloudflare trace public-IP lookup failed: %s", exc)
        ip = None
    if ip:
        return ip

    try:
        return resolve_public_ip_via_dns(timeout_seconds=timeout_seconds)
    except (
        httpx.HTTPError,
        dns.exception.DNSException,
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        LookupError,
        ConnectionError,
        TimeoutError,
        ImportError,
        EOFError,
    ) as exc:  # pragma: no cover - defensive network guard
        logger.warning("OpenDNS public-IP lookup failed: %s", exc)
        return None


def resolve_public_ip_via_cloudflare_trace(
    timeout_seconds: float = 2.0,
) -> str | None:
    """Resolve the current public IPv4 using Cloudflare's trace endpoint."""
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        response = client.get(_CLOUDFLARE_TRACE_URL)
        response.raise_for_status()
        return _extract_cloudflare_trace_ipv4(response.text)


def resolve_public_ip_via_dns(timeout_seconds: float = 2.0) -> str | None:
    """Resolve the current public IPv4 using OpenDNS as a fallback."""
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = _OPENDNS_RESOLVERS
    resolver.timeout = timeout_seconds
    resolver.lifetime = timeout_seconds
    answers = list(resolver.resolve("myip.opendns.com", "A", search=False))
    if not answers:
        return None
    return _normalize_ipv4_address(str(answers[0]).strip())


def _extract_cloudflare_trace_ipv4(trace_body: str) -> str | None:
    """Extract and validate the ``ip=`` IPv4 value from Cloudflare trace text."""
    for line in trace_body.splitlines():
        key, separator, value = line.partition("=")
        if separator and key == "ip":
            return _normalize_ipv4_address(value.strip())
    return None


def _normalize_ipv4_address(value: str) -> str | None:
    """Return a canonical IPv4 string, or None when the value is not IPv4."""
    try:
        return str(IPv4Address(value))
    except AddressValueError:
        return None


def geolocate_public_ip(
    ip: str,
    timeout_seconds: float = 5.0,
) -> GroundEntryPoint | None:
    """Geolocate a public IP using ipinfo.io."""
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        response = client.get(f"https://ipinfo.io/{ip}/json")
        response.raise_for_status()
        payload = response.json()

    loc = str(payload.get("loc") or "")
    try:
        latitude_raw, longitude_raw = loc.split(",", maxsplit=1)
        latitude = float(latitude_raw)
        longitude = float(longitude_raw)
        if not _has_valid_geographic_coordinates(latitude, longitude):
            logger.warning("Ground entry point has invalid coordinates")
            return None
    except (TypeError, ValueError):
        logger.warning("Ground entry point geolocation missing loc field")
        return None

    return GroundEntryPoint(
        ip=str(payload.get("ip") or ip),
        city=_clean_location_part(payload.get("city")),
        region=_clean_location_part(payload.get("region")),
        country=_clean_location_part(payload.get("country")),
        latitude=latitude,
        longitude=longitude,
    )


_resolver = GroundEntryPointResolver()


def invalidate_cached_ground_entry_point() -> None:
    """Invalidate current ground-entry state so the next lookup re-discovers it."""
    _resolver.invalidate(clear_geolocation_cache=True)


def discover_ground_entry_point(
    timeout_seconds: float = 5.0,
) -> GroundEntryPoint | None:
    """Discover the public egress IP and geolocate it."""

    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: resolve_public_ip(
            timeout_seconds=min(timeout_seconds, 2.0)
        ),
        geolocator=lambda ip: geolocate_public_ip(ip, timeout_seconds=timeout_seconds),
    )
    return resolver.refresh(force=True)


def get_cached_ground_entry_point(
    *,
    include_environment_override: bool = False,
) -> GroundEntryPoint | None:
    """Return the last-known ground entry point without forcing a network lookup."""
    return _resolver.current(include_environment_override=include_environment_override)


def get_cached_pop_observation() -> PopObservation:
    """Read current public-IP observation without performing discovery."""
    return _resolver.observation()


def clear_ground_entry_point_metrics() -> None:
    """Clear plain gauges and remove any previously published labelled series."""
    global _last_ground_entry_point_location_labels, _last_ground_entry_point_info_labels

    starlink_ground_entry_point_latitude_degrees.set(math.nan)
    starlink_ground_entry_point_longitude_degrees.set(math.nan)

    if _last_ground_entry_point_location_labels is not None:
        try:
            starlink_ground_entry_point_location.remove(
                *_last_ground_entry_point_location_labels
            )
        except KeyError:
            pass
        _last_ground_entry_point_location_labels = None

    if _last_ground_entry_point_info_labels is not None:
        try:
            starlink_ground_entry_point_info.remove(
                *_last_ground_entry_point_info_labels
            )
        except KeyError:
            pass
        _last_ground_entry_point_info_labels = None


def publish_ground_entry_point_metrics(entry_point: GroundEntryPoint | None) -> None:
    """Publish ground entry point metrics for Grafana and Prometheus exports."""
    global _last_ground_entry_point_location_labels, _last_ground_entry_point_info_labels

    clear_ground_entry_point_metrics()
    if entry_point is None:
        return

    lat_label = f"{entry_point.latitude:.6g}"
    lon_label = f"{entry_point.longitude:.6g}"
    location_labels = (
        lat_label,
        lon_label,
        entry_point.city,
        entry_point.region,
        entry_point.country,
        entry_point.ip,
        entry_point.label,
    )
    info_labels = (
        entry_point.city,
        entry_point.region,
        entry_point.country,
        entry_point.ip,
        entry_point.label,
        entry_point.pop_id or "",
        entry_point.identity_source,
        entry_point.matched_cidr or "",
        entry_point.freshness,
        str(entry_point.discrepancy).lower(),
    )

    if entry_point.freshness == "fresh":
        starlink_ground_entry_point_latitude_degrees.set(entry_point.latitude)
        starlink_ground_entry_point_longitude_degrees.set(entry_point.longitude)
        starlink_ground_entry_point_location.labels(
            lat=location_labels[0],
            lon=location_labels[1],
            city=location_labels[2],
            region=location_labels[3],
            country=location_labels[4],
            ip=location_labels[5],
            display=location_labels[6],
        ).set(1)
        _last_ground_entry_point_location_labels = location_labels
    starlink_ground_entry_point_info.labels(
        city=info_labels[0],
        region=info_labels[1],
        country=info_labels[2],
        ip=info_labels[3],
        display=info_labels[4],
        pop_id=info_labels[5],
        identity_source=info_labels[6],
        matched_cidr=info_labels[7],
        freshness=info_labels[8],
        discrepancy=info_labels[9],
    ).set(1)

    _last_ground_entry_point_info_labels = info_labels


def refresh_ground_entry_point_metrics(
    now_monotonic: float | None = None,
    force: bool = False,
) -> GroundEntryPoint | None:
    """Refresh DNS-watched ground-entry state and publish current metrics."""
    global _last_ground_entry_point_refresh_monotonic

    entry_point = _resolver.refresh(force=force)
    publish_ground_entry_point_metrics(entry_point)
    _last_ground_entry_point_refresh_monotonic = (
        time.monotonic() if now_monotonic is None else now_monotonic
    )
    return entry_point


def maybe_refresh_ground_entry_point_metrics(
    refresh_interval_seconds: float | None = None,
    now_monotonic: float | None = None,
) -> GroundEntryPoint | None:
    """Refresh entry-point metrics only when the DNS watcher interval has elapsed."""
    interval_seconds = (
        _DEFAULT_REFRESH_INTERVAL_SECONDS
        if refresh_interval_seconds is None
        else refresh_interval_seconds
    )
    if not math.isfinite(interval_seconds) or interval_seconds <= 0:
        logger.warning(
            "Invalid ground entry refresh interval %r; using default %.1f seconds",
            interval_seconds,
            _DEFAULT_REFRESH_INTERVAL_SECONDS,
        )
        interval_seconds = _DEFAULT_REFRESH_INTERVAL_SECONDS

    current_monotonic = time.monotonic() if now_monotonic is None else now_monotonic

    if (
        _last_ground_entry_point_refresh_monotonic is None
        or (current_monotonic - _last_ground_entry_point_refresh_monotonic)
        >= interval_seconds
    ):
        return refresh_ground_entry_point_metrics(now_monotonic=current_monotonic)

    return get_cached_ground_entry_point()


def _entry_point_from_environment() -> GroundEntryPoint | None:
    """Build a ground entry point from explicit environment overrides."""
    lat_raw = os.getenv("STARLINK_GROUND_ENTRY_LATITUDE")
    lon_raw = os.getenv("STARLINK_GROUND_ENTRY_LONGITUDE")
    if not (lat_raw and lon_raw):
        return None
    try:
        latitude = float(lat_raw)
        longitude = float(lon_raw)
        if not _has_valid_geographic_coordinates(latitude, longitude):
            logger.warning("Ground entry point has invalid coordinates")
            return None
    except ValueError:
        logger.warning("Invalid STARLINK_GROUND_ENTRY latitude/longitude override")
        return None
    return GroundEntryPoint(
        ip=os.getenv("STARLINK_GROUND_ENTRY_IP", ""),
        city=_clean_location_part(os.getenv("STARLINK_GROUND_ENTRY_CITY")),
        region=_clean_location_part(
            os.getenv("STARLINK_GROUND_ENTRY_REGION")
            or os.getenv("STARLINK_GROUND_ENTRY_STATE")
        ),
        country=_clean_location_part(os.getenv("STARLINK_GROUND_ENTRY_COUNTRY")),
        latitude=latitude,
        longitude=longitude,
    )


def _display_location_parts(city: str, region: str, country: str) -> list[str]:
    """Choose dashboard location parts without placeholder junk or punctuation gaps."""
    clean_city = _clean_location_part(city)
    clean_region = _clean_location_part(region)
    clean_country = _clean_location_part(country)

    if clean_country.upper() == "US" and clean_region:
        return [part for part in (clean_city, clean_region) if part]
    return [part for part in (clean_city, clean_country) if part]


def _clean_location_part(value: object) -> str:
    """Normalize empty/placeholder location fields to an empty string."""
    if value is None:
        return ""
    text = str(value).strip().strip(",")
    if text.lower() in {"", "none", "null", "unknown", "n/a", "na"}:
        return ""
    return text
