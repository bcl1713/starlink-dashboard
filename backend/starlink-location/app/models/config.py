"""Pydantic configuration models for Starlink simulator."""

from pydantic import BaseModel, Field, field_validator
from typing import Literal


class RouteConfig(BaseModel):
    """Configuration for route simulation."""

    pattern: Literal["circular", "straight"] = Field(
        default="circular",
        description="Route pattern: circular or straight line"
    )
    latitude_start: float = Field(
        default=40.7128,
        description="Starting latitude (degrees)"
    )
    longitude_start: float = Field(
        default=-74.0060,
        description="Starting longitude (degrees)"
    )
    radius_km: float = Field(
        default=100.0,
        description="Radius for circular route (kilometers)"
    )
    distance_km: float = Field(
        default=500.0,
        description="Total distance for straight route (kilometers)"
    )

    @field_validator("radius_km", "distance_km")
    @classmethod
    def validate_positive(cls, v: float) -> float:
        """Ensure distance values are positive."""
        if v <= 0:
            raise ValueError("Distance values must be positive")
        return v


class NetworkConfig(BaseModel):
    """Configuration for network metrics simulation."""

    latency_min_ms: float = Field(
        default=20.0,
        description="Minimum latency (milliseconds)"
    )
    latency_typical_ms: float = Field(
        default=50.0,
        description="Typical latency (milliseconds)"
    )
    latency_max_ms: float = Field(
        default=80.0,
        description="Maximum latency without spikes (milliseconds)"
    )
    latency_spike_max_ms: float = Field(
        default=200.0,
        description="Maximum latency with spikes (milliseconds)"
    )
    spike_probability: float = Field(
        default=0.05,
        description="Probability of latency spike (0.0-1.0)"
    )

    throughput_down_min_mbps: float = Field(
        default=50.0,
        description="Minimum download throughput (Mbps)"
    )
    throughput_down_max_mbps: float = Field(
        default=200.0,
        description="Maximum download throughput (Mbps)"
    )
    throughput_up_min_mbps: float = Field(
        default=10.0,
        description="Minimum upload throughput (Mbps)"
    )
    throughput_up_max_mbps: float = Field(
        default=40.0,
        description="Maximum upload throughput (Mbps)"
    )

    packet_loss_min_percent: float = Field(
        default=0.0,
        description="Minimum packet loss percentage (0.0-100.0)"
    )
    packet_loss_max_percent: float = Field(
        default=5.0,
        description="Maximum packet loss percentage (0.0-100.0)"
    )

    @field_validator("spike_probability")
    @classmethod
    def validate_probability(cls, v: float) -> float:
        """Ensure probability is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Probability must be between 0.0 and 1.0")
        return v

    @field_validator("packet_loss_min_percent", "packet_loss_max_percent")
    @classmethod
    def validate_packet_loss(cls, v: float) -> float:
        """Ensure packet loss is between 0 and 100."""
        if not 0.0 <= v <= 100.0:
            raise ValueError("Packet loss must be between 0.0 and 100.0")
        return v


class ObstructionConfig(BaseModel):
    """Configuration for obstruction simulation."""

    min_percent: float = Field(
        default=0.0,
        description="Minimum obstruction percentage"
    )
    max_percent: float = Field(
        default=30.0,
        description="Maximum obstruction percentage"
    )
    variation_rate: float = Field(
        default=0.5,
        description="Rate of obstruction variation (0.0-1.0)"
    )

    @field_validator("min_percent", "max_percent")
    @classmethod
    def validate_obstruction_percent(cls, v: float) -> float:
        """Ensure obstruction percentage is between 0 and 100."""
        if not 0.0 <= v <= 100.0:
            raise ValueError("Obstruction percentage must be between 0.0 and 100.0")
        return v


class PositionConfig(BaseModel):
    """Configuration for position simulation."""

    speed_min_knots: float = Field(
        default=300.0,
        description="Minimum speed (knots)"
    )
    speed_max_knots: float = Field(
        default=350.0,
        description="Maximum speed (knots)"
    )
    altitude_min_feet: float = Field(
        default=328.0,
        description="Minimum altitude in feet (default ~100 meters)"
    )
    altitude_max_feet: float = Field(
        default=32808.0,
        description="Maximum altitude in feet (default ~10000 meters)"
    )
    heading_variation_rate: float = Field(
        default=5.0,
        description="Rate of heading variation (degrees per update)"
    )

    @field_validator("speed_min_knots", "speed_max_knots")
    @classmethod
    def validate_speed(cls, v: float) -> float:
        """Ensure speed values are non-negative."""
        if v < 0:
            raise ValueError("Speed must be non-negative")
        return v


class HeadingTrackerConfig(BaseModel):
    """Configuration for heading tracker service.

    The heading tracker calculates direction of movement based on GPS
    position changes over time.
    """

    min_distance_meters: float = Field(
        default=10.0,
        description="Minimum distance traveled to calculate heading (meters)"
    )
    max_age_seconds: float = Field(
        default=30.0,
        description="Maximum age of previous position for heading calculation (seconds)"
    )

    @field_validator("min_distance_meters", "max_age_seconds")
    @classmethod
    def validate_positive(cls, v: float) -> float:
        """Ensure configuration values are positive."""
        if v <= 0:
            raise ValueError("Configuration values must be positive")
        return v


class SimulationConfig(BaseModel):
    """Main simulation configuration."""

    mode: Literal["simulation", "live"] = Field(
        default="simulation",
        description="Operation mode: simulation or live"
    )
    update_interval_seconds: float = Field(
        default=1.0,
        description="Interval between metric updates (seconds)"
    )
    route: RouteConfig = Field(
        default_factory=RouteConfig,
        description="Route simulation configuration"
    )
    network: NetworkConfig = Field(
        default_factory=NetworkConfig,
        description="Network metrics simulation configuration"
    )
    obstruction: ObstructionConfig = Field(
        default_factory=ObstructionConfig,
        description="Obstruction simulation configuration"
    )
    position: PositionConfig = Field(
        default_factory=PositionConfig,
        description="Position simulation configuration"
    )
    heading_tracker: HeadingTrackerConfig = Field(
        default_factory=HeadingTrackerConfig,
        description="Heading tracker configuration"
    )

    @field_validator("update_interval_seconds")
    @classmethod
    def validate_update_interval(cls, v: float) -> float:
        """Ensure update interval is positive."""
        if v <= 0:
            raise ValueError("Update interval must be positive")
        return v
