"""Trial inclusion must be atomic and cannot change any established export."""

import io
import json
import zipfile
from dataclasses import replace
from datetime import datetime, timezone

import pytest
from pptx import Presentation

from app.core.config import ConfigManager
from app.mission import exporter as exporter_api
from app.mission.exporter import (
    TimelineExportFormat,
    generate_timeline_export,
    trial_maps,
    trial_pptx,
    trial_projection,
)
from app.mission.exporter import __main__ as exporter
from app.mission.exporter.snapshot_inputs import SourcePayload
from app.mission.exporter.snapshot_views import SnapshotViews
from app.mission.models import Mission, MissionLeg
from app.mission.package import __main__ as package
from tests.unit import test_export_snapshot
from tests.unit.test_trial_pptx import inputs

export_inputs = test_export_snapshot.export_inputs

TRIAL = "exports/mission/mission-customer-briefing-trial.pptx"
LEGACY = {
    "mission.json",
    "legs/f01.json",
    "manifest.json",
    "exports/legs/f01/timeline.csv",
    "exports/legs/f01/slides.pptx",
    "exports/mission/mission-timeline.csv",
    "exports/mission/mission-slides.pptx",
}


@pytest.fixture
def package_inputs(monkeypatch):
    frozen, _, maps = inputs("F01")
    frozen = replace(
        frozen,
        source_payloads=(
            SourcePayload("pois", b"[]"),
            SourcePayload("ground_entry", b"null"),
        ),
    )
    monkeypatch.setattr(package, "capture_export_snapshot", lambda *a: frozen)
    monkeypatch.setattr(
        exporter_api, "_generate_route_map", lambda *a, **kw: maps[0].views[0].png
    )
    monkeypatch.setattr(trial_maps, "render_trial_maps", lambda *a: maps)

    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 8, tzinfo=timezone.utc)

    monkeypatch.setattr(package, "datetime", FixedClock)
    monkeypatch.setattr(exporter, "datetime", FixedClock)
    return frozen, maps


def flag(value):
    ConfigManager.get_instance().update_config(
        {"customer_briefing_trial_enabled": value}
    )


def contents(result):
    with result.stream, zipfile.ZipFile(result.stream) as archive:
        assert archive.testzip() is None
        return {name: archive.read(name) for name in archive.namelist()}


def pptx_parts(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {
            n: archive.read(n) for n in archive.namelist() if n != "docProps/core.xml"
        }


def direct(frozen):
    views = SnapshotViews(frozen)
    return generate_timeline_export(
        TimelineExportFormat.PPTX,
        views.mission().legs[0],
        views.timeline("f01"),
        route_manager=views.route_manager,
        poi_manager=views.poi_manager,
    ).content


def test_trial_flag_file_set_and_direct_pptx_preserved(package_inputs, monkeypatch):
    frozen, _ = package_inputs
    flag(False)
    legacy_direct = direct(frozen)
    original_project = trial_projection.project_trial_leg
    original_build = trial_pptx.build_trial_pptx
    original_maps = trial_maps.render_trial_maps

    def forbidden(*a, **kw):
        pytest.fail("disabled export entered a trial stage")

    monkeypatch.setattr(trial_projection, "project_trial_leg", forbidden)
    monkeypatch.setattr(trial_maps, "render_trial_maps", forbidden)
    monkeypatch.setattr(trial_pptx, "build_trial_pptx", forbidden)
    disabled = package.export_mission_package_result(frozen.mission_id, None, None)
    assert disabled.trial_status == "disabled" and disabled.warnings == ()
    legacy = contents(disabled)
    assert set(legacy) == LEGACY
    manifest = json.loads(legacy["manifest.json"])
    assert "trial_status" not in manifest and "warnings" not in manifest
    assert "export_labels" not in manifest
    with package.export_mission_package(frozen.mission_id, None, None) as stream:
        assert zipfile.ZipFile(stream).namelist() == list(legacy)

    monkeypatch.setattr(trial_projection, "project_trial_leg", original_project)
    monkeypatch.setattr(trial_maps, "render_trial_maps", original_maps)
    monkeypatch.setattr(trial_pptx, "build_trial_pptx", original_build)
    flag(True)
    included = package.export_mission_package_result(frozen.mission_id, None, None)
    assert included.trial_status == "included"
    enabled = contents(included)
    assert set(enabled) == LEGACY | {TRIAL}
    manifest = json.loads(enabled["manifest.json"])
    assert manifest["trial_status"] == "included"
    assert manifest["warnings"] == list(included.warnings)
    assert manifest["export_labels"][TRIAL] == "Customer briefing — Trial"
    assert manifest["file_structure"]["mission_exports"].count(TRIAL) == 1
    assert manifest["statistics"]["total_files"] == len(enabled)
    assert len(Presentation(io.BytesIO(enabled[TRIAL])).slides) > 0
    for name in LEGACY - {"manifest.json"}:
        if name.endswith(".pptx"):
            assert pptx_parts(enabled[name]) == pptx_parts(legacy[name])
        else:
            assert enabled[name] == legacy[name]
    assert pptx_parts(direct(frozen)) == pptx_parts(legacy_direct)


@pytest.mark.parametrize(
    "stage", ["projection", "map", "pptx", "validation", "invalid-bytes"]
)
def test_trial_failure_preserves_legacy_package(package_inputs, monkeypatch, stage):
    frozen, _ = package_inputs
    flag(False)
    legacy = contents(
        package.export_mission_package_result(frozen.mission_id, None, None)
    )
    flag(True)

    def fail(*a, **kw):
        raise RuntimeError("secret /private/customer/token\r\n" + "x" * 10000)

    targets = {
        "projection": (trial_projection, "project_trial_leg"),
        "map": (trial_maps, "render_trial_maps"),
        "pptx": (trial_pptx, "build_trial_pptx"),
        "validation": (trial_pptx, "validate_trial_pptx"),
        "invalid-bytes": (trial_pptx, "build_trial_pptx"),
    }
    module, name = targets[stage]
    monkeypatch.setattr(
        module,
        name,
        (lambda *a: b"broken pptx") if stage == "invalid-bytes" else fail,
        raising=False,
    )
    result = package.export_mission_package_result(frozen.mission_id, None, None)
    assert result.trial_status == "failed"
    exported = contents(result)
    assert set(exported) == LEGACY
    manifest = json.loads(exported["manifest.json"])
    assert manifest["trial_status"] == "failed"
    assert "export_labels" not in manifest
    assert TRIAL not in manifest["file_structure"]["mission_exports"]
    assert manifest["warnings"] == list(result.warnings)
    assert result.warnings and len(json.dumps(result.warnings)) < 2048
    assert "secret" not in str(result.warnings) and "/private" not in str(
        result.warnings
    )
    assert all("\r" not in w and "\n" not in w for w in result.warnings)
    for name in LEGACY - {"manifest.json"}:
        if name.endswith(".pptx"):
            assert pptx_parts(exported[name]) == pptx_parts(legacy[name])
        else:
            assert exported[name] == legacy[name]


def test_trial_fallback_warns_safely_without_omitting_valid_deck(
    package_inputs, monkeypatch
):
    frozen, maps = package_inputs
    flag(True)
    monkeypatch.setattr(
        trial_maps,
        "render_trial_maps",
        lambda *a: (replace(maps[0], warnings=("secret\r\n/private" * 1000,)),),
    )
    result = package.export_mission_package_result(frozen.mission_id, None, None)
    assert result.trial_status == "included"
    assert result.warnings and "fallback" in " ".join(result.warnings).lower()
    assert "secret" not in str(result.warnings)
    assert len(json.dumps(result.warnings)) < 2048
    assert TRIAL in contents(result)


@pytest.mark.parametrize("enabled", [False, True])
def test_trial_flag_captured_before_snapshot_and_legacy_work(
    package_inputs, monkeypatch, enabled
):
    frozen, _ = package_inputs
    flag(enabled)

    def capture(*a):
        flag(not enabled)
        return frozen

    monkeypatch.setattr(package, "capture_export_snapshot", capture)
    result = package.export_mission_package_result(frozen.mission_id, None, None)
    assert result.trial_status == ("included" if enabled else "disabled")
    assert (TRIAL in contents(result)) == enabled


def test_trial_is_built_only_after_legacy_exports(package_inputs, monkeypatch):
    frozen, _ = package_inputs
    flag(True)
    finished = []
    combined = package._add_combined_mission_exports_to_zip
    projection = trial_projection.project_trial_leg

    def legacy(*a, **kw):
        combined(*a, **kw)
        finished.append(True)

    def project(leg):
        assert finished == [True]
        assert leg is frozen.legs[0]
        return projection(leg)

    monkeypatch.setattr(package, "_add_combined_mission_exports_to_zip", legacy)
    monkeypatch.setattr(trial_projection, "project_trial_leg", project)
    result = package.export_mission_package_result(frozen.mission_id, None, None)
    assert result.trial_status == "included"
    assert TRIAL in contents(result)


def test_trial_enabled_preserves_importable_sources(
    tmp_path, monkeypatch, export_inputs
):
    import asyncio

    from fastapi import UploadFile
    from starlette.requests import Request

    from app.mission import routes_v2, storage
    from app.services.poi_manager import POIManager
    from app.services.route_manager import RouteManager

    mission, routes, pois, _ = export_inputs
    kml = b"""<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><LineString><coordinates>0,0,0 0,1,0</coordinates></LineString></Placemark></Document></kml>"""
    (routes.routes_dir / "r.kml").write_bytes(kml)
    _, _, maps = inputs("F01")
    monkeypatch.setattr(
        exporter_api, "_generate_route_map", lambda *a, **kw: maps[0].views[0].png
    )
    monkeypatch.setattr(
        trial_maps, "render_trial_maps", lambda *a: (replace(maps[0], leg_id="l"),)
    )
    flag(True)
    before = (storage.MISSIONS_DIR / mission.id / "mission.json").read_bytes()
    result = package.export_mission_package_result(mission.id, routes, pois)
    assert result.trial_status == "included"
    with result.stream:
        data = result.stream.read()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.testzip() is None and TRIAL in archive.namelist()
        assert archive.read("routes/r.kml") == kml
        assert Mission.model_validate_json(archive.read("mission.json")) == mission
        assert (
            MissionLeg.model_validate_json(archive.read("legs/l.json"))
            == mission.legs[0]
        )
        assert (
            json.loads(archive.read("pois/l-pois.json"))["pois"][0]["name"]
            == "Captured POI"
        )
    assert (storage.MISSIONS_DIR / mission.id / "mission.json").read_bytes() == before
    imported_routes = RouteManager(tmp_path / "import-routes")
    imported_pois = POIManager(tmp_path / "import-pois.json")
    # Exercise actual source import, with its timeline generation disabled to
    # keep this check about source round-trip and the extra deck's inertness.
    monkeypatch.setattr(
        routes_v2, "_generate_timelines_for_imported_legs", lambda *a: []
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v2/missions/import",
            "headers": [],
            "client": ("testclient", 50000),
        }
    )
    imported = asyncio.run(
        routes_v2.import_mission(
            request=request,
            file=UploadFile(file=io.BytesIO(data), filename="mission.zip"),
            route_manager=imported_routes,
            poi_manager=imported_pois,
        )
    )
    assert imported["success"] is True and imported["mission_id"] == mission.id
    assert (
        storage.load_mission_v2(mission.id).legs[0].transports
        == mission.legs[0].transports
    )
    assert imported_routes.get_route("r").points[-1].latitude == 1
    assert any(p.name == "Captured POI" for p in imported_pois.list_pois())
