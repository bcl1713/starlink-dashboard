"""Ground entry point discovery and Prometheus publication."""

from __future__ import annotations

import logging
import math
import os
import time
from dataclasses import dataclass
from functools import lru_cache

import httpx

from app.core.metrics.prometheus_metrics import (
    starlink_ground_entry_point_info,
    starlink_ground_entry_point_latitude_degrees,
    starlink_ground_entry_point_location,
    starlink_ground_entry_point_longitude_degrees,
)

logger = logging.getLogger(__name__)

_DEFAULT_REFRESH_INTERVAL_SECONDS = 300.0
_last_ground_entry_point_location_labels: tuple[str, str, str, str, str] | None = None
_last_ground_entry_point_info_labels: tuple[str, str, str] | None = None
_last_ground_entry_point_refresh_monotonic: float | None = None


@dataclass(frozen=True, slots=True)
class GroundEntryPoint:
    """Public internet egress location used as a ground entry point proxy."""

    ip: str
    city: str
    country: str
    latitude: float
    longitude: float

    @property
    def label(self) -> str:
        """Return compact city/country display text for dashboards."""
        parts = [part for part in (self.city, self.country) if part]
        return ", ".join(parts) if parts else "Unknown"


@lru_cache(maxsize=1)
def get_cached_ground_entry_point() -> GroundEntryPoint | None:
    """Resolve and cache the current public egress location.

    The lookup intentionally fails closed: if public-IP or geolocation services
    are unavailable, metrics and exports continue with empty ground-entry values
    rather than delaying telemetry collection. Apparently even satellites must
    occasionally wait for a website to answer.
    """
    return discover_ground_entry_point()


def invalidate_cached_ground_entry_point() -> None:
    """Invalidate the cached ground entry point so the next lookup re-discovers it."""
    get_cached_ground_entry_point.cache_clear()


def discover_ground_entry_point(
    timeout_seconds: float = 5.0,
) -> GroundEntryPoint | None:
    """Discover the public egress IP and geolocate it with ipinfo.io."""
    configured = _entry_point_from_environment()
    if configured is not None:
        return configured

    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            ip = client.get("https://ifconfig.me/ip").text.strip()
            if not ip:
                return None
            response = client.get(f"https://ipinfo.io/{ip}/json")
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:  # pragma: no cover - defensive network guard
        logger.warning("Failed to discover ground entry point: %s", exc)
        return None

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
        city=str(payload.get("city") or ""),
        country=str(payload.get("country") or ""),
        latitude=latitude,
        longitude=longitude,
    )


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
            starlink_ground_entry_point_info.remove(*_last_ground_entry_point_info_labels)
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
        entry_point.country,
        entry_point.ip,
    )
    info_labels = (entry_point.city, entry_point.country, entry_point.ip)

    starlink_ground_entry_point_latitude_degrees.set(entry_point.latitude)
    starlink_ground_entry_point_longitude_degrees.set(entry_point.longitude)
    starlink_ground_entry_point_location.labels(
        lat=location_labels[0],
        lon=location_labels[1],
        city=location_labels[2],
        country=location_labels[3],
        ip=location_labels[4],
    ).set(1)
    starlink_ground_entry_point_info.labels(
        city=info_labels[0],
        country=info_labels[1],
        ip=info_labels[2],
    ).set(1)

    _last_ground_entry_point_location_labels = location_labels
    _last_ground_entry_point_info_labels = info_labels


def refresh_ground_entry_point_metrics(
    now_monotonic: float | None = None,
) -> GroundEntryPoint | None:
    """Invalidate cached discovery, re-resolve the entry point, and publish metrics."""
    global _last_ground_entry_point_refresh_monotonic

    invalidate_cached_ground_entry_point()
    entry_point = get_cached_ground_entry_point()
    publish_ground_entry_point_metrics(entry_point)
    _last_ground_entry_point_refresh_monotonic = (
        time.monotonic() if now_monotonic is None else now_monotonic
    )
    return entry_point


def maybe_refresh_ground_entry_point_metrics(
    refresh_interval_seconds: float | None = None,
    now_monotonic: float | None = None,
) -> GroundEntryPoint | None:
    """Refresh entry-point metrics only when the periodic refresh interval has elapsed."""
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

    if _last_ground_entry_point_refresh_monotonic is None or (
        current_monotonic - _last_ground_entry_point_refresh_monotonic
    ) >= interval_seconds:
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
        city=os.getenv("STARLINK_GROUND_ENTRY_CITY", ""),
        country=os.getenv("STARLINK_GROUND_ENTRY_COUNTRY", ""),
        latitude=latitude,
        longitude=longitude,
    )
