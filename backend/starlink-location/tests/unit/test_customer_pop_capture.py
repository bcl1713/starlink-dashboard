"""Catalog capture participates in consistency gates and detached worker inputs."""

import json

import pytest

from app.core.config import ConfigManager
from app.mission.exporter.snapshot_inputs import SnapshotCaptureError, canonical_json
from app.mission.slide_cache.capture import (
    capture_is_current,
    capture_raw,
    normalize_capture,
)
from app.services.pop.catalog import DEFAULT_CATALOG_PATH
from tests.unit.test_export_snapshot import (
    export_inputs as export_inputs,  # noqa: PLC0414 — explicit re-export
)


def configured_catalog(tmp_path, monkeypatch):
    path = tmp_path / "pops.json"
    path.write_bytes(DEFAULT_CATALOG_PATH.read_bytes())
    monkeypatch.setattr(ConfigManager().get_config().pop, "catalog_path", path)
    return path


def change_catalog(path):
    value = json.loads(path.read_bytes())
    value["sites"][0]["city"] = "Changed configured city"
    path.write_bytes(canonical_json(value))


def test_catalog_edit_during_capture_rejects_obsolete_inputs(
    export_inputs, tmp_path, monkeypatch
):
    _, routes, pois, _ = export_inputs
    path = configured_catalog(tmp_path, monkeypatch)
    raw = capture_raw("m", routes, pois)
    change_catalog(path)
    assert not capture_is_current(raw)
    with pytest.raises(SnapshotCaptureError):
        normalize_capture(raw)


def test_catalog_update_cancels_publication_and_queues_preparation(
    export_inputs, tmp_path, monkeypatch
):
    from app.mission.slide_cache.coordinator import reconcile
    from tests.unit.test_slide_cache import store

    _, routes, pois, _ = export_inputs
    path = configured_catalog(tmp_path, monkeypatch)
    cache, memo = store(tmp_path), {}
    reconcile("m", routes, pois, cache, "renderer", memo=memo)
    job = cache.claim()
    change_catalog(path)
    reconcile("m", routes, pois, cache, "renderer", memo=memo)
    assert not cache.publish("m", "l", job["token"], b"old", b"pdf", b"evidence")
    replacement = cache.claim()
    assert replacement["fingerprint"] != job["fingerprint"]
    assert replacement["inputs"] != job["inputs"]


def test_worker_uses_immutable_captured_catalog_without_current_configuration(
    export_inputs, tmp_path, monkeypatch
):
    from app.mission.exporter.snapshot import prepare_export_snapshot
    from app.mission.exporter.snapshot_views import SnapshotViews, captured_pop_catalog
    from app.mission.slide_cache.identity import decode_inputs, leg_inputs
    from app.services.pop.catalog import load_catalog

    _, routes, pois, _ = export_inputs
    path = configured_catalog(tmp_path, monkeypatch)
    original = load_catalog(path)
    metadata, sources, warnings, _ = normalize_capture(capture_raw("m", routes, pois))
    assert captured_pop_catalog(sources) == original
    inputs = leg_inputs(metadata, sources, "l", "renderer")[1]
    change_catalog(path)

    def forbidden(*args, **kwargs):
        raise AssertionError("Worker read current catalog/configuration")

    monkeypatch.setattr("app.services.pop.catalog.load_catalog", forbidden)
    monkeypatch.setattr(ConfigManager, "get_config", forbidden)
    metadata, sources, warnings, *_ = decode_inputs(inputs)
    snapshot = prepare_export_snapshot(metadata, sources, warnings)
    timeline = SnapshotViews(snapshot).timeline("l")
    assert timeline.pop_forecast.catalog_fingerprint == original.fingerprint
    assert timeline.call_continuity is not None
    assert timeline.call_continuity.revision == timeline.pop_forecast.revision
    from app.mission.pop_continuity import capabilities_from_timeline
    from app.services.pop.continuity import project_call_continuity

    assert timeline.call_continuity == project_call_continuity(
        timeline.pop_forecast,
        capabilities_from_timeline(timeline),
        start_utc=snapshot.legs[0].utc_bounds[0],
        end_utc=snapshot.legs[0].utc_bounds[1],
    )
    assert snapshot.legs[0].preparation_origin == "rebuilt"
    assert captured_pop_catalog(snapshot.source_payloads) == original


def test_catalog_change_inside_dependency_read_rejects_mixed_capture(
    export_inputs, tmp_path, monkeypatch
):
    from app.mission.exporter import snapshot_inputs

    _, routes, pois, _ = export_inputs
    path = configured_catalog(tmp_path, monkeypatch)
    raw = capture_raw("m", routes, pois)
    read = snapshot_inputs._read_dependencies
    calls = 0

    def changed_during_read(*args, **kwargs):
        nonlocal calls
        sources = read(*args, **kwargs)
        calls += 1
        if calls == 1:
            change_catalog(path)
        return sources

    monkeypatch.setattr(snapshot_inputs, "_read_dependencies", changed_during_read)
    with pytest.raises(SnapshotCaptureError, match="changed during capture"):
        normalize_capture(raw)
    assert calls == 2


@pytest.mark.parametrize("content", [None, b'{"sites": []}', b"not json"])
def test_unavailable_catalog_is_captured_without_live_worker_fallback(
    export_inputs, tmp_path, monkeypatch, content
):
    from app.mission.exporter.snapshot import prepare_export_snapshot
    from app.mission.exporter.snapshot_views import SnapshotViews, captured_pop_catalog

    _, routes, pois, _ = export_inputs
    path = configured_catalog(tmp_path, monkeypatch)
    if content is None:
        path.unlink()
    else:
        path.write_bytes(content)
    metadata, sources, warnings, _ = normalize_capture(capture_raw("m", routes, pois))
    assert captured_pop_catalog(sources) is None
    # A repaired live catalog cannot enter inputs that captured unavailability.
    path.write_bytes(DEFAULT_CATALOG_PATH.read_bytes())
    snapshot = prepare_export_snapshot(metadata, sources, warnings)
    forecast = SnapshotViews(snapshot).timeline("l").pop_forecast
    assert forecast.status == "unavailable"
    assert forecast.catalog_fingerprint == ""
    assert not forecast.transitions


def test_cached_timeline_forecast_rebases_to_captured_planned_inputs(
    export_inputs, tmp_path, monkeypatch
):
    from dataclasses import replace

    from app.mission.exporter import snapshot as module
    from app.mission.exporter.snapshot_views import SnapshotViews, captured_pop_catalog
    from app.mission.models import MissionLegTimeline
    from tests.unit.test_customer_pop import forecast
    from tests.unit.test_export_snapshot import BASE

    _, routes, pois, _ = export_inputs
    configured_catalog(tmp_path, monkeypatch)
    metadata, sources, warnings, _ = normalize_capture(capture_raw("m", routes, pois))
    cached = MissionLegTimeline(
        mission_leg_id="l", pop_forecast=forecast([("live-obsolete", BASE)])
    )
    cached.statistics["pop_call_outage_seconds"] = 600
    cached.statistics["planned_communications_outage_seconds"] = 600
    cached.statistics["longest_call_outage_seconds"] = 600
    sources = tuple(
        (
            replace(s, content=cached.model_dump_json().encode())
            if s.name == "cache/l"
            else s
        )
        for s in sources
    )

    def fail(*args, **kwargs):
        raise ValueError("Forced independent coverage rebuild failure")

    monkeypatch.setattr(module, "prepare_mission_timeline", fail)
    result = module.prepare_export_snapshot(metadata, sources, warnings)
    assert result.legs[0].preparation_origin == "cached"
    rebuilt_timeline = SnapshotViews(result).timeline("l")
    assert rebuilt_timeline.call_continuity is None
    assert "pop_call_outage_seconds" not in rebuilt_timeline.statistics
    assert "planned_communications_outage_seconds" not in rebuilt_timeline.statistics
    assert "longest_call_outage_seconds" not in rebuilt_timeline.statistics
    rebuilt_forecast = rebuilt_timeline.pop_forecast
    assert rebuilt_forecast.status == "ready"
    assert (
        rebuilt_forecast.catalog_fingerprint
        == captured_pop_catalog(sources).fingerprint
    )
    assert rebuilt_forecast.revision != "captured-planning"
    assert all(t.crossing.id != "live-obsolete" for t in rebuilt_forecast.transitions)


def test_catalog_update_during_worker_render_rejects_final_publication(
    export_inputs, tmp_path, monkeypatch
):
    from app.mission.slide_cache import coordinator
    from tests.unit.test_slide_cache import store

    _, routes, pois, _ = export_inputs
    path = configured_catalog(tmp_path, monkeypatch)
    cache = store(tmp_path)
    owner = coordinator.SlideCoordinator(routes, pois, cache=cache)
    coordinator.reconcile("m", routes, pois, cache, owner.revision)
    job = cache.claim()
    staging_paths = []

    def rendered_old_inputs(command, staging, **kwargs):
        staging_paths.append(staging)
        (staging / "snapshot.json").write_bytes(b"old captured snapshot")
        (staging / "result.json").write_text('{"included": true, "warning": null}')
        (staging / "pages.pdf").write_bytes(b"old pdf")
        (staging / "evidence.json").write_bytes(b"old evidence")
        change_catalog(path)
        return 0

    monkeypatch.setattr(coordinator, "run_owned_renderer", rendered_old_inputs)
    owner.run_job(job)
    current = cache.records("m")["l"]
    assert current["token"] != job["token"]
    assert current["state"] == "queued"
    assert current["pdf"] is None
    assert not cache.publish("m", "l", job["token"], b"old", b"pdf", b"evidence")
    assert staging_paths and all(not p.exists() for p in staging_paths)
    assert not owner.thread.is_alive()
