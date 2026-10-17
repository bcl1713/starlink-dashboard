"""Synthetic inputs only; prediction and detection stay in production services."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.mission.models import (
    Mission,
    MissionLeg,
    MissionLegTimeline,
    TimelineSegment,
    TransportConfig,
)
from app.operator.clock import Clock
from app.operator.models import CreateRecord

RUN_ID = "synthetic-operator-demo-v1"
START = datetime(2026, 10, 17, 16, tzinfo=timezone.utc)


class ScenarioClock:
    """Process-local acceptance clock; never exposed over HTTP."""

    def __init__(self, now=START):
        self.current, self.elapsed = now, 0.0

    def now(self):
        return self.current

    def monotonic(self):
        return self.elapsed

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("Scenario clock advances must be nonnegative")
        self.current += timedelta(seconds=seconds)
        self.elapsed += seconds


def make_demo(clock: Clock) -> dict:
    missions = [
        Mission(
            id=f"synthetic-mission-{letter}",
            name=f"Synthetic Mission {letter.upper()}",
            legs=[
                MissionLeg(
                    id=f"synthetic-leg-{index}",
                    name=f"Synthetic Leg {index}",
                    route_id="synthetic-route",
                    transports=TransportConfig(initial_x_satellite_id="X-1"),
                )
                for index in (1, 2)
            ],
        )
        for letter in ("a", "b")
    ]
    commands = []
    for mission in missions:
        for kind in ("journal_entry", "conference", "transport_report"):
            payload = {
                "entry_type": "note" if kind == "journal_entry" else kind,
                "title": f"Synthetic {kind}",
                "note": "Synthetic acceptance input; no measured routing verification",
            }
            if kind == "transport_report":
                payload.update(transport="Ka", status="reported_available")
            commands.append(
                CreateRecord(
                    record_type=kind,
                    mission_id=mission.id,
                    leg_id=mission.legs[0].id if kind == "journal_entry" else None,
                    scope="leg" if kind == "journal_entry" else "mission",
                    time={
                        "occurred_at": clock.now(),
                        "precision": "exact",
                        "end_state": "ongoing" if kind == "conference" else "instant",
                    },
                    payload=payload,
                )
            )
    return {
        "synthetic": True,
        "run_id": RUN_ID,
        "missions": missions,
        "commands": commands,
        "observations": {"pop_status": "unknown", "source_mode": "simulation"},
    }


def pop_inputs(clock, *, fallback=None):
    """Build a known route and independent transport inputs, never predictions."""
    from app.mission.pop_forecast import forecast_for_mission, mission_forecast_revision
    from app.mission.timeline_builder.calculator import RouteTemporalProjector
    from app.models.route import (
        ParsedRoute,
        RouteMetadata,
        RoutePoint,
        RouteTimingProfile,
    )
    from app.services.pop.models import PopCatalog, PopObservation, PopSite

    start, end = clock.now(), clock.now() + timedelta(minutes=40)
    route = ParsedRoute(
        metadata=RouteMetadata(
            name="Synthetic route", file_path="synthetic.kml", point_count=3
        ),
        points=[
            RoutePoint(
                latitude=0,
                longitude=lon,
                sequence=i,
                expected_arrival_time=start + timedelta(minutes=minute),
                expected_segment_speed_knots=600,
            )
            for i, (lon, minute) in enumerate([(-10, 0), (0, 10), (10, 40)])
        ],
        timing_profile=RouteTimingProfile(
            departure_time=start, arrival_time=end, has_timing_data=True
        ),
    )
    catalog = PopCatalog(
        sites=tuple(
            PopSite(
                id=f"synthetic-{name}",
                city=f"Synthetic {name}",
                country="US",
                latitude=0,
                longitude=lon,
                source="synthetic",
                coordinate_source="synthetic",
            )
            for name, lon in [("a", -5), ("b", 15)]
        ),
        fingerprint="synthetic-pop-v1",
    )
    projector = RouteTemporalProjector(route, start, end)
    ka = "available" if fallback == "Ka" else "offline"
    raw = ["x_aft_cone"] if fallback == "X" else ["x_elevation"]
    interval = {
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "physical_x_state": "available" if fallback == "X" else "degraded",
        "physical_ka_state": ka,
        "physical_ku_state": "available",
        "policy_x_state": "offline",
        "policy_ka_state": ka,
        "policy_ku_state": "available",
        "raw_constraints": raw,
        "physical_reasons": [],
        "policy_reasons": [],
    }
    timeline = MissionLegTimeline(
        mission_leg_id="synthetic-leg-1",
        segments=[
            TimelineSegment(
                id="synthetic-segment",
                start_time=start,
                end_time=end,
                status="degraded",
                x_state="offline",
                ka_state=ka,
                ku_state="available",
                metadata={
                    "planning_policy": "prefer_starshield_v1",
                    "planning_interval": interval,
                    "transport_constraints": {"X": raw},
                },
            )
        ],
        pop_forecast=forecast_for_mission(
            route,
            projector,
            catalog,
            revision=mission_forecast_revision(route, projector, catalog),
            starshield_enabled=True,
        ),
    )
    sample = SimpleNamespace(
        position=SimpleNamespace(
            latitude=0,
            longitude=-10,
            speed=300,
            observed_at=start,
            speed_observed_at=start,
        )
    )
    return {
        "route": route,
        "catalog": catalog,
        "projector": projector,
        "timeline": timeline,
        "telemetry": sample,
        "observation": PopObservation(
            ip=None, entry=None, status="unknown", source="simulation"
        ),
        "mode": "simulation",
        "enabled": True,
        "now": start,
        "observed_now": start,
        "lifecycle_token": RUN_ID,
    }


def flight_observations(clock, mission, leg, *, offset=0):
    """Synthetic operational-format inputs; never used by simulation acceptance."""
    from app.services.flight_events.models import FlightObservation

    for second in range(711):
        speed, altitude = 0, 100
        if 301 <= second <= 320:
            speed = 10
        elif 321 <= second <= 350:
            speed, altitude = 120, 500
        elif 351 <= second <= 360:
            speed, altitude = 200, 10000
        elif 361 <= second <= 400:
            speed = 25
        now = clock.now() + timedelta(seconds=offset + second)
        yield FlightObservation(
            observed_at=now,
            received_at=now,
            position_observed_at=now,
            speed_observed_at=now,
            altitude_observed_at=now,
            altitude_validity_source="synthetic-operational-format",
            altitude_usable=True,
            latitude=40,
            longitude=-70,
            speed_knots=speed,
            altitude_feet=altitude,
            destination_distance_m=1000,
            source_mode="live",
            mission_id=mission,
            leg_id=leg,
            route_id="synthetic-route",
        )


class SyntheticRawReader:
    """Sparse synthetic raw samples deliberately preserve collection gaps."""

    def read(self, begin, end):
        return [
            (
                begin + timedelta(seconds=second),
                "starlink_dish_speed_knots",
                {"source": "synthetic-operational-format"},
                0,
                "live",
                begin,
            )
            for second in range(0, int((end - begin).total_seconds()) + 1, 30)
        ]
