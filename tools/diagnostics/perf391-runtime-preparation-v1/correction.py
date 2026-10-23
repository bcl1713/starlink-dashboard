"""Offline correction identity layer; historical manifests and assets stay frozen."""

import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASELINE = "09095e263d3d1c237309b9f2359fa879b91353d2"
INTEGRATION = "tools/diagnostics/perf391-diagnostic-integration-v1/"
RUNTIME = "tools/diagnostics/perf391-runtime-preparation-v1/"
SOURCE_FILES = {
    INTEGRATION + name
    for name in (
        "browser-probe.ts",
        "browser.mjs",
        "collect.mjs",
        "tests/browser.test.mjs",
        "tests/collection.test.mjs",
        "tests/frontend/probe.test.ts",
        "tests/frontend/application.test.tsx",
    )
} | {
    RUNTIME + name
    for name in (
        "browser-owner.proposed.mjs",
        "browser-evidence.mjs",
        "backend_evidence.py",
        "execute.proposed.py",
        "analyze-runtime.py",
        "test_executor.py",
        "correction.py",
        "test_node_identity.py",
    )
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_correction(manifest=None):
    manifest = manifest or json.loads(
        (HERE / "diagnostic-correction-overlay.json").read_bytes()
    )
    if (
        manifest["baseline"] != BASELINE
        or set(manifest["source_files"]) != SOURCE_FILES
    ):
        raise ValueError("correction source inventory")
    for name, identity in manifest["source_files"].items():
        path = REPO / name
        if path.is_symlink() or digest(path.read_bytes()) != identity["sha256"]:
            raise ValueError("correction source drift: " + name)
        if identity["predecessor_sha256"] is not None:
            old = subprocess.check_output(
                ["git", "show", BASELINE + ":" + name], cwd=REPO
            )
            if digest(old) != identity["predecessor_sha256"]:
                raise ValueError("correction predecessor drift: " + name)
    for name, expected in manifest["immutable_files"].items():
        if digest((REPO / name).read_bytes()) != expected:
            raise ValueError("immutable evidence drift: " + name)
        old = subprocess.check_output(["git", "show", BASELINE + ":" + name], cwd=REPO)
        if digest(old) != expected:
            raise ValueError("immutable predecessor drift: " + name)
    if manifest["compiled_assets"] != {
        "state": "unbuilt",
        "sha256": None,
        "runtime_qualified": False,
    }:
        raise ValueError("unqualified correction assets")
    return {
        "baseline": BASELINE,
        "verified_source_files": len(SOURCE_FILES),
        "verified_immutable_files": len(manifest["immutable_files"]),
        "runtime_qualified": False,
    }


def require_runtime_assets():
    # Old image receipts describe the immutable predecessor, never this correction.
    raise ValueError(
        "corrected diagnostic assets unbuilt; separate authorization required"
    )


if __name__ == "__main__":
    print(json.dumps(verify_correction(), sort_keys=True, indent=2))
