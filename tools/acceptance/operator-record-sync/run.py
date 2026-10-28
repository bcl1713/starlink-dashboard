#!/usr/bin/env python3
"""Issue 430: isolated exact-commit production images and two browser contexts."""

import argparse
import importlib.util
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "record_sync_owner", ROOT / "tools/acceptance/overview-advisories/run.py"
)
overview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overview)


def qualify(owner):
    env = owner.env | {
        "OPERATOR_SYNC_ORIGIN": f"http://127.0.0.1:{owner.ownership['port']}",
        "OPERATOR_SYNC_EVIDENCE": str(owner.root),
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
    owner.execute(
        [
            "timeout",
            "--kill-after=10s",
            "10m",
            "npx",
            "--no-install",
            "playwright",
            "test",
            "--config",
            "playwright.operator-record-sync.config.ts",
        ],
        timeout=620,
        cwd=ROOT / "frontend/mission-planner",
        env=env,
    )
    return json.loads((owner.root / "operator-record-sync-proof.json").read_text())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()
    overview.transport.journal.Owner = overview.OverviewOwner
    report = overview.transport.journal.run(
        args.candidate, args.project, args.evidence, qualification=qualify
    )
    print(json.dumps(report, indent=2))
