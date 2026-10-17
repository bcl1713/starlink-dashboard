"""Transition cues use window entry/exit positions, not the PoP or crossing."""

from app.mission.models import MissionLeg, TransportConfig
from app.mission.timeline_preparation import prepare_mission_timeline
from app.services.route_manager import RouteManager
from tests.unit.test_mission_pop_forecast import route, sites


def test_prepared_transition_has_entry_and_exit_map_pois(tmp_path):
    manager = RouteManager(routes_dir=tmp_path / "routes")
    r = route()
    manager.add_route("r", r)
    leg = MissionLeg(
        id="leg",
        name="leg",
        route_id="r",
        transports=TransportConfig(initial_x_satellite_id="X-1"),
    )
    artifacts = prepare_mission_timeline(
        leg,
        manager,
        discover_coverage=False,
        pop_catalog=sites(("a", 0, -5), ("b", 0, 15)),
    )
    timeline = artifacts.timeline
    transition = timeline.pop_forecast.transitions[0]
    cues = [
        p
        for p in artifacts.generated_pois
        if p.kind in ("starshield_transition_start", "starshield_transition_end")
    ]
    assert [p.kind for p in cues] == [
        "starshield_transition_start",
        "starshield_transition_end",
    ]
    assert [p.expected_arrival_time for p in cues] == [
        transition.window_start_utc,
        transition.window_end_utc,
    ]
    assert cues[0].longitude < transition.crossing.longitude < cues[1].longitude
    assert all(p.mission_id == "leg" and p.route_id == "r" for p in cues)
    assert (
        len(
            [
                p
                for p in timeline.map_pois
                if p.kind.startswith("starshield_transition_")
            ]
        )
        == 2
    )
