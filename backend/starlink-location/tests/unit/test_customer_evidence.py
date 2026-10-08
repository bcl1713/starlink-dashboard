"""Evidence requires successful actual PDF/cleanup proof and exact identity."""

import importlib
import json
from copy import deepcopy

import pytest

from tests.unit.test_customer_document import inputs


def report(captured, view):
    from app.mission.exporter.customer_display import display_row

    rows = [
        {
            "legId": view.leg_id,
            "rowId": r.id,
            "page": 1,
            "displayCells": list(
                display_row(
                    {
                        "et": ("≈ " if r.clock.approximate else "")
                        + r.clock.start
                        + "–"
                        + r.clock.end,
                        "impact": r.impact,
                        "remaining": r.remaining,
                        "posture": r.posture,
                    }
                )
            ),
            "cellsMatched": True,
            "inBounds": True,
        }
        for r in view.rows
    ]
    return {
        "schemaVersion": 1,
        "status": "success",
        "legId": view.leg_id,
        "snapshotFingerprint": captured.fingerprint,
        "sharedBrowser": True,
        "launchCount": 1,
        "fit": {
            "pageCount": 1,
            "visibleRowIds": [r.id for r in view.rows],
            "overflow": [],
        },
        "cleanup": {"success": True},
        "totalMs": 1234,
        "artifacts": {
            "htmlPath": "mission-customer-briefing-trial.html",
            "pngPath": "mission-customer-briefing-trial.png",
            "pdfPath": "mission-customer-briefing-trial.pdf",
        },
        "artifactHashes": {
            "htmlPath": "a" * 64,
            "pngPath": "b" * 64,
            "pdfPath": "c" * 64,
        },
        "pdfValidation": {
            "verified": True,
            "pageCount": 1,
            "pageSizePt": [960, 540],
            "rows": rows,
        },
    }


def build(*args):
    name = "app.mission.exporter.customer_evidence"
    assert importlib.util.find_spec(name), "evidence validation contract absent"
    return importlib.import_module(name).build_customer_evidence(*args)


def test_evidence_rejects_mismatched_snapshot_and_page_rows():
    captured, trial, view = inputs()
    for field, value in (
        ("snapshotFingerprint", "other"),
        ("legId", "other"),
        ("totalMs", 60001),
        ("status", "failed"),
    ):
        raw = report(captured, view)
        raw[field] = value
        with pytest.raises(ValueError):
            build(captured, trial, view, raw)
    raw = report(captured, view)
    raw["fit"]["visibleRowIds"].pop()
    with pytest.raises(ValueError):
        build(captured, trial, view, raw)
    raw = report(captured, view)
    raw["cleanup"]["success"] = False
    with pytest.raises(ValueError):
        build(captured, trial, view, raw)
    raw = report(captured, view)
    raw["pdfValidation"]["verified"] = False
    with pytest.raises(ValueError):
        build(captured, trial, view, raw)


def test_evidence_preserves_exact_unknown_and_source_records():
    captured, trial, view = inputs("composition-incomplete-x")
    evidence = build(captured, trial, view, report(captured, view))
    parsed = json.loads(evidence)
    assert evidence == build(captured, trial, view, deepcopy(report(captured, view)))
    assert all(
        i["decisions"][2]["value"] == "?" for i in parsed["canonical"]["intervals"]
    )
    assert any(
        s["reason"].startswith("PRIVATE") for s in parsed["canonical"]["sources"]
    )
    assert parsed["canonical"]["utcBounds"] == [
        "2026-10-25T14:00:00Z",
        "2026-10-25T22:00:00Z",
    ]
    assert all(
        i["clocks"]["start"]["zulu"] and i["clocks"]["start"]["t_plus"]
        for i in parsed["canonical"]["intervals"]
    )
    assert parsed["pages"][0]["rowIds"] == [r.id for r in view.rows]


def test_evidence_rejects_unverified_actual_pdf_rows():
    captured, trial, view = inputs()
    raw = report(captured, view)
    for rows in (
        None,
        [],
        [
            {
                "rowId": r.id,
                "legId": view.leg_id,
                "page": 1,
                "cellsMatched": False,
                "inBounds": True,
            }
            for r in view.rows
        ],
    ):
        raw["pdfValidation"]["rows"] = rows
        with pytest.raises(ValueError):
            build(captured, trial, view, raw)
