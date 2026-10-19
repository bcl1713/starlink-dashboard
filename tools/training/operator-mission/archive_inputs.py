"""Explicit #370 synthetic operational-format archive inputs, not replay data."""

import importlib.util
import json
import os
import sys
from pathlib import Path


def run(root):
    if os.getenv("OPERATOR_TRAINING_FIXTURE") != "explicit-private-training-v1":
        raise ValueError("Explicit private training fixture required")
    spec = importlib.util.spec_from_file_location(
        "operator_training_archive_scenario", Path(__file__).with_name("scenario.py")
    )
    scenario = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scenario)
    namespace = scenario.training_namespace(root, mode="simulation")
    from app.mission import storage
    from app.services.flight_events.live_adapter import FlightEventRuntime
    from scenario import START, ScenarioClock, SyntheticRawReader, flight_observations

    storage.MISSIONS_DIR = root / "missions"
    missions = storage.list_mission_metadata_v2()
    if len(missions) != 1:
        raise ValueError("Exactly one private fixture mission required")
    mission = storage.load_mission_v2(missions[0].id)
    marker = mission.metadata.get("operator_training_fixture", {})
    if marker.get("namespace") != namespace:
        raise ValueError("Private mission namespace differs")
    provenance = {
        "synthetic": True,
        "source_format": "synthetic-operational-format",
        "relation_to_replay": "independent archive exercise; not replay measurements or aircraft data",
        "existing_fixture": "tools/acceptance/operator-journal/scenario.py:flight_observations/SyntheticRawReader",
    }
    existing = mission.metadata.get("operator_training_archive_inputs")
    if existing is not None and existing != provenance:
        raise ValueError("Archive input provenance differs; preserve for review")
    runtime = FlightEventRuntime(root / "synthetic-operational-archive")
    try:
        for index, leg in enumerate(mission.legs):
            for observation in flight_observations(
                ScenarioClock(), mission.id, leg.id, offset=index * 2700
            ):
                observation.route_id = leg.route_id
                runtime.accept(observation)
        from datetime import timedelta

        clock = ScenarioClock(START + timedelta(hours=2))
        for _ in range(500):
            clock.advance(300)
            runtime.capture.backfill_one(SyntheticRawReader(), clock.now())
            runtime.capture.recover(clock.now())
        captures = [runtime.archive.capture(mission.id, leg.id) for leg in mission.legs]
        assert all(capture and capture["state"] == "sealed" for capture in captures)
        if existing is None:
            mission.metadata["operator_training_archive_inputs"] = provenance
            storage.save_mission_v2(mission)
        return {**provenance, "mission_id": mission.id, "sealedLegs": len(captures)}
    finally:
        runtime.close()


if __name__ == "__main__":
    print(json.dumps(run(Path(sys.argv[1]))))
