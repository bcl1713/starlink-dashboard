"""Descriptor-confined evidence authority for acceptance platform output."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Mapping

_SHA = re.compile(r"[0-9a-f]{40}")
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC


def prepare_evidence_root(root: Path) -> Path:
    """Create the SHA-qualified root through no-follow directory descriptors."""
    root = root.absolute()
    if not _SHA.fullmatch(root.name):
        raise ValueError("evidence root must be SHA-qualified")
    parent_fd = _open_directory(root.parent)
    try:
        try:
            os.mkdir(root.name, 0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
        root_fd = os.open(root.name, _DIR_FLAGS, dir_fd=parent_fd)
    finally:
        os.close(parent_fd)
    try:
        os.fchmod(root_fd, 0o700)
    finally:
        os.close(root_fd)
    return root


def write_artifacts(root: Path, artifacts: Mapping[str, bytes]) -> str:
    """Persist only caller-provided byte artifacts, then inventory them exactly once."""
    root = prepare_evidence_root(root)
    root_fd = _open_directory(root)
    try:
        for relative, content in sorted(artifacts.items()):
            _write_relative(root_fd, relative, content)
        inventory = _inventory(root_fd)
        encoded = json.dumps({"artifacts": inventory}, sort_keys=True, separators=(",", ":")).encode()
        _write_relative(root_fd, "manifest.json", encoded)
        sums = "".join(f"{item['sha256']}  {item['path']}\n" for item in inventory).encode()
        _write_relative(root_fd, "SHA256SUMS", sums)
    finally:
        os.close(root_fd)
    verify_manifest(root)
    return hashlib.sha256(encoded).hexdigest()


def write_private(root: Path, relative: str, content: bytes) -> None:
    root_fd = _open_directory(prepare_evidence_root(root))
    try:
        _write_relative(root_fd, relative, content)
    finally:
        os.close(root_fd)


def verify_manifest(root: Path) -> None:
    """Recompute manifest and SHA256SUMS against no-follow retained bytes."""
    root_fd = _open_directory(root)
    try:
        manifest_bytes = _read_relative(root_fd, "manifest.json")
        manifest = json.loads(manifest_bytes)
        items = manifest.get("artifacts")
        if not isinstance(items, list):
            raise ValueError("invalid evidence manifest")
        expected_sums = "".join(f"{item['sha256']}  {item['path']}\n" for item in items).encode()
        if _read_relative(root_fd, "SHA256SUMS") != expected_sums:
            raise ValueError("evidence checksum inventory drift")
        previous = ""
        for item in items:
            relative, digest = item.get("path"), item.get("sha256")
            if not isinstance(relative, str) or not isinstance(digest, str) or relative <= previous:
                raise ValueError("invalid evidence manifest")
            content = _read_relative(root_fd, relative)
            if hashlib.sha256(content).hexdigest() != digest or len(content) != item.get("bytes"):
                raise ValueError("evidence checksum verification failed")
            previous = relative
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("invalid evidence manifest") from error
    finally:
        os.close(root_fd)


def _open_directory(path: Path) -> int:
    if not path.is_absolute():
        raise ValueError("evidence path must be absolute")
    fd = os.open("/", _DIR_FLAGS)
    try:
        for part in path.parts[1:]:
            next_fd = os.open(part, _DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise ValueError("evidence parent must not be a symlink")


def _parts(relative: str) -> tuple[str, ...]:
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("evidence artifact path must be contained")
    return path.parts


def _directory_for(root_fd: int, parts: tuple[str, ...]) -> tuple[int, str]:
    fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            try:
                os.mkdir(part, 0o700, dir_fd=fd)
            except FileExistsError:
                pass
            next_fd = os.open(part, _DIR_FLAGS, dir_fd=fd)
            os.fchmod(next_fd, 0o700)
            os.close(fd)
            fd = next_fd
        return fd, parts[-1]
    except OSError as error:
        os.close(fd)
        raise ValueError("evidence parent must not be a symlink") from error


def _write_relative(root_fd: int, relative: str, content: bytes) -> None:
    directory_fd, name = _directory_for(root_fd, _parts(relative))
    try:
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory_fd)
        try:
            os.write(fd, content)
            os.fchmod(fd, 0o600)
        finally:
            os.close(fd)
    except FileExistsError as error:
        raise ValueError("evidence target already exists") from error
    finally:
        os.close(directory_fd)


def _read_relative(root_fd: int, relative: str) -> bytes:
    directory_fd, name = _directory_for(root_fd, _parts(relative))
    try:
        fd = os.open(name, _FILE_FLAGS, dir_fd=directory_fd)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError("evidence target must be a regular file")
            return os.read(fd, os.fstat(fd).st_size)
        finally:
            os.close(fd)
    finally:
        os.close(directory_fd)


def _inventory(root_fd: int) -> list[dict[str, object]]:
    # Artifacts are supplied as controlled relative names; recursive walk via fd avoids links.
    entries: list[dict[str, object]] = []
    for base, dirs, files in os.walk(f"/proc/self/fd/{root_fd}", followlinks=False):
        dirs[:] = [name for name in dirs if not os.path.islink(os.path.join(base, name))]
        for name in files:
            path = os.path.join(base, name)
            if os.path.islink(path) or name in {"manifest.json", "SHA256SUMS"}:
                continue
            relative = os.path.relpath(path, f"/proc/self/fd/{root_fd}")
            content = _read_relative(root_fd, relative)
            entries.append({"path": relative, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    return sorted(entries, key=lambda item: str(item["path"]))
