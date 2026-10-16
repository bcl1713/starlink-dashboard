#!/usr/bin/env python3
"""Exact committed production images, real CDP browser and delivered PDF checks."""

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/acceptance/customer-briefing"))
from production import ProductionOwner, free_loopback_port


def validate_candidate(repository, candidate):
    def git(*args):
        return subprocess.check_output(
            ["git", *args], cwd=repository, text=True, timeout=30
        ).strip()

    if (
        re.fullmatch(r"[0-9a-f]{40}", candidate) is None
        or candidate != git("rev-parse", "HEAD")
        or git("status", "--porcelain")
    ):
        raise ValueError("Acceptance requires clean committed full HEAD")


def validate_image(identity, candidate):
    revision = (
        identity.get("Config", {})
        .get("Labels", {})
        .get("org.opencontainers.image.revision")
    )
    if revision != candidate or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", identity.get("Id", "")
    ):
        raise ValueError("Production image identity differs from candidate")
    return {"id": identity["Id"], "revision": revision}


def build_candidate(owner, candidate):
    run_id = time.time_ns()
    context = owner.root / "candidate-source"
    archive = owner.root / "candidate-source.tar"
    owner.env.update(
        BRIEFING_BACKEND_IMAGE=f"briefing-pop-backend:{candidate[:12]}-{run_id}",
        BRIEFING_FRONTEND_IMAGE=f"briefing-pop-frontend:{candidate[:12]}-{run_id}",
        BRIEFING_PORT=str(free_loopback_port()),
        BRIEFING_ENABLED="true",
        BRIEFING_SOURCE_ROOT=str(context),
    )
    owner.ownership["temporaryPaths"] += [str(context), str(archive)]
    owner.ownership["loopbackListener"] = {
        "address": "127.0.0.1",
        "port": int(owner.env["BRIEFING_PORT"]),
    }
    owner.ownership["dockerHost"] = os.environ.get("DOCKER_HOST")
    owner.ownership["dockerContext"] = os.environ.get("DOCKER_CONTEXT")
    owner.persist()
    owner.execute(
        ["git", "archive", "--format=tar", f"--output={archive}", candidate], timeout=60
    )
    source_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    context.mkdir()
    with tarfile.open(archive) as source:
        source.extractall(context, filter="data")
    owner.compose_file = (
        context / "tools/acceptance/customer-briefing/compose.production.yml"
    )
    owner.ownership["composeFile"] = str(owner.compose_file)
    owner.persist()
    images = {}
    for name, dockerfile, build_context in (
        ("backend", "backend/starlink-location/Dockerfile", context),
        (
            "frontend",
            "frontend/mission-planner/Dockerfile",
            context / "frontend/mission-planner",
        ),
    ):
        tag = owner.env[f"BRIEFING_{name.upper()}_IMAGE"]
        owner.ownership["images"].append(tag)
        owner.persist()
        command = [
            "docker",
            "build",
            "--no-cache",
            "-f",
            str(context / dockerfile),
            "--build-arg",
            f"ACCEPTANCE_CANDIDATE_SHA={candidate}",
            "-t",
            tag,
        ]
        if ca := os.environ.get("CODEX_PROXY_CERT"):
            command += ["--secret", f"id=proxy_ca,src={ca}"]
        owner.execute([*command, str(build_context)], timeout=1800)
        identity = json.loads(
            owner.execute(
                ["docker", "image", "inspect", tag, "--format", "{{json .}}"],
                timeout=30,
            )
        )
        images[name] = {"tag": tag, **validate_image(identity, candidate)}
    return {"images": images, "sourceArchiveSha256": source_hash}


def run(candidate, evidence_root, *, qualify=None):
    validate_candidate(ROOT, candidate)
    evidence_root = Path(evidence_root).resolve()
    if evidence_root.exists() and any(evidence_root.iterdir()):
        raise ValueError("Evidence destination must be new or empty")
    owner = ProductionOwner(
        f"briefing-pop-{candidate[:12]}-{time.time_ns()}", evidence_root
    )
    summary = {
        "candidateSha": candidate,
        "checksPassed": False,
        "project": owner.project,
        "fixtureKind": "sanitized deterministic simulation/provider inputs; no operational Starshield claims",
    }
    handlers = {
        number: signal.signal(number, owner.signal)
        for number in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        summary.update(build_candidate(owner, candidate))
        if qualify is None:
            from qualify import qualify as qualify_pop

            qualify = qualify_pop
        summary["qualification"] = qualify(owner)
        summary["checksPassed"] = True
        return summary
    except BaseException as error:
        summary["error"] = str(error)
        raise
    finally:
        try:
            owner.cleaning = True
            try:
                owner.compose("logs", "--no-color", timeout=30)
            except (RuntimeError, TimeoutError, OSError):
                pass
            owner.finalize_summary(summary)
        finally:
            for number, handler in handlers.items():
                signal.signal(number, handler)
            (owner.root / "summary.json").write_text(json.dumps(summary, indent=2))
            hashes = {
                str(path.relative_to(owner.root)): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in sorted(owner.root.rglob("*"))
                if path.is_file() and path.name != "hashes.json"
            }
            (owner.root / "hashes.json").write_text(json.dumps(hashes, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.candidate_sha, arguments.evidence_root), indent=2))
