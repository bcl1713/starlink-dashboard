"""Reviewed normalization boundaries must fail safely before changing state."""

import pytest

from app.mission.models import ManualAARTrack, ManualAARTrackPoint, ManualRouteSplice
from app.simulation.run_plan import SimulationValidationError, prepare_mission_run
from tests.unit.simulation_run_fixtures import timed_plan_sources
from tests.unit.test_simulation_run_plan import multiplier_input


def test_duplicate_sparse_vertex_has_a_timing_validation_error(tmp_path):
    leg, routes, pois = timed_plan_sources(tmp_path)
    route = routes.get_route("replay")
    route.points[1].longitude = 0
    route.points[1].expected_arrival_time = None
    with pytest.raises(SimulationValidationError, match="positive duration") as error:
        prepare_mission_run("mission-1", leg, multiplier_input(10), routes, pois)
    assert error.value.field == "route"
    assert route.points[1].expected_arrival_time is None


@pytest.mark.parametrize("missing", [False, True])
def test_unavailable_selected_splice_does_not_replay_base_route(tmp_path, missing):
    leg, routes, pois = timed_plan_sources(tmp_path)
    leg.transports.manual_aar_tracks = (
        []
        if missing
        else [
            ManualAARTrack(
                id="far",
                name="Far diversion",
                points=[
                    ManualAARTrackPoint(latitude=50, longitude=0.3),
                    ManualAARTrackPoint(latitude=50, longitude=1.7),
                ],
            )
        ]
    )
    leg.transports.manual_route_splice = ManualRouteSplice(
        enabled_track_id="far", speed_knots=400
    )
    with pytest.raises(SimulationValidationError, match="Selected diversion") as error:
        prepare_mission_run("mission-1", leg, multiplier_input(10), routes, pois)
    assert error.value.field == "route"
    assert not leg.is_active
