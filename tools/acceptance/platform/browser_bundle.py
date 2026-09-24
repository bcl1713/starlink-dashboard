"""Descriptor-bound verification and launch of platform browser bundles on Linux."""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from .model import PlatformProfile

_VERSION_TIMEOUT_SECONDS = 15
_OPEN_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_OPEN_EXECUTABLE = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC


@dataclass
class BrowserLaunchSpec:
    """A closeable launch authority bound to one verified executable descriptor."""

    _fd: int

    def start(self, *arguments: str) -> subprocess.Popen[bytes]:
        """Start the verified browser without resolving a mutable browser pathname."""
        return _start_descriptor(self._require_open(), arguments)

    def close(self) -> None:
        """Release the retained executable descriptor."""
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def __enter__(self) -> Self:
        self._require_open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _require_open(self) -> int:
        if self._fd < 0:
            raise ValueError("browser launch specification is closed")
        return self._fd


@dataclass
class BrowserBundle:
    """Verified browser metadata with a closeable descriptor-bound launch factory."""

    sha256: str
    version: str
    byte_size: int
    _fd: int

    def launch_spec(self) -> BrowserLaunchSpec:
        """Return an independently closeable descriptor-bound launch specification."""
        if self._fd < 0:
            raise ValueError("browser bundle is closed")
        return BrowserLaunchSpec(os.dup(self._fd))

    def close(self) -> None:
        """Release the descriptor retained after identity verification."""
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def __enter__(self) -> Self:
        if self._fd < 0:
            raise ValueError("browser bundle is closed")
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def verify_browser_bundle(
    profile: PlatformProfile,
    *,
    _after_identity_open: Callable[[], None] | None = None,
) -> BrowserBundle:
    """Open, validate, probe, and retain a platform-owned browser by descriptor."""
    profile.validate()
    browser = profile.browser
    fd = _open_verified_file(browser.executable, browser.store_root)
    try:
        _verify_descriptor_identity(fd, browser.byte_size, browser.sha256)
        if _after_identity_open is not None:
            _after_identity_open()
        version = _read_version(fd)
        if version != browser.version:
            raise ValueError("browser identity version mismatch")
        return BrowserBundle(browser.sha256, version, browser.byte_size, fd)
    except BaseException:
        os.close(fd)
        raise


def _open_verified_file(executable: Path, store_root: Path) -> int:
    if not store_root.is_absolute() or not executable.is_absolute():
        raise ValueError("browser executable and store root must be absolute")
    try:
        relative = executable.relative_to(store_root)
    except ValueError as error:
        raise ValueError("browser executable escapes store root") from error
    if not relative.parts or ".." in relative.parts:
        raise ValueError("browser executable escapes store root")
    try:
        directory_fd = os.open(store_root, _OPEN_DIRECTORY)
        try:
            for component in relative.parts[:-1]:
                next_fd = os.open(component, _OPEN_DIRECTORY, dir_fd=directory_fd)
                os.close(directory_fd)
                directory_fd = next_fd
            return os.open(relative.parts[-1], _OPEN_EXECUTABLE, dir_fd=directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as error:
        if error.errno == getattr(os, "ELOOP", 40) or _is_symlink(store_root):
            raise ValueError("browser executable path contains a symlink") from error
        raise ValueError("browser filesystem validation failed") from error


def _is_symlink(path: Path) -> bool:
    try:
        return stat.S_ISLNK(os.lstat(path).st_mode)
    except OSError:
        return False


def _verify_descriptor_identity(fd: int, byte_size: int, sha256: str) -> None:
    try:
        file_stat = os.fstat(fd)
        if not stat.S_ISREG(file_stat.st_mode):
            raise ValueError("browser executable must be a regular file")
        if not file_stat.st_mode & 0o111:
            raise ValueError("browser executable must be executable")
        if file_stat.st_size != byte_size:
            raise ValueError("browser identity size mismatch")
        if _sha256_descriptor(fd) != sha256:
            raise ValueError("browser identity hash mismatch")
    except OSError as error:
        raise ValueError("browser filesystem validation failed") from error


def _sha256_descriptor(fd: int) -> str:
    digest = hashlib.sha256()
    os.lseek(fd, 0, os.SEEK_SET)
    while chunk := os.read(fd, 1024 * 1024):
        digest.update(chunk)
    os.lseek(fd, 0, os.SEEK_SET)
    return digest.hexdigest()


def _descriptor_path(fd: int) -> str:
    return f"/proc/self/fd/{fd}"


def _read_version(fd: int) -> str:
    try:
        result = subprocess.run(
            (_descriptor_path(fd), "--version"),
            executable=_descriptor_path(fd),
            pass_fds=(fd,),
            check=True,
            capture_output=True,
            text=True,
            timeout=_VERSION_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError("browser identity version check failed") from error
    return result.stdout.strip()


def _start_descriptor(fd: int, arguments: tuple[str, ...]) -> subprocess.Popen[bytes]:
    try:
        return subprocess.Popen(
            (_descriptor_path(fd), *arguments),
            executable=_descriptor_path(fd),
            pass_fds=(fd,),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as error:
        raise ValueError("browser launch failed") from error
