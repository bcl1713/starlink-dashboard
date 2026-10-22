"""Load the exact #407 dependency from immutable Git, never from a mutable PR tree."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import build


def prepare_collector(root, repo):
    root = Path(root)
    raw = build.git(
        repo, "archive", "--format=tar", build.PINS["collector"], build.COLLECTOR
    )
    files = build.archive_files(raw)
    if not root.exists():
        root.mkdir(parents=True)
        for name, (data, mode) in files.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(0o755 if mode == "100755" else 0o644)
    build.verify_dependency(
        repo, "collector", build.PINS["collector"], build.tree_manifest(root)["files"]
    )
    location = root / build.COLLECTOR
    loaded = sys.modules.get("perf391_network_evidence")
    if (
        loaded is not None
        and Path(loaded.__file__).resolve()
        != (location / "perf391_network_evidence/__init__.py").resolve()
    ):
        raise ValueError("another collector already imported")
    sys.path.insert(0, str(location))
    try:
        return SimpleNamespace(
            **{
                name: importlib.import_module("perf391_network_evidence." + name)
                for name in ("model", "record", "adapters", "analyze")
            }
        )
    finally:
        sys.path.remove(str(location))
