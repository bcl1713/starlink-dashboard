"""Effective identity ignores no-op selections and retains execution changes."""

from types import SimpleNamespace

from app.mission.effective_route import prepare_effective_route
from app.mission.models import (
    ManualAARTrack,
    ManualRouteSplice,
    MissionLeg,
    TransportConfig,
)
from app.mission.pop_capabilities import capability_input_revision
from app.satellites.catalog import SatelliteCatalog
from tests.unit.test_manual_aar_track import _timed_manual_track_route
from tests.unit.test_pop_continuity import START


def identity(leg, manager):
    return capability_input_revision(
        leg,
        prepare_effective_route(leg, manager),
        satellite_catalog=SatelliteCatalog(),
        ka_snapshot={"valid": False, "digest": None},
    )


def test_effective_identity_retains_independent_manual_track_changes():
    manager = SimpleNamespace(get_route=lambda _: _timed_manual_track_route(START))
    leg = MissionLeg(
        id="leg",
        name="Leg",
        route_id="r",
        transports=TransportConfig(initial_x_satellite_id="X-1"),
    )
    original = identity(leg, manager)
    leg.transports.manual_aar_tracks = [
        ManualAARTrack(
            id="independent",
            name="AR",
            points=[
                {"latitude": 50, "longitude": -49},
                {"latitude": 30, "longitude": -49},
            ],
        )
    ]
    changed = identity(leg, manager)
    assert changed != original
    leg.transports.manual_aar_tracks[0].points[1].latitude = 35
    assert identity(leg, manager) != changed


def test_selected_feasible_splice_and_speed_still_invalidate_identity():
    manager = SimpleNamespace(get_route=lambda _: _timed_manual_track_route(START))
    leg = MissionLeg(
        id="leg",
        name="Leg",
        route_id="r",
        transports=TransportConfig(initial_x_satellite_id="X-1"),
    )
    original = identity(leg, manager)
    leg.transports.manual_aar_tracks = [
        ManualAARTrack(
            id="selected",
            name="AR",
            points=[
                {"latitude": 50, "longitude": -49},
                {"latitude": 30, "longitude": -49},
            ],
        )
    ]
    leg.transports.manual_route_splice = ManualRouteSplice(
        enabled_track_id="selected", speed_knots=500
    )
    selected = identity(leg, manager)
    assert selected != original
    leg.transports.manual_route_splice.speed_knots = 450
    assert identity(leg, manager) != selected
