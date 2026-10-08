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
