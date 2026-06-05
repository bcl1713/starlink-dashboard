"""Tests for ground entry point discovery and metric formatting."""

from __future__ import annotations

from prometheus_client import generate_latest

from app.core.metrics import REGISTRY
from app.services.ground_entry_point import (
    GroundEntryPoint,
    publish_ground_entry_point_metrics,
)


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
