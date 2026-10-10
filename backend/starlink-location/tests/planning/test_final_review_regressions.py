"""Cross-boundary regressions for canonical clones and effective AR timing."""

import json
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.mission import storage
from app.mission.planning.models import LegHistory, SaveDraft
from app.mission.planning.routes import router
from app.mission.timeline_preparation import prepare_mission_timeline

from . import test_proposals
from .test_packages import archive
from .test_reviewed_save import confirmed, review, snapshot

prepared = test_proposals.prepared
service = test_proposals.service


def ar_draft(service, view, mode="fixed_utc"):
    from app.mission.planning.match import match_ar_windows

    from .test_match import leg

    card = view.expected_legs[0].leg
    route = service.store.route_manager.get_route(card.route.route_id)
    row = match_ar_windows(leg(), route)[0]
    row.confirmed_units = "flight_level"
    row.source_altitude = 210
    row.confirmed = True
    row.start_anchor.timing_mode = mode
    row.end_anchor.timing_mode = mode
    draft = card.draft.model_copy(deep=True)
    draft.ar_corrections = [row]
    return draft


def save_ar(service, view, draft):
    return service.store.save_draft(
        view.mission.id,
        "card-1",
        SaveDraft(
            expected_revision=view.revision, draft=draft, ar_section_status="listed"
        ),
    )


def test_collision_rebuilds_installed_and_historical_snapshots(prepared, monkeypatch):
    from app.mission.exporter.snapshot import capture_export_snapshot
    from app.mission.planning.models import AnchoredSwap, PlanningLock
    from app.mission.planning.packages import commit_package, stage_package
    from app.satellites import catalog

    service, view = confirmed(prepared)
    draft = ar_draft(service, view, "route_bound")
    anchor = draft.ar_corrections[0].start_anchor
    draft.swaps = [AnchoredSwap(id="swap", target_satellite_id="WEST", anchor=anchor)]
    draft.locks = [
        PlanningLock(id="lock", kind="swap", target_satellite_id="WEST", anchor=anchor)
    ]
    view = save_ar(service, view, draft)
    view = service.save_reviewed(
        view.mission.id,
        "card-1",
        review(view, confirmed_ar_ids=["ar"], no_ars_confirmed=False),
    )
    mission, manifest = service.store._load(view.mission.id)
    installed = mission.legs[0]
    original = prepare_mission_timeline(
        installed, service.store.route_manager, service.store.poi_manager
    )
    manifest.leg_history.append(
        LegHistory(
            leg=manifest.expected_legs[0].model_copy(deep=True),
            installed_leg=installed,
            timeline=original.timeline,
            source_ids=[s.id for s in manifest.source_revisions],
            revision=manifest.revision,
            reason="revision",
        )
    )
    service.store.persist(mission, manifest)
    before = snapshot(service)
    monkeypatch.setattr(
        "app.mission.exporter.snapshot_inputs.get_satellite_catalog",
        catalog.get_satellite_catalog,
    )
    with archive(service, mission.id) as handle, zipfile.ZipFile(handle) as zf:
        plan = stage_package(zf, None, service.sources)
    cloned = commit_package(plan, None)
    _, history = service.store._load(cloned.mission.id)
    for clone in [cloned.mission.legs[0], history.leg_history[0].installed_leg]:
        assert clone.route_id != installed.route_id
        for field in ("route_json", "anchor_route_json"):
            assert (
                json.loads(getattr(clone.transports.planning_inputs, field))["route_id"]
                == clone.route_id
            )
        rebuilt = prepare_mission_timeline(
            clone, service.store.route_manager, service.store.poi_manager
        )
        assert rebuilt.planning_evaluation == original.planning_evaluation
        assert (
            clone.transports.evaluation_context
            == installed.transports.evaluation_context
        )
    exported = capture_export_snapshot(
        cloned.mission.id, service.store.route_manager, service.store.poi_manager
    )
    assert exported.legs[0].preparation_origin == "rebuilt"
    assert all(
        __import__("pathlib").Path(path).read_bytes() == data
        for path, data in before.items()
    )


@pytest.mark.parametrize("departure", ["11:30:00", "06:00:00", "10:30:00", "07:30:00"])
def test_outside_fixed_ar_preview_and_review_never_publish(prepared, departure):
    from .test_match import utc

    service, view = confirmed(prepared)
    draft = ar_draft(service, view)
    view = save_ar(service, view, draft)
    installed = service.save_reviewed(
        view.mission.id,
        "card-1",
        review(view, confirmed_ar_ids=["ar"], no_ars_confirmed=False),
    )
    installed_bytes = storage.get_mission_leg_file_path(
        view.mission.id, installed.mission.legs[0].id
    ).read_bytes()
    draft.adjusted_departure_time = utc(departure)
    view = save_ar(service, installed, draft)
    before = snapshot(service)
    app = FastAPI()
    app.state.planning_service = service
    app.include_router(router)
    prefix = f"/api/v2/missions/planning/missions/{view.mission.id}/legs/card-1"
    with TestClient(app) as client:
        preview = client.post(
            prefix + "/preview",
            json={
                "expected_revision": view.revision,
                "draft": draft.model_dump(mode="json"),
                "ar_section_status": "listed",
            },
        )
        assert preview.status_code == 200, preview.text
        assert any("effective flight" in e["message"] for e in preview.json()["errors"])
        rejected = client.post(
            prefix + "/reviewed",
            json=review(
                view, confirmed_ar_ids=["ar"], no_ars_confirmed=False
            ).model_dump(mode="json"),
        )
        assert rejected.status_code == 422, rejected.text
    assert snapshot(service) == before
    current = service.store.read(view.mission.id)
    assert (
        storage.get_mission_leg_file_path(
            view.mission.id, installed.mission.legs[0].id
        ).read_bytes()
        == installed_bytes
    )
    assert current.expected_legs[0].leg.draft.ar_corrections == draft.ar_corrections


@pytest.mark.parametrize("mode", ["fixed_utc", "route_bound", "elapsed"])
def test_effective_ar_valid_modes_and_elapsed_overflow(prepared, mode):
    from app.mission.planning.inputs import build_inputs

    from .test_match import utc

    service, view = confirmed(prepared)
    draft = ar_draft(service, view, mode)
    draft.adjusted_departure_time = utc("09:15:00")
    row = draft.ar_corrections[0]
    if mode == "elapsed":
        row.start_anchor.elapsed_seconds = 600
        row.end_anchor.elapsed_seconds = 12000
    inputs = build_inputs(
        view.expected_legs[0].leg,
        draft,
        service.store.route_manager,
        service.store.poi_manager,
        service.store.planning_constraints_provider(),
    )
    if mode == "elapsed":
        assert any("effective flight" in error for error in inputs.unresolved)
    else:
        assert not inputs.unresolved
        assert inputs.ar_windows[0].start_time == utc(
            "10:15:20" if mode == "route_bound" else "10:00:20"
        )
        assert row.entry_time == utc("10:00:00")
        assert row.start_anchor.timing_mode == mode


@pytest.mark.parametrize(
    "field", ["route_json", "anchor_route_json", "structural_draft_json"]
)
def test_malformed_embedded_snapshot_rejected_before_writes(prepared, field):
    import io

    from app.mission.planning.packages import stage_package

    service, view = confirmed(prepared)
    view = service.save_reviewed(view.mission.id, "card-1", review(view))
    payload = io.BytesIO()
    with archive(service, view.mission.id) as handle, zipfile.ZipFile(
        handle
    ) as original, zipfile.ZipFile(payload, "w") as changed:
        for name in original.namelist():
            content = original.read(name)
            if name == "mission.json":
                raw = json.loads(content)
                raw["legs"][0]["transports"]["planning_inputs"][field] = "{broken"
                content = json.dumps(raw).encode()
            changed.writestr(name, content)
    before = snapshot(service)
    with zipfile.ZipFile(payload) as archive_file, pytest.raises(
        ValueError, match="Invalid embedded planning"
    ):
        stage_package(archive_file, None, service.sources)
    assert snapshot(service) == before
