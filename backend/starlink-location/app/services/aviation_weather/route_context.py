"""Copy the route Overview selects under the active-leg gate; hash after release."""

import hashlib
import struct

from app.mission.storage import get_active_leg_lock
from app.models.route_sigmets import RouteContext


def route_context_key(source, route_id, runtime_id, run_id, points) -> str:
    # Validate before allocating the canonical byte stream.
    candidate = RouteContext(
        context_key="0" * 64,
        source=source,
        route_id=route_id,
        route_name="",
        runtime_id=runtime_id,
        run_id=run_id,
        points=points,
    )
    digest = hashlib.sha256(b"route-context-v1\0")
    for value in (source, route_id, runtime_id or "", run_id or ""):
        encoded = value.encode("utf-8")
        digest.update(struct.pack(">I", len(encoded)))
        digest.update(encoded)
    digest.update(struct.pack(">I", len(candidate.points)))
    for longitude, latitude in candidate.points:
        digest.update(struct.pack(">dd", longitude or 0.0, latitude or 0.0))
    return digest.hexdigest()


def select_route_context(route_manager, simulation_service) -> RouteContext | None:
    source, runtime_id, run_id = "ordinary", None, None
    with get_active_leg_lock():
        route_id = route_manager.get_active_route_id()
        route = route_manager.get_active_route()
        if simulation_service is not None:
            status = simulation_service.status()
            plan = simulation_service.runtime.selected_plan()
            if (
                status.state in ("running", "completed")
                and status.run is not None
                and plan is not None
                and plan.route_id == status.run.route_id
            ):
                source, runtime_id, run_id = (
                    "simulation",
                    status.runtime_id,
                    status.run.run_id,
                )
                route_id, route = plan.route_id, plan.artifacts.route
        if route is None or route_id is None:
            return None
        selected = route.model_copy(deep=True)
    points = [[point.longitude, point.latitude] for point in selected.points]
    return RouteContext(
        context_key=route_context_key(source, route_id, runtime_id, run_id, points),
        source=source,
        route_id=route_id,
        route_name=selected.metadata.name,
        runtime_id=runtime_id,
        run_id=run_id,
        points=points,
        waypoint_occurrences={
            w.occurrence_id: w.point_sequence
            for w in selected.waypoints
            if w.occurrence_id is not None and w.point_sequence is not None
        },
    )
