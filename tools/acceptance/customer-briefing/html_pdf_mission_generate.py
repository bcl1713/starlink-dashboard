"""Synthetic mission qualification; production capture/ZIP acceptance is separate."""

import json
import os
import shutil
import subprocess
from pathlib import Path

from html_pdf_inspect import normalized_pdf_hash
from PIL import Image

from app.mission.exporter.customer_document import build_customer_mission_document
from app.mission.exporter.customer_evidence import build_customer_mission_evidence
from app.mission.exporter.snapshot_inputs import canonical_json
from tests.unit.customer_briefing_fixtures import fixture, mission_snapshot

FRONTEND = Path("/renderer/frontend/mission-planner")


def generate_missions(root, run):
    root = root / "missions"
    root.mkdir()
    names = (
        "mission-two-page",
        "mission-three-page",
        "mission-over-budget",
        "mission-five-leg",
        "mission-midnight",
    )
    captured = {name: mission_snapshot(name) for name in names}
    for name, snapshot in captured.items():
        (root / (name + ".json")).write_bytes(
            canonical_json(build_customer_mission_document(snapshot))
        )
    attempts = []

    def render(name, attempt, fault=None, budget=60000):
        output = root / attempt
        output.mkdir()
        env = {**os.environ, "CHECKPOINT_BUDGET_MS": str(budget)}
        if fault:
            env["CHECKPOINT_FAULT"] = fault
        code = run(
            [
                "timeout",
                "--kill-after=10s",
                "70s",
                "node",
                "src/mission-export/briefing-render.mjs",
                str(root / (name + ".json")),
                str(output),
                str(FRONTEND / "dist-mission-export"),
            ],
            root / (attempt + ".log"),
            env=env,
            timeout=85,
        )
        report = json.loads((output / "render-report.json").read_text())
        if not report["cleanup"]["success"] or report["totalMs"] > budget:
            raise ValueError("Mission cleanup/deadline failed: " + attempt)
        attempts.append(
            {
                "attempt": attempt,
                "status": report["status"],
                "errorCode": report["errorCode"],
                "totalMs": report["totalMs"],
                "marginMs": budget - report["totalMs"],
                "stages": report["stages"],
                "cleanup": report["cleanup"],
            }
        )
        if fault or name == "mission-over-budget":
            if (
                code == 0
                or report["status"] != "failed"
                or report["artifacts"] is not None
            ):
                raise ValueError("Mission failure incorrectly published: " + attempt)
            if (
                any(output.glob("*.pdf"))
                or any(output.glob("*.png"))
                or any(output.glob("*.html"))
            ):
                raise ValueError("Mission failure left optional artifacts: " + attempt)
            if name == "mission-over-budget" and report["errorCode"] != "page-budget":
                raise ValueError(
                    "Unexpected over-budget failure: " + report["errorCode"]
                )
            return output, report
        if code or report["status"] != "success" or report["launchCount"] != 1:
            raise ValueError(
                "Mission render failed: " + attempt + ": " + str(report.get("error"))
            )
        if report["fit"]["pageCount"] != fixture(name)["expectedPages"]:
            raise ValueError(
                "Mission page count mismatch: "
                + attempt
                + ": "
                + str(report["fit"]["pageCount"])
            )
        payload = build_customer_mission_document(captured[name])
        evidence = build_customer_mission_evidence(
            captured[name], payload, report["pagePlan"], report
        )
        (output / "mission-customer-briefing-evidence.json").write_bytes(evidence)
        return output, report

    identities, deliveries = [], {}
    for number in range(1, 4):
        output, report = render("mission-five-leg", f"five-leg-cold-{number}")
        if any(m["status"] != "primary" for m in report["maps"].values()):
            raise ValueError("Representative five-leg useful maps missing")
        pdf = output / report["artifacts"]["pdfPath"]
        text = subprocess.check_output(
            ["pdftotext", "-layout", str(pdf), "-"], text=True, timeout=30
        )
        identities.append(
            {
                "text": text,
                "normalizedPdfHash": normalized_pdf_hash(pdf),
                "pagePlan": report["pagePlan"],
                "fit": report["fit"],
                "previewHashes": {
                    k: v for k, v in report["artifactHashes"].items() if k != "pdfPath"
                },
            }
        )
        if number == 1:
            deliveries["five-leg"] = output
    if any(identity != identities[0] for identity in identities[1:]):
        raise ValueError("Five-leg cold render nondeterminism")
    for name in ("mission-two-page", "mission-three-page", "mission-midnight"):
        deliveries[name] = render(name, name)[0]
    render("mission-over-budget", "mission-over-budget")
    fault_payload = build_customer_mission_document(captured["mission-five-leg"])
    fault_payload["legs"] = fault_payload["legs"][:1]
    fault_payload["legs"][0]["mapInput"] = None
    (root / "fault-single-leg.json").write_bytes(canonical_json(fault_payload))
    for fault in (
        "startup",
        "font",
        "image",
        "measure-hang",
        "print",
        "print-hang",
        "verify-hang",
        "cleanup",
    ):
        render("fault-single-leg", "failure-" + fault, fault=fault, budget=8000)
    for name, output in deliveries.items():
        pdf = output / "mission-customer-briefing.pdf"
        report = json.loads((output / "render-report.json").read_text())
        text = subprocess.check_output(
            ["pdftotext", "-layout", str(pdf), "-"], text=True, timeout=30
        )
        if (
            any(p["kind"] == "continuation" for p in report["pagePlan"]["pages"])
            and "Coordination windows continued" not in text
        ):
            raise ValueError("Continuation copy missing in PDF")
        for mode in ("color", "grayscale"):
            args = ["pdftoppm", "-r", "240", "-png"]
            if mode == "grayscale":
                args.append("-gray")
            subprocess.run(
                [*args, str(pdf), str(output / ("pdf-" + mode))],
                check=True,
                timeout=90,
                capture_output=True,
            )
        delivered = root / "delivered" / name
        delivered.mkdir(parents=True)
        for file in output.iterdir():
            if (
                file.suffix in (".pdf", ".png")
                or file.name == "mission-customer-briefing-evidence.json"
            ):
                shutil.copy2(file, delivered / file.name)
        for file in delivered.glob("*.png"):
            with Image.open(file) as image:
                if image.size != (3200, 1800):
                    raise ValueError("Mission PDF/preview raster geometry mismatch")
    summary = {
        "checksPassed": True,
        "fixtureKind": "synthetic immutable DTO; production path acceptance pending",
        "visualAcceptance": "pending",
        "attempts": attempts,
        "deliveries": list(deliveries),
        "determinism": {"coldRuns": 3, "textGeometryPixelsPagesNormalizedPdf": True},
    }
    (root / "mission-generation-report.json").write_text(json.dumps(summary, indent=2))
    return summary
