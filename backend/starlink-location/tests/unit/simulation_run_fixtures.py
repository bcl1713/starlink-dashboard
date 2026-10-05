"""Hand-timed replay fixtures; no external feeds or wall-clock dependencies."""

from datetime import datetime, timedelta, timezone

from app.mission.models import MissionLeg, TransportConfig
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint, RouteTimingProfile
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager

BASE = datetime(2025, 1, 1, tzinfo=timezone.utc)


def timed_plan_sources(tmp_path):
    route = ParsedRoute(
        metadata=RouteMetadata(name="Replay", file_path="replay.kml", point_count=3),
        points=[
            RoutePoint(
                latitude=0,
                longitude=lon,
                sequence=i,
                expected_arrival_time=BASE + timedelta(seconds=sec),
            )
            for i, (lon, sec) in enumerate([(0, 0), (1, 300), (2, 1200)])
        ],
        timing_profile=RouteTimingProfile(
            departure_time=BASE,
            arrival_time=BASE + timedelta(seconds=1200),
            has_timing_data=True,
        ),
    )
    routes = RouteManager(tmp_path / "routes")
    routes._routes["replay"] = route
    pois = POIManager(tmp_path / "pois.json")
    leg = MissionLeg(
        id="leg-1",
        name="Replay",
        route_id="replay",
        transports=TransportConfig(initial_x_satellite_id="X-1"),
        adjusted_departure_time=BASE + timedelta(hours=1),
    )
    return leg, routes, pois


class Clocks:
    def __init__(self):
        self.elapsed = 0.0
        self.utc = datetime(2026, 10, 5, tzinfo=timezone.utc)

    def monotonic(self):
        return self.elapsed

    def utc_now(self):
        return self.utc

    def advance(self, seconds):
        self.elapsed += seconds
        self.utc += timedelta(seconds=seconds)
