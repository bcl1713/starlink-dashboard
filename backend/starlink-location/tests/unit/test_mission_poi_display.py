"""Generated presentation normalizes old labels without rewriting stored/user names."""

from typing import get_args

import pytest

from app.models.poi import POI, MissionPoiKind
from app.mission.poi_display import MISSION_POI_LABELS, display_poi_name

LABELS = {
    "departure": "Takeoff",
    "arrival": "Landing",
    "aar_start": "AR Begins",
    "aar_end": "AR Ends",
    "ka_coverage_exit": "KA Coverage Ends",
    "ka_coverage_entry": "KA Coverage Resumes",
    "ka_transition": "KA Satellite Handover",
    "ka_outage_start": "Planned KA Outage Begins",
    "ka_outage_end": "Planned KA Outage Ends",
    "x_band_transition": "X-Band Satellite Handover",
    "x_band_warning_start": "X-Band Restriction Begins",
    "x_band_warning_end": "X-Band Restriction Ends",
    "starshield_transition_start": "Starshield Transition Window Begins",
    "starshield_transition_end": "Starshield Transition Window Ends",
    "starshield_outage_start": "Planned Starshield Outage Begins",
    "starshield_outage_end": "Planned Starshield Outage Ends",
}


def test_every_typed_kind_has_the_explicit_owner_vocabulary():
    assert MISSION_POI_LABELS == LABELS
    assert set(LABELS) == set(get_args(MissionPoiKind))


@pytest.mark.parametrize(
    "kind,old",
    [
        ("aar_start", "AR\nStart"),
        ("aar_end", "AR\nEnd"),
        ("x_band_warning_start", "X-Band Shut Down"),
        ("x_band_warning_end", "X-Band Turn On"),
        ("x_band_transition", "X-Band\nSwap"),
        ("ka_coverage_exit", "CommKa\nExit"),
        ("ka_coverage_entry", "CommKa\nEnter"),
        ("ka_transition", "CommKa\nSwap"),
        ("ka_outage_start", "Ka\nLoss"),
        ("ka_outage_end", "Ka\nRestore"),
        ("starshield_outage_start", "Starshield\nLoss"),
        ("starshield_outage_end", "Starshield\nRestore"),
        ("starshield_transition_start", "Starshield transition entry"),
        ("starshield_transition_end", "Starshield transition exit"),
    ],
)
def test_legacy_generated_names_are_display_only(kind, old):
    poi = POI(
        id="stable-id",
        name=old,
        latitude=0,
        longitude=0,
        kind=kind,
        generated_source="mission-timeline",
    )
    before = poi.model_copy(deep=True)
    assert display_poi_name(poi) == LABELS[kind]
    assert poi == before
    assert display_poi_name(poi.model_copy(update={"generated_source": None})) == old
    assert (
        display_poi_name(poi.model_copy(update={"name": "My custom note"}))
        == "My custom note"
    )


def test_preserves_endpoints_and_supported_satellite_detail():
    def poi(kind, name):
        return POI(
            id="same",
            name=name,
            kind=kind,
            latitude=0,
            longitude=0,
            generated_source="mission-timeline",
        )

    assert display_poi_name(poi("departure", "McGuire AFB")) == "McGuire AFB"
    assert display_poi_name(poi("arrival", "McGuire AFB")) == "McGuire AFB"
    assert (
        display_poi_name(poi("ka_transition", "Ka Transition SAT-a → SAT-b"))
        == "KA Satellite Handover SAT-a → SAT-b"
    )
