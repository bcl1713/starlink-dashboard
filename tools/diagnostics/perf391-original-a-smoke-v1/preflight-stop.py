"""Read-only offline evidence for the browser identity stop; never launches services."""

import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PREP = HERE.with_name("perf391-runtime-preparation-v1")
BUILT = HERE.with_name("perf391-built-images-v1")
sys.path.insert(0, str(PREP))
from prepare import check_release, sha, verify_overlay
from launcher import validate_receipt


def main():
    plan_path = BUILT / "evidence/runtime-build-plan.json"
    plan = json.loads(plan_path.read_bytes())
    verify_overlay(plan)
    result = {
        "status": "STOP_PREFLIGHT_BROWSER_NODE_IDENTITY",
        "runtime_attempts": 0,
        "authorization": "https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6355361655",
        "starting_commit": "68f3f644beef98cd8412e8a354c8621540660739",
        "stage5": check_release(),
        "overlay_verified": True,
        "build_plan_sha256": sha(plan_path),
        "receipts": {},
        "manifests": {},
    }
    for name, root in (("built_images", BUILT),):
        manifest = root / "artifact-manifest.json"
        entries = json.loads(manifest.read_bytes())["files"]
        errors = [p for p, expected in entries.items() if sha(root / p) != expected]
        assert not errors, errors
        result["manifests"][name] = {"sha256": sha(manifest), "verified_files": len(entries)}
    node = Path(shutil.which("node")).resolve()
    version = subprocess.check_output([str(node), "--version"], text=True, timeout=3).strip().removeprefix("v")
    result["actual_browser_node"] = {"path": str(node), "version": version, "sha256": sha(node)}
    for role in ("A", "C"):
        path = BUILT / "evidence" / ("built-" + role + ".json")
        receipt = json.loads(path.read_bytes())
        validate_receipt(receipt, plan, sha(plan_path))
        changed = copy.deepcopy(receipt)
        changed["browser"].update(node_version=version, node_sha256=sha(node))
        try:
            validate_receipt(changed, plan, sha(plan_path))
        except ValueError as error:
            rejection = str(error)
        else:
            raise AssertionError("Expected historical browser Node rejection")
        assert receipt["browser"]["node_version"] != version
        result["receipts"][role] = {
            "sha256": sha(path), "closed_receipt_and_retained_assets_valid": True,
            "browser": receipt["browser"], "images": receipt["images"],
            "historical_browser_node_rejection": rejection,
        }
    (HERE / "evidence/offline-preflight.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(result["status"])


if __name__ == "__main__":
    main()
