"""Current saved revisions own publication, independently of renderer lifetime."""

import importlib
import json
from dataclasses import replace

from app.mission.exporter.snapshot_inputs import SourcePayload, canonical_json
from tests.unit.test_customer_document import inputs


def store(tmp_path):
    module = importlib.import_module("app.mission.slide_cache.store")
    return module.SlideStore(tmp_path / "slides.sqlite3")


def test_superseding_save_rejects_late_worker_publication(tmp_path):
    cache = store(tmp_path)
    first = cache.request("m", "a", "old", b"old inputs")
    assert cache.claim()["token"] == first
    second = cache.request("m", "a", "new", b"new inputs")
    assert second != first
    assert not cache.publish("m", "a", first, b"stale snapshot", b"pdf", b"evidence")
    assert cache.claim()["token"] == second
    assert cache.publish("m", "a", second, b"current snapshot", b"pdf", b"evidence")
    assert cache.records("m")["a"]["snapshot"] == b"current snapshot"


def test_duplicate_requests_reuse_ready_artifacts_and_other_legs(tmp_path):
    cache = store(tmp_path)
    first = cache.request("m", "a", "one", b"inputs")
    cache.claim()
    cache.publish("m", "a", first, b"snapshot", b"pdf", b"evidence")
    cache.request("m", "b", "two", b"other")
    assert cache.request("m", "a", "one", b"inputs") == first
    assert cache.records("m")["a"]["state"] == "ready"
    cache.invalidate("m", ["b"])
    assert cache.records("m")["a"]["pdf"] == b"pdf"


def test_deleted_leg_cannot_publish_and_restart_recovers_running(tmp_path):
    cache = store(tmp_path)
    first = cache.request("m", "a", "one", b"inputs")
    cache.claim()
    cache.recover()
    assert cache.claim()["token"] == first
    cache.remove_except("m", [])
    assert not cache.publish("m", "a", first, b"snapshot", b"pdf", b"evidence")
    assert cache.records("m") == {}


def test_invalidation_cancels_token_before_new_inputs_are_captured(tmp_path):
    cache = store(tmp_path)
    token = cache.request("m", "a", "one", b"inputs")
    cache.claim()
    cache.invalidate("m", ["a"])
    assert not cache.current("m", "a", token)
    assert cache.claim() is None


def test_leg_identity_ignores_another_leg_but_tracks_route_and_order():
    from app.mission.slide_cache.identity import leg_inputs

    metadata = canonical_json(
        {
            "id": "m",
            "name": "Mission",
            "legs": [
                {"id": "a", "name": "A", "route_id": "r"},
                {"id": "b", "name": "B", "route_id": "s"},
            ],
        }
    )
    sources = (
        SourcePayload("route/r", b'{"distance":1}'),
        SourcePayload("route/s", b'{"distance":2}'),
    )
    first = leg_inputs(metadata, sources, "a", "v1")[0]
    other = json.loads(metadata)
    other["legs"][1]["name"] = "Edited B"
    assert leg_inputs(canonical_json(other), sources, "a", "v1")[0] == first
    assert (
        leg_inputs(
            metadata,
            (replace(sources[0], content=b'{"distance":3}'), sources[1]),
            "a",
            "v1",
        )[0]
        != first
    )
    assert leg_inputs(metadata, sources, "a", "v2")[0] != first
    other["legs"].reverse()
    assert leg_inputs(canonical_json(other), sources, "a", "v1")[0] != first


def test_snapshot_roundtrip_retains_immutable_evidence():
    from app.mission.slide_cache.identity import decode_snapshot, encode_snapshot

    captured = inputs()[0]
    assert decode_snapshot(encode_snapshot(captured)) == captured


def test_route_reparse_import_clock_does_not_invalidate_pages():
    from app.mission.slide_cache.identity import leg_inputs

    metadata = canonical_json({"id": "m", "legs": [{"id": "a", "route_id": "r"}]})
    route = {"metadata": {"imported_at": "2026-10-09T12:00:00Z"}, "points": [1]}
    before = leg_inputs(
        metadata, (SourcePayload("route/r", canonical_json(route)),), "a", "v1"
    )[0]
    route["metadata"]["imported_at"] = "2026-10-09T13:00:00Z"
    assert (
        leg_inputs(
            metadata, (SourcePayload("route/r", canonical_json(route)),), "a", "v1"
        )[0]
        == before
    )
    route["points"] = [2]
    assert (
        leg_inputs(
            metadata, (SourcePayload("route/r", canonical_json(route)),), "a", "v1"
        )[0]
        != before
    )


def test_ready_identity_survives_coverage_and_catalog_cache_reset(
    tmp_path, monkeypatch
):
    from app.mission import storage, timeline_service
    from app.mission.models import Mission, MissionLeg, TransportConfig
    from app.mission.slide_cache.coordinator import reconcile
    from app.satellites import catalog
    from app.satellites.coverage import CoverageSampler

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    path = tmp_path / "data/sat_coverage/commka.geojson"
    path.parent.mkdir(parents=True)
    path.write_text('{"type":"FeatureCollection","features":[]}')
    storage.save_mission_v2(
        Mission(
            id="m",
            name="Mission",
            legs=[
                MissionLeg(
                    id="a",
                    name="A",
                    route_id="",
                    transports=TransportConfig(initial_x_satellite_id=""),
                )
            ],
        )
    )
    monkeypatch.setattr(timeline_service, "_COVERAGE_SAMPLER", CoverageSampler(path))
    monkeypatch.setattr(
        catalog, "_catalog", catalog.load_satellite_catalog(read_only=True)
    )
    cache = store(tmp_path)
    reconcile("m", None, None, cache, "v1")
    job = cache.claim()
    cache.publish("m", "a", job["token"], b"snapshot", b"pdf", b"evidence")
    monkeypatch.setattr(timeline_service, "_COVERAGE_SAMPLER", None)
    monkeypatch.setattr(catalog, "_catalog", None)
    reconcile("m", None, None, cache, "v1")
    assert cache.records("m")["a"]["token"] == job["token"]
    assert cache.records("m")["a"]["state"] == "ready"
    path.write_text('{"type":"FeatureCollection","features":[],"revision":2}')
    reconcile("m", None, None, cache, "v1")
    assert cache.records("m")["a"]["state"] == "queued"
    job = cache.claim()
    cache.publish("m", "a", job["token"], b"snapshot", b"pdf", b"evidence")
    monkeypatch.setattr(
        catalog, "_catalog", catalog.load_satellite_catalog(read_only=True)
    )
    catalog_path = tmp_path / "data/satellites/catalog.yaml"
    catalog_path.parent.mkdir()
    catalog_path.write_text(
        "satellites:\n  - id: X-New\n    transport: X\n    longitude: -100\n"
    )
    reconcile("m", None, None, cache, "v1")
    assert cache.records("m")["a"]["state"] == "queued"


def test_storage_save_invalidates_changed_leg_without_rendering(tmp_path, monkeypatch):
    from app.mission import storage
    from app.mission.models import Mission, MissionLeg, TransportConfig
    from app.mission.slide_cache.store import default_store

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    mission = Mission(
        id="m",
        name="Mission",
        legs=[
            MissionLeg(
                id=leg,
                name=leg,
                route_id="r",
                transports=TransportConfig(initial_x_satellite_id="X"),
            )
            for leg in ("a", "b")
        ],
    )
    storage.save_mission_v2(mission)
    cache = default_store()
    a = cache.request("m", "a", "one", b"inputs")
    cache.request("m", "b", "two", b"other")
    cache.claim()
    mission.legs[0].name = "Updated A"
    storage.save_mission_v2(mission)
    assert not cache.current("m", "a", a)
    assert cache.records("m")["b"]["state"] == "queued"


def test_unrelated_leg_pois_do_not_invalidate_current_leg():
    from app.mission.slide_cache.identity import leg_inputs

    metadata = canonical_json(
        {
            "id": "m",
            "legs": [{"id": "a", "route_id": "r"}, {"id": "b", "route_id": "s"}],
        }
    )
    pois = [
        {"id": "global", "mission_id": None, "route_id": None, "longitude": 1},
        {"id": "b-poi", "mission_id": "m", "route_id": "s", "longitude": 2},
    ]
    first = leg_inputs(
        metadata, (SourcePayload("pois", canonical_json(pois)),), "a", "v1"
    )[0]
    pois[1]["longitude"] = 3
    assert (
        leg_inputs(metadata, (SourcePayload("pois", canonical_json(pois)),), "a", "v1")[
            0
        ]
        == first
    )
    pois[0]["longitude"] = 4
    assert (
        leg_inputs(metadata, (SourcePayload("pois", canonical_json(pois)),), "a", "v1")[
            0
        ]
        != first
    )


def test_local_css_changes_invalidate_renderer_revision(tmp_path, monkeypatch):
    from app.mission.slide_cache import identity

    script = tmp_path / "backend/starlink-location/app/mission/slide_cache/identity.py"
    script.parent.mkdir(parents=True)
    script.write_text("# cache")
    css = tmp_path / "frontend/mission-planner/src/mission-export/briefing/briefing.css"
    css.parent.mkdir(parents=True)
    css.write_text("header {color: red}")
    monkeypatch.setattr(identity, "__file__", str(script))
    before = identity.renderer_revision()
    css.write_text("header {color: blue}")
    assert identity.renderer_revision() != before


def test_deployed_renderer_does_not_require_checkout_depth(tmp_path, monkeypatch):
    from pathlib import Path

    from app.mission.slide_cache import identity

    renderer = tmp_path / "renderer"
    renderer.mkdir()
    css = renderer / "briefing.css"
    css.write_text("header {color: red}")
    monkeypatch.setattr(
        identity, "__file__", "/app/app/mission/slide_cache/identity.py"
    )
    monkeypatch.setattr(
        identity,
        "Path",
        lambda value: (
            renderer if value == "/opt/customer-briefing/renderer" else Path(value)
        ),
    )
    before = identity.renderer_revision()
    css.write_text("header {color: blue}")
    assert identity.renderer_revision() != before


def test_shared_route_generated_pois_do_not_supersede_unchanged_leg():
    from app.mission.slide_cache.identity import leg_inputs

    metadata = canonical_json(
        {
            "id": "m",
            "legs": [{"id": "a", "route_id": "r"}, {"id": "b", "route_id": "r"}],
        }
    )
    poi = {
        "id": "generated",
        "mission_id": "m",
        "route_id": "r",
        "generated_source": "mission-timeline",
        "longitude": 1,
    }
    before = leg_inputs(
        metadata, (SourcePayload("pois", canonical_json([poi])),), "b", "v1"
    )[0]
    poi["longitude"] = 2
    assert (
        leg_inputs(
            metadata, (SourcePayload("pois", canonical_json([poi])),), "b", "v1"
        )[0]
        == before
    )


def test_persisted_pois_converge_across_stale_api_managers(tmp_path, monkeypatch):
    from app.mission import storage
    from app.mission.models import Mission, MissionLeg, TransportConfig
    from app.mission.slide_cache.coordinator import reconcile
    from app.mission.slide_cache.identity import decode_inputs
    from app.models.poi import POICreate, POIUpdate
    from app.services.poi_manager import POIManager

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    storage.save_mission_v2(
        Mission(
            id="m",
            name="Mission",
            legs=[
                MissionLeg(
                    id="a",
                    name="A",
                    route_id="",
                    transports=TransportConfig(initial_x_satellite_id=""),
                )
            ],
        )
    )
    first = POIManager(tmp_path / "pois.json")
    poi = first.create_poi(POICreate(name="X", latitude=0, longitude=1))
    second = POIManager(tmp_path / "pois.json")
    second.update_poi(poi.id, POIUpdate(longitude=2))
    assert first.list_pois()[0].longitude == 1  # Production manager remains stale.
    cache = store(tmp_path)
    reconcile("m", None, first, cache, "v1")
    desired = cache.records("m")["a"]
    reconcile("m", None, second, cache, "v1")
    assert cache.records("m")["a"]["token"] == desired["token"]
    _, sources, _, _, _ = decode_inputs(desired["inputs"])
    assert (
        json.loads(next(s.content for s in sources if s.name == "pois"))[0]["longitude"]
        == 2
    )
