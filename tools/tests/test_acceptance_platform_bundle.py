from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from acceptance.platform import browser_bundle
from acceptance.platform.browser_bundle import BrowserLaunchSpec, verify_browser_bundle
from acceptance.platform.model import BrowserProfile, PlatformProfile


@pytest.fixture
def executable_tmp_path(tmp_path: Path) -> Iterator[Path]:
    """Use the worktree because the harness scratch directory is mounted noexec."""
    path = Path.cwd() / ".pytest-browser-bundle" / tmp_path.name
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path.parent, ignore_errors=True)


def _fake_executable(path: Path, *, version: str, marker: Path | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    marker_write = ""
    if marker is not None:
        escaped_marker = str(marker).replace("\\", "\\\\").replace('"', '\\"')
        marker_write = f"""\n    FILE *marker = fopen("{escaped_marker}", "a");
    if (marker != NULL) {{ fputs("executed", marker); fclose(marker); }}"""
    escaped_version = version.replace("\\", "\\\\").replace('"', '\\"')
    source = path.with_suffix(".c")
    source.write_text(
        f"""#include <stdio.h>
int main(void) {{
    puts("{escaped_version}");{marker_write}
    return 0;
}}
""",
        encoding="utf-8",
    )
    subprocess.run(("cc", str(source), "-o", str(path)), check=True)
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


def test_bundle_probes_verified_file_after_same_version_replacement(
    tmp_path: Path, executable_tmp_path: Path
) -> None:
    marker = tmp_path / "executed"
    executable = _fake_executable(
        executable_tmp_path / "store/chrome", version="Chrome 124"
    )
    profile = _profile_for(
        executable, version="Chrome 124", store_root=executable_tmp_path / "store"
    )

    def replace_path() -> None:
        _fake_executable(executable, version="Chrome 124", marker=marker)

    bundle = verify_browser_bundle(profile, _after_identity_open=replace_path)
    bundle.close()

    assert not marker.exists()


def test_launch_spec_executes_verified_file_after_path_replacement(
    tmp_path: Path, executable_tmp_path: Path
) -> None:
    old_marker = tmp_path / "old-executed"
    malicious_marker = tmp_path / "malicious-executed"
    executable = _fake_executable(
        executable_tmp_path / "store/chrome", version="Chrome 124", marker=old_marker
    )
    bundle = verify_browser_bundle(
        _profile_for(
            executable, version="Chrome 124", store_root=executable_tmp_path / "store"
        )
    )
    spec = bundle.launch_spec()
    _fake_executable(executable, version="Chrome 124", marker=malicious_marker)

    process = spec.start()
    assert process.wait(timeout=5) == 0
    spec.close()
    bundle.close()

    assert old_marker.read_text(encoding="utf-8") == "executedexecuted"
    assert not malicious_marker.exists()


def test_platform_browser_launch_adds_only_certified_angle_swiftshader_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launched_arguments: tuple[str, ...] = ()

    class FakeProcess:
        pass

    def capture_start(_: int, arguments: tuple[str, ...]) -> FakeProcess:
        nonlocal launched_arguments
        launched_arguments = arguments
        return FakeProcess()

    monkeypatch.setattr(browser_bundle, "_start_descriptor", capture_start)
    descriptor = BrowserLaunchSpec(os.open("/dev/null", os.O_RDONLY))
    try:
        descriptor.start("about:blank")
    finally:
        descriptor.close()

    assert launched_arguments == (
        "--use-gl=angle",
        "--use-angle=swiftshader",
        "about:blank",
    )
    assert launched_arguments.count("--use-gl=angle") == 1
    assert launched_arguments.count("--use-angle=swiftshader") == 1
    assert not any(
        argument.startswith(("--use-gl", "--use-angle", "--enable-unsafe-swiftshader"))
        and argument not in {"--use-gl=angle", "--use-angle=swiftshader"}
        for argument in launched_arguments
    )


@pytest.mark.parametrize(
    "argument",
    (
        "--use-gl=desktop",
        "--use-angle=default",
        "--enable-unsafe-swiftshader",
        "--enable-unsafe-swiftshader=true",
    ),
)
def test_platform_browser_launch_rejects_caller_gl_selection_before_start(
    monkeypatch: pytest.MonkeyPatch, argument: str
) -> None:
    """Fails if callers can alter the descriptor-owned GL composition."""
    started = False

    def capture_start(_: int, __: tuple[str, ...]) -> None:
        nonlocal started
        started = True

    monkeypatch.setattr(browser_bundle, "_start_descriptor", capture_start)
    descriptor = BrowserLaunchSpec(os.open("/dev/null", os.O_RDONLY))
    try:
        with pytest.raises(ValueError, match="platform-owned"):
            descriptor.start(argument)
    finally:
        descriptor.close()

    assert not started


def test_version_probe_survives_parent_component_symlink_replacement(
    tmp_path: Path, executable_tmp_path: Path
) -> None:
    marker = tmp_path / "malicious-executed"
    store_root = executable_tmp_path / "store"
    executable = _fake_executable(store_root / "bin/chrome", version="Chrome 124")
    replacement = executable_tmp_path / "replacement"
    _fake_executable(replacement / "bin/chrome", version="Chrome 124", marker=marker)
    profile = _profile_for(executable, version="Chrome 124", store_root=store_root)

    def replace_parent() -> None:
        store_root.rename(executable_tmp_path / "original-store")
        store_root.symlink_to(replacement, target_is_directory=True)

    bundle = verify_browser_bundle(profile, _after_identity_open=replace_parent)
    bundle.close()

    assert not marker.exists()


def test_bundle_rejects_symlinked_executable(tmp_path: Path) -> None:
    target = _fake_executable(tmp_path / "target", version="Chrome 124")
    executable = tmp_path / "chrome"
    executable.symlink_to(target)

    with pytest.raises(ValueError, match="symlink"):
        verify_browser_bundle(_profile_for(executable, version="Chrome 124"))


def test_bundle_rejects_parent_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target"
    store_root = tmp_path / "store"
    store_root.symlink_to(target, target_is_directory=True)
    executable = store_root / "chrome"
    _fake_executable(target / "chrome", version="Chrome 124")

    with pytest.raises(ValueError, match="symlink"):
        verify_browser_bundle(
            _profile_for(executable, version="Chrome 124", store_root=store_root)
        )


@pytest.mark.parametrize("missing", ["store", "executable"])
def test_bundle_normalizes_missing_filesystem_objects(
    tmp_path: Path, missing: str
) -> None:
    store_root = tmp_path / "store"
    executable = store_root / "chrome"
    if missing == "store":
        profile = _profile_for(
            executable,
            version="Chrome 124",
            byte_size=1,
            sha256="0" * 64,
            store_root=store_root,
        )
    else:
        store_root.mkdir()
        profile = _profile_for(
            executable,
            version="Chrome 124",
            byte_size=1,
            sha256="0" * 64,
            store_root=store_root,
        )

    with pytest.raises(ValueError, match="filesystem"):
        verify_browser_bundle(profile)


def test_bundle_rejects_executable_outside_store_root(tmp_path: Path) -> None:
    executable = _fake_executable(tmp_path / "outside/chrome", version="Chrome 124")

    with pytest.raises(ValueError, match="escapes store root"):
        verify_browser_bundle(
            _profile_for(
                executable, version="Chrome 124", store_root=tmp_path / "store"
            )
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


def test_bundle_rejects_version_mismatch(tmp_path: Path) -> None:
    executable = _fake_executable(tmp_path / "chrome", version="Chrome 123")

    with pytest.raises(ValueError, match="identity version"):
        verify_browser_bundle(_profile_for(executable, version="Chrome 124"))


def test_launch_spec_close_prevents_descriptor_reuse(executable_tmp_path: Path) -> None:
    executable = _fake_executable(executable_tmp_path / "chrome", version="Chrome 124")
    bundle = verify_browser_bundle(_profile_for(executable, version="Chrome 124"))
    spec = bundle.launch_spec()
    spec.close()
    bundle.close()

    with pytest.raises(ValueError, match="closed"):
        spec.start()
    with pytest.raises(ValueError, match="closed"):
        bundle.launch_spec()


def test_default_profile_is_explicitly_unprovisioned_template() -> None:
    profile = (
        Path(__file__).parents[1] / "acceptance/platform/profiles/default.toml"
    ).read_text(encoding="utf-8")

    assert "DELIBERATELY UNPROVISIONED PLATFORM TEMPLATE" in profile
    assert "UNPROVISIONED_BROWSER_DO_NOT_LAUNCH" in profile
    assert "must not install a browser" in profile


def test_verifier_source_never_mentions_installer_execution() -> None:
    source = Path(__file__).parents[1] / "acceptance/platform/browser_bundle.py"

    assert all(
        term not in source.read_text(encoding="utf-8") for term in ("npm", "npx")
    )
