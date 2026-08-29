"""Tests for strict monitoring response DTOs."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.monitoring import (
    ActiveLinkResponse,
    GroundEntryPointResponse,
    MonitoringHistoryRequest,
    MonitoringHistoryResponse,
    MonitoringSample,
    MonitoringSeries,
    RouteCoordinateResponse,
)

UTC_NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


def test_monitoring_history_contract_forbids_extra_fields_and_serializes_utc() -> None:
    response = MonitoringHistoryResponse(
        generated_at=UTC_NOW,
        window_start=UTC_NOW,
        window_end=UTC_NOW,
        range_seconds=60,
        step_seconds=10,
        series=[
            MonitoringSeries(metric=metric, samples=[])
            for metric in MonitoringHistoryResponse.metric_order()
        ],
    )

    assert list(response.model_dump(mode="json")) == [
        "generated_at",
        "window_start",
        "window_end",
        "range_seconds",
        "step_seconds",
        "series",
    ]
    assert response.model_dump(mode="json")["generated_at"].endswith("Z")

    with pytest.raises(ValidationError):
        MonitoringSample(timestamp=UTC_NOW, value=1.0, extra=True)


def test_datetime_fields_reject_naive_and_normalize_to_utc() -> None:
    eastern = datetime.fromisoformat("2026-08-29T08:00:00-04:00")
    sample = MonitoringSample(timestamp=eastern, value=2.5)

    assert sample.timestamp == UTC_NOW
    assert sample.model_dump(mode="json")["timestamp"] == "2026-08-29T12:00:00Z"

    with pytest.raises(ValidationError):
        MonitoringSample(
            timestamp=datetime(2026, 8, 29, 12, 0),  # noqa: DTZ001
            value=1.0,
        )


def test_metric_literals_and_series_order_are_strict() -> None:
    with pytest.raises(ValidationError):
        MonitoringSeries(metric="cpu_percent", samples=[])

    series = [
        MonitoringSeries(metric="longitude_degrees", samples=[]),
        MonitoringSeries(metric="latitude_degrees", samples=[]),
        MonitoringSeries(metric="latency_ms", samples=[]),
        MonitoringSeries(metric="throughput_down_mbps", samples=[]),
        MonitoringSeries(metric="throughput_up_mbps", samples=[]),
        MonitoringSeries(metric="packet_loss_percent", samples=[]),
    ]
    with pytest.raises(ValidationError):
        MonitoringHistoryResponse(
            generated_at=UTC_NOW,
            window_start=UTC_NOW,
            window_end=UTC_NOW,
            range_seconds=60,
            step_seconds=10,
            series=series,
        )


def test_history_request_bounds_when_represented_internally() -> None:
    assert MonitoringHistoryRequest(range_seconds=60, step_seconds=1)
    assert MonitoringHistoryRequest(range_seconds=3600, step_seconds=60)

    for field, value in [
        ("range_seconds", 59),
        ("range_seconds", 3601),
        ("step_seconds", 0),
        ("step_seconds", 61),
    ]:
        kwargs = {"range_seconds": 60, "step_seconds": 10}
        kwargs[field] = value
        with pytest.raises(ValidationError):
            MonitoringHistoryRequest(**kwargs)


def test_ground_entry_point_response_has_no_public_ip_field() -> None:
    fields = set(GroundEntryPointResponse.model_fields)

    assert "ip" not in fields
    assert "public_ip" not in fields
    assert fields == {
        "available",
        "observed_at",
        "generated_at",
        "display",
        "city",
        "region",
        "country",
        "latitude",
        "longitude",
    }


def test_phase_one_freshness_dtos_are_strict_and_utc_aware() -> None:
    active = ActiveLinkResponse(
        active=True,
        observed_at=UTC_NOW,
        generated_at=UTC_NOW,
    )
    route = RouteCoordinateResponse(
        latitude=40.0,
        longitude=-73.0,
        altitude_meters=None,
        revision_at=UTC_NOW,
        generated_at=UTC_NOW,
    )

    assert active.model_dump(mode="json")["generated_at"].endswith("Z")
    assert route.model_dump(mode="json")["revision_at"].endswith("Z")

    with pytest.raises(ValidationError):
        ActiveLinkResponse(active=True, generated_at=UTC_NOW, extra=True)
