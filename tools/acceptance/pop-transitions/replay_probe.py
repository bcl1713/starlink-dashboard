"""Actual-image physical replay baselines, distinct from planner call availability."""

import json
import sys
from pathlib import Path

from app.mission import storage
from app.mission.exporter.snapshot_pop import capture_pop_catalog, captured_pop_catalog
from app.mission.planning.sources import SourceStore
from app.mission.timeline_preparation import prepare_mission_timeline
from app.mission.timeline_service import _get_default_coverage_sampler
from app.models.simulation_run import TargetRuntimePacing
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from app.simulation.run_plan import prepare_mission_run
from app.simulation.run_replay import project_run_frame


def main():
    records = json.loads(sys.argv[1])
    data_root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/data")
    sources = SourceStore(storage.MISSIONS_DIR, data_root / "routes")
    routes = RouteManager(
        data_root / "routes", profile_resolver=sources.resolve_profile
    )
    routes._load_existing_routes()
    pois = POIManager(data_root / "pois.json")
    sampler = _get_default_coverage_sampler()
    catalog = captured_pop_catalog(capture_pop_catalog())
    assert catalog is not None, "Physical probe requires captured ready catalog"
    results = {}
    for name, item in records.items():
        mission = storage.load_mission_v2(item["missionId"])
        leg = next(leg for leg in mission.legs if leg.id == item["legId"])
        plan = prepare_mission_run(
            mission.id,
            leg,
            TargetRuntimePacing(
                mode="target_runtime", runtime_seconds=300 if name == "crossing" else 20
            ),
            routes,
            pois,
            sampler,
        )
        control = prepare_mission_timeline(
            leg.model_copy(deep=True),
            routes,
            pois,
            sampler,
            mission.id,
            normalize_for_simulation=True,
            pop_catalog=None,
        )
        # This is an actual second preparation with no available PoP catalog.
        # It must retain every physical event, including real landing blackouts.
        actual_events = json.dumps(
            [vars(event) for event in plan.artifacts.events],
            default=str,
            sort_keys=True,
        )
        control_events = json.dumps(
            [vars(event) for event in control.events], default=str, sort_keys=True
        )
        assert actual_events == control_events, (
            name,
            "PoP changed physical replay events",
        )
        start, end = (
            plan.artifacts.projector.start_time,
            plan.artifacts.projector.end_time,
        )
        boundaries = sorted(
            {
                start,
                end,
                *(
                    e.timestamp
                    for e in plan.replay_events
                    if start <= e.timestamp <= end
                ),
            }
        )
        frames = []
        for index, at in enumerate(boundaries):
            frame = project_run_frame(plan, at, None)
            frames.append(
                {
                    "startUtc": at.isoformat(),
                    "endUtc": (
                        boundaries[index + 1].isoformat()
                        if index + 1 < len(boundaries)
                        else None
                    ),
                    "transportStates": {
                        transport.value: state.value
                        for transport, state in frame.transport_states.items()
                    },
                }
            )
        assert (
            plan.artifacts.timeline.pop_forecast.catalog_fingerprint
            == catalog.fingerprint
        )
        endpoint = plan.artifacts.route.points[-1]
        results[name] = {
            "catalogSites": [site.model_dump(mode="json") for site in catalog.sites],
            "endpoint": {
                "latitude": endpoint.latitude,
                "longitude": endpoint.longitude,
            },
            "frames": frames,
            "physicalEventsUnchangedWithUnavailablePopCatalog": True,
            "physicalEvents": json.loads(actual_events),
            "preparedForecast": plan.artifacts.timeline.pop_forecast.model_dump(
                mode="json"
            ),
            "planningPolicy": leg.transports.planning_policy,
        }
    print(
        json.dumps(
            {
                "basis": "Actual shipped prepared physical replay frames at exact UTC event boundaries; separate from saved planner availability",
                "cases": results,
            }
        )
    )


if __name__ == "__main__":
    main()
