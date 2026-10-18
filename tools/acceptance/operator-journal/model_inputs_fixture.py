"""Acceptance-only raw inputs; normal production adapter calculates every event."""

import json
from datetime import timedelta
from pathlib import Path

from events_fixture import EventsClock, seed_events
from scenario import START

from app.mission import storage
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint, RouteTimingProfile
from app.operator.time_models import utc_timestamp

MISSION, LEG = "synthetic-mission-a", "synthetic-leg-1"


class ModelClock(EventsClock):
    def __init__(self, root):
        super().__init__(root)
        path = Path(root) / "operator" / "synthetic-model-inputs.json"
        if path.exists():
            self.set(json.loads(path.read_text())["now"])
        else:
            self.set(START + timedelta(minutes=10))


class ModelInputsFixture:
    def __init__(self, main, runtime, root, clock):
        self.main, self.runtime, self.clock = main, runtime, clock
        self.path = Path(root) / "operator" / "synthetic-model-inputs.json"
        self.state = (
            json.loads(self.path.read_text())
            if self.path.exists()
            else {
                "now": clock.now().isoformat(),
                "longitude": -5,
                "route_shift": 0,
                "satellite_longitude": 90,
                "stale": False,
                "missing_pop": False,
                "active": True,
            }
        )
        self.ids = seed_events(runtime.service, clock)
        self.update({})

    def update(self, changes):
        if set(changes) - set(self.state):
            raise ValueError("Unknown raw input")
        with storage.get_active_leg_lock():
            state = self.state | changes
            self.clock.set(utc_timestamp(state["now"]))
            data = Path("data")
            coverage = data / "sat_coverage"
            coverage.mkdir(parents=True, exist_ok=True)
            (coverage / "commka.geojson").write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {"satellite_id": "AOR"},
                                "geometry": {
                                    "type": "Polygon",
                                    "coordinates": [
                                        [
                                            [-20, -10],
                                            [20, -10],
                                            [20, 10],
                                            [-20, 10],
                                            [-20, -10],
                                        ]
                                    ],
                                },
                            }
                        ],
                    }
                )
            )
            satellites = data / "satellites"
            satellites.mkdir(exist_ok=True)
            (satellites / "catalog.yaml").write_text(
                "satellites:\n  - id: X-1\n    transport: X\n    longitude: "
                + str(state["satellite_longitude"])
                + "\n"
            )
            pop_path = data / "operator" / "synthetic-pops.json"
            if state["missing_pop"]:
                pop_path.unlink(missing_ok=True)
            else:
                pop_path.write_text(
                    json.dumps(
                        {
                            "sites": [
                                {
                                    "id": name,
                                    "city": name,
                                    "country": "US",
                                    "latitude": 0,
                                    "longitude": lon,
                                    "source": "synthetic",
                                    "coordinate_source": "synthetic",
                                }
                                for name, lon in [("a", -5), ("b", 15)]
                            ]
                        }
                    )
                )
            coordinator = self.main._coordinator
            config = coordinator.get_config().model_copy(deep=True)
            if config.pop.catalog_path != pop_path:
                config.pop.catalog_path = pop_path
                coordinator.update_config(config)
            mission = storage.load_mission_v2(MISSION)
            for leg in mission.legs:
                leg.is_active = leg.id == LEG and state["active"]
                leg.transports.starshield_enabled = True
            storage.save_mission_v2(mission)
            route_id = mission.legs[0].route_id
            start = START + timedelta(minutes=state["route_shift"])
            route = ParsedRoute(
                route_id=route_id,
                metadata=RouteMetadata(
                    name="Synthetic current route",
                    file_path="synthetic.kml",
                    point_count=3,
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
                    departure_time=start,
                    arrival_time=start + timedelta(minutes=40),
                    has_timing_data=True,
                ),
            )
            manager = self.main.app.state.route_manager
            manager.add_route(route_id, route)
            manager.activate_route(route_id)
            sample = coordinator.get_current_telemetry().model_copy(deep=True)
            sample.position.latitude, sample.position.longitude = 0, state["longitude"]
            sample.position.speed, sample.position.heading = 600, 90
            observed = self.clock.now() - timedelta(seconds=60 if state["stale"] else 0)
            sample.position.observed_at = observed
            sample.position.speed_observed_at = observed
            coordinator.restore_telemetry(sample)
            self.state = state
            self.path.write_text(json.dumps(state))
            return {"synthetic": True, "rawInputsOnly": True, "ids": self.ids, **state}
