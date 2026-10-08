"""Container entrypoint: synthetic DTO injection and two checkpoint pages only."""

import json
import os
import platform
import signal
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

from app.mission.exporter.customer_document import build_customer_document
from app.mission.exporter.customer_evidence import build_customer_evidence
from app.mission.exporter.customer_pdf import verify_customer_pdf
from app.mission.exporter.customer_view import project_customer_leg
from app.mission.exporter.snapshot import ExportSnapshot
from app.mission.exporter.snapshot_inputs import canonical_json
from app.mission.exporter.trial_projection import project_trial_leg
from html_pdf_checkpoint import publish_checkpoint
from html_pdf_inspect import inspect_pdf, normalized_pdf_hash
from tests.unit.customer_briefing_fixtures import fixture, snapshot

FRONTEND = Path("/renderer/frontend/mission-planner")
ASSETS = FRONTEND / "dist-mission-export"
active = None


def stop(signum, frame):
    if active and active.poll() is None:
        os.killpg(active.pid, signal.SIGTERM)
        try:
            active.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(active.pid, signal.SIGKILL)
            active.wait(timeout=10)
    raise KeyboardInterrupt("Checkpoint cancelled")


def run(args, log, env=None, timeout=85):
    global active
    with log.open("w") as stream:
        active = subprocess.Popen(
            args,
            cwd=FRONTEND,
            env=env,
            start_new_session=True,
            stdout=stream,
            stderr=subprocess.STDOUT,
        )
        (log.with_suffix(".ownership.json")).write_text(
            json.dumps(
                {
                    "command": args,
                    "pid": active.pid,
                    "pgid": active.pid,
                    "log": str(log),
                }
            )
        )
        try:
            return active.wait(timeout=timeout)
        except BaseException:
            if active.poll() is None:
                os.killpg(active.pid, signal.SIGTERM)
                try:
                    active.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(active.pid, signal.SIGKILL)
                    active.wait(timeout=10)
            raise
        finally:
            active = None


def canonical(name):
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


def generate(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, stop)
    inputs = root / "inputs"
    inputs.mkdir(exist_ok=True)
    fixtures = {
        name: canonical(name)
        for name in ("composition-assessed", "composition-incomplete-x")
    }
    input_hashes = {}
    for name, (captured, trial, view) in fixtures.items():
        raw = canonical_json(build_customer_document(captured, view, trial))
        (inputs / (name + ".json")).write_bytes(raw)
        input_hashes[name] = sha256(raw).hexdigest()
    manifest = {
        "candidateSha": os.environ.get("CHECKPOINT_CANDIDATE_SHA"),
        "imageId": os.environ.get("CHECKPOINT_IMAGE_ID"),
        "nodeVersion": subprocess.check_output(
            ["node", "--version"], text=True
        ).strip(),
        "pythonVersion": platform.python_version(),
        "platform": platform.platform(),
        "cpuCount": os.cpu_count(),
        "playwrightVersion": json.loads(
            (FRONTEND / "node_modules/playwright-core/package.json").read_text()
        )["version"],
        "fixtureKind": "synthetic immutable DTO injection; no API capture or legacy ZIP equivalence claim",
        "fixtureHashes": {
            name: sha256(canonical_json(fixture(name))).hexdigest() for name in fixtures
        },
        "inputHashes": input_hashes,
        "reuseCommit": "575730a8",
        "retainedModules": [
            "snapshot",
            "snapshot_inputs",
            "snapshot_views",
            "trial_projection",
            "trial_clocks",
            "customer_view",
            "customer_clocks",
            "pure map inputs and scene",
        ],
        "hashes": {},
    }
    for label, file in {
        "lockfile": FRONTEND / "package-lock.json",
        "osPackages": Path("/opt/briefing-os-packages.txt"),
        "pythonPackages": Path("/opt/briefing-python-packages.txt"),
        "dayTexture": ASSETS / "earth-day-hi.jpg",
        "nightTexture": ASSETS / "city-lights-mask.png",
    }.items():
        manifest["hashes"][label] = sha256(file.read_bytes()).hexdigest()
    (root / "runtime-manifest.json").write_text(json.dumps(manifest, indent=2))
    if os.environ.get("CHECKPOINT_RUNTIME_TESTS") == "1":
        code = run(
            [
                "timeout",
                "--kill-after=10s",
                "10m",
                "node",
                "--test",
                "src/mission-export/briefing-render.browser-test.mjs",
            ],
            root / "runtime-tests.log",
            env={**os.environ, "CHECKPOINT_OUTPUT": str(root)},
            timeout=615,
        )
        if code:
            raise ValueError("Real-process runtime tests failed; see runtime-tests.log")
    results = []
    identities = []
    delivered = root / "delivered"
    delivered.mkdir(exist_ok=True)

    def render(run_name, fixture_name, fault=None):
        out = root / "renders" / run_name
        out.mkdir(parents=True)
        env = {**os.environ}
        if fault:
            env["CHECKPOINT_FAULT"] = fault
        code = run(
            [
                "timeout",
                "--kill-after=10s",
                "70s",
                "node",
                "src/mission-export/briefing-render.mjs",
                str(inputs / (fixture_name + ".json")),
                str(out),
                str(ASSETS),
            ],
            out / "runner.log",
            env=env,
        )
        report = json.loads((out / "render-report.json").read_text())
        if code and report["status"] == "success":
            raise ValueError("Runner failure cannot qualify render")
        return out, report

    for n in range(1, 4):
        out, report = render(f"fully-assessed-cold-{n}", "composition-assessed")
        if (
            report["status"] != "success"
            or report["map"]["status"] != "primary"
            or report["launchCount"] != 1
            or not report["sharedBrowser"]
            or report["fit"]["redFraction"] != 5 / 480
        ):
            raise ValueError(f"Primary cold render {n} unqualified: {report}")
        if set(report["fit"]["postures"]) != {
            "Nominal",
            "Degraded",
            "Limited / elevated risk",
            "Communications unavailable",
        }:
            raise ValueError("Missing four posture colors")
        inspection = inspect_pdf(
            out / report["artifacts"]["pdfPath"],
            out / report["artifacts"]["pngPath"],
            report["fit"]["pdfExpectations"],
        )
        (out / "pdf-inspection.json").write_text(json.dumps(inspection, indent=2))
        report["pdfValidation"] = {
            k: inspection[k] for k in ("verified", "pageCount", "pageSizePt", "rows")
        }
        report["pdfValidation"]["textHash"] = sha256(
            inspection["text"].encode()
        ).hexdigest()
        captured, trial, view = fixtures["composition-assessed"]
        evidence = build_customer_evidence(captured, trial, view, report)
        browser = Path(report["browserIdentity"]["executable"])
        manifest["hashes"]["browser"] = sha256(browser.read_bytes()).hexdigest()
        identity = {
            "text": inspection["text"],
            "pixelHash": inspection["previewPixelHash"],
            "pdf": normalized_pdf_hash(out / report["artifacts"]["pdfPath"]),
            "geometry": [
                (i.start_time.isoformat(), i.end_time.isoformat(), i.posture)
                for i in trial.intervals
            ],
            "pageRows": report["fit"]["visibleRowIds"],
        }
        identities.append(identity)
        results.append(
            {
                "request": n,
                "totalMs": report["totalMs"],
                "marginMs": 60000 - report["totalMs"],
                "stages": report["stages"],
                "launchCount": report["launchCount"],
                "mapStatus": report["map"]["status"],
                "cleanup": report["cleanup"],
            }
        )
        if n == 1:
            staged = root / "primary-staging"
            staged.mkdir()
            for name in report["artifacts"].values():
                (staged / name).write_bytes((out / name).read_bytes())
            publish_checkpoint(staged, delivered / "fully-assessed", evidence)
    if identities[1:] != identities[:-1]:
        (root / "determinism-failure.json").write_text(json.dumps(identities, indent=2))
        raise ValueError(
            "Cold customer text/geometry/decoded PNG/normalized PDF changed"
        )
    out, report = render("incomplete-x", "composition-incomplete-x")
    if (
        report["status"] != "success"
        or report["fit"]["noticeCount"] != 1
        or "Communications unavailable" in report["fit"]["postures"]
    ):
        raise ValueError("Incomplete-X page unqualified")
    inspection = inspect_pdf(
        out / report["artifacts"]["pdfPath"],
        out / report["artifacts"]["pngPath"],
        report["fit"]["pdfExpectations"],
    )
    (out / "pdf-inspection.json").write_text(json.dumps(inspection, indent=2))
    report["pdfValidation"] = {
        k: inspection[k] for k in ("verified", "pageCount", "pageSizePt", "rows")
    }
    if inspection["text"].count("X-Band planning incomplete") != 1 or any(
        phrase not in " ".join(word["text"] for word in inspection["words"])
        for phrase in ("No transport confirmed available", "1 confirmed", "0 confirmed")
    ):
        raise ValueError("Incomplete-X customer content missing")
    captured, trial, view = fixtures["composition-incomplete-x"]
    evidence = build_customer_evidence(captured, trial, view, report)
    staged = root / "incomplete-staging"
    staged.mkdir()
    for name in report["artifacts"].values():
        (staged / name).write_bytes((out / name).read_bytes())
    publish_checkpoint(staged, delivered / "incomplete-x", evidence)
    _, fallback = render("fallback", "composition-assessed", "map")
    if (
        fallback["status"] != "success"
        or fallback["map"]["status"] != "unavailable"
        or fallback["fit"]["mapCount"] != 0
    ):
        raise ValueError("Fallback failed")
    _, overflow = render("overflow", "composition-assessed", "overflow-title")
    if overflow["status"] != "failed" or overflow["artifacts"] is not None:
        raise ValueError("Overflow published partial pair")
    damaged_pdf_controls = []
    for damage in ("missing", "duplicate", "swapped", "changed", "split"):
        out, damaged = render(
            "pdf-row-" + damage, "composition-assessed", "pdf-row-" + damage
        )
        if damaged["status"] != "success":
            raise ValueError("Damage control did not reach actual PDF print")
        try:
            verify_customer_pdf(
                out / damaged["artifacts"]["pdfPath"],
                damaged["fit"]["pdfExpectations"],
                timeout_seconds=20,
            )
        except ValueError:
            damaged_pdf_controls.append(
                {"damage": damage, "actualPdfRejected": True, "domClaimedAllRows": True}
            )
        else:
            raise ValueError("Actual PDF row damage incorrectly qualified: " + damage)
    (root / "pdf-row-controls.json").write_text(
        json.dumps(damaged_pdf_controls, indent=2)
    )
    manifest["fontAssetHashes"] = report["assetHashes"]
    (root / "runtime-manifest.json").write_text(json.dumps(manifest, indent=2))
    summary = {
        "checksPassed": True,
        "actualPdfRowControls": damaged_pdf_controls,
        "visualAcceptance": "pending",
        "scanTest": "pending",
        "pageCounts": {"fullyAssessed": 1, "incompleteX": 1},
        "coldRenders": results,
        "determinism": {
            "customerText": True,
            "svgGeometry": True,
            "decodedPreviewPixels": True,
            "pageAssignments": True,
            "normalizedPdfStructure": True,
            "excludedPdfMetadata": ["CreationDate", "ModDate", "document ID"],
        },
        "incompleteX": {
            "totalMs": report["totalMs"],
            "stages": report["stages"],
            "cleanup": report["cleanup"],
        },
        "fallback": {
            "status": fallback["status"],
            "map": fallback["map"]["status"],
            "cleanup": fallback["cleanup"],
        },
        "overflow": {
            "status": overflow["status"],
            "errorCode": overflow["errorCode"],
            "cleanup": overflow["cleanup"],
        },
        "runtimeTests": os.environ.get("CHECKPOINT_RUNTIME_TESTS") == "1",
    }
    (root / "generation-report.json").write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    print(json.dumps(generate(Path(sys.argv[1])), indent=2))
