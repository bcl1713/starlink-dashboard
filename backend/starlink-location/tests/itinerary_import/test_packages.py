"""Source provenance and history survive actual package staging and cloning."""

import io
import json
from zipfile import ZipFile

import pytest

from app.mission import storage
from app.mission.planning.packages import commit_package, stage_package
from app.mission.planning.sources import source_closure
from app.mission.planning.store import PlanningStore

from .test_creation_api import importer, kml_bytes, pdf_bytes, wait  # noqa: F401


def archive(mission, service):
    stream = io.BytesIO()
    with ZipFile(stream, "w") as zf:
        zf.writestr("mission.json", mission.model_dump_json())
        for source in source_closure(mission, None):
            path = service.mission_root / ".planning" / source.owned_relative_path
            zf.writestr("planning/" + source.owned_relative_path, path.read_bytes())
            if source.kind == "route_kml":
                zf.writestr(
                    "routes/" + source.id + ".kml",
                    (
                        service.route_manager.routes_dir / (source.id + ".kml")
                    ).read_bytes(),
                )
                zf.writestr(
                    "routes/" + source.id + ".profile.json",
                    (
                        service.route_manager.routes_dir / (source.id + ".profile.json")
                    ).read_bytes(),
                )
        for item in mission.metadata["itinerary_import"].get("history", []):
            id = item["snapshot_id"]
            zf.writestr(
                "itinerary/history/" + id + ".json",
                (
                    storage.get_mission_directory(mission.id)
                    / ".itinerary-history"
                    / (id + ".json")
                ).read_bytes(),
            )
    stream.seek(0)
    return stream


def test_clone_preserves_retained_sources_and_revision_history(importer):  # noqa: F811
    client, service = importer
    op = service.start(pdf_bytes(), [("r.kml", kml_bytes())], "package-first")
    wait(client, op.id)
    rev = service.start(
        pdf_bytes(), [("r.kml", kml_bytes())], "package-rev", op.mission_id
    )
    ready = wait(client, rev.id)
    assert ready["state"] == "ready", ready
    service.commit_revision(rev.id, ready["generation"], {})
    mission = storage.load_mission_v2(op.mission_id)
    assert len(source_closure(mission, None)) >= 3
    store = PlanningStore(
        service.mission_root, service.route_manager, service.poi_manager
    )
    with ZipFile(archive(mission, service)) as zf:
        plan = stage_package(zf, None, store.sources)
        clone = commit_package(plan, None).mission
    assert clone.id != mission.id
    assert clone.metadata["itinerary_import"]["revision"] == 2
    for item in clone.metadata["itinerary_import"]["history"]:
        assert (
            storage.get_mission_directory(clone.id)
            / ".itinerary-history"
            / (item["snapshot_id"] + ".json")
        ).exists()
    assert {s.id for s in source_closure(clone, None)}.isdisjoint(
        {s.id for s in source_closure(mission, None)}
    )
    for source in source_closure(mission, None):
        if source.kind == "route_kml":
            descriptor = json.loads(
                store.sources.descriptor_path(source.id).read_bytes()
            )
            assert descriptor["owner"] == mission.id
    for source in source_closure(clone, None):
        assert source.owner == clone.id
        assert store.sources.path(source).exists()


def test_unsupported_provenance_version_rejected():
    from app.mission.models import Mission

    with pytest.raises(ValueError, match="version"):
        source_closure(
            Mission(id="m", name="M", metadata={"itinerary_import": {"version": 999}}),
            None,
        )


@pytest.mark.parametrize("packaged_only", [False, True])
def test_clone_resolves_satellites_from_current_global_configuration(
    importer, monkeypatch, packaged_only  # noqa: F811
):
    from app.models.poi import POICreate
    from app.satellites.catalog import SatelliteCatalog

    client, service = importer
    monkeypatch.setattr("app.satellites.catalog._catalog", SatelliteCatalog())
    satellite = service.poi_manager.create_poi(
        POICreate(
            name="X-configured", latitude=0, longitude=0, category="satellite", icon="X"
        )
    )
    op = service.start(pdf_bytes(), [("r.kml", kml_bytes())], "poi-configured")
    assert wait(client, op.id)["state"] == "committed"
    mission = storage.load_mission_v2(op.mission_id)
    store = PlanningStore(
        service.mission_root, service.route_manager, service.poi_manager
    )
    stream = archive(mission, service)
    if packaged_only:
        service.poi_manager.delete_poi(satellite.id)
        from app.mission.planning.packages import _poi_record

        with ZipFile(stream, "a") as zf:
            zf.writestr(
                "pois/satellites.json", json.dumps({"pois": [_poi_record(satellite)]})
            )
    with ZipFile(stream) as zf:
        plan = stage_package(zf, None, store.sources)
    assert (
        commit_package(plan, None).mission.legs[0].transports.initial_x_satellite_id
        == "X-configured"
    )
