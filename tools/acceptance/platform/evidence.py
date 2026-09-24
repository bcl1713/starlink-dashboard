"""Private, SHA-qualified evidence storage for platform capability cards."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Mapping

_SHA = re.compile(r"[0-9a-f]{40}")


def prepare_evidence_root(root: Path) -> Path:
    """Create a private SHA-named root without following filesystem links."""
    root = root.absolute()
    if not _SHA.fullmatch(root.name):
        raise ValueError("evidence root must be SHA-qualified")
    _reject_symlink_parents(root.parent)
    if root.exists() and root.is_symlink():
        raise ValueError("evidence root must not be a symlink")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    return root


def write_artifacts(root: Path, artifacts: Mapping[str, bytes]) -> str:
    """Write bounded relative artifacts and a verified sorted manifest."""
    root = prepare_evidence_root(root)
    for relative, content in sorted(artifacts.items()):
        target = _safe_target(root, relative)
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        _reject_symlink_parents(target.parent)
        if target.exists() and target.is_symlink():
            raise ValueError("evidence target must not be a symlink")
        target.write_bytes(content)
        os.chmod(target, 0o600)
    inventory = _inventory(root)
    manifest = {"artifacts": inventory}
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    _write_private(root / "manifest.json", encoded)
    checksum_lines = "".join(f"{item['sha256']}  {item['path']}\n" for item in inventory)
    _write_private(root / "SHA256SUMS", checksum_lines.encode())
    verify_manifest(root)
    return hashlib.sha256(encoded).hexdigest()


def verify_manifest(root: Path) -> None:
    """Recompute every retained checksum from the verified artifact root."""
    manifest_path = root / "manifest.json"
    if manifest_path.is_symlink():
        raise ValueError("evidence manifest must not be a symlink")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["artifacts"]:
        target = _safe_target(root, item["path"])
        if hashlib.sha256(target.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("evidence checksum verification failed")


def _inventory(root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name not in {"manifest.json", "SHA256SUMS"}:
            relative = path.relative_to(root).as_posix()
            entries.append({"path": relative, "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return entries


def _safe_target(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("evidence artifact path must be contained")
    target = root.joinpath(path)
    if target.parent.is_symlink():
        raise ValueError("evidence parent must not be a symlink")
    return target


def _reject_symlink_parents(path: Path) -> None:
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        if current.exists() and current.is_symlink():
            raise ValueError("evidence parent must not be a symlink")


def _write_private(path: Path, content: bytes) -> None:
    if path.exists() and path.is_symlink():
        raise ValueError("evidence target must not be a symlink")
    path.write_bytes(content)
    os.chmod(path, 0o600)
