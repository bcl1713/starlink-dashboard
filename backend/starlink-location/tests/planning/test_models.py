"""Typed planning contracts and legacy-compatible occurrence anchors."""

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.mission.models import AARWindow, MissionLeg, TransportConfig, XTransition
from app.mission.planning import models
from app.mission.planning.identity import planning_identity

from .cases import anchor_fields, ar_fields, expected_leg_fields


def test_expected_leg_without_executable_route():
    leg = models.ExpectedLeg.model_validate(expected_leg_fields())
    assert leg.route is None
    assert leg.draft is None
    assert leg.installed_leg_id is None


def test_legacy_leg_omits_new_optional_fields():
    before = MissionLeg(
        id="legacy",
        name="Legacy",
        route_id="old-route",
        transports=TransportConfig(initial_x_satellite_id="X-1"),
    ).model_dump(exclude_none=True)
    after = MissionLeg.model_validate(before).model_dump(exclude_none=True)
    assert before == after
    assert "starshield_enabled" not in after["transports"]
    assert "planning_policy" not in after["transports"]
    assert "evaluation_context" not in after["transports"]


@pytest.mark.parametrize(
    "change",
    [
        {"fraction": 1.01},
        {"fraction": -0.01},
        {"fraction": float("nan")},
        {"latitude": float("inf")},
        {"longitude": 181},
        {"segment_index": -1},
        {"source_time": "2026-10-25T12:00:30"},
        {"timing_mode": "elapsed"},
        {"timing_mode": "fixed_utc", "elapsed_seconds": 60},
    ],
)
def test_invalid_anchor_rejected(change):
    with pytest.raises(ValidationError):
        models.RouteAnchor.model_validate(anchor_fields(**change))


def test_occurrences_and_timing_survive_legacy_transport_roundtrip():
    anchor = anchor_fields(timing_mode="elapsed", elapsed_seconds=30)
    transport = TransportConfig(
        initial_x_satellite_id="X-1",
        starshield_enabled=False,
        planning_policy="prefer_starshield_v1",
        x_transitions=[
            XTransition(
                id="swap",
                latitude=35,
                longitude=179.5,
                target_satellite_id="X-2",
                anchor=anchor,
            )
        ],
        aar_windows=[
            AARWindow(
                id="ar",
                start_waypoint_name="REPEATED",
                end_waypoint_name="REPEATED",
                start_anchor=anchor,
                end_anchor=anchor_fields(occurrence_id="occurrence-2"),
            )
        ],
    )
    restored = TransportConfig.model_validate_json(transport.model_dump_json())
    assert restored.x_transitions[0].anchor.elapsed_seconds == 30
    assert restored.aar_windows[0].end_anchor.occurrence_id == "occurrence-2"
    assert restored.starshield_enabled is False


@pytest.mark.parametrize(
    "change",
    [
        {
            "ku_overrides": [
                {
                    "id": "outage",
                    "start_time": "2026-10-25T12:00:00Z",
                    "duration_seconds": 30,
                }
            ]
        },
        {
            "locks": [
                {"id": "lock", "target_satellite_id": "X-2", "anchor": anchor_fields()}
            ]
        },
        {"starshield_enabled": False},
    ],
)
def test_planning_identity_changes_with_operational_inputs(change):
    before = {"starshield_enabled": True, "ku_overrides": [], "locks": []}
    after = {**deepcopy(before), **change}
    assert planning_identity(before) != planning_identity(after)


def test_identity_normalizes_utc_and_numbers_but_preserves_order():
    assert planning_identity(
        {"time": "2026-10-25T12:00:00Z", "x": 1}
    ) == planning_identity(
        {"x": 1.0, "time": datetime(2026, 10, 25, 12, tzinfo=timezone.utc)}
    )
    assert planning_identity(
        {"time": "2026-10-25T14:00:00+02:00"}
    ) == planning_identity({"time": "2026-10-25T12:00:00Z"})
    assert planning_identity({"records": [1, 2]}) != planning_identity(
        {"records": [2, 1]}
    )
    assert planning_identity(
        {"route_id": "old", "content_hash": "a" * 64}
    ) == planning_identity({"route_id": "remapped", "content_hash": "a" * 64})


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_identity_rejects_nonfinite_numbers(number):
    with pytest.raises(ValueError):
        planning_identity({"altitude": number})


def test_ar_preserves_source_units_and_requires_confirmation_for_geometry():
    ar = models.ItineraryAR.model_validate(ar_fields())
    with pytest.raises(ValueError, match="confirmed"):
        ar.geometric_height_meters()
    confirmed = models.ItineraryAR.model_validate(
        ar_fields(confirmed_units="flight_level")
    )
    assert confirmed.geometric_height_meters() == pytest.approx(6400.8)
    assert confirmed.source_altitude == 210


@pytest.mark.parametrize(
    "change",
    [
        {"exit_time": "2026-10-25T12:09:00Z"},
        {"match_status": "excluded"},
        {"source_altitude": float("nan")},
        {"entry_time": "2026-10-25T12:10:00"},
    ],
)
def test_ar_rejects_invalid_inputs(change):
    with pytest.raises(ValidationError):
        models.ItineraryAR.model_validate(ar_fields(**change))


def test_leg_rejects_ar_outside_utc_window():
    with pytest.raises(ValidationError):
        models.ExpectedLeg.model_validate(
            expected_leg_fields(ar_rows=[ar_fields(exit_time="2026-10-25T15:00:00Z")])
        )


def test_access_confirmation_is_bound_to_selected_ids():
    selected = {
        "permitted_satellite_ids": ["X-1"],
        "access_confirmation": {"satellite_ids": ["X-1"], "confirmed": True},
    }
    draft = models.PlanningDraft.model_validate(selected)
    assert draft.access_confirmation.confirmed
    changed = models.PlanningDraft.model_validate(
        {**selected, "permitted_satellite_ids": ["X-2"]}
    )
    assert changed.access_confirmation is None
    assert changed.starshield_enabled is True


def test_context_retains_exact_grid_and_rejects_unknown_version():
    fields = {
        "seed_times": ["2026-10-25T12:00:30Z"],
        "candidate_times": [
            "2026-10-25T12:00:00Z",
            "2026-10-25T12:00:30Z",
            "2026-10-25T14:00:00Z",
        ],
        "boundaries": [
            "2026-10-25T12:00:00Z",
            "2026-10-25T12:00:30Z",
            "2026-10-25T14:00:00Z",
        ],
        "input_identity": "a" * 64,
    }
    context = models.EvaluationContext.model_validate(fields)
    assert context.seed_times[0].second == 30
    assert (
        models.EvaluationContext.model_validate_json(context.model_dump_json())
        == context
    )
    with pytest.raises(ValidationError, match="migration"):
        models.EvaluationContext.model_validate({**fields, "version": "unknown"})


def test_manifest_schema_and_expected_leg_links_are_validated():
    fields = {"expected_legs": [expected_leg_fields()]}
    assert models.PlanningManifest.model_validate(fields).schema_version == 1
    with pytest.raises(ValidationError, match="migration"):
        models.PlanningManifest.model_validate({**fields, "schema_version": 2})
    with pytest.raises(ValidationError):
        models.PlanningManifest.model_validate(
            {"expected_legs": [expected_leg_fields(ordinal=2)]}
        )
    with pytest.raises(ValidationError):
        models.PlanningManifest.model_validate(
            {
                "expected_legs": [
                    expected_leg_fields(installed_leg_id="installed"),
                    expected_leg_fields(
                        id="expected-2", ordinal=2, installed_leg_id="installed"
                    ),
                ]
            }
        )


def test_card_review_status_is_derived_from_current_identity():
    review = {
        "input_identity": "a" * 64,
        "saved_at": "2026-10-25T14:00:00Z",
        "no_ars_confirmed": True,
        "satellite_plan_confirmed": True,
    }
    leg = models.ExpectedLeg.model_validate(expected_leg_fields(review=review))
    assert (
        models.ExpectedLegCard(leg=leg, input_identity="a" * 64).review_status
        == "awaiting_kml"
    )
    binding = {
        "route_id": "route-owned",
        "source_id": "source-owned",
        "content_hash": "a" * 64,
        "filename": "route.kml",
    }
    leg = models.ExpectedLeg.model_validate(
        expected_leg_fields(route=binding, review=review)
    )
    assert (
        models.ExpectedLegCard(leg=leg, input_identity="a" * 64).review_status
        == "reviewed"
    )
    assert (
        models.ExpectedLegCard(leg=leg, input_identity="b" * 64).review_status
        == "needs_review"
    )


def test_public_source_serialization_omits_storage_path():
    source = models.SourceRevision(
        id="source",
        owner="mission",
        kind="itinerary_pdf",
        filename="source.pdf",
        content_hash="a" * 64,
        owned_relative_path="mission/source.pdf",
        expires_at="2026-10-26T12:00:00Z",
    )
    assert source.owned_relative_path == "mission/source.pdf"
    assert "owned_relative_path" not in source.model_dump(mode="json")
    assert source.storage_record()["owned_relative_path"] == "mission/source.pdf"
    with pytest.raises(ValidationError):
        models.SourceRevision.model_validate(
            {**source.storage_record(), "owned_relative_path": "../other.pdf"}
        )


@pytest.mark.parametrize(
    "request_name",
    [
        "ConfirmItinerary",
        "AcceptRouteBinding",
        "SaveDraft",
        "PreviewDraft",
        "GenerateProposal",
        "ApplyProposal",
        "SaveReviewed",
        "ApplyRevision",
    ],
)
def test_mutations_have_typed_wire_schema(request_name):
    schema = getattr(models, request_name).model_json_schema()
    assert schema["additionalProperties"] is False
    assert (
        "expected_revision" in schema["required"]
        if request_name != "ConfirmItinerary"
        else "preview_id" in schema["required"]
    )
    if request_name in {"ApplyProposal", "SaveReviewed", "ApplyRevision"}:
        assert "input_identity" in schema["required"]


def test_evaluation_intervals_are_valid_half_open_windows():
    with pytest.raises(ValidationError):
        models.EvaluationInterval(
            start_time="2026-10-25T12:00:00Z", end_time="2026-10-25T12:00:00Z"
        )


def test_replacing_selected_ids_clears_access_confirmation():
    draft = models.PlanningDraft(
        permitted_satellite_ids=["X-1"],
        access_confirmation={"satellite_ids": ["X-1"], "confirmed": True},
    )
    draft.permitted_satellite_ids = ["X-2"]
    assert draft.access_confirmation is None


def test_route_bindings_are_immutable_and_unknown_profiles_need_migration():
    binding = models.RouteBinding(
        route_id="owned",
        source_id="source",
        content_hash="a" * 64,
        filename="route.kml",
    )
    with pytest.raises(ValidationError):
        binding.route_id = "other"
    with pytest.raises(ValidationError, match="migration"):
        models.RouteBinding.model_validate(
            {**binding.model_dump(), "ingestion_profile": "planning_v2"}
        )


def test_public_manifest_has_a_separate_lossless_storage_representation():
    source = models.SourceRevision(
        id="source",
        owner="mission",
        kind="route_kml",
        filename="route.kml",
        content_hash="a" * 64,
        owned_relative_path="mission/route.kml",
    )
    manifest = models.PlanningManifest(source_revisions=[source])
    assert (
        "owned_relative_path"
        not in manifest.model_dump(mode="json")["source_revisions"][0]
    )
    assert models.PlanningManifest.model_validate(manifest.storage_record()) == manifest


@pytest.mark.parametrize(
    "changes",
    [
        {
            "ka_outages": [
                {
                    "id": "outage",
                    "start_time": "2026-10-25T12:00:00Z",
                    "duration_seconds": float("inf"),
                }
            ]
        },
        {
            "ku_overrides": [
                {
                    "id": "outage",
                    "start_time": "2026-10-25T12:00:00",
                    "duration_seconds": 30,
                }
            ]
        },
        {
            "locks": [
                {"id": "a", "target_satellite_id": "X-1", "anchor": anchor_fields()},
                {"id": "b", "target_satellite_id": "X-2", "anchor": anchor_fields()},
            ]
        },
    ],
)
def test_drafts_reject_invalid_operational_inputs(changes):
    with pytest.raises(ValidationError):
        models.PlanningDraft.model_validate(changes)


def test_satellite_eligibility_requires_validated_x_position_and_does_not_grant_access():
    with pytest.raises(ValidationError):
        models.PlanningSatelliteOption(
            id="X-1", label="Configured", transport="X", eligible=True
        )
    option = models.PlanningSatelliteOption(
        id="X-1",
        label="Configured",
        transport="X",
        eligible=True,
        latitude=0,
        longitude=10,
    )
    assert "access_confirmation" not in option.model_dump()


def test_identity_normalizes_minute_precision_utc_timestamps():
    assert planning_identity({"time": "2026-10-25T12:00Z"}) == planning_identity(
        {"time": "2026-10-25T12:00:00Z"}
    )


def test_permitted_ids_cannot_be_mutated_through_the_returned_collection():
    draft = models.PlanningDraft(
        permitted_satellite_ids=["X-1"],
        access_confirmation={"satellite_ids": ["X-1"], "confirmed": True},
    )
    with pytest.raises(AttributeError):
        draft.permitted_satellite_ids.append("X-2")
    assert tuple(draft.permitted_satellite_ids) == ("X-1",)
    assert draft.access_confirmation.confirmed


def test_permitted_ids_augmented_replacement_invalidates_access():
    draft = models.PlanningDraft(
        permitted_satellite_ids=["X-1"],
        access_confirmation={"satellite_ids": ["X-1"], "confirmed": True},
    )
    draft.permitted_satellite_ids += ("X-2",)
    assert tuple(draft.permitted_satellite_ids) == ("X-1", "X-2")
    assert draft.access_confirmation is None


def test_confirmation_ids_cannot_be_mutated_through_a_retained_reference():
    confirmation = models.AccessConfirmation(satellite_ids=["X-1"], confirmed=True)
    draft = models.PlanningDraft(
        permitted_satellite_ids=["X-1"], access_confirmation=confirmation
    )
    with pytest.raises(AttributeError):
        confirmation.satellite_ids.append("X-2")
    assert tuple(draft.access_confirmation.satellite_ids) == ("X-1",)


def test_retained_confirmation_cannot_be_reassigned():
    confirmation = models.AccessConfirmation(satellite_ids=["X-1"], confirmed=True)
    draft = models.PlanningDraft(
        permitted_satellite_ids=["X-1"], access_confirmation=confirmation
    )
    with pytest.raises(ValidationError):
        confirmation.satellite_ids = ("X-2",)
    assert tuple(draft.access_confirmation.satellite_ids) == ("X-1",)


@pytest.mark.parametrize(
    "source_text",
    [
        "2026-10-25T12:10 AR TRACK 210",
        "2026-10-25T12:10:00Z AR TRACK 210",
        "2026-10-25T12:10:00Z continued evidence",
    ],
)
def test_identity_preserves_datetime_prefixed_evidence_text(source_text):
    expected = hashlib.sha256(
        json.dumps({"source_text": source_text}, separators=(",", ":")).encode()
    ).hexdigest()
    assert planning_identity({"source_text": source_text}) == expected


def test_immutable_satellite_ids_still_serialize_as_wire_arrays():
    draft = models.PlanningDraft(
        permitted_satellite_ids=["X-1"],
        access_confirmation={"satellite_ids": ["X-1"], "confirmed": True},
    )
    dumped = draft.model_dump(mode="json")
    assert dumped["permitted_satellite_ids"] == ["X-1"]
    assert dumped["access_confirmation"]["satellite_ids"] == ["X-1"]
    restored = models.PlanningDraft.model_validate_json(draft.model_dump_json())
    assert restored == draft
