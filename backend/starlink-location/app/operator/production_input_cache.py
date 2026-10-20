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


def validation_key(adapter, metadata, sources, config, context, catalog):
    """Prove the prior full validation still applies without reparsing missions.

    The normal capture always creates detached models. Only read-only validation
    calls reuse them, and still collect fresh telemetry on every call.
    """
    from app.mission import storage

    paths = set(storage.MISSIONS_DIR.glob("*/mission.json"))
    for path in tuple(paths):
        paths.update(storage._iter_mission_leg_files(path.parent / "legs"))
    tokens = []
    for path in sorted(paths):
        stat = path.stat()
        tokens.append(
            (
                str(path),
                stat.st_dev,
                stat.st_ino,
                stat.st_size,
                stat.st_mtime_ns,
                stat.st_ctime_ns,
            )
        )
    active = adapter.route_manager.get_active_route()
    return (
        metadata,
        sources,
        tuple(tokens),
        config.model_dump(mode="json"),
        context,
        catalog,
        adapter.route_manager.get_active_route_id(),
        canonical_json(active.model_dump(mode="json") if active else None),
        tuple(
            (s.name, adapter.route_manager.source_file_revision(s.name[4:]))
            for s in sources
            if s.name.startswith("kml/")
        ),
    )
