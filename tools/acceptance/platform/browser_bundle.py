"""Verify pre-provisioned browser executables before health checks use them."""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .model import PlatformProfile

_VERSION_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class BrowserBundle:
    """A browser executable whose immutable identity was verified."""

    executable: Path
    sha256: str
    version: str
    byte_size: int
    _store_root: Path

    def launch_command(
        self,
        *arguments: str,
        _after_initial_hash: Callable[[], None] | None = None,
    ) -> tuple[str, ...]:
        """Return a launch command only if the executable identity still matches."""
        _verify_file_identity(
            self.executable, self._store_root, self.byte_size, self.sha256
        )
        if _after_initial_hash is not None:
            _after_initial_hash()
        _verify_file_identity(
            self.executable, self._store_root, self.byte_size, self.sha256
        )
        return (str(self.executable), *arguments)


def verify_browser_bundle(
    profile: PlatformProfile,
    *,
    _after_initial_hash: Callable[[], None] | None = None,
) -> BrowserBundle:
    """Verify a platform-owned browser without resolving any executable via PATH."""
    profile.validate()
    browser = profile.browser
    executable = _verified_regular_file(browser.executable, browser.store_root)
    _verify_file_identity(
        executable, browser.store_root, browser.byte_size, browser.sha256
    )
    if _after_initial_hash is not None:
        _after_initial_hash()
    version = _read_version(executable)
    if version != browser.version:
        raise ValueError("browser identity version mismatch")
    _verify_file_identity(
        executable, browser.store_root, browser.byte_size, browser.sha256
    )
    return BrowserBundle(
        executable=executable,
        sha256=browser.sha256,
        version=version,
        byte_size=browser.byte_size,
        _store_root=browser.store_root.absolute(),
    )


def _verified_regular_file(executable: Path, store_root: Path) -> Path:
    if not store_root.is_absolute() or not executable.is_absolute():
        raise ValueError("browser executable and store root must be absolute")
    try:
        relative_path = executable.relative_to(store_root)
    except ValueError as error:
        raise ValueError("browser executable escapes store root") from error
    if ".." in relative_path.parts:
        raise ValueError("browser executable escapes store root")
    _reject_symlink_components(executable, store_root)
    executable_stat = os.lstat(executable)
    if not stat.S_ISREG(executable_stat.st_mode):
        raise ValueError("browser executable must be a regular file")
    if not executable_stat.st_mode & 0o111:
        raise ValueError("browser executable must be executable")
    return executable


def _reject_symlink_components(executable: Path, store_root: Path) -> None:
    current = store_root
    while True:
        if stat.S_ISLNK(os.lstat(current).st_mode):
            raise ValueError("browser executable path contains a symlink")
        if current == executable:
            return
        try:
            current = current / executable.relative_to(current).parts[0]
        except ValueError as error:
            raise ValueError("browser executable escapes store root") from error


def _verify_file_identity(
    executable: Path, store_root: Path, byte_size: int, sha256: str
) -> None:
    executable = _verified_regular_file(executable, store_root)
    if executable.stat().st_size != byte_size:
        raise ValueError("browser identity size mismatch")
    if _sha256_file(executable) != sha256:
        raise ValueError("browser identity hash mismatch")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as bundle:
        for chunk in iter(lambda: bundle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_version(executable: Path) -> str:
    try:
        result = subprocess.run(
            (str(executable), "--version"),
            check=True,
            capture_output=True,
            text=True,
            timeout=_VERSION_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError("browser identity version check failed") from error
    return result.stdout.strip()
