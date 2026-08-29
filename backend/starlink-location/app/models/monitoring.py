"""Strict monitoring response models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MonitoringMetric = Literal[
    "latitude_degrees",
    "longitude_degrees",
    "latency_ms",
    "throughput_down_mbps",
    "throughput_up_mbps",
    "packet_loss_percent",
]

MONITORING_METRIC_ORDER: tuple[MonitoringMetric, ...] = (
    "latitude_degrees",
    "longitude_degrees",
    "latency_ms",
    "throughput_down_mbps",
    "throughput_up_mbps",
    "packet_loss_percent",
)


class StrictMonitoringModel(BaseModel):
    """Base for strict response DTOs with UTC-aware datetimes."""

    model_config = ConfigDict(extra="forbid", strict=True)

    @model_validator(mode="after")
    def _normalize_datetimes(self) -> StrictMonitoringModel:
        for field_name in self.__class__.model_fields:
            value = getattr(self, field_name)
            if isinstance(value, datetime):
                setattr(self, field_name, _as_utc(value))
        return self


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


class MonitoringSample(StrictMonitoringModel):
    """Single monitoring time-series point."""

    timestamp: datetime
    value: float | None


class MonitoringSeries(StrictMonitoringModel):
    """Samples for one allow-listed monitoring metric."""

    metric: MonitoringMetric
    samples: list[MonitoringSample]


class MonitoringHistoryRequest(StrictMonitoringModel):
    """Internal validated history parameters."""

    range_seconds: int = Field(ge=60, le=3600)
    step_seconds: int = Field(ge=1, le=60)


class MonitoringHistoryResponse(StrictMonitoringModel):
    """Monitoring history response."""

    generated_at: datetime
    window_start: datetime
    window_end: datetime
    range_seconds: int
    step_seconds: int
    series: list[MonitoringSeries]

    @classmethod
    def metric_order(cls) -> tuple[MonitoringMetric, ...]:
        return MONITORING_METRIC_ORDER

    @model_validator(mode="after")
    def _validate_series_order(self) -> MonitoringHistoryResponse:
        expected = list(MONITORING_METRIC_ORDER)
        actual = [series.metric for series in self.series]
        if actual != expected:
            raise ValueError("series must be in monitoring metric order")
        return self


class GroundEntryPointResponse(StrictMonitoringModel):
    """Ground entry point response without public IP disclosure."""

    available: bool
    observed_at: datetime | None
    generated_at: datetime
    display: str | None
    city: str | None
    region: str | None
    country: str | None
    latitude: float | None
    longitude: float | None


class ActiveLinkResponse(StrictMonitoringModel):
    """Active Starlink link freshness response."""

    active: bool
    observed_at: datetime | None = None
    generated_at: datetime


class ActiveXLinkCoordinate(StrictMonitoringModel):
    """Single aircraft or satellite endpoint in an active X-band link."""

    satellite_id: str
    state: str
    color: str
    relative_azimuth_degrees: float
    in_forbidden_window: bool
    point: str
    sequence: int
    latitude: float
    longitude: float
    observed_at: datetime | None


class ActiveXLinkItem(StrictMonitoringModel):
    """One rendered active X-band link segment."""

    satellite_id: str
    state: str
    color: str
    relative_azimuth_degrees: float
    in_forbidden_window: bool
    coordinates: list[ActiveXLinkCoordinate]


class ActiveXLinkResponse(StrictMonitoringModel):
    """Typed active X-band overlay response with truthful freshness fields."""

    coordinates: list[ActiveXLinkCoordinate]
    links: list[ActiveXLinkItem]
    total: int
    satellite_id: str | None
    pending_satellite_id: str | None
    handoff: dict[str, Any]
    state: str | None
    color: str | None
    relative_azimuth_degrees: float | None
    in_forbidden_window: bool | None
    observed_at: datetime | None
    generated_at: datetime


class RouteCoordinateResponse(StrictMonitoringModel):
    """Route coordinate freshness response."""

    latitude: float
    longitude: float
    altitude_meters: float | None = None
    revision_at: datetime | None
    generated_at: datetime


class RouteCoordinatePoint(StrictMonitoringModel):
    """Single tabular route coordinate."""

    latitude: float
    longitude: float
    altitude_meters: float | None = None
    sequence: float


class RouteCoordinatesResponse(StrictMonitoringModel):
    """Tabular route coordinate response with source and response freshness."""

    coordinates: list[RouteCoordinatePoint]
    total: int
    route_id: str | None
    route_name: str | None
    revision_at: datetime | None
    generated_at: datetime
