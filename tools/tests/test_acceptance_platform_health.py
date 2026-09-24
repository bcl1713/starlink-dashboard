from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from acceptance.platform.browser_bundle import BrowserLaunchSpec
from acceptance.platform.evidence import (
    prepare_evidence_root,
    verify_manifest,
    write_artifacts,
)
from acceptance.platform.health import (
    HealthProbeResult,
    PlatformHealthExecutor,
    run_platform_health,
    run_product_lane,
    start_final_browser_session,
    validate_fingerprint,
)
from acceptance.platform.model import BrowserProfile, Outcome, PlatformProfile


class _Process:
    def __init__(self, alive: bool = True) -> None:
        self.alive = alive
        self.terminated = False
        self.stdout = b"diagnostic stdout"
        self.stderr = b"diagnostic stderr"

    def poll(self) -> None:
        return None if self.alive else 1

    def terminate(self) -> None:
        self.terminated = True
        self.alive = False

    def wait(self, timeout: float | None = None) -> int:
        return 0


class _Launch:
    def __init__(self) -> None:
        self.process = _Process()
        self.closed = False
        self.arguments: tuple[str, ...] = ()

    def start(self, *arguments: str) -> _Process:
        self.arguments = arguments
        return self.process

    def close(self) -> None:
        self.closed = True


class _Bundle:
    sha256 = "c" * 64
    version = "Chrome 124"
    byte_size = 1

    def __init__(self) -> None:
        self.launch = _Launch()
        self.closed = False

    def launch_spec(self) -> _Launch:
        return self.launch

    def close(self) -> None:
        self.closed = True


PLATFORM_CARD = Path(__file__).parents[1] / "acceptance/browser/platform-card.mjs"


def _profile(
    *, checksum: str = "a" * 64, store_root: Path = Path("/opt/platform")
) -> PlatformProfile:
    return PlatformProfile(
        version="test-profile",
        checksum=checksum,
        browser=BrowserProfile(
            store_root, store_root / "chrome", "Chrome 124", 1, "c" * 64
        ),
    )


def _metrics() -> dict[str, object]:
    return {
        "innerWidth": 1920,
        "innerHeight": 1080,
        "visualWidth": 1920,
        "visualHeight": 1080,
        "dpr": 1,
        "raster": [1920, 1080],
        "nativeResize": True,
    }


def _executor(
    bundle: _Bundle, *, ready: bool = True, card: HealthProbeResult | None = None
) -> PlatformHealthExecutor:
    xvfb = _Process()
    return PlatformHealthExecutor(
        probe=lambda command: " ".join(command),
        verify_bundle=lambda _: bundle,
        start_xvfb=lambda display: xvfb,
        cdp_version=lambda _: {"Browser": "Chrome 124"} if ready else None,
        run_card=lambda *_: card
        or HealthProbeResult(
            "Chrome 124", _metrics(), {"neutral.png": b"png", "metrics.json": b"{}"}
        ),
        clock=lambda: 0.0,
        sleep=lambda _: None,
    )


def test_product_lane_requires_a_sealed_validated_fingerprint_before_execution(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    profile = _profile()
    root = tmp_path / ("6" * 40)
    run_platform_health(profile, root, _executor(_Bundle()), card_path=PLATFORM_CARD)
    result = run_product_lane(
        profile=profile,
        fingerprint_path=root / "fingerprint.json",
        execute=lambda: calls.append("product"),
    )
    assert result.outcome is Outcome.PASSED
    assert calls == ["product"]
    with pytest.raises(ValueError, match="fingerprint"):
        run_product_lane(
            profile=profile,
            fingerprint_path=root / "missing.json",
            execute=lambda: calls.append("unexpected"),
        )
    assert calls == ["product"]


def test_exact_unprovisioned_template_retains_failure_evidence_before_any_command(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    profile = PlatformProfile(
        "unprovisioned-template",
        "0" * 64,
        BrowserProfile(
            Path("/opt/acceptance-platform/browser"),
            Path("/opt/acceptance-platform/browser/chrome"),
            "UNPROVISIONED_BROWSER_DO_NOT_LAUNCH",
            0,
            "0" * 64,
        ),
    )
    executor = PlatformHealthExecutor(
        probe=lambda command: calls.append(" ".join(command)) or "unexpected"
    )
    root = tmp_path / ("f" * 40)
    result = run_platform_health(profile, root, executor)
    assert result.outcome is Outcome.ENVIRONMENT_BLOCKED
    assert result.reason == "platform profile is deliberately unprovisioned"
    assert calls == []
    assert (root / "fingerprint.json").exists()
    verify_manifest(root)
    assert json.loads((root / "blocked.json").read_text())["reason"] == result.reason


def test_magic_fields_with_wrong_template_paths_are_not_unprovisioned(
    tmp_path: Path,
) -> None:
    profile = PlatformProfile(
        "unprovisioned-template",
        "0" * 64,
        BrowserProfile(
            Path("/wrong"),
            Path("/wrong/chrome"),
            "UNPROVISIONED_BROWSER_DO_NOT_LAUNCH",
            0,
            "0" * 64,
        ),
    )
    result = run_platform_health(
        profile, tmp_path / ("a" * 40), PlatformHealthExecutor(probe=lambda _: "x")
    )
    assert result.reason.startswith("platform health failed:")


def test_lifecycle_waits_for_child_and_cdp_then_closes_everything(
    tmp_path: Path,
) -> None:
    bundle = _Bundle()
    result = run_platform_health(
        _profile(), tmp_path / ("b" * 40), _executor(bundle), card_path=PLATFORM_CARD
    )
    assert result.outcome is Outcome.PASSED
    assert bundle.launch.closed and bundle.closed and bundle.launch.process.terminated
    assert "--remote-debugging-port=" in " ".join(bundle.launch.arguments)
    assert "--remote-debugging-address=127.0.0.1" in bundle.launch.arguments
    assert any(
        argument.startswith("--user-data-dir=") for argument in bundle.launch.arguments
    )
    assert any(
        argument.startswith("--display=:") and argument != "--display=:91"
        for argument in bundle.launch.arguments
    )


def test_final_session_uses_profile_pinned_headed_xvfb_and_requires_neutral_metrics(
    tmp_path: Path,
) -> None:
    bundle = _Bundle()
    session = start_final_browser_session(_profile(), tmp_path, _executor(bundle))

    assert session.cdp_url.startswith("http://127.0.0.1:")
    assert any(
        argument.startswith("--display=:") for argument in bundle.launch.arguments
    )
    assert "--headless" not in bundle.launch.arguments
    assert session.metrics["raster"] == [1920, 1080]
    assert session.profile_dir.parent == tmp_path
    session.close()
    assert bundle.launch.closed and bundle.closed and bundle.launch.process.terminated
    assert session.artifacts["browser.stderr.log"] == b"diagnostic stderr"
    assert session.artifacts["xvfb.stdout.log"] == b"diagnostic stdout"


def test_session_cleanup_removes_owned_xvfb_socket_only_after_xvfb_exits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from acceptance.platform import health

    monkeypatch.chdir(tmp_path)
    socket_path = Path("X123")
    unix_socket = __import__("socket").socket(__import__("socket").AF_UNIX)
    unix_socket.bind(str(socket_path))
    bundle = _Bundle()
    session = start_final_browser_session(_profile(), tmp_path, _executor(bundle))
    monkeypatch.setattr(health, "_xvfb_socket_path", lambda _: socket_path)

    try:
        session.close()
    finally:
        unix_socket.close()

    assert not socket_path.exists()


def test_session_cleanup_keeps_xvfb_socket_when_owned_xvfb_is_still_alive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from acceptance.platform import health

    class StubbornXvfb(_Process):
        def terminate(self) -> None:
            self.terminated = True

    monkeypatch.chdir(tmp_path)
    socket_path = Path("X124")
    unix_socket = __import__("socket").socket(__import__("socket").AF_UNIX)
    unix_socket.bind(str(socket_path))
    bundle = _Bundle()
    executor = _executor(bundle)
    executor = PlatformHealthExecutor(
        **{**executor.__dict__, "start_xvfb": lambda _: StubbornXvfb()}
    )
    session = start_final_browser_session(_profile(), tmp_path, executor)
    monkeypatch.setattr(health, "_xvfb_socket_path", lambda _: socket_path)

    try:
        with pytest.raises(ValueError, match="task Xvfb process remains after cleanup"):
            session.close()
        assert socket_path.exists()
    finally:
        unix_socket.close()
        socket_path.unlink(missing_ok=True)


def test_xvfb_termination_failure_drains_every_remaining_session_resource(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from acceptance.platform import health

    class FailingXvfb(_Process):
        def terminate(self) -> None:
            self.terminated = True
            raise OSError("xvfb teardown failed")

    bundle = _Bundle()
    xvfb = FailingXvfb()
    executor = _executor(bundle)
    executor = PlatformHealthExecutor(
        **{**executor.__dict__, "start_xvfb": lambda _: xvfb}
    )
    session = start_final_browser_session(_profile(), tmp_path, executor)
    browser_cleanup_calls: list[object] = []
    cleanup_verification: list[tuple[bool, bool, bool]] = []
    original_terminate_browser_group = health._terminate_browser_group

    def terminate_browser_group(process: object) -> None:
        browser_cleanup_calls.append(process)
        original_terminate_browser_group(process)

    monkeypatch.setattr(health, "_terminate_browser_group", terminate_browser_group)
    monkeypatch.setattr(
        health,
        "_verify_browser_cleanup",
        lambda _display, _port, profile, _pgid: cleanup_verification.append(
            (profile.exists(), bundle.launch.closed, bundle.closed)
        ),
    )

    with pytest.raises(OSError, match="xvfb teardown failed"):
        session.close()

    assert browser_cleanup_calls == [bundle.launch.process]
    assert session.artifacts["browser.stderr.log"] == b"diagnostic stderr"
    assert session.artifacts["xvfb.stderr.log"] == b"diagnostic stderr"
    assert bundle.launch.closed and bundle.closed
    assert not session.profile_dir.exists()
    assert cleanup_verification == [(False, True, True)]
    session.close()


def test_final_session_rejects_mismatched_neutral_metrics_before_build(
    tmp_path: Path,
) -> None:
    bundle = _Bundle()
    bad = _metrics()
    bad["raster"] = [1919, 1080]

    with pytest.raises(ValueError, match="neutral viewport"):
        start_final_browser_session(
            _profile(),
            tmp_path,
            _executor(bundle, card=HealthProbeResult("Chrome", bad, {})),
        )

    assert bundle.launch.closed and bundle.closed and bundle.launch.process.terminated


def test_browser_group_cleanup_kills_descendant_after_leader_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from acceptance.platform import health

    class DeadLeader:
        pid = 4242

        def poll(self) -> int:
            return 1

        def wait(self, timeout: float | None = None) -> int:
            return 1

    signals: list[int] = []
    group_survives = True

    def killpg(pgid: int, signal: int) -> None:
        nonlocal group_survives
        assert pgid == DeadLeader.pid
        signals.append(signal)
        if signal == 9:
            group_survives = False
        elif signal == 0 and not group_survives:
            raise ProcessLookupError

    monkeypatch.setattr(health.os, "killpg", killpg)
    health._terminate_browser_group(DeadLeader())
    assert signals == [15, 0, 9, 0]


def test_readiness_timeout_retains_diagnostics_and_never_runs_card(
    tmp_path: Path,
) -> None:
    bundle = _Bundle()
    invoked = False
    executor = _executor(bundle, ready=False)
    executor = PlatformHealthExecutor(
        **{
            **executor.__dict__,
            "run_card": lambda *_: (_ for _ in ()).throw(AssertionError("card ran")),
            "clock": iter((0.0, 121.0)).__next__,
        }
    )
    result = run_platform_health(
        _profile(), tmp_path / ("c" * 40), executor, card_path=PLATFORM_CARD
    )
    assert result.outcome is Outcome.ENVIRONMENT_BLOCKED
    assert "readiness" in result.reason
    assert not invoked
    assert (
        tmp_path / ("c" * 40) / "browser.stderr.log"
    ).read_bytes() == b"diagnostic stderr"
    assert (
        tmp_path / ("c" * 40) / "xvfb.stdout.log"
    ).read_bytes() == b"diagnostic stdout"
    assert (
        tmp_path / ("c" * 40) / "xvfb.stderr.log"
    ).read_bytes() == b"diagnostic stderr"
    assert bundle.launch.closed and bundle.closed and bundle.launch.process.terminated


def test_cleanup_failure_preserves_primary_health_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from acceptance.platform import health

    cleanup_reason = "task browser process group remains after cleanup"
    monkeypatch.setattr(
        health,
        "_terminate_browser_group",
        lambda _: (_ for _ in ()).throw(ValueError(cleanup_reason)),
    )
    root = tmp_path / ("e" * 40)
    executor = _executor(_Bundle(), ready=False)
    executor = PlatformHealthExecutor(
        **{**executor.__dict__, "clock": iter((0.0, 121.0)).__next__}
    )

    result = run_platform_health(_profile(), root, executor, card_path=PLATFORM_CARD)

    blocked = json.loads((root / "blocked.json").read_text())
    fingerprint = json.loads((root / "fingerprint.json").read_text())
    assert result.outcome is Outcome.ENVIRONMENT_BLOCKED
    assert "readiness" in result.reason
    assert blocked["reason"] == result.reason
    assert fingerprint["reason"] == result.reason
    assert blocked["cleanup_reason"] == cleanup_reason
    assert fingerprint["cleanup_reason"] == cleanup_reason


def test_evidence_rejects_symlink_nested_target_and_is_private(tmp_path: Path) -> None:
    root = prepare_evidence_root(tmp_path / ("d" * 40))
    write_artifacts(root, {"safe/nested/ok": b"yes"})
    assert (root / "safe").stat().st_mode & 0o777 == 0o700
    assert (root / "safe/nested").stat().st_mode & 0o777 == 0o700
    assert (root / "safe/nested/ok").stat().st_mode & 0o777 == 0o600
    blocked = prepare_evidence_root(tmp_path / ("3" * 40))
    (blocked / "nested").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        write_artifacts(blocked, {"nested/escape": b"no"})
    assert blocked.stat().st_mode & 0o777 == 0o700


def test_default_card_result_is_parsed_and_persisted_by_python(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from acceptance.platform import health

    bundle = _Bundle()
    payload = {
        "browserVersion": "Chrome 124",
        "metrics": _metrics(),
        "artifacts": {"neutral.png": "cG5n", "metrics.json": "e30="},
    }
    monkeypatch.setattr(
        health.subprocess,
        "run",
        lambda *args, **kwargs: type(
            "Run", (), {"stdout": json.dumps(payload).encode()}
        )(),
    )
    executor = _executor(bundle)
    executor = PlatformHealthExecutor(**{**executor.__dict__, "run_card": None})
    result = run_platform_health(
        _profile(), tmp_path / ("4" * 40), executor, card_path=PLATFORM_CARD
    )
    assert result.outcome is Outcome.PASSED
    assert (tmp_path / ("4" * 40) / "neutral.png").read_bytes() == b"png"


def test_fingerprint_recomputes_card_and_retained_artifact_checksums(
    tmp_path: Path,
) -> None:
    bundle = _Bundle()
    root = tmp_path / ("e" * 40)
    result = run_platform_health(
        _profile(), root, _executor(bundle), card_path=PLATFORM_CARD
    )
    assert (
        validate_fingerprint(
            _profile(), root / "fingerprint.json", card_path=PLATFORM_CARD
        )
        == result
    )
    (root / "neutral.png").write_bytes(b"mutated")
    with pytest.raises(ValueError, match="evidence"):
        validate_fingerprint(
            _profile(), root / "fingerprint.json", card_path=PLATFORM_CARD
        )


def test_fingerprint_rejects_card_drift(tmp_path: Path) -> None:
    bundle = _Bundle()
    card = tmp_path / "card.mjs"
    card.write_bytes(PLATFORM_CARD.read_bytes())
    root = tmp_path / ("1" * 40)
    run_platform_health(_profile(), root, _executor(bundle), card_path=card)
    card.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="card checksum"):
        validate_fingerprint(_profile(), root / "fingerprint.json", card_path=card)


def test_metrics_require_visual_viewport_native_resize_and_decoded_raster(
    tmp_path: Path,
) -> None:
    bundle = _Bundle()
    bad = _metrics()
    bad["visualWidth"] = 1919
    result = run_platform_health(
        _profile(),
        tmp_path / ("2" * 40),
        _executor(bundle, card=HealthProbeResult("Chrome", bad, {})),
        card_path=PLATFORM_CARD,
    )
    assert result.outcome is Outcome.ENVIRONMENT_BLOCKED


def test_platform_card_resolves_locked_playwright_before_a_failed_cdp_connection() -> (
    None
):
    result = subprocess.run(
        ["node", str(PLATFORM_CARD), "http://127.0.0.1:9"],
        capture_output=True,
        check=False,
        text=True,
    )
    diagnostics = result.stdout + result.stderr
    assert result.returncode != 0
    assert "ERR_MODULE_NOT_FOUND" not in diagnostics
    assert "Cannot find package '@playwright/test'" not in diagnostics
    assert "ECONNREFUSED" in diagnostics


def test_platform_card_uses_native_protocol_and_platform_output_channel() -> None:
    source = PLATFORM_CARD.read_text(encoding="utf-8")
    assert "Browser.getWindowForTarget" in source
    assert "Browser.setContentsSize" in source
    assert "Emulation.setDeviceMetricsOverride" not in source
    assert "process.stdout.write" in source
    assert "writeFile" not in source


def test_descriptor_browser_launch_captures_private_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import acceptance.platform.browser_bundle as bundle_module

    captured: dict[str, object] = {}

    class Popen:
        pass

    monkeypatch.setattr(
        bundle_module.subprocess,
        "Popen",
        lambda *args, **kwargs: captured.update(kwargs) or Popen(),
    )
    descriptor = BrowserLaunchSpec(os.open("/dev/null", os.O_RDONLY))
    try:
        descriptor.start("about:blank")
    finally:
        descriptor.close()
    assert captured["stdout"] is bundle_module.subprocess.PIPE
    assert captured["stderr"] is bundle_module.subprocess.PIPE


def test_failing_node_card_retains_stdout_and_stderr_before_blocking(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from acceptance.platform import health

    def fail(*_: object, **__: object) -> None:
        raise health.subprocess.CalledProcessError(
            1, "node", output=b"card stdout", stderr=b"card stderr"
        )

    monkeypatch.setattr(health.subprocess, "run", fail)
    bundle = _Bundle()
    executor = _executor(bundle)
    executor = PlatformHealthExecutor(**{**executor.__dict__, "run_card": None})
    root = tmp_path / ("9" * 40)
    result = run_platform_health(_profile(), root, executor, card_path=PLATFORM_CARD)
    assert result.outcome is Outcome.ENVIRONMENT_BLOCKED
    assert (root / "card.stdout.log").read_bytes() == b"card stdout"
    assert (root / "card.stderr.log").read_bytes() == b"card stderr"
    verify_manifest(root)


def test_fingerprint_replacement_and_symlink_are_rejected_before_claims(
    tmp_path: Path,
) -> None:
    root = tmp_path / ("8" * 40)
    run_platform_health(_profile(), root, _executor(_Bundle()), card_path=PLATFORM_CARD)
    (root / "fingerprint.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="authority|fingerprint"):
        validate_fingerprint(
            _profile(), root / "fingerprint.json", card_path=PLATFORM_CARD
        )
    (root / "fingerprint.json").unlink()
    (root / "fingerprint.json").symlink_to(tmp_path / "missing.json")
    with pytest.raises(ValueError, match="authority|fingerprint"):
        validate_fingerprint(
            _profile(), root / "fingerprint.json", card_path=PLATFORM_CARD
        )


def test_card_symlink_is_rejected_before_checksum_claim(tmp_path: Path) -> None:
    root = tmp_path / ("7" * 40)
    card = tmp_path / "card.mjs"
    card.write_bytes(PLATFORM_CARD.read_bytes())
    run_platform_health(_profile(), root, _executor(_Bundle()), card_path=card)
    card.unlink()
    card.symlink_to(PLATFORM_CARD)
    with pytest.raises(ValueError, match="authority|card checksum"):
        validate_fingerprint(_profile(), root / "fingerprint.json", card_path=card)
