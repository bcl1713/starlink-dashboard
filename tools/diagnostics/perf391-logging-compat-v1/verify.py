"""Verify retained logging checkpoint hashes and protected source scope offline."""

import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
manifest = json.loads((HERE / "artifact-manifest.json").read_bytes())
actual = {
    p.relative_to(HERE).as_posix()
    for p in HERE.rglob("*")
    if p.is_file() and p.name != "artifact-manifest.json"
}
assert actual == set(manifest["files"]), "checkpoint file closure changed"
for base, entries in ((HERE, manifest["files"]), (REPO, manifest["external_files"])):
    for name, expected in entries.items():
        path = base / name
        assert not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
changed = subprocess.check_output(
    ["git", "diff", "--name-only", manifest["starting_commit"], "--"],
    cwd=REPO,
    text=True,
    timeout=10,
).splitlines()
allowed = {
    "tools/diagnostics/perf391-runtime-preparation-v1/prepare.py",
    "tools/diagnostics/perf391-runtime-preparation-v1/node-contract-overlay.json",
    "tools/diagnostics/perf391-runtime-preparation-v1/test_logging.py",
}
assert all(
    p in allowed or p.startswith("tools/diagnostics/perf391-logging-compat-v1/")
    for p in changed
), changed
cleanup = json.loads((HERE / "evidence/cleanup.json").read_bytes())
assert (
    cleanup["clean"] and not cleanup["process_survivors"] and not cleanup["listeners"]
)
assert len(cleanup["images"]) == 4
print(
    f"Verified {len(actual)} checkpoint files, {len(manifest['external_files'])} external identities and diagnostic-only change scope; production, frozen tools, closed receipts and original failed smoke unchanged."
)
