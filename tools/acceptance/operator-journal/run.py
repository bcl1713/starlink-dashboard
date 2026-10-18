#!/usr/bin/env python3
"""Exact committed Operator images, real browsers, media failures and cleanup."""

import argparse
import hashlib
import importlib.util
import json
import os
import signal
import tarfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from ownership import Owner, free_port

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "pop_candidate_identity", ROOT / "tools/acceptance/pop-transitions/run.py"
)
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)
validate_candidate, validate_image = (
    identity.validate_candidate,
    identity.validate_image,
)


def build_candidate(owner, candidate):
    source, archive = owner.root / "source", owner.root / "source.tar"
    owner.env.update(
        ACCEPTANCE_CANDIDATE_SHA=candidate,
        OPERATOR_SOURCE_ROOT=str(source),
        OPERATOR_ACCEPTANCE_PORT=str(free_port()),
    )
    owner.ownership["temporaryPaths"] += [str(source), str(archive)]
    owner.ownership["port"] = int(owner.env["OPERATOR_ACCEPTANCE_PORT"])
    owner.persist()
    owner.execute(
        ["git", "archive", "--format=tar", f"--output={archive}", candidate], timeout=60
    )
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    source.mkdir()
    with tarfile.open(archive) as bundle:
        bundle.extractall(source, filter="data")
    owner.compose_file = source / "tools/acceptance/operator-journal/compose.yml"
    owner.ownership["composeFile"] = str(owner.compose_file)
    owner.persist()
    images = {}
    for name, dockerfile, context in (
        ("backend", "backend/starlink-location/Dockerfile", source),
        (
            "frontend",
            "frontend/mission-planner/Dockerfile",
            source / "frontend/mission-planner",
        ),
    ):
        tag = f"{owner.project}-{name}:{candidate}"
        owner.env[f"OPERATOR_{name.upper()}_IMAGE"] = f"{owner.project}-{name}"
        owner.ownership["images"].append(tag)
        owner.persist()
        command = [
            "docker",
            "build",
            "-f",
            str(source / dockerfile),
            "--build-arg",
            f"ACCEPTANCE_CANDIDATE_SHA={candidate}",
            "-t",
            tag,
        ]
        if ca := os.environ.get("CODEX_PROXY_CERT"):
            command += ["--secret", f"id=proxy_ca,src={ca}"]
        owner.execute([*command, str(context)], timeout=2700)
        image = json.loads(
            owner.execute(
                ["docker", "image", "inspect", tag, "--format", "{{json .}}"],
                timeout=30,
            )
        )
        images[name] = {"tag": tag, **validate_image(image, candidate)}
    owner.ownership["imageIdentity"] = images
    owner.persist()
    owner.compose(
        "up", "-d", "--no-build", "--wait", "--wait-timeout", "180", timeout=210
    )
    container = owner.compose("ps", "-q", "mission-planner", timeout=15).strip()
    runtime = json.loads(
        owner.execute(
            ["docker", "inspect", container, "--format", "{{json .}}"], timeout=15
        )
    )
    if not runtime["NetworkSettings"]["Ports"].get("80/tcp"):
        owner.start_relay(container)
    origin = f"http://127.0.0.1:{owner.ownership['port']}"
    deadline = time.monotonic() + 30
    while True:
        try:
            with urlopen(origin, timeout=5) as response:
                assert response.status == 200
                assert response.headers["Server"].startswith("nginx/")
                owner.ownership["originTraversal"] = {
                    "origin": origin,
                    "nginx": response.headers["Server"],
                    "transport": (
                        "docker-exec-byte-relay" if owner.relay else "published-port"
                    ),
                    "container": container,
                }
            owner.persist()
            break
        except URLError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.2)
    return {"images": images, "sourceArchiveSha256": digest}


def run_checks(root, checks):
    report = {"checks": {}, "errors": {}}
    for name, check in checks.items():
        try:
            report["checks"][name] = check()
        except InterruptedError:
            raise
        except (RuntimeError, OSError, AssertionError, ValueError) as error:
            report["errors"][name] = str(error)
        (root / "qualification.json").write_text(json.dumps(report, indent=2))
    if report["errors"]:
        raise RuntimeError(f"Acceptance checks failed: {report['errors']}")
    return report["checks"]


def communications_proof(root):
    proof = json.loads((root / "communications-proof.json").read_text())
    for field in (
        "synthetic",
        "createReschedule",
        "retrospectiveCorrection",
        "removeRestore",
        "conferenceIndependent",
        "twoClientConflict",
        "offlineRetry",
        "restart",
        "duplicateSubmission",
    ):
        if proof.get(field) is not True:
            raise ValueError(f"Missing communications evidence: {field}")
    if proof.get("captures") != ["1920x1080", "390x844", "844x390"]:
        raise ValueError("Missing communications viewport evidence")
    return proof


def conferences_proof(root):
    proof = json.loads((root / "conferences-proof.json").read_text())
    for field in (
        "synthetic",
        "reuse",
        "overlap",
        "joiningOrders",
        "interruptRestore",
        "discrepancy",
        "twoClients",
        "retryFrozenTime",
        "retryConcurrentEdit",
        "restart",
        "sourceCoverage",
    ):
        if proof.get(field) is not True:
            raise ValueError(f"Missing conference evidence: {field}")
    if proof.get("captures") != ["1920x1080", "390x844", "844x390"]:
        raise ValueError("Missing conference viewport evidence")
    return proof


def issues_proof(root):
    proof = json.loads((root / "issues-proof.json").read_text())
    for field in (
        "synthetic",
        "descriptionOnly",
        "workaroundMonitoring",
        "independentCapability",
        "snapshotBoundaries",
        "resolvedCorrection",
        "correctionLineage",
        "twoClients",
        "reloadFrozenRetry",
        "epochQuarantine",
        "restart",
        "multileg",
        "noReadinessInference",
    ):
        if proof.get(field) is not True:
            raise ValueError(f"Missing issue evidence: {field}")
    if proof.get("captures") != ["1920x1080", "390x844", "844x390"]:
        raise ValueError("Missing issue viewport evidence")
    return proof


EVENT_FIELDS = (
    "synthetic",
    "timelineIndependent",
    "tenMinutePrep",
    "scheduleMoved",
    "cancelSuppressed",
    "protectedUnknown",
    "actualPopPrediction",
    "predictionChanged",
    "twoClients",
    "acknowledgment",
    "boundedCatchup",
    "offlineReconnect",
    "restart",
    "unavailableSources",
    "localOnly",
    "draftPreserved",
    "sameBrowserDedup",
    "hiddenTab",
)


def events_proof(root):
    proof = json.loads((root / "events-proof.json").read_text())
    for field in EVENT_FIELDS:
        if proof.get(field) is not True:
            raise ValueError(f"Missing event evidence: {field}")
    if proof.get("captures") != ["1920x1080", "390x844", "844x390"]:
        raise ValueError("Missing event viewport evidence")
    return {field: proof[field] for field in EVENT_FIELDS} | {
        "captures": proof["captures"]
    }


def qualify_events(owner):
    from events_probe import run as run_event_probe
    from failures import run_failure_suite

    origin = f"http://127.0.0.1:{owner.ownership['port']}"
    env = owner.env | {
        "OPERATOR_ACCEPTANCE_ORIGIN": origin,
        "OPERATOR_ACCEPTANCE_PROJECT": owner.project,
        "OPERATOR_ACCEPTANCE_EVIDENCE": str(owner.root),
        "PLAYWRIGHT_BROWSERS_PATH": os.environ.get(
            "PLAYWRIGHT_BROWSERS_PATH", "/home/oracle-worker/.cache/ms-playwright"
        ),
        "npm_config_offline": "true",
        "npm_config_update_notifier": "false",
        "npm_config_cache": str(owner.root / "npm-cache"),
    }
    owner.ownership["temporaryPaths"].append(str(owner.root / "npm-cache"))
    owner.persist()

    def browser():
        owner.execute(
            [
                "timeout",
                "--kill-after=10s",
                "20m",
                "npx",
                "--no-install",
                "playwright",
                "test",
                "--config",
                "playwright.operator-journal.config.ts",
                "--grep",
                "unified event timeline|Operator display controls|aircraft LAN HTTP",
            ],
            timeout=1220,
            cwd=ROOT / "frontend/mission-planner",
            env=env,
        )
        displays = json.loads((owner.root / "displays-proof.json").read_text())
        assert (
            displays["completed"]
            and displays["historySynced"]
            and displays["overviewRenderedVisibilitySynced"]
        )
        assert displays["browserErrors"] == []
        lan = json.loads((owner.root / "events-lan-http.json").read_text())
        assert (
            lan["actualNonSecureOrigin"]
            and lan["randomUUIDAbsent"]
            and lan["acknowledgmentCommitted"]
            and lan["timelineRendered"]
        )
        assert lan["secureContext"] is False and lan["browserErrors"] == []
        return {
            "events": events_proof(owner.root),
            "overviewCompatibility": displays,
            "lanHttp": lan,
        }

    def exports():
        result = json.loads(
            owner.compose(
                "exec",
                "-T",
                "--user",
                "appuser",
                "starlink-location",
                "python",
                "/acceptance/export_probe.py",
                timeout=120,
            ).splitlines()[-1]
        )
        (owner.root / "events-exports.json").write_text(json.dumps(result, indent=2))
        return result

    return run_checks(
        owner.root,
        {
            "eventsBackend": lambda: run_event_probe(owner, origin, owner.root),
            "eventsBrowser": browser,
            "storageFailures": lambda: run_failure_suite(owner, origin=origin),
            "existingExports": exports,
            "node": lambda: owner.execute(["node", "--version"], timeout=10).strip(),
        },
    )


def models_proof(root):
    proof = json.loads((root / "model-alerts-proof.json").read_text())
    for field in (
        "synthetic",
        "rawInputsOnly",
        "foregroundSoundOnce",
        "incomingProtectedActivity",
        "twoClientAcknowledgment",
        "positionUpdatesActualPop",
        "staleReason",
        "unavailableReason",
        "routeScheduleUpdated",
        "deactivationRetires",
        "restartNoResurrection",
        "offlineReconnect",
        "partialIndependentWarning",
    ):
        if proof.get(field) is not True:
            raise ValueError(f"Missing real-model evidence: {field}")
    if proof.get("captures") != ["1920x1080", "390x844", "844x390"]:
        raise ValueError("Missing real-model viewport evidence")
    live = json.loads((root / "live-eta-proof.json").read_text())
    for field in (
        "synthetic",
        "rawInputsOnly",
        "lateDeparture",
        "earlyDeparture",
        "speedThreshold",
        "displayedTimeMatches",
        "foregroundSoundOnce",
        "deviationRejoin",
        "revisedRoute",
        "unavailableExplicit",
    ):
        if live.get(field) is not True:
            raise ValueError(f"Missing live ETA evidence: {field}")
    if live.get("viewports") != [1920, 390]:
        raise ValueError("Missing live ETA viewport evidence")
    return proof | {"liveEta": live}


def qualify_models(owner):
    from events_probe import run as event_probe
    from failures import run_failure_suite

    origin = f"http://127.0.0.1:{owner.ownership['port']}"
    env = owner.env | {
        "OPERATOR_ACCEPTANCE_ORIGIN": origin,
        "OPERATOR_ACCEPTANCE_PROJECT": owner.project,
        "OPERATOR_ACCEPTANCE_EVIDENCE": str(owner.root),
        "PLAYWRIGHT_BROWSERS_PATH": os.environ.get(
            "PLAYWRIGHT_BROWSERS_PATH", "/home/oracle-worker/.cache/ms-playwright"
        ),
        "npm_config_offline": "true",
        "npm_config_update_notifier": "false",
        "npm_config_cache": str(owner.root / "npm-cache"),
    }
    owner.ownership["temporaryPaths"].append(str(owner.root / "npm-cache"))
    owner.persist()

    def browser():
        owner.execute(
            [
                "timeout",
                "--kill-after=10s",
                "15m",
                "npx",
                "--no-install",
                "playwright",
                "test",
                "--config",
                "playwright.operator-journal.config.ts",
                "--grep",
                "real model foreground warning|Operator display controls|aircraft LAN HTTP",
            ],
            timeout=920,
            cwd=ROOT / "frontend/mission-planner",
            env=env,
        )
        lan = json.loads((owner.root / "events-lan-http.json").read_text())
        assert (
            lan["actualNonSecureOrigin"]
            and lan["randomUUIDAbsent"]
            and lan["acknowledgmentCommitted"]
        )
        assert lan["secureContext"] is False and not lan["browserErrors"]
        displays = json.loads((owner.root / "displays-proof.json").read_text())
        assert (
            displays["completed"]
            and displays["overviewRenderedVisibilitySynced"]
            and not displays["browserErrors"]
        )
        return {
            "models": models_proof(owner.root),
            "lanHttp": lan,
            "overview": displays,
        }

    def exports():
        return json.loads(
            owner.compose(
                "exec",
                "-T",
                "--user",
                "appuser",
                "starlink-location",
                "python",
                "/acceptance/export_probe.py",
                timeout=120,
            ).splitlines()[-1]
        )

    return run_checks(
        owner.root,
        {
            "realModelsBrowser": browser,
            "ackDurabilityBackup": lambda: event_probe(owner, origin, owner.root),
            "storageFailures": lambda: run_failure_suite(owner, origin=origin),
            "existingExports": exports,
        },
    )


def qualify(owner):
    from failures import run_failure_suite

    origin = f"http://127.0.0.1:{owner.ownership['port']}"
    frontend = ROOT / "frontend/mission-planner"
    if not (frontend / "node_modules/@playwright/test").exists():
        raise RuntimeError(
            "Provisioned frontend dependencies required; no runtime download"
        )
    env = owner.env | {
        "OPERATOR_ACCEPTANCE_ORIGIN": origin,
        "OPERATOR_ACCEPTANCE_PROJECT": owner.project,
        "OPERATOR_ACCEPTANCE_EVIDENCE": str(owner.root),
        "PLAYWRIGHT_BROWSERS_PATH": os.environ.get(
            "PLAYWRIGHT_BROWSERS_PATH", "/home/oracle-worker/.cache/ms-playwright"
        ),
        "npm_config_offline": "true",
        "npm_config_update_notifier": "false",
        "npm_config_cache": str(owner.root / "npm-cache"),
    }
    owner.ownership["temporaryPaths"].append(str(owner.root / "npm-cache"))
    owner.persist()

    def browser():
        owner.execute(
            [
                "timeout",
                "--kill-after=10s",
                "20m",
                "npx",
                "--no-install",
                "playwright",
                "test",
                "--config",
                "playwright.operator-journal.config.ts",
                "--grep-invert",
                "issue exception workflow",
            ],
            timeout=1220,
            cwd=frontend,
            env=env,
        )
        owner.execute(
            [
                "timeout",
                "--kill-after=10s",
                "20m",
                "npx",
                "--no-install",
                "playwright",
                "test",
                "--config",
                "playwright.operator-journal.config.ts",
                "--grep",
                "issue exception workflow",
            ],
            timeout=1220,
            cwd=frontend,
            env=env,
        )
        return {
            "journal": json.loads((owner.root / "browser-proof.json").read_text()),
            "shell": json.loads((owner.root / "shell-proof.json").read_text()),
            "displays": json.loads((owner.root / "displays-proof.json").read_text()),
            "communications": communications_proof(owner.root),
            "conferences": conferences_proof(owner.root),
            "issues": issues_proof(owner.root),
        }

    def probe(script, destination):
        result = json.loads(
            owner.compose(
                "exec",
                "-T",
                "--user",
                "appuser",
                "starlink-location",
                "python",
                f"/acceptance/{script}.py",
                timeout=120,
            ).splitlines()[-1]
        )
        (owner.root / destination).write_text(json.dumps(result, indent=2))
        return result

    return run_checks(
        owner.root,
        {
            "browser": browser,
            "failures": lambda: run_failure_suite(owner, origin=origin),
            "communications": lambda: probe(
                "communications_probe", "communications-projections.json"
            ),
            "issues": lambda: probe("issues_probe", "issues-projections.json"),
            "conferences": lambda: probe(
                "conferences_probe", "conferences-projections.json"
            ),
            "projections": lambda: probe("projection_probe", "projections.json"),
            "exports": lambda: probe("export_probe", "exports.json"),
            "node": lambda: owner.execute(["node", "--version"], timeout=10).strip(),
        },
    )


def run(
    candidate,
    project,
    evidence,
    *,
    qualification=qualify,
    events=False,
    models=False,
    transport=False,
):
    validate_candidate(ROOT, candidate)
    evidence = Path(evidence).resolve()
    if evidence.exists():
        raise ValueError("Use a new evidence directory reserved for this run")
    owner = Owner(project, evidence)
    if transport:
        owner.deadline += 1800
    if models or transport:
        owner.env["OPERATOR_MODEL_ALERTS_ACCEPTANCE"] = "true"
    if events:
        owner.env["OPERATOR_EVENTS_ACCEPTANCE"] = "true"
    report = {
        "candidateSha": candidate,
        "project": project,
        "checksPassed": False,
        "fixture": "synthetic simulation fixed at 2026-10-17T16:00:00Z; no aircraft claims",
    }
    handlers = {
        s: signal.signal(s, owner.signal) for s in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        owner.admit()
        report.update(build_candidate(owner, candidate))
        if transport:
            from transport_qualification import qualify_transport

            qualification = qualify_transport
        report["qualification"] = (
            qualify_models if models else qualify_events if events else qualification
        )(owner)
        report["checksPassed"] = True
        return report
    except BaseException as error:
        report["error"] = str(error)
        raise
    finally:
        try:
            owner.cleaning = True
            try:
                if owner.admitted:
                    owner.compose("logs", "--no-color", timeout=30)
            except (RuntimeError, OSError, TimeoutError):
                pass
            report["cleanup"] = owner.close()
        except BaseException as error:
            report.update(checksPassed=False, cleanupError=str(error))
            raise
        finally:
            owner.release()
            for number, handler in handlers.items():
                signal.signal(number, handler)
            (evidence / "summary.json").write_text(json.dumps(report, indent=2))
            hashes = {
                str(p.relative_to(evidence)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(evidence.rglob("*"))
                if p.is_file() and p.name != "hashes.json"
            }
            (evidence / "hashes.json").write_text(json.dumps(hashes, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument(
        "--events",
        action="store_true",
        help="Run the synthetic event-feed/notification slice",
    )
    parser.add_argument(
        "--model-alerts",
        action="store_true",
        help="Qualify normal production modeled-restriction warnings",
    )
    parser.add_argument(
        "--transport",
        action="store_true",
        help="Qualify transport decisions with real model inputs",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                args.candidate,
                args.project,
                args.evidence,
                events=args.events,
                models=args.model_alerts,
                transport=args.transport,
            ),
            indent=2,
        )
    )
