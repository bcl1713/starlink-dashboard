#!/usr/bin/env python3
"""Workspace measurements using the existing owned production-image runner."""

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

from fixtures import build_workspace_fixture

ROOT = Path(__file__).resolve().parents[3]
HARNESS = ROOT / "tools/acceptance/operator-journal"
sys.path.insert(0, str(HARNESS))
spec = importlib.util.spec_from_file_location("journal_acceptance", HARNESS / "run.py")
journal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(journal)

SEED = """
import json,sys
from pathlib import Path
from uuid import NAMESPACE_URL,uuid5
from app.mission import storage
from app.mission.models import Mission
from app.operator.models import Actor,CreateRecord
from app.operator.references import MissionReferences
from app.operator.service import OperatorService
from app.operator.settings import OperatorSettings
from app.operator.store import OperatorStore
from scenario import ScenarioClock,RUN_ID
storage.MISSIONS_DIR=Path('/app/data/missions')
settings=OperatorSettings(enabled=True,root=Path('/app/data/operator'),source_mode='simulation',simulation_run_id=RUN_ID)
clock=ScenarioClock()
store=OperatorStore.open(settings,initialize=False,clock=clock)
try:
 service=OperatorService(store,clock=clock,actor=Actor(backend='synthetic workspace prerequisite'),references=MissionReferences())
 epoch=str(store.health().api_epoch)
 for fixture in json.loads(sys.argv[1]):
  storage.save_mission_v2(Mission.model_validate(fixture['mission']))
  for i,body in enumerate(fixture['planned_commands']):
   service.execute(CreateRecord.model_validate(body),key=str(uuid5(NAMESPACE_URL,fixture['namespace']+'/call/'+str(i))),epoch=epoch)
finally:
 store.close()
"""


def qualify(owner):
    fixtures = [build_workspace_fixture(seed) for seed in ("normal", "busy")]
    (owner.root / "workspace-inputs.json").write_text(json.dumps(fixtures, indent=2))
    owner.compose("exec", "-T", "starlink-location", "python", "-c", SEED,
                  json.dumps(fixtures), timeout=60)
    env = owner.env | {
        "OPERATOR_ACCEPTANCE_ORIGIN": f"http://127.0.0.1:{owner.ownership['port']}",
        "OPERATOR_ACCEPTANCE_EVIDENCE": str(owner.root),
        "OPERATOR_WORKSPACE_INPUTS": str(owner.root / "workspace-inputs.json"),
        "PLAYWRIGHT_BROWSERS_PATH": os.environ.get(
            "PLAYWRIGHT_BROWSERS_PATH", "/home/oracle-worker/.cache/ms-playwright"),
        "npm_config_offline": "true",
        "npm_config_update_notifier": "false",
    }
    owner.execute(["timeout", "--kill-after=10s", "10m", "npx", "--no-install",
                   "playwright", "test", "--config", "playwright.operator-workspace.config.ts",
                   "--grep", "baseline"], timeout=620,
                  cwd=ROOT / "frontend/mission-planner", env=env)
    result = json.loads((owner.root / "workspace-baseline.json").read_text())
    try:
        owner.execute(["timeout", "--kill-after=10s", "3m", "npx", "--no-install",
                       "playwright", "test", "--config", "playwright.operator-workspace.config.ts",
                       "--grep", "approved workspace"], timeout=200,
                      cwd=ROOT / "frontend/mission-planner", env=env)
    except RuntimeError:
        log = Path(owner.ownership["commands"][-1]["log"]).read_text()
        if "Operator workspace" not in log or "element(s) not found" not in log:
            raise
        result["approvedDestinationRed"] = {
            "reason": "Operator workspace navigation absent after healthy legacy page loaded",
            "log": owner.ownership["commands"][-1]["log"],
        }
    else:
        raise AssertionError("Baseline unexpectedly contains the approved workspace")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(journal.run(args.candidate, args.project, args.evidence,
                                 qualification=qualify), indent=2))
