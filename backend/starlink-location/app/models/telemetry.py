"""Pydantic telemetry data models for Starlink simulator."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PositionData(BaseModel):
    """Position telemetry data."""

    latitude: float = Field(
        ...,
        description="Latitude in decimal degrees (-90 to 90)"
    )
    longitude: float = Field(
        ...,
        description="Longitude in decimal degrees (-180 to 180)"
    )
    altitude: float = Field(
        ...,
        description="Altitude in feet above sea level"
    )
    speed: float = Field(
        default=0.0,
        description="Speed in knots"
    )
    heading: float = Field(
        default=0.0,
        description="Heading in degrees (0-360, 0=North)"
    )


class NetworkData(BaseModel):
    """Network metrics telemetry data."""

    latency_ms: float = Field(
        ...,
        description="Round-trip latency in milliseconds"
    )
    throughput_down_mbps: float = Field(
        ...,
        description="Download throughput in Mbps"
    )
    throughput_up_mbps: float = Field(
        ...,
        description="Upload throughput in Mbps"
    )
    packet_loss_percent: float = Field(
        ...,
        description="Packet loss as percentage (0-100)"
    )


class ObstructionData(BaseModel):
    """Obstruction telemetry data."""

    obstruction_percent: float = Field(
        ...,
        description="Obstruction percentage (0-100)"
    )


class EnvironmentalData(BaseModel):
    """Environmental and status telemetry data."""

    signal_quality_percent: float = Field(
        default=100.0,
        description="Signal quality as percentage (0-100)"
    )
    uptime_seconds: float = Field(
        default=0.0,
        description="System uptime in seconds"
    )
    temperature_celsius: Optional[float] = Field(
        default=None,
        description="Equipment temperature in Celsius"
    )


class TelemetryData(BaseModel):
    """Complete telemetry data from simulator."""

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )

    timestamp: datetime = Field(
        ...,
        description="Timestamp of telemetry sample"
    )
    position: PositionData = Field(
        ...,
        description="Position information"
    )
    network: NetworkData = Field(
        ...,
        description="Network metrics"
    )
    obstruction: ObstructionData = Field(
        ...,
        description="Obstruction information"
    )
    environmental: EnvironmentalData = Field(
        default_factory=EnvironmentalData,
        description="Environmental and status information"
    )
