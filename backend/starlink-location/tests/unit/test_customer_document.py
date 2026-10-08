"""Exact, safe document contract, independent of browser rendering."""

import importlib
import json
from dataclasses import replace
from hashlib import sha256

import pytest

from app.mission.exporter.customer_view import project_customer_leg
from app.mission.exporter.snapshot import ExportSnapshot
from app.mission.exporter.snapshot_inputs import canonical_json
from app.mission.exporter.trial_projection import project_trial_leg
from tests.unit.customer_briefing_fixtures import fixture, snapshot


def inputs(name="composition-assessed"):
    data = fixture(name)
    leg = snapshot(data)
    captured = ExportSnapshot(
        data["mission"]["id"],
        sha256(canonical_json(data)).hexdigest(),
        canonical_json(data["mission"]),
        (leg,),
        (),
        (),
    )
    trial = project_trial_leg(leg)
    view = project_customer_leg(leg, trial, leg_number=1, leg_count=1)
    return captured, trial, view


def build(*args):
    name = "app.mission.exporter.customer_document"
    assert importlib.util.find_spec(name), "document serialization contract absent"
    return importlib.import_module(name).build_customer_document(*args)


def test_document_preserves_geometry_and_safe_customer_fields():
    captured, trial, view = inputs()
    payload = build(captured, view, trial)
    assert payload["flight"] == {
        "startUtc": "2026-10-25T14:00:00Z",
        "endUtc": "2026-10-25T22:00:00Z",
    }
    red = [
        i for i in payload["intervals"] if i["posture"] == "Communications unavailable"
    ]
    assert len(red) == 1
    assert [red[0]["startUtc"], red[0]["endUtc"]] == [
        "2026-10-25T16:25:00Z",
        "2026-10-25T16:30:00Z",
    ]
    assert payload["header"]["timing"] == "DEP 10:00 ET | ARR 18:00 ET | 8h 00m"
    assert not any(
        t in json.dumps({k: v for k, v in payload.items() if k != "mapInput"})
        for t in ("PRIVATE", "rule-17", "abcdef123")
    )
    assert [r["id"] for r in payload["rows"]] == [r.id for r in view.rows]


def test_document_rejects_identity_and_partition_mismatch():
    captured, trial, view = inputs()
    for bad in (
        replace(captured, legs=captured.legs * 2),
        replace(captured, legs=(replace(captured.legs[0], leg_id="other"),)),
    ):
        with pytest.raises(ValueError):
            build(bad, view, trial)
    bad = replace(trial, intervals=trial.intervals[1:])
    with pytest.raises(ValueError):
        build(captured, replace(view, intervals=bad.intervals), bad)
    with pytest.raises(ValueError):
        build(
            captured,
            view,
            replace(
                trial,
                utc_bounds=(
                    trial.utc_bounds[0].replace(tzinfo=None),
                    trial.utc_bounds[1],
                ),
            ),
        )


def test_document_map_has_customer_endpoints_without_event_ordinals():
    captured, trial, view = inputs()
    payload = build(captured, view, trial)
    assert payload["mapInput"]["endpointLabels"] == {
        "departure": "KADW",
        "arrival": "PAED",
    }
    assert payload["mapInput"]["markers"] == []
    assert payload["rows"] and all(r["id"] for r in payload["rows"])


@pytest.mark.parametrize("invalid", ["missing", "malformed", "timing", "density"])
def test_map_input_diagnostics_survive_document_and_evidence(invalid):
    from app.mission.exporter.map_inputs import build_map_input
    from tests.unit.test_customer_evidence import build as evidence
    from tests.unit.test_customer_evidence import report

    captured, trial, view = inputs()
    route = json.loads(captured.legs[0].effective_route_json)
    if invalid == "missing":
        route_json = None
    elif invalid == "malformed":
        route_json = canonical_json({"points": [{"latitude": "bad"}]})
    elif invalid == "timing":
        route["points"][0]["expected_arrival_time"] = "2026-10-25T13:00:00Z"
        route_json = canonical_json(route)
    else:
        route["points"] = route["points"] * 501
        route_json = canonical_json(route)
    leg = replace(captured.legs[0], effective_route_json=route_json)
    captured = replace(captured, legs=(leg,))
    _, reasons = build_map_input(leg, trial)
    assert reasons
    payload = build(captured, view, trial)
    assert payload.get("mapInputDiagnostics") == list(reasons)
    raw = report(captured, view)
    raw["map"] = {"status": "unavailable", "warnings": ["Runtime map failed"]}
    result = json.loads(evidence(captured, trial, view, raw))
    assert result["mapInputDiagnostics"] == list(reasons)
    assert result["render"]["map"]["warnings"] == ["Runtime map failed"]
    assert captured.legs[0].effective_route_json == route_json


def test_successful_map_diagnostics_are_retained(monkeypatch):
    import app.mission.exporter.customer_document as module
    from app.mission.exporter.map_inputs import build_map_input

    captured, trial, view = inputs()
    map_input, _ = build_map_input(captured.legs[0], trial)
    monkeypatch.setattr(
        module, "build_map_input", lambda *args: (map_input, ("Position advisory",))
    )
    payload = build(captured, view, trial)
    assert payload.get("mapInputDiagnostics") == ["Position advisory"]
    assert payload["mapInput"]


def test_document_rows_carry_exact_display_cells():
    captured, trial, view = inputs()
    payload = build(captured, view, trial)
    assert payload["rows"][0].get("displayCells") == [
        "10:00–10:15",
        "Takeoff SOF",
        "Ka, Starshield, X-Band",
        "Nominal",
    ]


def mission_document(captured):
    import app.mission.exporter.customer_document as module

    assert hasattr(module, "build_customer_mission_document"), "Mission contract absent"
    return module.build_customer_mission_document(captured)


def test_mission_projects_ordered_legs_from_one_snapshot_without_mutation():
    captured, _, _ = inputs()
    legs = tuple(replace(captured.legs[0], leg_id=f"leg-{n}") for n in range(5))
    captured = replace(captured, legs=legs)
    payload = mission_document(captured)
    assert payload["schemaVersion"] == 2
    assert payload["missionId"] == captured.mission_id
    assert payload["snapshotFingerprint"] == captured.fingerprint
    assert [leg["legId"] for leg in payload["legs"]] == [leg.leg_id for leg in legs]
    for number, leg in enumerate(payload["legs"], 1):
        assert leg["snapshotFingerprint"] == captured.fingerprint
        assert leg["header"]["title"].startswith(f"LEG {number} OF 5")
        assert leg["flight"]["startUtc"] == "2026-10-25T14:00:00Z"
        assert leg["rows"][0]["displayCells"][0] == "10:00–10:15"
    assert captured.legs == legs


@pytest.mark.parametrize("case", ["empty", "duplicate", "bounds"])
def test_mission_rejects_unusable_identity_and_flight_data(case):
    captured, _, _ = inputs()
    legs = {
        "empty": (),
        "duplicate": captured.legs * 2,
        "bounds": (replace(captured.legs[0], utc_bounds=None),),
    }[case]
    with pytest.raises(ValueError):
        mission_document(replace(captured, legs=legs))


def test_mission_missing_map_retains_reasons_and_transport_facts():
    captured, _, _ = inputs()
    captured = replace(
        captured, legs=(replace(captured.legs[0], effective_route_json=None),)
    )
    leg = mission_document(captured)["legs"][0]
    assert leg["mapInput"] is None
    assert leg["mapInputDiagnostics"]
    assert any(row["posture"] == "Communications unavailable" for row in leg["rows"])


def test_document_rejects_reversed_and_duplicate_customer_rows():
    captured, trial, view = inputs()
    for rows in (view.rows[::-1], view.rows[:1] * 2):
        with pytest.raises(ValueError):
            build(captured, replace(view, rows=rows), trial)


@pytest.mark.parametrize(
    "name",
    [
        "mission-two-page",
        "mission-three-page",
        "mission-over-budget",
        "mission-five-leg",
    ],
)
def test_mission_fixture_material_rows_and_per_leg_flight_axes(name):
    from tests.unit.customer_briefing_fixtures import mission_snapshot

    captured = mission_snapshot(name)
    payload = mission_document(captured)
    assert len(payload["legs"]) == (5 if name == "mission-five-leg" else 1)
    for leg in payload["legs"]:
        assert all(row["impact"] != "Assessment changed" for row in leg["rows"])
        assert len({row["id"] for row in leg["rows"]}) == len(leg["rows"])
        assert all(
            a["endUtc"] <= b["startUtc"] for a, b in zip(leg["rows"], leg["rows"][1:])
        )
        assert all(
            leg["flight"]["startUtc"]
            <= row["startUtc"]
            < row["endUtc"]
            <= leg["flight"]["endUtc"]
            for row in leg["rows"]
        )
    if name == "mission-five-leg":
        assert all(
            a["flight"]["endUtc"] < b["flight"]["startUtc"]
            for a, b in zip(payload["legs"], payload["legs"][1:])
        )
