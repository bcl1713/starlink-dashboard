"""Source revisions merge against the accepted baseline, never over live edits."""

from app.mission.models import Mission, MissionLeg, TransportConfig


def mission():
    return Mission(
        id="m",
        name="Keep this name",
        legs=[
            MissionLeg(
                id="leg",
                name="AAAA–BBBB",
                route_id="r",
                transports=TransportConfig(initial_x_satellite_id="X"),
            )
        ],
    )


def merge(base, current, incoming, choices=None):
    from app.mission.itinerary_import.revisions import prepare_revision

    return prepare_revision(None, current, base, incoming, choices or {})


def test_manual_only_edits_and_source_only_edits_merge_independently():
    base = mission()
    current = base.model_copy(deep=True)
    incoming = base.model_copy(deep=True)
    current.legs[0].notes = "My note"
    incoming.legs[0].transports.starshield_enabled = False
    result = merge(base, current, incoming)
    assert result.conflicts == []
    assert result.mission.name == "Keep this name"
    assert result.mission.legs[0].notes == "My note"
    assert result.mission.legs[0].transports.starshield_enabled is False


def test_both_change_same_field_requires_explicit_choice():
    base = mission()
    current = base.model_copy(deep=True)
    incoming = base.model_copy(deep=True)
    current.legs[0].notes = "Manual"
    incoming.legs[0].notes = "New source"
    result = merge(base, current, incoming)
    assert [c.field for c in result.conflicts] == ["legs.leg.notes"]
    accepted = merge(base, current, incoming, {"legs.leg.notes": "retain"})
    assert accepted.conflicts == [] and accepted.mission.legs[0].notes == "Manual"
    assert (
        merge(base, current, incoming, {"legs.leg.notes": "replace"})
        .mission.legs[0]
        .notes
        == "New source"
    )


def test_identity_name_and_unchanged_leg_ids_are_retained():
    base = mission()
    current = base.model_copy(deep=True)
    incoming = base.model_copy(deep=True)
    incoming.name = "New extracted name"
    result = merge(base, current, incoming)
    assert result.mission.id == "m" and result.mission.name == current.name
    assert result.mission.legs[0].id == "leg"


def test_removed_manually_edited_leg_requires_a_choice():
    base = mission()
    current = base.model_copy(deep=True)
    incoming = base.model_copy(deep=True)
    current.legs[0].notes = "Keep my work"
    incoming.legs = []
    result = merge(base, current, incoming)
    assert result.conflicts and result.conflicts[0].field == "legs.leg"


def test_unmodified_active_leg_is_preserved():
    base = mission()
    current = base.model_copy(deep=True)
    current.legs[0].is_active = True
    assert merge(base, current, base).mission.legs[0].is_active
