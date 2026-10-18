"""Required production transport workflows, layered onto real model qualification."""

import json
import os
from pathlib import Path

FIELDS = (
    "synthetic",
    "appliedOnly",
    "multiService",
    "independentReports",
    "unknownActualRouting",
    "activeCallAdvisory",
    "retrospectiveCorrection",
    "twoClientConflict",
    "lostReceipt",
    "offlineReconnect",
    "restart",
    "linkRemoveRestore",
    "crossMission",
    "realLiveEta",
    "staleUnknown",
    "lanHttp",
)


def transport_proof(root):
    proof = json.loads((Path(root) / "transport-proof.json").read_text())
    for field in FIELDS:
        if proof.get(field) is not True:
            raise ValueError(f"Missing transport evidence: {field}")
    if proof.get("captures") != ["1920x1080", "390x844", "844x390"]:
        raise ValueError("Missing transport viewports")
    return proof


def qualify_transport(owner):
    from run import ROOT, qualify_models, run_checks

    baseline = qualify_models(owner)
    origin = f"http://127.0.0.1:{owner.ownership['port']}"
    env = owner.env | {
        "OPERATOR_ACCEPTANCE_ORIGIN": origin,
        "OPERATOR_ACCEPTANCE_PROJECT": owner.project,
        "OPERATOR_ACCEPTANCE_EVIDENCE": str(owner.root),
        "OPERATOR_TRANSPORT_ACCEPTANCE": "true",
        "PLAYWRIGHT_BROWSERS_PATH": os.environ.get(
            "PLAYWRIGHT_BROWSERS_PATH", "/home/oracle-worker/.cache/ms-playwright"
        ),
        "npm_config_offline": "true",
        "npm_config_update_notifier": "false",
        "npm_config_cache": str(owner.root / "npm-cache"),
    }

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
                "transport decision production",
            ],
            timeout=920,
            cwd=ROOT / "frontend/mission-planner",
            env=env,
        )
        return transport_proof(owner.root)

    def backend():
        output = owner.compose(
            "exec",
            "-T",
            "--user",
            "appuser",
            "starlink-location",
            "python",
            "/acceptance/transport_probe.py",
            timeout=180,
        )
        result = json.loads(output.splitlines()[-1])
        (owner.root / "transport-backend.json").write_text(json.dumps(result, indent=2))
        return result

    return run_checks(
        owner.root,
        {
            "existingModelAndFailureControls": lambda: baseline,
            "transportBrowser": browser,
            "transportDurability": backend,
        },
    )
