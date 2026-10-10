"""Reviewed publication uses live inputs and never publishes provisional drafts."""

import pytest

from app.mission.planning.errors import PlanningFailure
from app.mission.planning.models import PreviewDraft, SaveDraft, SaveReviewed

from . import test_proposals

prepared = test_proposals.prepared
service = test_proposals.service


def snapshot(service):
    return {
        str(p): p.read_bytes()
        for root in (service.store.root, service.store.route_manager.routes_dir)
        for p in root.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }


def review(view, **changes):
    return SaveReviewed(
        **{
            "expected_revision": view.revision,
            "input_identity": view.expected_legs[0].input_identity,
            "satellite_plan_confirmed": True,
            "no_ars_confirmed": True,
            "gap_acknowledged": True,
            **changes,
        }
    )


def confirmed(prepared):
    service, view = prepared
    draft = view.expected_legs[0].leg.draft.model_copy(deep=True)
    draft.no_ars_confirmed = True
    view = service.store.save_draft(
        view.mission.id,
        "card-1",
        SaveDraft(expected_revision=view.revision, draft=draft),
    )
    return service, view


def test_preview_is_read_only_and_uses_shared_evaluation(prepared):
    service, view = prepared
    before = snapshot(service)
    result = service.preview(
        view.mission.id,
        "card-1",
        PreviewDraft(
            expected_revision=view.revision, draft=view.expected_legs[0].leg.draft
        ),
    )
    assert result.intervals
    assert snapshot(service) == before
    assert service.store.read(view.mission.id).mission.legs == []


def test_reviewed_save_creates_first_inactive_leg_and_canonical_timeline(prepared):
    service, view = confirmed(prepared)
    assert view.mission.legs == []
    saved = service.save_reviewed(view.mission.id, "card-1", review(view))
    assert saved.mission.legs[0].is_active is False
    assert (
        saved.expected_legs[0].leg.review.input_identity
        == saved.expected_legs[0].input_identity
    )
    assert saved.revision == view.revision + 1
    from app.mission.timeline_preparation import prepare_mission_timeline

    artifacts = prepare_mission_timeline(
        saved.mission.legs[0],
        service.store.route_manager,
        service.store.poi_manager,
        parent_mission_id=view.mission.id,
        constraint_config=service.store.planning_constraints_provider(),
    )
    assert artifacts.planning_evaluation is not None
    assert saved.mission.legs[0].transports.planning_inputs is not None


@pytest.mark.parametrize(
    "changes",
    [
        {"satellite_plan_confirmed": False},
        {"no_ars_confirmed": False},
        {"confirmed_ar_ids": ["fabricated"]},
        {"excluded_ar_ids": ["fabricated"]},
    ],
)
def test_incomplete_review_has_no_writes(prepared, changes):
    service, view = confirmed(prepared)
    before = snapshot(service)
    with pytest.raises(PlanningFailure) as error:
        service.save_reviewed(view.mission.id, "card-1", review(view, **changes))
    assert error.value.status_code == 422
    assert snapshot(service) == before


def test_stale_review_preserves_new_draft_without_writes(prepared):
    service, view = confirmed(prepared)
    draft = view.expected_legs[0].leg.draft.model_copy(deep=True)
    draft.starshield_enabled = False
    service.store.save_draft(
        view.mission.id,
        "card-1",
        SaveDraft(expected_revision=view.revision, draft=draft),
    )
    before = snapshot(service)
    with pytest.raises(PlanningFailure) as error:
        service.save_reviewed(view.mission.id, "card-1", review(view))
    assert error.value.status_code == 409
    assert snapshot(service) == before


@pytest.mark.parametrize("dependency", ["catalog", "config", "coverage"])
def test_changed_dependencies_during_preparation_reject_without_writes(
    prepared, monkeypatch, dependency
):
    service, view = confirmed(prepared)
    import app.mission.planning.review as module

    original = module.prepare_mission_timeline

    def raced(*args, **kwargs):
        result = original(*args, **kwargs)
        if dependency == "catalog":
            from app.satellites.catalog import get_satellite_catalog

            get_satellite_catalog().get_satellite("SOUTH").longitude = 70
        elif dependency == "config":
            from app.satellites.rules import ConstraintConfig

            service.store.planning_constraints_provider = lambda: ConstraintConfig(
                elevation_min_degrees=11
            )
        else:
            from types import SimpleNamespace

            monkeypatch.setattr(
                "app.mission.exporter.snapshot_inputs._coverage_inputs",
                lambda: [SimpleNamespace(name="changed", digest="changed")],
            )
        return result

    monkeypatch.setattr(module, "prepare_mission_timeline", raced)
    before = snapshot(service)
    with pytest.raises(PlanningFailure) as error:
        service.save_reviewed(view.mission.id, "card-1", review(view))
    assert error.value.status_code == 409
    assert snapshot(service) == before


def test_unresolved_legacy_swap_blocks_preview_proposal_and_review(prepared):
    from app.mission.planning.models import GenerateProposal, PlanningDraft

    service, view = confirmed(prepared)
    data = view.expected_legs[0].leg.draft.model_dump()
    data["unresolved_x_transitions"] = [
        {"id": "legacy", "target_satellite_id": "SOUTH", "latitude": 1, "longitude": 2}
    ]
    draft = PlanningDraft.model_validate(data)
    view = service.store.save_draft(
        view.mission.id,
        "card-1",
        SaveDraft(expected_revision=view.revision, draft=draft),
    )
    assert any(
        e.field == "unresolved_x_transitions" for e in view.expected_legs[0].errors
    )
    before = snapshot(service)
    for action in (
        lambda: service.preview(
            view.mission.id,
            "card-1",
            PreviewDraft(expected_revision=view.revision, draft=draft),
        ),
        lambda: service.save_reviewed(view.mission.id, "card-1", review(view)),
    ):
        with pytest.raises((PlanningFailure, ValueError)):
            action()
    with pytest.raises(PlanningFailure) as proposal_error:
        service.proposals.generate(
            view.mission.id,
            "card-1",
            GenerateProposal(
                expected_revision=view.revision,
                input_identity=view.expected_legs[0].input_identity,
            ),
        )
    assert proposal_error.value.error.code == "unresolved_x_transitions"
    assert "accepted timed route occurrence" in proposal_error.value.error.message
    assert snapshot(service) == before


@pytest.mark.parametrize(
    "dependency", ["moved", "deleted", "config", "coverage", "route"]
)
def test_reopen_invalidates_review_without_mutating_provenance(
    prepared, monkeypatch, dependency
):
    service, view = confirmed(prepared)
    saved = service.save_reviewed(view.mission.id, "card-1", review(view))
    from app.satellites.catalog import get_satellite_catalog

    if dependency == "moved":
        get_satellite_catalog().get_satellite("SOUTH").longitude = 80
    elif dependency == "deleted":
        del get_satellite_catalog().satellites["SOUTH"]
    elif dependency == "config":
        from app.satellites.rules import ConstraintConfig

        service.store.planning_constraints_provider = lambda: ConstraintConfig(
            elevation_min_degrees=11
        )
    elif dependency == "coverage":
        from types import SimpleNamespace

        monkeypatch.setattr(
            "app.mission.exporter.snapshot_inputs._coverage_inputs",
            lambda: [SimpleNamespace(name="changed", digest="changed")],
        )
    else:
        service.store.route_manager.get_route(
            saved.expected_legs[0].leg.route.route_id
        ).content_hash = ("b" * 64)
    before = snapshot(service)
    reopened = service.store.read(view.mission.id)
    assert reopened.expected_legs[0].review_status == "needs_review"
    assert (
        reopened.expected_legs[0].input_identity
        == saved.expected_legs[0].input_identity
    )
    assert snapshot(service) == before
    assert service.store._load(view.mission.id)[1].expected_legs[0].review is not None


def test_managed_put_stages_unanchored_inputs_preserving_executable(prepared):
    service, view = confirmed(prepared)
    view = service.save_reviewed(view.mission.id, "card-1", review(view))
    installed = view.mission.legs[0]
    from app.mission.models import XTransition

    changed = installed.model_copy(deep=True)
    changed.transports.x_transitions = [
        XTransition(id="raw", target_satellite_id="WEST", latitude=20, longitude=30)
    ]
    changed.transports.starshield_enabled = False
    changed.name = "Pending changes"
    result = service.update_managed_leg(
        view.mission.id,
        installed.id,
        changed,
        view.revision,
        view.expected_legs[0].input_identity,
    )
    assert result["leg"]["transports"] == installed.transports.model_dump()
    current = service.store.read(view.mission.id)
    assert current.expected_legs[0].review_status == "needs_review"
    draft = current.expected_legs[0].leg.draft
    assert draft.unresolved_x_transitions[0].latitude == 20
    assert draft.starshield_enabled is False
    assert current.mission.legs[0].name == "Pending changes"
    before = snapshot(service)
    with pytest.raises(PlanningFailure) as error:
        service.save_reviewed(view.mission.id, "card-1", review(view))
    assert error.value.status_code == 409
    assert snapshot(service) == before


@pytest.mark.parametrize("revision,identity", [(None, None), (1, "f" * 64)])
def test_managed_put_requires_current_cas(prepared, revision, identity):
    service, view = confirmed(prepared)
    view = service.save_reviewed(view.mission.id, "card-1", review(view))
    before = snapshot(service)
    with pytest.raises(PlanningFailure) as error:
        service.update_managed_leg(
            view.mission.id,
            view.mission.legs[0].id,
            view.mission.legs[0],
            revision,
            identity,
        )
    assert error.value.status_code == 409
    assert snapshot(service) == before


def test_managed_nonplan_put_preserves_review_and_increments_revision(prepared):
    service, view = confirmed(prepared)
    view = service.save_reviewed(view.mission.id, "card-1", review(view))
    changed = view.mission.legs[0].model_copy(deep=True)
    changed.name = "Renamed"
    service.update_managed_leg(
        view.mission.id,
        changed.id,
        changed,
        view.revision,
        view.expected_legs[0].input_identity,
    )
    current = service.store.read(view.mission.id)
    assert current.revision == view.revision + 1
    assert current.expected_legs[0].review_status == "reviewed"


@pytest.mark.asyncio
async def test_ordinary_put_delegates_managed_cas_and_retains_omitted_fields(prepared):
    from app.mission.models import MissionLeg
    from app.mission.routes_v2 import update_leg

    service, view = confirmed(prepared)
    view = service.save_reviewed(view.mission.id, "card-1", review(view))
    old = view.mission.legs[0]
    incoming = MissionLeg(
        id=old.id,
        name="New name",
        route_id=old.route_id,
        transports={"initial_x_satellite_id": old.transports.initial_x_satellite_id},
    )
    result = await update_leg(
        view.mission.id,
        old.id,
        incoming,
        route_manager=service.store.route_manager,
        poi_manager=service.store.poi_manager,
        expected_revision=view.revision,
        input_identity=view.expected_legs[0].input_identity,
    )
    assert result["leg"]["transports"] == old.transports.model_dump()
    assert (
        service.store.read(view.mission.id).expected_legs[0].review_status == "reviewed"
    )


@pytest.mark.asyncio
async def test_parent_metadata_edit_preserves_latest_draft_and_review(prepared):
    from app.mission.models import MissionUpdate
    from app.mission.routes_v2 import update_mission

    service, view = confirmed(prepared)
    view = service.save_reviewed(view.mission.id, "card-1", review(view))
    from types import SimpleNamespace

    parent = await update_mission(
        view.mission.id,
        MissionUpdate(name="Parent renamed"),
        request=SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(planning_service=service))
        ),
    )
    current = service.store.read(view.mission.id)
    assert parent.name == "Parent renamed"
    assert current.revision == view.revision + 1
    assert current.expected_legs[0].review_status == "reviewed"
    assert current.expected_legs[0].leg.draft == view.expected_legs[0].leg.draft


def test_managed_ar_put_stages_raw_window_without_fabricated_time(prepared):
    from app.mission.models import AARWindow

    service, view = confirmed(prepared)
    view = service.save_reviewed(view.mission.id, "card-1", review(view))
    incoming = view.mission.legs[0].model_copy(deep=True)
    incoming.transports.aar_windows = [
        AARWindow(id="new-ar", start_waypoint_name="ENTRY", end_waypoint_name="EXIT")
    ]
    service.update_managed_leg(
        view.mission.id,
        incoming.id,
        incoming,
        view.revision,
        view.expected_legs[0].input_identity,
    )
    current = service.store.read(view.mission.id)
    pending = current.expected_legs[0].leg.draft.unresolved_aar_windows[0]
    assert pending.start_waypoint_name == "ENTRY"
    assert pending.override_start_time is None
    assert current.mission.legs[0].transports.model_dump(
        mode="json"
    ) == view.mission.legs[0].transports.model_dump(mode="json")


@pytest.mark.parametrize("change", ["active", "route"])
def test_managed_put_rejects_active_plan_edit_and_route_replacement(prepared, change):
    from app.mission import storage

    service, view = confirmed(prepared)
    view = service.save_reviewed(view.mission.id, "card-1", review(view))
    incoming = view.mission.legs[0].model_copy(deep=True)
    if change == "active":
        parent = storage.load_mission_v2(view.mission.id)
        parent.legs[0].is_active = True
        storage.save_mission_v2(parent)
        incoming.transports.starshield_enabled = False
    else:
        incoming.route_id = "replacement"
    before = snapshot(service)
    with pytest.raises(PlanningFailure) as error:
        service.update_managed_leg(
            view.mission.id,
            incoming.id,
            incoming,
            view.revision,
            view.expected_legs[0].input_identity,
        )
    assert error.value.status_code == 409
    assert snapshot(service) == before


def test_valid_ordinary_put_changes_draft_and_invalidates_review(prepared):
    service, view = confirmed(prepared)
    view = service.save_reviewed(view.mission.id, "card-1", review(view))
    incoming = view.mission.legs[0].model_copy(deep=True)
    incoming.transports.starshield_enabled = False
    result = service.update_managed_leg(
        view.mission.id,
        incoming.id,
        incoming,
        view.revision,
        view.expected_legs[0].input_identity,
    )
    current = service.store.read(view.mission.id)
    assert result["leg"]["transports"]["starshield_enabled"] is False
    assert current.expected_legs[0].leg.draft.starshield_enabled is False
    assert current.expected_legs[0].review_status == "needs_review"
    assert current.expected_legs[0].leg.draft.evaluation_context is None


def test_pending_swap_resolution_then_review_installs_requested_schedule(prepared):
    from app.mission import storage
    from app.mission.models import XTransition
    from app.mission.planning.models import AnchoredSwap, RouteAnchor

    service, view = confirmed(prepared)
    view = service.save_reviewed(view.mission.id, "card-1", review(view))
    incoming = view.mission.legs[0].model_copy(deep=True)
    timeline = storage.get_leg_timeline_path(incoming.id, view.mission.id).read_bytes()
    markers = service.store.poi_manager.pois_file.read_bytes()
    incoming.transports.x_transitions = [
        XTransition(id="pending", target_satellite_id="WEST", latitude=20, longitude=30)
    ]
    service.update_managed_leg(
        view.mission.id,
        incoming.id,
        incoming,
        view.revision,
        view.expected_legs[0].input_identity,
    )
    assert (
        storage.get_leg_timeline_path(incoming.id, view.mission.id).read_bytes()
        == timeline
    )
    assert service.store.poi_manager.pois_file.read_bytes() == markers
    current = service.store.read(view.mission.id)
    draft = current.expected_legs[0].leg.draft.model_copy(deep=True)
    route = service.store.route_manager.get_route(incoming.route_id)
    draft.swaps = [
        AnchoredSwap(
            id="pending",
            target_satellite_id="WEST",
            anchor=RouteAnchor(
                route_id=route.route_id,
                content_hash=route.content_hash,
                segment_index=0,
                fraction=0,
                occurrence_id=route.points[0].occurrence_id,
                source_time=route.points[0].expected_arrival_time,
                latitude=route.points[0].latitude,
                longitude=route.points[0].longitude,
            ),
        )
    ]
    draft.unresolved_x_transitions = []
    current = service.store.save_draft(
        view.mission.id,
        "card-1",
        SaveDraft(expected_revision=current.revision, draft=draft),
    )
    saved = service.save_reviewed(view.mission.id, "card-1", review(current))
    assert saved.mission.legs[0].transports.x_transitions[0].id == "pending"
    assert saved.mission.legs[0].transports.x_transitions[0].anchor is not None


def test_re_review_preserves_installed_leg_metadata(prepared):
    service, view = confirmed(prepared)
    view = service.save_reviewed(view.mission.id, "card-1", review(view))
    updated = view.mission.legs[0].model_copy(deep=True)
    updated.name = "Reviewed custom title"
    updated.description = "Executive communications"
    service.update_managed_leg(
        view.mission.id,
        updated.id,
        updated,
        view.revision,
        view.expected_legs[0].input_identity,
    )
    current = service.store.read(view.mission.id)
    saved = service.save_reviewed(view.mission.id, "card-1", review(current))
    assert saved.mission.legs[0].name == updated.name
    assert saved.mission.legs[0].description == updated.description


def test_unrecognized_ar_section_is_provisional_in_preview(prepared):
    service, view = prepared
    result = service.preview(
        view.mission.id,
        "card-1",
        PreviewDraft(
            expected_revision=view.revision,
            draft=view.expected_legs[0].leg.draft,
            ar_section_status="unrecognized",
        ),
    )
    assert any(error.code == "unresolved_ar" for error in result.errors)


def test_managed_put_rejects_unsupported_initial_ka_selection_without_writes(prepared):
    service, view = confirmed(prepared)
    view = service.save_reviewed(view.mission.id, "card-1", review(view))
    incoming = view.mission.legs[0].model_copy(deep=True)
    incoming.transports.initial_ka_satellite_ids = ["AOR"]
    before = snapshot(service)
    with pytest.raises(PlanningFailure) as error:
        service.update_managed_leg(
            view.mission.id,
            incoming.id,
            incoming,
            view.revision,
            view.expected_legs[0].input_identity,
        )
    assert error.value.status_code == 422
    assert error.value.error.code == "initial_ka_selection_unsupported"
    assert "preserve" in error.value.error.message
    assert snapshot(service) == before


@pytest.mark.parametrize("omitted", [True, False])
def test_existing_initial_ka_selection_survives_put_and_review(prepared, omitted):
    from app.mission import storage
    from app.mission.models import MissionLeg

    service, view = confirmed(prepared)
    view = service.save_reviewed(view.mission.id, "card-1", review(view))
    parent = storage.load_mission_v2(view.mission.id)
    parent.legs[0].transports.initial_ka_satellite_ids = ["AOR"]
    storage.save_mission_v2(parent)
    view = service.store.read(view.mission.id)
    data = view.mission.legs[0].model_dump()
    data["transports"]["starshield_enabled"] = False
    if omitted:
        del data["transports"]["initial_ka_satellite_ids"]
    incoming = MissionLeg.model_validate(data)
    result = service.update_managed_leg(
        view.mission.id,
        incoming.id,
        incoming,
        view.revision,
        view.expected_legs[0].input_identity,
    )
    assert result["leg"]["transports"]["initial_ka_satellite_ids"] == ["AOR"]
    current = service.store.read(view.mission.id)
    reviewed = service.save_reviewed(view.mission.id, "card-1", review(current))
    assert reviewed.mission.legs[0].transports.initial_ka_satellite_ids == ["AOR"]
