#!/usr/bin/env python3
"""Reuse exact-SHA builds/ownership cleanup for the focused PoP evidence journey."""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/acceptance/pop-transitions"))
sys.path.insert(0, str(ROOT / "tools/acceptance/customer-briefing"))
# The shared runner validates clean HEAD, builds production Dockerfiles and owns
# all command process groups, private images, Compose volumes and loopback ports.
from run import run  # noqa: E402


def qualify(owner):
    source = Path(owner.env["BRIEFING_SOURCE_ROOT"])
    owner.compose_file = source / "tools/acceptance/pop-evidence/compose.yml"
    owner.ownership["composeFile"] = str(owner.compose_file)
    owner.ownership["volumes"] = [
        f"{owner.project}_{name}" for name in ("app-data", "poi-data")
    ]
    owner.persist()
    owner.compose("up", "-d", "--wait", "--wait-timeout", "150", timeout=180)
    browser_root = Path(
        os.environ.get("PLAYWRIGHT_BROWSERS_PATH", Path.home() / ".cache/ms-playwright")
    )
    owner.execute(
        [
            "node",
            str(
                source
                / "tools/acceptance/browser/provision-v2-mission-retirement-chromium.mjs"
            ),
            "--mode",
            "verify",
            "--project-dir",
            str(ROOT / "frontend/mission-planner"),
            "--browser-root",
            str(browser_root),
            "--task-root",
            str(owner.root),
            "--provenance-file",
            str(owner.root / "browser-provenance.json"),
        ],
        timeout=30,
    )
    owner.execute(
        [
            "node",
            str(source / "tools/acceptance/pop-evidence/browser.mjs"),
            f"http://127.0.0.1:{owner.env['BRIEFING_PORT']}",
            str(owner.root),
            str(ROOT / "frontend/mission-planner"),
        ],
        timeout=240,
    )
    # Prometheus /metrics is an internal backend endpoint; Nginx proxies /api/.
    metrics = owner.compose(
        "exec",
        "-T",
        "starlink-location",
        "curl",
        "--fail",
        "--silent",
        "http://127.0.0.1:8000/metrics",
        timeout=30,
    )
    (owner.root / "synthetic-metrics.txt").write_text(metrics)
    if (
        'city="Tokyo"' not in metrics
        or 'identity_source="operator_static_cidr"' not in metrics
    ):
        raise AssertionError(
            "Internal metrics did not retain the canonical Tokyo identity"
        )
    return json.loads((owner.root / "browser.json").read_text())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.candidate_sha, args.evidence_root, qualify=qualify), indent=2
        )
    )
