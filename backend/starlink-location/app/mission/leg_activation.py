"""Compensated paced activation; the runtime is the last commit point."""

import logging

from fastapi import HTTPException

from app.mission.storage import (
    get_active_leg_lock,
    get_leg_timeline_path,
    get_mission_lock,
    list_mission_metadata_v2,
    load_mission_v2,
    save_mission_timeline,
    save_mission_v2,
)
from app.mission.timeline_preparation import publish_mission_pois
from app.models.simulation_run import SimulationStart
from app.services.flight_state import get_flight_state_manager
from app.services.mission_clock_service import (
    apply_mission_activation_clock_settings,
    persist_mission_clock_settings_best_effort,
)
from app.services.overview_clock_geography import OfflineClockGeography
from app.services.overview_clock_location import resolve_clock_location
from app.services.overview_clock_settings import OverviewClockSettingsStore
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager
from app.simulation.run_service import SimulationRunService

logger = logging.getLogger(__name__)


def activate_leg_transaction(
    mission_id: str,
    leg_id: str,
    route_manager: RouteManager,
    poi_manager: POIManager,
    clock_settings_store: OverviewClockSettingsStore,
    run_service: SimulationRunService,
    simulation: SimulationStart,
    coverage_sampler=None,
) -> dict:
    with get_active_leg_lock():
        mission = load_mission_v2(mission_id)
        if mission is None:
            raise HTTPException(404, "Mission not found")
        leg = next((leg for leg in mission.legs if leg.id == leg_id), None)
        if leg is None:
            raise HTTPException(404, "Leg not found")
        if run_service.coordinator is None or run_service.publish is None:
            raise HTTPException(503, "Replay collection is not initialized")
        tick = run_service.prepare_start(mission_id, leg, simulation)
        missions = {
            metadata.id: load_mission_v2(metadata.id)
            for metadata in list_mission_metadata_v2()
        }
        missions[mission_id] = mission
        missions = {key: value for key, value in missions.items() if value is not None}
        snapshots = {
            key: parent.model_copy(deep=True) for key, parent in missions.items()
        }
        previous_route = route_manager.get_active_route_id()
        poi_checkpoint = poi_manager.checkpoint()
        flight = get_flight_state_manager()
        flight_checkpoint = flight.checkpoint()
        coordinator = run_service.coordinator
        telemetry_checkpoint = coordinator.checkpoint_telemetry()
        timeline_path = get_leg_timeline_path(leg_id, mission_id)
        timeline_bytes = timeline_path.read_bytes() if timeline_path.exists() else None
        changed = []
        try:
            for key, parent in sorted(missions.items()):
                for child in parent.legs:
                    child.is_active = key == mission_id and child.id == leg_id
                if parent != snapshots[key]:
                    changed.append(key)
                    with get_mission_lock(key):
                        save_mission_v2(parent)
            if (
                not route_manager.activate_route(leg.route_id)
                and route_manager.get_active_route_id() != leg.route_id
            ):
                raise RuntimeError("Target route could not be activated")
            publish_mission_pois(
                tick.plan.artifacts, poi_manager, mission_id, leg.route_id
            )
            # POIManager's legacy writer logs failures; verify durable publication.
            persisted = poi_manager.pois_file.read_text()
            import json

            saved = json.loads(persisted).get("pois", {})
            if set(saved) != {poi.id for poi in poi_manager.list_pois()}:
                raise OSError("Generated POIs were not persisted")
            save_mission_timeline(
                leg_id, tick.plan.artifacts.timeline, parent_mission_id=mission_id
            )
            telemetry = coordinator.update(replay_frame=tick.frame)
            run_service.publish(telemetry, tick)
            result = run_service.runtime.commit_tick(tick)
        except (
            RuntimeError,
            ValueError,
            OSError,
            TypeError,
            AttributeError,
            KeyError,
            LookupError,
        ) as exc:
            for key in changed:
                with get_mission_lock(key):
                    save_mission_v2(snapshots[key])
            route_manager.deactivate_route()
            if previous_route is not None:
                route_manager.activate_route(previous_route)
            poi_manager.restore_checkpoint(poi_checkpoint)
            if timeline_bytes is None:
                timeline_path.unlink(missing_ok=True)
            else:
                timeline_path.write_bytes(timeline_bytes)
            flight.restore_checkpoint(flight_checkpoint)
            coordinator.restore_telemetry(telemetry_checkpoint)
            from app.core.metrics import clear_telemetry_metrics

            clear_telemetry_metrics()
            logger.exception("Paced activation failed and was compensated")
            raise HTTPException(500, "Failed to activate paced mission leg") from exc
        geography = OfflineClockGeography()
        persist_mission_clock_settings_best_effort(
            lambda: apply_mission_activation_clock_settings(
                clock_settings_store,
                route_points=tick.plan.artifacts.route.points,
                resolve_location=lambda latitude, longitude: resolve_clock_location(
                    latitude,
                    longitude,
                    time_zone_lookup=geography.time_zone_at,
                    locality_lookup=geography.locality_at,
                ),
            ),
            lifecycle_event="activating a paced mission leg",
        )
        return {
            "status": "success",
            "active_leg_id": leg_id,
            "simulation_run": result.model_dump(mode="json"),
        }
