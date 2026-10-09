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
                        "et": r.clock.start + "–" + r.clock.end,
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
            "htmlPath": "mission-customer-briefing.html",
            "pngPath": "mission-customer-briefing.png",
            "pdfPath": "mission-customer-briefing.pdf",
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
    captured, projection, view = inputs()
    for field, value in (
        ("snapshotFingerprint", "other"),
        ("legId", "other"),
        ("totalMs", 60001),
        ("status", "failed"),
    ):
        raw = report(captured, view)
        raw[field] = value
        with pytest.raises(ValueError):
            build(captured, projection, view, raw)
    raw = report(captured, view)
    raw["fit"]["visibleRowIds"].pop()
    with pytest.raises(ValueError):
        build(captured, projection, view, raw)
    raw = report(captured, view)
    raw["cleanup"]["success"] = False
    with pytest.raises(ValueError):
        build(captured, projection, view, raw)
    raw = report(captured, view)
    raw["pdfValidation"]["verified"] = False
    with pytest.raises(ValueError):
        build(captured, projection, view, raw)


def test_evidence_preserves_exact_unknown_and_source_records():
    captured, projection, view = inputs("composition-incomplete-x")
    evidence = build(captured, projection, view, report(captured, view))
    parsed = json.loads(evidence)
    assert evidence == build(
        captured, projection, view, deepcopy(report(captured, view))
    )
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
    captured, projection, view = inputs()
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
            build(captured, projection, view, raw)


def mission_case():
    from dataclasses import replace

    from app.mission.exporter.customer_document import build_customer_mission_document

    captured, _, _ = inputs()
    captured = replace(
        captured,
        legs=tuple(replace(captured.legs[0], leg_id=f"leg-{i}") for i in range(2)),
    )
    payload = build_customer_mission_document(captured)
    pages = []
    proof = []
    for leg in payload["legs"]:
        chunks = (
            [leg["rows"][:3], leg["rows"][3:]]
            if leg["legId"] == "leg-0"
            else [leg["rows"]]
        )
        for index, rows in enumerate(chunks, 1):
            number = len(pages) + 1
            pages.append(
                {
                    "page": number,
                    "legId": leg["legId"],
                    "legPage": index,
                    "legPageCount": len(chunks),
                    "kind": "primary" if index == 1 else "continuation",
                    "flightStartUtc": leg["flight"]["startUtc"],
                    "flightEndUtc": leg["flight"]["endUtc"],
                    "rowStartUtc": rows[0]["startUtc"],
                    "rowEndUtc": rows[-1]["endUtc"],
                    "rowIds": [r["id"] for r in rows],
                }
            )
            proof.extend(
                {
                    "legId": leg["legId"],
                    "rowId": r["id"],
                    "page": number,
                    "displayCells": r["displayCells"],
                    "cellsMatched": True,
                    "inBounds": True,
                }
                for r in rows
            )
    plan = {
        "schemaVersion": 2,
        "missionId": captured.mission_id,
        "snapshotFingerprint": captured.fingerprint,
        "pages": pages,
    }
    raw = {
        "schemaVersion": 2,
        "status": "success",
        "missionId": captured.mission_id,
        "snapshotFingerprint": captured.fingerprint,
        "sharedBrowser": True,
        "launchCount": 1,
        "pagePlan": plan,
        "fit": {
            "pageCount": 3,
            "pages": [
                {
                    "page": p["page"],
                    "legId": p["legId"],
                    "visibleRowIds": p["rowIds"],
                    "overflow": [],
                    "labelOverlaps": [],
                    "width": 1280,
                    "height": 720,
                }
                for p in pages
            ],
        },
        "maps": {
            l["legId"]: {
                "status": "unavailable",
                "inputDiagnostics": l["mapInputDiagnostics"],
                "warnings": ["Map skipped"],
            }
            for l in payload["legs"]
        },
        "cleanup": {"success": True},
        "totalMs": 4321,
        "pdfValidation": {
            "verified": True,
            "pageCount": 3,
            "pageSizePt": [960, 540],
            "rows": proof,
            "fonts": ["DejaVuSans", "DejaVuSans-Bold"],
        },
        "artifacts": {
            "pdfPath": "mission-customer-briefing.pdf",
            "htmlPath": "private-preview.html",
            "pngPath": "private-preview.png",
        },
        "artifactHashes": {
            "pdfPath": "c" * 64,
            "htmlPath": "a" * 64,
            "pngPath": "b" * 64,
        },
    }
    return captured, payload, plan, raw


def mission_evidence(*args):
    module = importlib.import_module("app.mission.exporter.customer_evidence")
    assert hasattr(
        module, "build_customer_mission_evidence"
    ), "Mission evidence contract absent"
    return module.build_customer_mission_evidence(*args)


def test_mission_evidence_retains_exact_leg_records_and_public_pdf_only():
    captured, payload, plan, raw = mission_case()
    original = deepcopy(raw)
    parsed = json.loads(mission_evidence(captured, payload, plan, raw))
    assert parsed["schemaVersion"] == 2
    assert [l["legId"] for l in parsed["legs"]] == ["leg-0", "leg-1"]
    assert parsed["pages"] == plan["pages"]
    assert all(l["canonical"]["sources"] and l["customerRows"] for l in parsed["legs"])
    assert all(
        l["canonical"]["intervals"][0]["clocks"]["start"]["t_plus"] == "T+00:00"
        for l in parsed["legs"]
    )
    assert parsed["render"]["artifacts"] == {"pdfPath": "mission-customer-briefing.pdf"}
    assert "private-preview" not in json.dumps(parsed)
    assert raw == original


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "duplicate",
        "wrong-cell",
        "wrong-leg",
        "wrong-page",
        "fingerprint",
        "cleanup",
        "deadline",
        "overflow",
        "flight-bounds",
        "map-reasons",
    ],
)
def test_mission_evidence_rejects_unqualified_or_mismatched_proof(case):
    captured, payload, plan, raw = mission_case()
    if case == "missing":
        raw["pdfValidation"]["rows"].pop()
    elif case == "duplicate":
        raw["pdfValidation"]["rows"].append(deepcopy(raw["pdfValidation"]["rows"][0]))
    elif case == "wrong-cell":
        raw["pdfValidation"]["rows"][0]["displayCells"][0] = "10:01"
    elif case == "wrong-leg":
        raw["pdfValidation"]["rows"][0]["legId"] = "leg-1"
    elif case == "wrong-page":
        raw["pdfValidation"]["rows"][0]["page"] = 2
    elif case == "fingerprint":
        payload["snapshotFingerprint"] = "other"
    elif case == "cleanup":
        raw["cleanup"]["success"] = False
    elif case == "deadline":
        raw["totalMs"] = 60001
    elif case == "overflow":
        raw["fit"]["pages"][0]["overflow"] = ["row"]
    elif case == "flight-bounds":
        plan["pages"][1]["flightStartUtc"] = plan["pages"][1]["rowStartUtc"]
    else:
        raw["maps"]["leg-0"]["inputDiagnostics"] = ["invented reason"]
    with pytest.raises(ValueError):
        mission_evidence(captured, payload, plan, raw)
