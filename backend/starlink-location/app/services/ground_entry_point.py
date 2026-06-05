"""Ground entry point discovery and Prometheus publication."""

from __future__ import annotations

import logging
import os
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


def publish_ground_entry_point_metrics(entry_point: GroundEntryPoint | None) -> None:
    """Publish ground entry point metrics for Grafana and Prometheus exports."""
    if entry_point is None:
        return

    lat_label = f"{entry_point.latitude:.6g}"
    lon_label = f"{entry_point.longitude:.6g}"
    starlink_ground_entry_point_latitude_degrees.set(entry_point.latitude)
    starlink_ground_entry_point_longitude_degrees.set(entry_point.longitude)
    starlink_ground_entry_point_location.labels(
        lat=lat_label,
        lon=lon_label,
        city=entry_point.city,
        country=entry_point.country,
        ip=entry_point.ip,
    ).set(1)
    starlink_ground_entry_point_info.labels(
        city=entry_point.city,
        country=entry_point.country,
        ip=entry_point.ip,
    ).set(1)


def refresh_ground_entry_point_metrics() -> GroundEntryPoint | None:
    """Resolve the cached ground entry point and publish its metrics."""
    entry_point = get_cached_ground_entry_point()
    publish_ground_entry_point_metrics(entry_point)
    return entry_point


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
