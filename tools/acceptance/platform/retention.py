"""Fixed retention policy parsing for acceptance maintenance."""

from __future__ import annotations

import hashlib
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .evidence import read_nofollow


@dataclass(frozen=True)
class RetentionPolicy:
    """The immutable retention limits approved for acceptance evidence."""

    version: int
    completed_generations_per_lane: int
    maintenance_report_count: int
    digest: str

    @classmethod
    def parse(cls, path: Path) -> RetentionPolicy:
        """Read one exact, no-follow TOML policy and bind its raw-byte digest."""
        raw = read_nofollow(path)
        try:
            values = tomllib.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
            raise ValueError("retention policy must be valid TOML") from error
        expected = {
            "version": 1,
            "completed_generations_per_lane": 3,
            "maintenance_report_count": 90,
        }
        if values != expected:
            raise ValueError("retention policy must match the fixed contract")
        return cls(**expected, digest=hashlib.sha256(raw).hexdigest())


_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC


def canonical_root(path: Path) -> Path:
    """Return an absolute existing directory only after no-follow traversal."""
    root = Path(os.path.abspath(path))
    root_fd = _open_confined_directory(root)
    os.close(root_fd)
    return root


def safe_relative(root: Path, candidate: Path) -> PurePosixPath:
    """Validate a candidate remains within root without traversing symlinks."""
    root = canonical_root(root)
    candidate = candidate.absolute()
    try:
        relative = candidate.relative_to(root)
    except ValueError as error:
        raise ValueError("candidate escapes retention root") from error
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError("candidate escapes retention root")
    root_fd = _open_confined_directory(root)
    _walk_existing_components(root_fd, relative)
    return PurePosixPath(relative.as_posix())


def _open_confined_directory(path: Path) -> int:
    fd = os.open("/", _DIRECTORY_FLAGS)
    try:
        for part in path.parts[1:]:
            next_fd = os.open(part, _DIRECTORY_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = next_fd
    except OSError as error:
        os.close(fd)
        raise ValueError("retention root must be a non-symlink directory") from error
    return fd


def _walk_existing_components(root_fd: int, relative: Path) -> None:
    fd = root_fd
    try:
        parts = relative.parts
        for index, part in enumerate(parts):
            flags = _FILE_FLAGS if index == len(parts) - 1 else _DIRECTORY_FLAGS
            try:
                next_fd = os.open(part, flags, dir_fd=fd)
            except FileNotFoundError:
                if index == len(parts) - 1:
                    return
                raise ValueError("candidate has a missing parent") from None
            except OSError as error:
                raise ValueError("candidate must not traverse a symlink") from error
            if index == len(parts) - 1:
                os.close(next_fd)
            else:
                os.close(fd)
                fd = next_fd
    finally:
        os.close(fd)
