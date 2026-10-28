#!/usr/bin/env python3
"""Issue 426 production images/Nginx with raw synthetic inputs and owned cleanup."""

import argparse
import importlib.util
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HARNESS = ROOT / "tools/acceptance/transport-availability/run.py"
spec = importlib.util.spec_from_file_location("overview_transport_owner", HARNESS)
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


def qualify(owner):
    env = owner.env | {
        "OVERVIEW_ADVISORIES_ORIGIN": f"http://127.0.0.1:{owner.ownership['port']}",
        "OVERVIEW_ADVISORIES_EVIDENCE": str(owner.root),
        "PLAYWRIGHT_BROWSERS_PATH": os.environ.get(
            "PLAYWRIGHT_BROWSERS_PATH", "/home/oracle-worker/.cache/ms-playwright"
        ),
        "npm_config_offline": "true",
        "npm_config_update_notifier": "false",
        "npm_config_cache": str(owner.root / "npm-cache"),
    }
    owner.ownership["temporaryPaths"].append(str(owner.root / "npm-cache"))
    owner.persist()
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
            "playwright.overview-advisories.config.ts",
        ],
        timeout=920,
        cwd=ROOT / "frontend/mission-planner",
        env=env,
    )
    return json.loads((owner.root / "overview-advisories-proof.json").read_text())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()
    transport.journal.Owner = transport.AvailabilityOwner
    try:
        report = transport.journal.run(
            args.candidate, args.project, args.evidence, qualification=qualify
        )
    finally:
        summary = args.evidence / "summary.json"
        if summary.exists():
            report = json.loads(summary.read_text())
            report["fixture"] = (
                "Synthetic raw KML, RF catalogs and controlled telemetry/clock inputs; normal production startup, active context, prediction, ledger and Nginx; live wall clock; no aircraft dependencies"
            )
            summary.write_text(json.dumps(report, indent=2))
            hashes = args.evidence / "hashes.json"
            values = json.loads(hashes.read_text())
            values["summary.json"] = hashlib.sha256(summary.read_bytes()).hexdigest()
            hashes.write_text(json.dumps(values, indent=2))
    print(json.dumps(report, indent=2))
