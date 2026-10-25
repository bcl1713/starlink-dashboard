"""Shared eligibility contract; physical coverage remains a separate concern."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.mission.availability import (
    availability_boundaries,
    resolve_availability,
    resolved_leg_availability,
)
from app.mission.availability_models import AvailabilityChange, MissionAvailability
from app.mission.models import Mission, MissionLeg, Transport, TransportConfig

NOW = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)


def leg(**settings):
    return MissionLeg(
        id="leg-1",
        name="First",
        route_id="route-1",
        transports=TransportConfig(initial_x_satellite_id="", **settings),
    )


def change(transport, unavailable=True, minute=10, **kwargs):
    return AvailabilityChange(
        id=f"event-{transport}-{minute}",
        transport=transport,
        unavailable=unavailable,
        effective_at=NOW + timedelta(minutes=minute),
        **kwargs,
    )


@pytest.mark.parametrize("transport", list(Transport))
@pytest.mark.parametrize(
    "default,override,want",
    [
        (None, None, True),
        (False, None, False),
        (False, True, True),
        (True, False, False),
    ],
)
def test_mission_default_and_leg_override(transport, default, override, want):
    mission = Mission(
        id="mission",
        name="Mission",
        availability=MissionAvailability(
            defaults={} if default is None else {transport: default}
        ),
    )
    item = leg(availability_overrides={} if override is None else {transport: override})
    result = resolve_availability(mission, item, NOW)
    assert result[transport] is want
    assert all(result[t] is True for t in Transport if t != transport)


@pytest.mark.parametrize("transport", list(Transport))
def test_failure_crosses_leg_boundary(transport):
    mission = Mission(
        id="mission",
        name="Mission",
        availability=MissionAvailability(
            defaults={transport: True}, history=(change(transport),)
        ),
    )
    first = leg(availability_overrides={transport: True})
    second = leg().model_copy(update={"id": "leg-2"})
    assert resolve_availability(mission, first, NOW)[transport] is True
    assert (
        resolve_availability(mission, first, NOW + timedelta(minutes=15))[transport]
        is False
    )
    assert (
        resolve_availability(mission, second, NOW + timedelta(hours=5))[transport]
        is False
    )


@pytest.mark.parametrize("transport", list(Transport))
@pytest.mark.parametrize("planned", [True, False])
def test_restore_releases_only_failure(transport, planned):
    mission = Mission(
        id="mission",
        name="Mission",
        availability=MissionAvailability(
            defaults={transport: planned},
            history=(change(transport), change(transport, False, 20)),
        ),
    )
    assert (
        resolve_availability(mission, leg(), NOW + timedelta(minutes=15))[transport]
        is False
    )
    assert (
        resolve_availability(mission, leg(), NOW + timedelta(minutes=20))[transport]
        is planned
    )


@pytest.mark.parametrize(
    "defaults,overrides,want",
    [
        ({}, {}, False),
        ({"X": True}, {}, False),
        ({"Ku": True}, {}, True),
        ({}, {"Ku": True}, True),
        ({"Ku": True}, {"Ku": False}, False),
    ],
)
def test_legacy_starshield_false(defaults, overrides, want):
    mission = Mission(
        id="mission",
        name="Mission",
        availability=MissionAvailability(defaults=defaults),
    )
    assert (
        resolve_availability(
            mission,
            leg(starshield_enabled=False, availability_overrides=overrides),
            NOW,
        )[Transport.KU]
        is want
    )


@pytest.mark.parametrize("transport", list(Transport))
def test_half_open_failure_window(transport):
    mission = Mission(
        id="mission",
        name="Mission",
        availability=MissionAvailability(
            history=(change(transport), change(transport, False, 20))
        ),
    )
    item = leg()
    for minute, want in [(9.999, True), (10, False), (19.999, False), (20, True)]:
        assert (
            resolve_availability(mission, item, NOW + timedelta(minutes=minute))[
                transport
            ]
            is want
        )
    assert availability_boundaries(mission, item, NOW, NOW + timedelta(hours=1)) == (
        NOW + timedelta(minutes=10),
        NOW + timedelta(minutes=20),
    )
    assert (
        availability_boundaries(
            mission, item, NOW + timedelta(minutes=10), NOW + timedelta(minutes=20)
        )
        == ()
    )


def test_snapshot_is_immutable_and_survives_persistence():
    mission = Mission(
        id="mission",
        name="Mission",
        availability=MissionAvailability(revision=4, history=(change("X"),)),
    )
    item = leg()
    snapshot = resolved_leg_availability(mission, item)
    mission.availability.defaults[Transport.KA] = False
    assert snapshot.resolve(NOW) == {
        Transport.X: True,
        Transport.KA: True,
        Transport.KU: True,
    }
    assert snapshot.resolve(NOW + timedelta(hours=1))[Transport.X] is False
    assert (
        snapshot.revision == 4
        and snapshot.mission_id == "mission"
        and snapshot.leg_id == "leg-1"
    )
    with pytest.raises((ValidationError, AttributeError)):
        snapshot.revision = 5
    with pytest.raises(ValidationError):
        mission.availability.history[0].unavailable = False
    restored = Mission.model_validate_json(mission.model_dump_json())
    assert (
        resolve_availability(restored, item, NOW + timedelta(hours=1))[Transport.X]
        is False
    )


def test_simulation_failures_are_isolated_from_live_and_other_runs():
    history = (change("X", simulation_run_id="sim-a"), change("Ka", minute=11))
    mission = Mission(
        id="mission", name="Mission", availability=MissionAvailability(history=history)
    )
    assert resolve_availability(mission, leg(), NOW + timedelta(hours=1)) == {
        Transport.X: True,
        Transport.KA: False,
        Transport.KU: True,
    }
    mission.availability = mission.availability.model_copy(
        update={"simulation_run_id": "sim-a"}
    )
    assert resolve_availability(mission, leg(), NOW + timedelta(hours=1)) == {
        Transport.X: False,
        Transport.KA: True,
        Transport.KU: True,
    }


@pytest.mark.parametrize(
    "payload", [{"transport": "invalid"}, {"effective_at": NOW.replace(tzinfo=None)}]
)
def test_invalid_failure_input(payload):
    data = dict(id="failure", transport="X", unavailable=True, effective_at=NOW)
    data.update(payload)
    with pytest.raises(ValidationError):
        AvailabilityChange(**data)


def test_invalid_planned_keys_and_values():
    with pytest.raises(ValidationError):
        MissionAvailability(defaults={"Starshield": False})
    with pytest.raises(ValidationError):
        TransportConfig(
            initial_x_satellite_id="", availability_overrides={"X": "false"}
        )


def test_resolver_requires_aware_instants_and_ordered_interval():
    mission = Mission(id="mission", name="Mission")
    with pytest.raises(ValueError):
        resolve_availability(mission, leg(), NOW.replace(tzinfo=None))
    with pytest.raises(ValueError):
        availability_boundaries(mission, leg(), NOW + timedelta(hours=1), NOW)
