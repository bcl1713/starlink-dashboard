from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest
from acceptance.platform.browser_bundle import verify_browser_bundle
from acceptance.platform.model import BrowserProfile, PlatformProfile


def _fake_executable(path: Path, *, version: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\nprintf '%s\\n' '{version}'\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | os.X_OK)
    return path


def _profile_for(
    executable: Path,
    *,
    version: str,
    sha256: str | None = None,
    byte_size: int | None = None,
    store_root: Path | None = None,
) -> PlatformProfile:
    return PlatformProfile(
        version="test-profile",
        checksum="a" * 64,
        browser=BrowserProfile(
            store_root=store_root or executable.parent,
            executable=executable,
            version=version,
            byte_size=byte_size if byte_size is not None else executable.stat().st_size,
            sha256=sha256 or hashlib.sha256(executable.read_bytes()).hexdigest(),
        ),
    )


@pytest.fixture
def version_runner(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    commands: list[tuple[str, ...]] = []

    def run(command: tuple[str, ...], **_: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="Chrome 124\n")

    monkeypatch.setattr("acceptance.platform.browser_bundle.subprocess.run", run)
    return commands


def test_bundle_returns_verified_absolute_executable(
    tmp_path: Path, version_runner: list[tuple[str, ...]]
) -> None:
    executable = _fake_executable(tmp_path / "chrome", version="Chrome 124")

    bundle = verify_browser_bundle(_profile_for(executable, version="Chrome 124"))

    assert bundle.executable == executable.absolute()
    assert bundle.version == "Chrome 124"
    assert version_runner == [(str(executable.absolute()), "--version")]


def test_bundle_rejects_symlinked_executable(tmp_path: Path) -> None:
    target = _fake_executable(tmp_path / "target", version="Chrome 124")
    executable = tmp_path / "chrome"
    executable.symlink_to(target)

    with pytest.raises(ValueError, match="symlink"):
        verify_browser_bundle(_profile_for(executable, version="Chrome 124"))


def test_bundle_rejects_executable_outside_store_root(tmp_path: Path) -> None:
    executable = _fake_executable(tmp_path / "outside/chrome", version="Chrome 124")

    with pytest.raises(ValueError, match="escapes store root"):
        verify_browser_bundle(
            _profile_for(
                executable, version="Chrome 124", store_root=tmp_path / "store"
            )
        )


def test_bundle_rejects_traversal_outside_store_root(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    executable = _fake_executable(
        store_root / "../outside/chrome", version="Chrome 124"
    )

    with pytest.raises(ValueError, match="escapes store root"):
        verify_browser_bundle(
            _profile_for(executable, version="Chrome 124", store_root=store_root)
        )


def test_bundle_rejects_non_regular_executable(tmp_path: Path) -> None:
    executable = tmp_path / "chrome"
    executable.mkdir()

    with pytest.raises(ValueError, match="regular file"):
        verify_browser_bundle(
            _profile_for(executable, version="Chrome 124", sha256="0" * 64, byte_size=0)
        )


def test_bundle_rejects_non_executable_file(tmp_path: Path) -> None:
    executable = _fake_executable(tmp_path / "chrome", version="Chrome 124")
    executable.chmod(executable.stat().st_mode & ~0o111)

    with pytest.raises(ValueError, match="executable"):
        verify_browser_bundle(_profile_for(executable, version="Chrome 124"))


@pytest.mark.parametrize(("sha256", "byte_size"), [("0" * 64, None), (None, 0)])
def test_bundle_rejects_identity_hash_or_size_mismatch(
    tmp_path: Path, sha256: str | None, byte_size: int | None
) -> None:
    executable = _fake_executable(tmp_path / "chrome", version="Chrome 124")

    with pytest.raises(ValueError, match="identity"):
        verify_browser_bundle(
            _profile_for(
                executable,
                version="Chrome 124",
                sha256=sha256,
                byte_size=byte_size,
            )
        )


def test_bundle_rejects_version_mismatch(
    tmp_path: Path, version_runner: list[tuple[str, ...]]
) -> None:
    executable = _fake_executable(tmp_path / "chrome", version="Chrome 123")

    with pytest.raises(ValueError, match="identity version"):
        verify_browser_bundle(_profile_for(executable, version="Chrome 123"))


def test_launch_command_rechecks_replacement_before_return(
    tmp_path: Path, version_runner: list[tuple[str, ...]]
) -> None:
    executable = _fake_executable(tmp_path / "chrome", version="Chrome 124")
    bundle = verify_browser_bundle(_profile_for(executable, version="Chrome 124"))

    def replace_executable() -> None:
        _fake_executable(executable, version="Chrome 125")

    with pytest.raises(ValueError, match="identity"):
        bundle.launch_command("--headless", _after_initial_hash=replace_executable)


def test_verifier_source_never_mentions_installer_execution() -> None:
    source = Path(__file__).parents[1] / "acceptance/platform/browser_bundle.py"

    assert all(
        term not in source.read_text(encoding="utf-8") for term in ("npm", "npx")
    )
