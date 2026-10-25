#!/usr/bin/env python3
"""Exact committed production/Nginx availability acceptance with owned cleanup."""

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HARNESS = ROOT / "tools/acceptance/operator-journal"
sys.path.insert(0, str(HARNESS))
spec = importlib.util.spec_from_file_location("journal_acceptance", HARNESS / "run.py")
journal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(journal)
OriginalOwner = journal.Owner


class AvailabilityOwner(OriginalOwner):
    def __init__(self, *args):
        super().__init__(*args)
        self.ownership["fixture"] = (
            "synthetic raw clocks, KML, Ka polygon and satellite inputs; normal app/runtime/calculations"
        )
        self.env["OPERATOR_ACCEPTANCE_HEALTH_PATH"] = "/health"
        self.persist()

    def execute(self, command, timeout=120, **kwargs):
        return super().execute(command, timeout=min(timeout, 2400), **kwargs)

    def compose(self, *args, timeout=120):
        source = self.env.get("OPERATOR_SOURCE_ROOT")
        if source:
            self.compose_file = (
                Path(source) / "tools/acceptance/transport-availability/compose.yml"
            )
            self.ownership["composeFile"] = str(self.compose_file)
            self.persist()
        return super().compose(*args, timeout=timeout)


def qualify(owner):
    fixture = ROOT / "tools/acceptance/transport-availability/availability_fixture.py"
    owner.ownership["fixtureSha256"] = hashlib.sha256(fixture.read_bytes()).hexdigest()
    owner.persist()
    env = owner.env | {
        "TRANSPORT_ACCEPTANCE_ORIGIN": f"http://127.0.0.1:{owner.ownership['port']}",
        "TRANSPORT_ACCEPTANCE_EVIDENCE": str(owner.root),
        "TRANSPORT_ACCEPTANCE_PROJECT": owner.project,
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
            "20m",
            "npx",
            "--no-install",
            "playwright",
            "test",
            "--config",
            "playwright.transport-availability.config.ts",
        ],
        timeout=1220,
        cwd=ROOT / "frontend/mission-planner",
        env=env,
    )
    return json.loads((owner.root / "transport-availability-proof.json").read_text())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    journal.Owner = AvailabilityOwner
    try:
        report = journal.run(
            args.candidate, args.project, args.evidence, qualification=qualify
        )
    finally:
        summary = args.evidence / "summary.json"
        if summary.exists():
            report = json.loads(summary.read_text())
            report["fixture"] = (
                "Synthetic raw KML, RF catalogs and controlled input clock starting 2035-03-01T12:00:00Z; genuine product live-mode and authoritative simulation-run paths; no aircraft claims"
            )
            summary.write_text(json.dumps(report, indent=2))
            hashes = args.evidence / "hashes.json"
            values = json.loads(hashes.read_text())
            values["summary.json"] = hashlib.sha256(summary.read_bytes()).hexdigest()
            hashes.write_text(json.dumps(values, indent=2))
    print(json.dumps(report, indent=2))
