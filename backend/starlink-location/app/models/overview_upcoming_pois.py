"""Response models for the Overview upcoming mission POIs endpoint."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_serializer

from app.models.poi import MissionPoiKind

OverviewUpcomingPoisState = Literal[
    "available",
    "no_active_mission",
    "route_unavailable",
    "inconsistent_active_mission",
    "no_generated_pois",
    "no_upcoming_pois",
    "unavailable",
]


class OverviewUpcomingPoi(BaseModel):
    """A generated mission POI projected for the Overview."""

    poi_id: str
    name: str
    kind: MissionPoiKind
    latitude: float
    longitude: float
    projected_route_progress: float | None = None
    expected_arrival_time: datetime | None = Field(
        default=None,
        description="Scheduled mission-plan time; never telemetry.",
    )
    eta_seconds: float | None = Field(
        default=None,
        description="Dynamic route-aware estimate; absent when not calculable.",
    )
    estimated_arrival_time: datetime | None = Field(
        default=None,
        description="calculated_at plus eta_seconds; never a scheduled timestamp.",
    )
    eta_type: Literal["anticipated", "estimated"]
    flight_phase: str
    upcoming: bool
    map_retained: bool


class OverviewUpcomingPoisResponse(BaseModel):
    """Overview POIs and their availability state."""

    state: OverviewUpcomingPoisState
    calculated_at: datetime
    pois: list[OverviewUpcomingPoi] = Field(default_factory=list)

    @property
    def top_five(self) -> list[OverviewUpcomingPoi]:
        """Return the next five table rows in dynamic ETA order."""
        upcoming = [poi for poi in self.pois if poi.upcoming]
        return sorted(
            upcoming,
            key=lambda poi: (
                poi.eta_seconds is None,
                poi.eta_seconds if poi.eta_seconds is not None else float("inf"),
                (
                    poi.projected_route_progress
                    if poi.projected_route_progress is not None
                    else float("inf")
                ),
                poi.name,
            ),
        )[:5]

    @field_serializer("calculated_at")
    def serialize_calculated_at(self, value: datetime) -> str:
        """Preserve an explicit UTC offset in the API contract."""
        return value.isoformat()
