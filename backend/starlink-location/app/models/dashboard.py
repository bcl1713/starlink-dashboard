"""Strict response models for dashboard telemetry."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DashboardModel(BaseModel):
    """Forbid accidental fields and non-finite values in public DTOs."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class StatusPosition(DashboardModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    altitude: float
    speed: float = Field(ge=0)
    heading: float = Field(ge=0, le=360)


class StatusNetwork(DashboardModel):
    latency_ms: float = Field(ge=0)
    throughput_down_mbps: float = Field(ge=0)
    throughput_up_mbps: float = Field(ge=0)
    packet_loss_percent: float = Field(ge=0, le=100)


class StatusObstruction(DashboardModel):
    obstruction_percent: float = Field(ge=0, le=100)


class StatusEnvironmental(DashboardModel):
    signal_quality_percent: float = Field(ge=0, le=100)
    uptime_seconds: float = Field(ge=0)
    temperature_celsius: float | None


class StatusResponse(DashboardModel):
    source: Literal["simulation", "live"]
    timestamp: datetime
    observed_at: datetime
    received_at: datetime
    position: StatusPosition
    network: StatusNetwork
    obstruction: StatusObstruction
    environmental: StatusEnvironmental


MetricName = Literal[
    "latitude_degrees",
    "longitude_degrees",
    "latency_ms",
    "throughput_down_mbps",
    "throughput_up_mbps",
    "packet_loss_percent",
]


class HistorySample(DashboardModel):
    timestamp: datetime
    value: float | None


class HistorySeries(DashboardModel):
    metric: MetricName
    samples: list[HistorySample]


class HistoryResponse(DashboardModel):
    generated_at: datetime
    window_start: datetime
    window_end: datetime
    range_seconds: int = Field(ge=60, le=1800)
    step_seconds: int = Field(ge=1, le=30)
    series: list[HistorySeries]

    @model_validator(mode="after")
    def validate_window(self) -> "HistoryResponse":
        if [item.metric for item in self.series] != list(METRIC_ORDER):
            raise ValueError("history series order is invalid")
        return self


class GroundEntryPointResponse(DashboardModel):
    available: bool
    observed_at: datetime | None
    generated_at: datetime
    display: str | None
    city: str | None
    region: str | None
    country: str | None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


METRIC_ORDER: tuple[MetricName, ...] = (
    "latitude_degrees",
    "longitude_degrees",
    "latency_ms",
    "throughput_down_mbps",
    "throughput_up_mbps",
    "packet_loss_percent",
)


def utc(value: datetime) -> datetime:
    """Require an aware instant and normalize it to UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)
