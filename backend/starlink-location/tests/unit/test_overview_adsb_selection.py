import pytest

from app.models.overview_adsb import AdsbContact, AdsbSettings
from app.services.overview_adsb_selection import position_state, select_contacts

NOW = 1791028800000.0


def contact(hex="00AB12", **changes):
    return AdsbContact(
        hex=hex,
        latitude=40,
        longitude=-75,
        position_observed_at_ms=NOW,
        acquired_at_ms=NOW,
        **changes
    )


@pytest.mark.parametrize(
    "age,state",
    [
        (29.999, "current"),
        (30, "stale"),
        (30.001, "stale"),
        (119.999, "stale"),
        (120, "expired"),
        (120.001, "expired"),
    ],
)
def test_exact_freshness_boundaries(age, state):
    c = contact()
    assert position_state(c, NOW + age * 1000) == state
    settings = AdsbSettings(enabled=True, include_hexes=["00AB12"])
    assert bool(select_contacts([c], settings, NOW + age * 1000)) == (
        state != "expired"
    )


def test_filter_precedence():
    contacts = [
        contact(military=False, callsign="RCH123"),
        contact("000002", military=False),
        contact("000003", military=True),
    ]
    settings = AdsbSettings(
        enabled=True,
        include_hexes=["00AB12", "000002"],
        exclude_hexes=["00AB12"],
        callsign_substrings=["NO"],
    )
    assert [c.hex for c in select_contacts(contacts, settings, NOW)] == ["000002"]
    assert select_contacts(contacts, AdsbSettings(), NOW) == []


def test_callsign_or_substrings():
    contacts = [
        contact(callsign=" xrch123 ", military=True),
        contact("000002", callsign="REACH9", military=True),
        contact("000003", military=True),
        contact("000004", callsign="RCH1", military=False),
    ]
    settings = AdsbSettings(enabled=True, callsign_substrings=["RCH", "REACH"])
    assert {c.hex for c in select_contacts(contacts, settings, NOW)} == {
        "00AB12",
        "000002",
    }
    assert len(select_contacts(contacts, AdsbSettings(enabled=True), NOW)) == 3


def test_included_only_empty_is_valid():
    assert (
        select_contacts(
            [contact(military=True)],
            AdsbSettings(enabled=True, mode="included_only"),
            NOW,
        )
        == []
    )


@pytest.mark.parametrize("reverse", [False, True])
def test_duplicate_newest_position_wins(reverse):
    old = contact(military=True, callsign="OLD")
    new = old.model_copy(
        update={"position_observed_at_ms": NOW + 1000, "callsign": "NEW"}
    )
    contacts = [old, new] if not reverse else [new, old]
    assert [
        c.callsign
        for c in select_contacts(contacts, AdsbSettings(enabled=True), NOW + 1000)
    ] == ["NEW"]
    later = new.model_copy(update={"acquired_at_ms": NOW + 2000, "callsign": "LATER"})
    assert (
        select_contacts([new, later], AdsbSettings(enabled=True), NOW + 1000)[
            0
        ].callsign
        == "LATER"
    )
