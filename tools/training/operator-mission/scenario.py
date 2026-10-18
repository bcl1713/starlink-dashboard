"""Explicit, private training identity; normal runtime policy is untouched."""

import json
from pathlib import Path
from uuid import UUID, uuid4

MARKER = ".operator-training-root.json"
VERSION = 1


def _checked_path(root):
    root = Path(root).absolute()
    if root.is_symlink() or any(parent.is_symlink() for parent in root.parents):
        raise ValueError("Training root must not be a symlink")
    if root == Path("/"):
        raise ValueError("Training root must be a private empty directory")
    return root


def training_namespace(root, *, mode):
    if mode != "simulation":
        raise ValueError("Training requires simulation mode")
    root = _checked_path(root)
    try:
        marker = json.loads((root / MARKER).read_text())
        token = str(UUID(marker["root_id"]))
        if marker != {
            "schema_version": VERSION,
            "purpose": "operator-training",
            "root_id": token,
            "namespace": "operator-training-v1-" + token,
        }:
            raise ValueError("Invalid training marker")
        return marker["namespace"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError(
            "Explicit marked nonproduction training root required"
        ) from error


def mark_root(root):
    root = _checked_path(root)
    if (root / MARKER).exists():
        training_namespace(root, mode="simulation")
        return json.loads((root / MARKER).read_text())
    if root.exists() and any(root.iterdir()):
        raise ValueError(
            "New training root must be empty; existing data is never adopted"
        )
    root.mkdir(parents=True, exist_ok=True)
    token = str(uuid4())
    marker = {
        "schema_version": VERSION,
        "purpose": "operator-training",
        "root_id": token,
        "namespace": "operator-training-v1-" + token,
    }
    with (root / MARKER).open("x") as handle:
        json.dump(marker, handle, indent=2)
    return marker


def stable_context(root, current_context):
    """Fixture-only adapter: replay segment IDs do not change the learner journal."""
    namespace = training_namespace(root, mode="simulation")

    def context():
        mode, _actual_segment = current_context()
        if mode != "simulation":
            raise ValueError("Training requires simulation mode")
        return mode, namespace

    return context
