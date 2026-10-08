import importlib

from app.mission.exporter.trial_projection import project_trial_leg

from tests.unit.customer_briefing_fixtures import fixture, snapshot


def test_map_input_preserves_exact_outage_markers_and_dateline():
    name = "app.mission.exporter.map_inputs"
    assert importlib.util.find_spec(name), "pure map contract absent"
    build = importlib.import_module(name).build_map_input
    captured = snapshot(fixture("composition-assessed"))
    before = captured.effective_route_json
    trial = project_trial_leg(captured)
    raw, warnings = build(captured, trial)
    assert not warnings
    red = next(i for i in trial.intervals if i.posture == "Communications unavailable")
    marker = next(m for m in raw["markers"] if m["id"] == red.id)
    point = raw["route"][marker["routeIndex"]]
    assert point["timestamp"] == "2026-10-25T16:25:00Z"
    assert 48 < point["latitude"] < 57
    assert captured.effective_route_json == before
    data = fixture("composition-assessed")
    points = data["route"]["points"]
    for n, point in enumerate(points):
        point["latitude"] = 20
        point["longitude"] = [170, 179, -179, -170][n]
    cap = snapshot(data)
    raw, warnings = build(cap, project_trial_leg(cap))
    assert not warnings
    mid = next(p for p in raw["route"] if p["timestamp"] == "2026-10-25T16:25:00Z")
    assert abs(mid["longitude"]) > 179
