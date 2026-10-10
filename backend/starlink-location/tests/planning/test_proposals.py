"""Proposal reads and publication preserve user edits and commit with CAS."""

import importlib.util


def test_proposal_service_exists():
    assert importlib.util.find_spec(
        "app.mission.planning.proposals"
    ), "Revision-safe proposal service is missing"


def test_generation_accepts_optional_idempotency_key():
    from app.mission.planning.models import GenerateProposal

    request = GenerateProposal(
        expected_revision=1, input_identity="a" * 64, idempotency_key="once"
    )
    assert request.idempotency_key == "once"


import pytest

from app.mission.planning.errors import PlanningFailure
from app.mission.planning.models import (
    AccessConfirmation,
    ApplyProposal,
    GenerateProposal,
    SaveDraft,
)

from . import test_store
from .test_policy import scenario
from .test_store import bind, create

service = test_store.service


@pytest.fixture
def prepared(service, tmp_path, monkeypatch):
    scenario(monkeypatch)
    view, _ = create(service)
    view = bind(service, tmp_path)
    draft = view.expected_legs[0].leg.draft.model_copy(deep=True)
    draft.permitted_satellite_ids = ("SOUTH", "WEST")
    draft.access_confirmation = AccessConfirmation(
        satellite_ids=draft.permitted_satellite_ids, confirmed=True
    )
    draft.initial_x_satellite_id = "SOUTH"
    view = service.store.save_draft(
        view.mission.id,
        "card-1",
        SaveDraft(expected_revision=view.revision, draft=draft),
    )
    draft = view.expected_legs[0].leg.draft.model_copy(deep=True)
    draft.access_confirmation = AccessConfirmation(
        satellite_ids=draft.permitted_satellite_ids, confirmed=True
    )
    view = service.store.save_draft(
        view.mission.id,
        "card-1",
        SaveDraft(expected_revision=view.revision, draft=draft),
    )
    return service, view


def proposal_api(prepared, monkeypatch):
    from app.mission.planning.proposals import ProposalService

    monkeypatch.setattr(
        "app.mission.planning.proposals.run_bounded",
        lambda fn, args, seconds: fn(*args),
    )
    service, view = prepared
    api = ProposalService(service.store)
    request = GenerateProposal(
        expected_revision=view.revision,
        input_identity=view.expected_legs[0].input_identity,
        idempotency_key="same",
    )
    return api, view, request


def test_generate_read_reload_idempotency_and_apply_preserve_source_card(
    prepared, monkeypatch
):
    api, view, request = proposal_api(prepared, monkeypatch)
    mission_id = view.mission.id
    before = api.store.read(mission_id)
    proposal = api.generate(mission_id, "card-1", request)
    after = api.store.read(mission_id)
    assert after.revision == before.revision
    assert (
        after.expected_legs[0].input_identity == before.expected_legs[0].input_identity
    )
    assert after.expected_legs[0].leg.draft == before.expected_legs[0].leg.draft
    assert after.expected_legs[0].computation_status == "ready"
    monkeypatch.setattr(
        "app.mission.planning.proposals.run_bounded",
        lambda *args: pytest.fail("read or idempotent retry reran solver"),
    )
    assert api.generate(mission_id, "card-1", request) == proposal
    assert api.get(mission_id, "card-1", proposal.id) == proposal
    assert "owned_relative_path" not in after.model_dump_json()
    manifest = api.store._load(mission_id)[1]
    assert len(manifest.proposal_refs) == 1
    assert list((api.store.root / mission_id / "planning" / "proposals").glob("*.json"))
    applied = api.apply(
        mission_id,
        "card-1",
        ApplyProposal(
            expected_revision=view.revision,
            input_identity=request.input_identity,
            proposal_id=proposal.id,
        ),
    )
    assert applied.revision == view.revision + 1
    assert applied.expected_legs[0].leg.draft == proposal.proposed_draft
    assert applied.expected_legs[0].leg.draft.evaluation_context == proposal.context
    assert applied.mission.legs == []


@pytest.mark.parametrize("change", ["ku", "enabled", "permitted", "timing"])
def test_late_result_after_draft_edit_is_409_without_lost_work(
    prepared, monkeypatch, change
):
    api, view, request = proposal_api(prepared, monkeypatch)
    from app.mission.planning.optimizer import optimize

    def interleaved(fn, args, seconds):
        draft = view.expected_legs[0].leg.draft.model_copy(deep=True)
        if change == "ku":
            from app.mission.models import KuOutageOverride

            draft.ku_overrides = [
                KuOutageOverride(
                    id="late",
                    start_time=view.expected_legs[0].leg.departure_time,
                    duration_seconds=30,
                )
            ]
        elif change == "enabled":
            draft.starshield_enabled = False
        elif change == "permitted":
            draft.permitted_satellite_ids = ("SOUTH",)
        else:
            from datetime import timedelta

            draft.adjusted_departure_time = view.expected_legs[
                0
            ].leg.departure_time + timedelta(seconds=17)
        api.store.save_draft(
            view.mission.id,
            "card-1",
            SaveDraft(expected_revision=view.revision, draft=draft),
        )
        return optimize(*args)

    monkeypatch.setattr("app.mission.planning.proposals.run_bounded", interleaved)
    with pytest.raises(PlanningFailure) as failure:
        api.generate(view.mission.id, "card-1", request)
    assert failure.value.status_code == 409
    assert api.store.read(view.mission.id).revision == view.revision + 1
    assert api.store._load(view.mission.id)[1].proposal_refs == []
    assert api.store.read(view.mission.id).mission.legs == []


def test_selection_change_requires_reconfirmation_and_retains_manual_assignments(
    prepared,
):
    service, view = prepared
    draft = view.expected_legs[0].leg.draft.model_copy(deep=True)
    draft.permitted_satellite_ids = ("WEST",)
    draft.access_confirmation = AccessConfirmation(
        satellite_ids=("WEST",), confirmed=True
    )
    saved = service.store.save_draft(
        view.mission.id,
        "card-1",
        SaveDraft(expected_revision=view.revision, draft=draft),
    )
    assert saved.expected_legs[0].leg.draft.access_confirmation is None
    assert saved.expected_legs[0].leg.draft.initial_x_satellite_id == "SOUTH"
    assert any(
        e.field == "initial_x_satellite_id" for e in saved.expected_legs[0].errors
    )


@pytest.mark.parametrize("dependency", ["catalog", "coverage", "config"])
def test_live_dependency_changes_stale_read_apply_and_late_publish(
    prepared, monkeypatch, dependency
):
    api, view, request = proposal_api(prepared, monkeypatch)
    from app.mission.exporter.snapshot_inputs import SourcePayload
    from app.satellites.rules import ConstraintConfig

    proposal = api.generate(view.mission.id, "card-1", request)
    if dependency == "catalog":
        from app.mission.planning import service as module

        catalog = module.get_satellite_catalog(read_only=True)
        catalog.get_satellite("SOUTH").longitude = 80
    elif dependency == "coverage":
        monkeypatch.setattr(
            "app.mission.exporter.snapshot_inputs._coverage_inputs",
            lambda: (SourcePayload("changed", b"{}"),),
        )
    else:
        api.constraints_provider = lambda: ConstraintConfig(elevation_min_degrees=22)
    assert api.get(view.mission.id, "card-1", proposal.id).state == "stale"
    assert (
        api.store.read(view.mission.id).expected_legs[0].computation_status == "stale"
    )
    before = api.store._load(view.mission.id)[1].storage_record()
    with pytest.raises(PlanningFailure) as failure:
        api.apply(
            view.mission.id,
            "card-1",
            ApplyProposal(
                expected_revision=view.revision,
                input_identity=request.input_identity,
                proposal_id=proposal.id,
            ),
        )
    assert failure.value.status_code == 409
    assert api.store._load(view.mission.id)[1].storage_record() == before


def test_manual_timing_edit_reseeds_even_onto_existing_candidate(prepared, monkeypatch):
    api, view, request = proposal_api(prepared, monkeypatch)
    from app.mission.planning.inputs import build_inputs
    from app.satellites.rules import ConstraintConfig

    from .cases import timed_swap

    leg = view.expected_legs[0].leg
    inputs = build_inputs(
        leg,
        leg.draft,
        api.store.route_manager,
        api.store.poi_manager,
        ConstraintConfig(),
    )
    draft = leg.draft.model_copy(deep=True)
    draft.swaps = [timed_swap(inputs, 61, "WEST")]
    saved = api.store.save_draft(
        view.mission.id,
        "card-1",
        SaveDraft(expected_revision=view.revision, draft=draft),
    )
    request = GenerateProposal(
        expected_revision=saved.revision,
        input_identity=saved.expected_legs[0].input_identity,
    )
    proposal = api.generate(view.mission.id, "card-1", request)
    applied = api.apply(
        view.mission.id,
        "card-1",
        ApplyProposal(**request.model_dump(), proposal_id=proposal.id),
    )
    assert (
        inputs.start_time + __import__("datetime").timedelta(seconds=61)
        in applied.expected_legs[0].leg.draft.evaluation_context.seed_times
    )
    draft = applied.expected_legs[0].leg.draft.model_copy(deep=True)
    draft.swaps = [timed_swap(inputs, 120, "WEST")]
    saved = api.store.save_draft(
        view.mission.id,
        "card-1",
        SaveDraft(expected_revision=applied.revision, draft=draft),
    )
    assert saved.expected_legs[0].leg.draft.evaluation_context is None


@pytest.mark.parametrize("mode", ["cancel", "disconnect"])
async def test_actual_asgi_request_cancellation_reaps_worker(
    prepared, monkeypatch, tmp_path, mode
):
    import asyncio
    import multiprocessing

    from fastapi import FastAPI

    from app.mission.planning.deadlines import run_bounded
    from app.mission.planning.routes import router

    from .test_deadlines import _slow_started

    service, view = prepared
    marker = tmp_path / "request-worker-started"

    def slow(fn, args, seconds, **kwargs):
        return run_bounded(_slow_started, (str(marker),), seconds, **kwargs)

    monkeypatch.setattr("app.mission.planning.proposals.run_bounded", slow)
    app = FastAPI()
    app.state.planning_service = service
    app.include_router(router)
    request = GenerateProposal(
        expected_revision=view.revision,
        input_identity=view.expected_legs[0].input_identity,
    )
    path = f"/api/v2/missions/planning/missions/{view.mission.id}/legs/card-1/proposals"
    sent = False
    disconnected = False
    messages = []

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {
                "type": "http.request",
                "body": request.model_dump_json().encode(),
                "more_body": False,
            }
        if disconnected:
            return {"type": "http.disconnect"}
        await asyncio.Event().wait()

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
    }
    before = {p.pid for p in multiprocessing.active_children()}
    task = asyncio.create_task(app(scope, receive, send))
    try:
        for _ in range(100):
            if marker.exists():
                break
            if task.done():
                await task
            await asyncio.sleep(0.05)
        assert marker.exists()
        if mode == "cancel":
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 3)
        else:
            disconnected = True
            await asyncio.wait_for(task, 3)
            assert (
                next(m for m in messages if m["type"] == "http.response.start")[
                    "status"
                ]
                == 503
            )
        assert {p.pid for p in multiprocessing.active_children()} == before
        assert service.store._load(view.mission.id)[1].proposal_refs == []
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("dependency", ["catalog", "coverage", "config"])
def test_live_dependency_changed_during_solver_discards_result(
    prepared, monkeypatch, dependency
):
    api, view, request = proposal_api(prepared, monkeypatch)
    from app.mission.exporter.snapshot_inputs import SourcePayload
    from app.mission.planning.optimizer import optimize
    from app.satellites.rules import ConstraintConfig

    before = api.store._load(view.mission.id)[1].storage_record()

    def interleaved(fn, args, seconds):
        result = optimize(*args)
        if dependency == "catalog":
            from app.satellites.catalog import get_satellite_catalog

            get_satellite_catalog(read_only=True).get_satellite("SOUTH").longitude = 80
        elif dependency == "coverage":
            monkeypatch.setattr(
                "app.mission.exporter.snapshot_inputs._coverage_inputs",
                lambda: (SourcePayload("changed", b"{}"),),
            )
        else:
            api.constraints_provider = lambda: ConstraintConfig(
                elevation_min_degrees=22
            )
        return result

    monkeypatch.setattr("app.mission.planning.proposals.run_bounded", interleaved)
    with pytest.raises(PlanningFailure) as failure:
        api.generate(view.mission.id, "card-1", request)
    assert failure.value.status_code == 409
    assert api.store._load(view.mission.id)[1].storage_record() == before


async def test_actual_application_shutdown_reaps_worker_and_restart_reopens(tmp_path):
    import asyncio
    import multiprocessing

    import main
    from app.mission.planning import deadlines

    from .test_deadlines import _slow_started, _value

    marker = tmp_path / "shutdown-owned"
    before = {p.pid for p in multiprocessing.active_children()}
    operation = asyncio.create_task(
        asyncio.to_thread(deadlines.run_bounded, _slow_started, (str(marker),), 30)
    )
    try:
        for _ in range(100):
            if marker.exists():
                break
            await asyncio.sleep(0.05)
        assert marker.exists()
        await asyncio.wait_for(main.shutdown_event(), 3)
        with pytest.raises(deadlines.PlanningWorkerError):
            await operation
        assert {p.pid for p in multiprocessing.active_children()} == before
    finally:
        deadlines.start_workers()
        await asyncio.gather(operation, return_exceptions=True)
    assert deadlines.run_bounded(_value, ("restarted",), 3) == "restarted"


def test_proposal_http_generate_read_apply_with_real_bounded_worker(prepared):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.mission.planning.routes import router

    service, view = prepared
    app = FastAPI()
    app.state.planning_service = service
    app.include_router(router)
    path = f"/api/v2/missions/planning/missions/{view.mission.id}/legs/card-1"
    request = GenerateProposal(
        expected_revision=view.revision,
        input_identity=view.expected_legs[0].input_identity,
        idempotency_key="http",
    )
    with TestClient(app) as client:
        response = client.post(
            path + "/proposals", json=request.model_dump(mode="json")
        )
        assert response.status_code == 200, response.text
        proposal = response.json()
        assert client.get(path + "/proposals/" + proposal["id"]).json() == proposal
        applied = client.post(
            path + "/apply",
            json=ApplyProposal(
                **request.model_dump(), proposal_id=proposal["id"]
            ).model_dump(mode="json"),
        )
        assert applied.status_code == 200, applied.text
        assert applied.json()["revision"] == view.revision + 1
