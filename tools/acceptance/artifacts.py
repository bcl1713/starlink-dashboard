"""Restricted, checksummed evidence artifact storage."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from .model import RunManifest

_ALLOWED_SUFFIXES = {".json", ".log", ".png", ".txt", ".html"}


class EvidenceWriter:
    """Write one private, SHA-qualified acceptance evidence directory."""

    def __init__(self, root: Path, sha: str) -> None:
        if (
            not isinstance(sha, str)
            or len(sha) != 40
            or any(c not in "0123456789abcdef" for c in sha)
        ):
            raise ValueError("sha must be a 40-character lowercase hexadecimal value")
        self.root = Path(root)
        self.sha = sha
        self.sha_root = self.root / sha
        self._mkdir_private(self.sha_root)
        self.artifact_root = self.sha_root / uuid4().hex
        self._mkdir_private(self.artifact_root)
        self._inventory: dict[str, dict[str, Any]] = {}
        self._finalized = False

    def record_json(self, relative_path: Path, value: Any) -> Path:
        text = json.dumps(value, indent=2, sort_keys=True) + "\n"
        return self.record_text(relative_path, text)

    def record_text(self, relative_path: Path, text: str) -> Path:
        if self._finalized:
            raise ValueError("cannot record artifacts after manifest finalization")
        if not isinstance(text, str):
            raise TypeError("artifact text must be a string")
        relative = self._validate_relative_path(relative_path)
        target = self.artifact_root / relative
        self._mkdir_private(target.parent)
        target.write_text(text, encoding="utf-8")
        target.chmod(0o600)
        self._inventory[relative.as_posix()] = self._inventory_entry(target, relative)
        return target

    def finalize_manifest(self, manifest: RunManifest) -> dict[str, Any]:
        if self._finalized:
            raise ValueError("manifest is already finalized")
        if manifest.sha != self.sha:
            raise ValueError("manifest sha does not match artifact root")
        data = manifest.to_dict()
        data["artifacts"] = [self._inventory[path] for path in sorted(self._inventory)]
        manifest_path = self.artifact_root / "manifest.json"
        manifest_path.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        manifest_path.chmod(0o600)
        checksum_paths = [*sorted(self._inventory), "manifest.json"]
        sums = "".join(
            f"{self._digest(self.artifact_root / path)}  {path}\n"
            for path in checksum_paths
        )
        sums_path = self.artifact_root / "SHA256SUMS"
        sums_path.write_text(sums, encoding="utf-8")
        sums_path.chmod(0o600)
        self._finalized = True
        return data

    def verify_checksums(self) -> None:
        sums_path = self.artifact_root / "SHA256SUMS"
        if not sums_path.is_file():
            raise ValueError("checksum inventory is missing")
        for line in sums_path.read_text(encoding="utf-8").splitlines():
            expected, separator, relative = line.partition("  ")
            if not separator or len(expected) != 64:
                raise ValueError("checksum inventory is invalid")
            target = self.artifact_root / self._validate_checksum_path(relative)
            if not target.is_file() or self._digest(target) != expected:
                raise ValueError(f"checksum verification failed for {relative}")

    def _validate_relative_path(self, path: Path) -> PurePosixPath:
        raw = str(path)
        candidate = PurePosixPath(raw)
        if (
            not raw
            or candidate.is_absolute()
            or ".." in candidate.parts
            or candidate.name in {"manifest.json", "SHA256SUMS"}
        ):
            raise ValueError("artifact path is outside the evidence root")
        if candidate.suffix not in _ALLOWED_SUFFIXES:
            raise ValueError("artifact path is not allowlisted")
        return candidate

    @staticmethod
    def _validate_checksum_path(raw: str) -> PurePosixPath:
        candidate = PurePosixPath(raw)
        if (
            not raw
            or candidate.is_absolute()
            or ".." in candidate.parts
            or candidate.name == "SHA256SUMS"
        ):
            raise ValueError("checksum path is outside the evidence root")
        return candidate

    @staticmethod
    def _mkdir_private(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o700)

    @staticmethod
    def _digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _inventory_entry(self, target: Path, relative: PurePosixPath) -> dict[str, Any]:
        return {
            "path": relative.as_posix(),
            "sha256": self._digest(target),
            "size": target.stat().st_size,
        }
