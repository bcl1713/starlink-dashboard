"""Parent settings reach planning guards and detached publication artifacts."""

from app.mission import storage
from app.mission.availability_routes import AvailabilitySettings
from app.mission.availability_service import AvailabilityService
from app.mission.planning.models import (
    GenerateProposal,
    PreviewDraft,
    SaveDraft,
    SaveReviewed,
)
from . import test_proposals

service = test_proposals.service
prepared = test_proposals.prepared


def disabled_parent(prepared):
    service, view = prepared
    AvailabilityService(service.store).command(
        view.mission.id,
        AvailabilitySettings(
            expected_revision=0, command_id="disable-X", defaults={"X": False}
        ),
    )
    view = service.store.read(view.mission.id)
    draft = view.expected_legs[0].leg.draft.model_copy(deep=True)
    draft.permitted_satellite_ids = ()
    draft.initial_x_satellite_id = None
    draft.access_confirmation = None
    view = service.store.save_draft(
        view.mission.id,
        "card-1",
        SaveDraft(expected_revision=view.revision, draft=draft),
    )
    return service, view


def test_parent_default_reaches_view_and_proposal_guards(prepared):
    service, view = disabled_parent(prepared)
    assert view.expected_legs[0].errors == []
    proposal = service.proposals.generate(
        view.mission.id,
        "card-1",
        GenerateProposal(
            expected_revision=view.revision,
            input_identity=view.expected_legs[0].input_identity,
        ),
    )
    assert proposal.proposed_draft is not None
    assert proposal.proposed_draft.swaps == []


def test_parent_snapshot_reaches_preview_review_and_installed_inputs(prepared):
    service, view = disabled_parent(prepared)
    evaluation = service.preview(
        view.mission.id,
        "card-1",
        PreviewDraft(
            expected_revision=view.revision, draft=view.expected_legs[0].leg.draft
        ),
    )
    assert all(i.physical_x_state == "offline" for i in evaluation.intervals)
    published = service.save_reviewed(
        view.mission.id,
        "card-1",
        SaveReviewed(
            expected_revision=view.revision,
            input_identity=view.expected_legs[0].input_identity,
            evaluation_identity=evaluation.context.input_identity,
            satellite_plan_confirmed=False,
            no_ars_confirmed=True,
        ),
    )
    installed = published.mission.legs[0]
    assert installed.transports.planning_inputs.availability.planned[0][1] is False
    changed = AvailabilityService(service.store).command(
        view.mission.id,
        AvailabilitySettings(
            expected_revision=1, command_id="disable-Ka", defaults={"Ka": False}
        ),
    )
    assert changed["revision"] == 2
    current = storage.load_mission_v2(view.mission.id).legs[0]
    assert current.transports.planning_inputs.availability.revision == 2
    assert (
        current.transports.planning_inputs.availability.resolve(
            current.transports.planning_inputs.start_time
        )["Ka"]
        is False
    )
    from app.mission.planning.grid import validate_context

    validate_context(
        current.transports.planning_inputs,
        published.expected_legs[0].leg.draft,
        current.transports.evaluation_context,
    )


def test_uninstalled_cards_expose_saved_inheritance_and_overrides(prepared):
    service, view = prepared
    availability = AvailabilityService(service.store)
    result = availability.command(
        view.mission.id,
        AvailabilitySettings(
            expected_revision=0,
            command_id="card-override",
            defaults={"Ka": False},
            leg_overrides={"card-1": {"Ku": False}},
        ),
    )
    cards = {leg["leg_id"]: leg for leg in result["legs"]}
    assert cards["card-1"]["overrides"] == {"Ku": False}
    assert cards["card-1"]["planned"] == {"X": True, "Ka": False, "Ku": False}
    assert result["leg_overrides"]["card-2"] == {}
    assert cards["card-2"]["planned"] == {"X": True, "Ka": False, "Ku": True}
    assert cards["card-1"]["installed_leg_id"] is None


def test_review_under_parent_defaults_remains_current_after_install(prepared):
    service, view = disabled_parent(prepared)
    evaluation = service.preview(
        view.mission.id,
        "card-1",
        PreviewDraft(
            expected_revision=view.revision, draft=view.expected_legs[0].leg.draft
        ),
    )
    published = service.save_reviewed(
        view.mission.id,
        "card-1",
        SaveReviewed(
            expected_revision=view.revision,
            input_identity=view.expected_legs[0].input_identity,
            evaluation_identity=evaluation.context.input_identity,
            satellite_plan_confirmed=False,
            no_ars_confirmed=True,
        ),
    )
    assert published.expected_legs[0].review_status == "reviewed"
    assert (
        service.store.read(view.mission.id).expected_legs[0].review_status == "reviewed"
    )


def test_operator_change_keeps_pending_draft_out_of_installed_profile(prepared):
    from .test_reviewed_save import review

    service, view = prepared
    published = service.save_reviewed(view.mission.id, "card-1", review(service, view))
    draft = published.expected_legs[0].leg.draft.model_copy(deep=True)
    draft.starshield_enabled = False
    pending = service.store.save_draft(
        view.mission.id,
        "card-1",
        SaveDraft(expected_revision=published.revision, draft=draft),
    )
    AvailabilityService(service.store).command(
        view.mission.id,
        AvailabilitySettings(
            expected_revision=0, command_id="only-availability", defaults={"Ka": False}
        ),
    )
    current = service.store.read(view.mission.id)
    assert current.mission.legs[0].transports.starshield_enabled is True
    assert current.expected_legs[0].leg.draft.starshield_enabled is False
    assert current.expected_legs[0].leg.draft.evaluation_context is None
    assert current.revision == pending.revision + 1


def test_restore_x_rebuilds_positions_from_retained_installed_assignments(prepared):
    from .test_reviewed_save import review

    service, view = prepared
    published = service.save_reviewed(view.mission.id, "card-1", review(service, view))
    availability = AvailabilityService(service.store)
    availability.command(
        view.mission.id,
        AvailabilitySettings(
            expected_revision=0, command_id="disable", defaults={"X": False}
        ),
    )
    availability.command(
        view.mission.id,
        AvailabilitySettings(
            expected_revision=1, command_id="restore", defaults={"X": True}
        ),
    )
    current = storage.load_mission_v2(view.mission.id).legs[0]
    assert (
        current.transports.initial_x_satellite_id
        == published.mission.legs[0].transports.initial_x_satellite_id
    )
    assert {
        sat.satellite_id for sat in current.transports.planning_inputs.satellites
    } == {"SOUTH", "WEST"}


def test_old_preview_payload_keeps_saved_leg_override(prepared):
    service, view = prepared
    AvailabilityService(service.store).command(
        view.mission.id,
        AvailabilitySettings(
            expected_revision=0,
            command_id="leg-only-X",
            leg_overrides={"card-1": {"X": False}},
        ),
    )
    view = service.store.read(view.mission.id)
    draft = view.expected_legs[0].leg.draft.model_dump(mode="json")
    draft.pop("availability_overrides")
    draft.update(
        permitted_satellite_ids=[],
        initial_x_satellite_id=None,
        access_confirmation=None,
    )
    result = service.preview(
        view.mission.id,
        "card-1",
        PreviewDraft.model_validate(
            {"expected_revision": view.revision, "draft": draft}
        ),
    )
    assert all(interval.physical_x_state == "offline" for interval in result.intervals)


def test_generation_uses_actual_adjusted_window_for_failure_guard(prepared):
    from datetime import timedelta
    from app.mission.availability_models import AvailabilityChange, MissionAvailability
    from app.mission.timeline_builder.calculator import derive_mission_window

    service, view = prepared
    mission, manifest = service.store._load(view.mission.id)
    card = manifest.expected_legs[0]
    start, end = derive_mission_window(
        service.store.route_manager.get_route(card.route.route_id)
    )
    card.departure_time, card.arrival_time = start, end
    mission.availability = MissionAvailability(
        revision=1,
        history=(
            AvailabilityChange(
                id="before-adjusted-flight",
                transport="X",
                unavailable=True,
                effective_at=start + timedelta(minutes=5),
            ),
        ),
    )
    service.store.persist(mission, manifest)
    draft = card.draft.model_copy(deep=True)
    draft.adjusted_departure_time = start + timedelta(hours=1)
    draft.permitted_satellite_ids = ()
    draft.initial_x_satellite_id = None
    draft.access_confirmation = None
    saved = service.store.save_draft(
        mission.id, card.id, SaveDraft(expected_revision=view.revision, draft=draft)
    )
    assert saved.expected_legs[0].errors == []
    generated = service.proposals.generate(
        mission.id,
        card.id,
        GenerateProposal(
            expected_revision=saved.revision,
            input_identity=saved.expected_legs[0].input_identity,
        ),
    )
    assert generated.proposed_draft is not None


def test_stale_override_context_is_not_saved_after_override_preservation(prepared):
    from app.mission.availability_context import expected_snapshot
    from app.mission.planning.inputs import build_inputs
    from app.mission.planning.grid import build_context

    service, view = prepared
    AvailabilityService(service.store).command(
        view.mission.id,
        AvailabilitySettings(
            expected_revision=0,
            command_id="own-card-X",
            leg_overrides={"card-1": {"X": False}},
        ),
    )
    current = service.store.read(view.mission.id)
    card = current.expected_legs[0].leg
    stale = card.draft.model_copy(deep=True)
    stale.availability_overrides = {"X": True}
    stale.starshield_enabled = False
    inputs = build_inputs(
        card,
        stale,
        service.store.route_manager,
        service.store.poi_manager,
        service.store.planning_constraints_provider(),
        availability=expected_snapshot(current.mission, card, stale),
    )
    stale.evaluation_context = build_context(inputs, stale)
    saved = service.store.save_draft(
        view.mission.id,
        card.id,
        SaveDraft(expected_revision=current.revision, draft=stale),
    )
    assert saved.expected_legs[0].leg.draft.availability_overrides == {"X": False}
    assert saved.expected_legs[0].leg.draft.evaluation_context is None


def test_legacy_absent_override_keeps_literal_review_input_identity():
    from app.mission.planning.identity import planning_identity
    from app.mission.planning.models import ExpectedLeg
    from app.mission.planning.store import leg_identity

    legacy = {
        "id": "legacy-card",
        "ordinal": 1,
        "departure_airport": "AAAA",
        "arrival_airport": "BBBB",
        "departure_time": "2026-10-25T12:00:00Z",
        "arrival_time": "2026-10-25T14:00:00Z",
        "ar_rows": [],
        "ar_section_status": "empty",
        "route": None,
        "draft": {
            "permitted_satellite_ids": [],
            "access_confirmation": None,
            "starshield_enabled": True,
            "no_ars_confirmed": False,
            "initial_x_satellite_id": None,
            "swaps": [],
            "unresolved_x_transitions": [],
            "unresolved_aar_windows": [],
            "ar_corrections": [],
            "manual_aar_tracks": [],
            "manual_route_splice": None,
            "ka_outages": [],
            "ku_overrides": [],
            "adjusted_departure_time": None,
            "locks": [],
            "planning_policy": "prefer_starshield_v1",
            "evaluation_context": None,
        },
    }
    restored = ExpectedLeg.model_validate(legacy)
    assert leg_identity(restored) == planning_identity(legacy)
    restored.draft.availability_overrides = {"X": False}
    assert leg_identity(restored) != planning_identity(legacy)


def test_legacy_environment_review_survives_until_real_availability_edit(prepared):
    from dataclasses import asdict
    from .test_reviewed_save import review
    from app.mission.exporter.snapshot_inputs import _coverage_inputs
    from app.mission.planning.identity import planning_identity
    from app.mission.planning.inputs import route_record, resolve_positions
    from app.mission.planning.proposals import environment_identity

    service, view = prepared
    service.save_reviewed(view.mission.id, "card-1", review(service, view))
    mission, manifest = service.store._load(view.mission.id)
    card = manifest.expected_legs[0]
    constraints = service.store.planning_constraints_provider()
    # The prefeature environment contract intentionally had no eligibility key.
    legacy_environment = planning_identity(
        {
            "route": route_record(
                service.store.route_manager.get_route(card.route.route_id)
            ),
            "positions": resolve_positions(
                card.draft.permitted_satellite_ids, service.store.poi_manager
            ),
            "constraints": asdict(constraints),
            "coverage": [(source.name, source.digest) for source in _coverage_inputs()],
        }
    )
    card.review.environment_identity = legacy_environment
    service.store.persist(mission, manifest)
    restored = service.store.read(mission.id)
    assert restored.expected_legs[0].review_status == "reviewed"
    assert (
        environment_identity(service.store, card, constraints, mission=mission)
        == legacy_environment
    )
    AvailabilityService(service.store).command(
        mission.id,
        AvailabilitySettings(
            expected_revision=0, command_id="real-parent-edit", defaults={"Ka": False}
        ),
    )
    changed, updated = service.store._load(mission.id)
    assert (
        environment_identity(
            service.store, updated.expected_legs[0], constraints, mission=changed
        )
        != legacy_environment
    )
    assert (
        service.store.read(mission.id).expected_legs[0].review_status == "needs_review"
    )
