"""Expected itinerary ordinal order is independent of publication order."""

from app.mission.planning.models import ExpectedLeg, PlanningManifest

from .cases import expected_leg_fields


def test_partial_order_retains_expected_numbers_and_legacy_order():
    from app.mission.planning.order import project_leg_order

    legs = [
        ExpectedLeg(**expected_leg_fields(id=f"card-{n}", ordinal=n)) for n in (1, 2, 3)
    ]
    legs[0].installed_leg_id = "z-last-lexical"
    legs[2].installed_leg_id = "a-first-lexical"
    manifest = PlanningManifest(expected_legs=legs)
    order = project_leg_order(
        manifest, ("a-first-lexical", "legacy-z", "z-last-lexical", "legacy-a")
    )
    assert order.executable_ids == (
        "z-last-lexical",
        "a-first-lexical",
        "legacy-z",
        "legacy-a",
    )
    assert order.numbers == {
        "z-last-lexical": 1,
        "a-first-lexical": 3,
        "legacy-z": 4,
        "legacy-a": 5,
    }
    assert order.total_count == 5


def test_unmanaged_order_is_unchanged():
    from app.mission.planning.order import project_leg_order

    order = project_leg_order(None, ("z", "a"))
    assert order.executable_ids == ("z", "a")
    assert order.numbers == {"z": 1, "a": 2}
    assert order.total_count == 2
