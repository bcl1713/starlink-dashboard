"""Pydantic models for GPS configuration API."""

from pydantic import BaseModel, Field


class GPSConfigRequest(BaseModel):
    """Request model for updating GPS configuration."""

    enabled: bool = Field(description="Whether to enable GPS for position data")


class GPSConfigResponse(BaseModel):
    """Response model for GPS configuration status."""

    enabled: bool = Field(description="Whether GPS is enabled for position data")
    ready: bool = Field(description="Whether GPS is ready to provide position data")
    satellites: int = Field(description="Number of satellites in view")
