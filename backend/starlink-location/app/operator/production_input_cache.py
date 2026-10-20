"""Reuse immutable normalized bytes only while every captured input still matches."""

from app.mission.exporter.snapshot_inputs import canonical_json
from app.mission.slide_cache import capture


def capture_static(adapter, mission_id):
    """Caller holds repository admission; telemetry is never cached here."""
    raw = capture.capture_raw(mission_id, adapter.route_manager, adapter.poi_manager)
    # File tokens alone miss accepted in-memory route/POI edits. Include their
    # complete values, including excluded POI projection fields used by exports.
    routes = {
        route_id: route.model_dump(mode="json") if route else None
        for route_id in adapter.route_manager.list_routes()
        for route in [adapter.route_manager.get_route(route_id)]
    }
    pois = (
        [
            poi.model_dump(mode="json")
            | {
                name: getattr(poi, name)
                for name, field in type(poi).model_fields.items()
                if field.exclude
            }
            for poi in adapter.poi_manager.list_pois()
        ]
        if adapter.poi_manager
        else []
    )
    key = (
        mission_id,
        raw.metadata,
        raw.legs,
        raw.dependency_token,
        canonical_json(routes),
        canonical_json(pois),
    )
    cached = getattr(adapter, "_static_capture", None)
    if cached is not None and cached[0] == key:
        return cached[1]
    metadata, sources, _warnings, _ = capture.normalize_capture(
        raw, persisted=True, fingerprints=False, include_timeline_cache=False
    )
    # Bytes and SourcePayloads contain no mutable mission/preparation objects.
    result = metadata, sources
    adapter._static_capture = key, result
    return result
