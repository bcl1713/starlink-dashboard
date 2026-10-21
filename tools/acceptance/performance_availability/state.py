"""Read-only acceptance adapter; no production route or metric definitions."""

import hashlib
import math
import time

NAMES = (
    *(
        "starlink_dish_" + name
        for name in (
            "latitude_degrees",
            "longitude_degrees",
            "altitude_feet",
            "speed_knots",
            "heading_degrees",
        )
    ),
    *(
        "starlink_network_" + name
        for name in (
            "latency_ms_current",
            "throughput_down_mbps_current",
            "throughput_up_mbps_current",
            "packet_loss_percent",
        )
    ),
    "starlink_dish_obstruction_percent",
    "starlink_signal_quality_percent",
)


def capture(main, metrics):
    """Snapshot the published head, or explicitly identify untracked legacy state.

    Legacy baselines have no frame publication diagnostics; do not invent them.
    No coordinator update, simulator construction, manager/file lookup, counter
    update, Prometheus scrape, or metric serialization occurs here.
    """
    began = time.perf_counter()
    cpu = time.thread_time()
    coordinator = main._coordinator
    telemetry = getattr(coordinator, "_last_valid_telemetry", None)
    routes = getattr(main, "_route_manager", None)
    active_route_id = getattr(routes, "_active_route_id", None)
    route = getattr(routes, "_routes", {}).get(active_route_id)
    source = {
        "mode": getattr(coordinator, "mode", "unknown"),
        "metric_source": getattr(telemetry, "metric_source", None),
        "acquired_at": telemetry.timestamp.timestamp() if telemetry else None,
        "coordinator_id": f"{id(coordinator)}:{getattr(coordinator, 'start_time', None)}:{getattr(coordinator, 'pop_lifecycle_token', 0)}",
        "active_route_id": active_route_id,
    }
    if store := getattr(metrics, "FRAME_STORE", None):
        source["acquired_at"] = None
        head = store.read()
        frame = head.frame
        source["last_observation_publication_time"] = (
            frame.last_observation_publication_time if frame else None
        )
        publication = {
            "state": head.status,
            "reason": head.reason,
            "input_revision": head.input_revision,
        }
        values = (
            {
                definition.name: family[0][1] if family else math.nan
                for definition, family in zip(store.schema, frame.families)
            }
            if frame
            else {}
        )
        if frame:
            identity = frame.identity
            source.update(
                mode=identity.mode,
                acquired_at=identity.observation_timestamp,
                coordinator_id=identity.coordinator_id,
                observation_id=identity.observation_id,
                route_id=identity.route_id,
                replay_runtime_id=identity.replay_runtime_id,
                replay_run_id=identity.replay_run_id,
                replay_revision=identity.replay_revision,
                replay_mission_time=identity.replay_mission_time,
            )
        expected_source = {
            "coordinator_id": f"{id(coordinator)}:{getattr(coordinator, 'start_time', None)}:{getattr(coordinator, 'pop_lifecycle_token', 0)}"
        }
        service = (
            getattr(getattr(main.app, "state", None), "simulation_run_service", None)
            if hasattr(main, "app")
            else None
        )
        plan = service.runtime.selected_plan() if service else None
        if plan:
            status = service.status()
            route = plan.artifacts.route
            expected_source.update(
                mode="replay",
                replay_runtime_id=status.runtime_id,
                replay_run_id=status.run.run_id if status.run else None,
                replay_revision=str(status.revision),
            )
        else:
            expected_source.update(
                mode=getattr(coordinator, "mode", "unknown"),
                replay_runtime_id=None,
                replay_run_id=None,
            )
        expected_source["route_id"] = (
            hashlib.sha256(route.model_dump_json().encode()).hexdigest()
            if route is not None
            else None
        )
        usable = head.status == "ready"
    else:
        expected_source = {}
        publication = {
            "state": "legacy-untracked",
            "reason": "No frame store in baseline",
        }
        values = {
            sample.name: sample.value
            for family in metrics.REGISTRY.collect()
            for sample in family.samples
            if sample.name in NAMES
        }
        usable = True
    now = time.time()
    fields = {
        name: {"available": usable and math.isfinite(values.get(name, math.nan))}
        for name in NAMES
    }
    return {
        "at": now,
        "publication": publication,
        "source": source,
        "expected_source": expected_source,
        "acquisition_age_seconds": (
            now - source["acquired_at"] if source["acquired_at"] else None
        ),
        "fields": fields,
        "capture_wall_ms": (time.perf_counter() - began) * 1000,
        "capture_thread_cpu_ms": (time.thread_time() - cpu) * 1000,
    }
