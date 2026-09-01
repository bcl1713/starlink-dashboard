"""Ground entry point discovery and Prometheus publication."""

from __future__ import annotations

import logging
import math
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from ipaddress import AddressValueError, IPv4Address

import dns.resolver
import httpx

from app.core.metrics.prometheus_metrics import (
    starlink_ground_entry_point_info,
    starlink_ground_entry_point_latitude_degrees,
    starlink_ground_entry_point_location,
    starlink_ground_entry_point_longitude_degrees,
)

logger = logging.getLogger(__name__)

_DEFAULT_REFRESH_INTERVAL_SECONDS = 1.0
_CLOUDFLARE_TRACE_URL = "https://1.1.1.1/cdn-cgi/trace"
_OPENDNS_RESOLVERS = ["208.67.222.222", "208.67.220.220"]
_last_ground_entry_point_location_labels: (
    tuple[str, str, str, str, str, str, str] | None
) = None
_last_ground_entry_point_info_labels: tuple[str, str, str, str, str] | None = None
_last_ground_entry_point_refresh_monotonic: float | None = None


@dataclass(frozen=True, slots=True)
class GroundEntryPoint:
    """Public internet egress location used as a ground entry point proxy."""

    ip: str
    city: str
    country: str
    latitude: float
    longitude: float
    region: str = ""
    observed_at: datetime | None = None

    @property
    def label(self) -> str:
        """Return compact, punctuation-safe display text for dashboards."""
        parts = _display_location_parts(
            city=self.city,
            region=self.region,
            country=self.country,
        )
        return ", ".join(parts) if parts else "Ground Entry Point"


class GroundEntryPointResolver:
    """Resolve public IP frequently, geolocating only when the IP changes."""

    def __init__(
        self,
        ip_resolver: Callable[[], str | None] | None = None,
        geolocator: Callable[[str], GroundEntryPoint | None] | None = None,
        poll_interval_seconds: float = _DEFAULT_REFRESH_INTERVAL_SECONDS,
        time_source: Callable[[], float] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._ip_resolver = ip_resolver or resolve_public_ip
        self._geolocator = geolocator or geolocate_public_ip
        self._poll_interval_seconds = poll_interval_seconds
        self._time_source = time_source or time.monotonic
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._last_lookup_at: float | None = None
        self._current_ip: str | None = None
        self._current_entry: GroundEntryPoint | None = None
        self._entry_cache: dict[str, GroundEntryPoint] = {}

    def current(self) -> GroundEntryPoint | None:
        """Return the most recently resolved ground entry point."""
        return self._current_entry

    def invalidate(self, clear_geolocation_cache: bool = False) -> None:
        """Clear current resolver state, optionally dropping per-IP geolocation cache."""
        self._last_lookup_at = None
        self._current_ip = None
        self._current_entry = None
        if clear_geolocation_cache:
            self._entry_cache.clear()

    def refresh(self, force: bool = False) -> GroundEntryPoint | None:
        """Refresh public IP state and geolocate only when the IP changes."""
        configured = _entry_point_from_environment()
        if configured is not None:
            observed = self._with_observed_at(configured)
            self._current_ip = observed.ip or self._current_ip
            self._current_entry = observed
            return observed

        now = self._time_source()
        if (
            not force
            and self._last_lookup_at is not None
            and now - self._last_lookup_at < self._poll_interval_seconds
        ):
            return self._current_entry

        self._last_lookup_at = now

        try:
            ip = self._ip_resolver()
        except (
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
            logger.warning("Failed to resolve public IP: %s", exc)
            return self._current_entry

        if not ip:
            return self._current_entry

        if ip == self._current_ip and self._current_entry is not None:
            # A successful same-IP revalidation is fresh evidence even though
            # geolocation fields remain cached; resolution failures returned
            # above deliberately retain the prior observation unchanged.
            observed = self._with_observed_at(
                self._current_entry, preserve_existing=False
            )
            self._current_entry = observed
            return observed

        cached_entry = self._entry_cache.get(ip)
        if cached_entry is not None:
            observed = self._with_observed_at(cached_entry, preserve_existing=False)
            self._current_ip = ip
            self._current_entry = observed
            return observed

        try:
            entry = self._geolocator(ip)
        except (
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
            logger.warning("Failed to geolocate public IP %s: %s", ip, exc)
            return self._current_entry

        if entry is None:
            return self._current_entry

        observed = self._with_observed_at(entry, preserve_existing=False)
        self._entry_cache[ip] = self._without_observed_at(entry)
        self._current_ip = ip
        self._current_entry = observed
        return observed

    def _with_observed_at(
        self,
        entry_point: GroundEntryPoint,
        *,
        preserve_existing: bool = True,
    ) -> GroundEntryPoint:
        observed_at = (
            entry_point.observed_at
            if preserve_existing and entry_point.observed_at is not None
            else self._utc_now()
        )
        return GroundEntryPoint(
            ip=entry_point.ip,
            city=entry_point.city,
            country=entry_point.country,
            latitude=entry_point.latitude,
            longitude=entry_point.longitude,
            region=entry_point.region,
            observed_at=observed_at,
        )

    def _without_observed_at(self, entry_point: GroundEntryPoint) -> GroundEntryPoint:
        return GroundEntryPoint(
            ip=entry_point.ip,
            city=entry_point.city,
            country=entry_point.country,
            latitude=entry_point.latitude,
            longitude=entry_point.longitude,
            region=entry_point.region,
            observed_at=None,
        )

    def _utc_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ground entry point clock must be timezone-aware")
        return value.astimezone(timezone.utc)


def resolve_public_ip(timeout_seconds: float = 2.0) -> str | None:
    """Resolve the current public IPv4, preferring Cloudflare trace."""
    try:
        ip = resolve_public_ip_via_cloudflare_trace(timeout_seconds=timeout_seconds)
    except (
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
    configured = _entry_point_from_environment()
    if configured is not None:
        return GroundEntryPointResolver()._with_observed_at(configured)

    resolver = GroundEntryPointResolver(
        ip_resolver=lambda: resolve_public_ip(
            timeout_seconds=min(timeout_seconds, 2.0)
        ),
        geolocator=lambda ip: geolocate_public_ip(ip, timeout_seconds=timeout_seconds),
    )
    return resolver.refresh(force=True)


def get_cached_ground_entry_point() -> GroundEntryPoint | None:
    """Return the last-known ground entry point without forcing a network lookup."""
    return _resolver.current()


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
    )

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
    starlink_ground_entry_point_info.labels(
        city=info_labels[0],
        region=info_labels[1],
        country=info_labels[2],
        ip=info_labels[3],
        display=info_labels[4],
    ).set(1)

    _last_ground_entry_point_location_labels = location_labels
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
