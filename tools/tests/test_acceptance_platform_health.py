from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from acceptance.platform.evidence import prepare_evidence_root, verify_manifest, write_artifacts
from acceptance.platform.health import (
    HealthFingerprint,
    HealthProbeResult,
    PlatformHealthExecutor,
    run_platform_health,
    run_product_lane,
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


def _profile(*, checksum: str = "a" * 64, store_root: Path = Path("/opt/platform")) -> PlatformProfile:
    return PlatformProfile(
        version="test-profile",
        checksum=checksum,
        browser=BrowserProfile(store_root, store_root / "chrome", "Chrome 124", 1, "c" * 64),
    )


def _metrics() -> dict[str, object]:
    return {"innerWidth": 1920, "innerHeight": 1080, "visualWidth": 1920, "visualHeight": 1080, "dpr": 1, "raster": [1920, 1080], "nativeResize": True}


def _executor(bundle: _Bundle, *, ready: bool = True, card: HealthProbeResult | None = None) -> PlatformHealthExecutor:
    xvfb = _Process()
    return PlatformHealthExecutor(
        probe=lambda command: " ".join(command),
        verify_bundle=lambda _: bundle,
        start_xvfb=lambda display: xvfb,
        cdp_version=lambda _: {"Browser": "Chrome 124"} if ready else None,
        run_card=lambda *_: card or HealthProbeResult("Chrome 124", _metrics(), {"neutral.png": b"png", "metrics.json": b"{}"}),
        clock=lambda: 0.0,
        sleep=lambda _: None,
    )


def test_health_failure_blocks_before_product_executor() -> None:
    calls: list[str] = []
    result = run_product_lane(health=lambda: HealthFingerprint.blocked("unprovisioned"), execute=lambda: calls.append("product"))
    assert result.outcome is Outcome.ENVIRONMENT_BLOCKED
    assert calls == []


def test_exact_unprovisioned_template_retains_failure_evidence_before_any_command(tmp_path: Path) -> None:
    calls: list[str] = []
    profile = PlatformProfile(
        "unprovisioned-template", "0" * 64,
        BrowserProfile(Path("/opt/acceptance-platform/browser"), Path("/opt/acceptance-platform/browser/chrome"), "UNPROVISIONED_BROWSER_DO_NOT_LAUNCH", 0, "0" * 64),
    )
    executor = PlatformHealthExecutor(probe=lambda command: calls.append(" ".join(command)) or "unexpected")
    root = tmp_path / ("f" * 40)
    result = run_platform_health(profile, root, executor)
    assert result.outcome is Outcome.ENVIRONMENT_BLOCKED
    assert result.reason == "platform profile is deliberately unprovisioned"
    assert calls == []
    assert (root / "fingerprint.json").exists()
    verify_manifest(root)
    assert json.loads((root / "blocked.json").read_text())["reason"] == result.reason


def test_magic_fields_with_wrong_template_paths_are_not_unprovisioned(tmp_path: Path) -> None:
    profile = PlatformProfile("unprovisioned-template", "0" * 64, BrowserProfile(Path("/wrong"), Path("/wrong/chrome"), "UNPROVISIONED_BROWSER_DO_NOT_LAUNCH", 0, "0" * 64))
    result = run_platform_health(profile, tmp_path / ("a" * 40), PlatformHealthExecutor(probe=lambda _: "x"))
    assert result.reason.startswith("platform health failed:")


def test_lifecycle_waits_for_child_and_cdp_then_closes_everything(tmp_path: Path) -> None:
    bundle = _Bundle()
    result = run_platform_health(_profile(), tmp_path / ("b" * 40), _executor(bundle), card_path=PLATFORM_CARD)
    assert result.outcome is Outcome.PASSED
    assert bundle.launch.closed and bundle.closed and bundle.launch.process.terminated
    assert "--remote-debugging-port=" in " ".join(bundle.launch.arguments)


def test_readiness_timeout_retains_diagnostics_and_never_runs_card(tmp_path: Path) -> None:
    bundle = _Bundle()
    invoked = False
    executor = _executor(bundle, ready=False)
    executor = PlatformHealthExecutor(**{**executor.__dict__, "run_card": lambda *_: (_ for _ in ()).throw(AssertionError("card ran")), "clock": iter((0.0, 121.0)).__next__})
    result = run_platform_health(_profile(), tmp_path / ("c" * 40), executor, card_path=PLATFORM_CARD)
    assert result.outcome is Outcome.ENVIRONMENT_BLOCKED
    assert "readiness" in result.reason
    assert not invoked
    assert (tmp_path / ("c" * 40) / "browser.stderr.log").read_bytes() == b"diagnostic stderr"
    assert bundle.launch.closed and bundle.closed and bundle.launch.process.terminated


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


def test_default_card_result_is_parsed_and_persisted_by_python(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import acceptance.platform.health as health

    bundle = _Bundle()
    payload = {"browserVersion": "Chrome 124", "metrics": _metrics(), "artifacts": {"neutral.png": "cG5n", "metrics.json": "e30="}}
    monkeypatch.setattr(health.subprocess, "run", lambda *args, **kwargs: type("Run", (), {"stdout": json.dumps(payload).encode()})())
    executor = _executor(bundle)
    executor = PlatformHealthExecutor(**{**executor.__dict__, "run_card": None})
    result = run_platform_health(_profile(), tmp_path / ("4" * 40), executor, card_path=PLATFORM_CARD)
    assert result.outcome is Outcome.PASSED
    assert (tmp_path / ("4" * 40) / "neutral.png").read_bytes() == b"png"


def test_fingerprint_recomputes_card_and_retained_artifact_checksums(tmp_path: Path) -> None:
    bundle = _Bundle()
    root = tmp_path / ("e" * 40)
    result = run_platform_health(_profile(), root, _executor(bundle), card_path=PLATFORM_CARD)
    assert validate_fingerprint(_profile(), root / "fingerprint.json", card_path=PLATFORM_CARD) == result
    (root / "neutral.png").write_bytes(b"mutated")
    with pytest.raises(ValueError, match="evidence"):
        validate_fingerprint(_profile(), root / "fingerprint.json", card_path=PLATFORM_CARD)


def test_fingerprint_rejects_card_drift(tmp_path: Path) -> None:
    bundle = _Bundle()
    card = tmp_path / "card.mjs"
    card.write_bytes(PLATFORM_CARD.read_bytes())
    root = tmp_path / ("1" * 40)
    run_platform_health(_profile(), root, _executor(bundle), card_path=card)
    card.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="card checksum"):
        validate_fingerprint(_profile(), root / "fingerprint.json", card_path=card)


def test_metrics_require_visual_viewport_native_resize_and_decoded_raster(tmp_path: Path) -> None:
    bundle = _Bundle()
    bad = _metrics()
    bad["visualWidth"] = 1919
    result = run_platform_health(_profile(), tmp_path / ("2" * 40), _executor(bundle, card=HealthProbeResult("Chrome", bad, {})), card_path=PLATFORM_CARD)
    assert result.outcome is Outcome.ENVIRONMENT_BLOCKED


def test_platform_card_uses_native_protocol_and_platform_output_channel() -> None:
    source = PLATFORM_CARD.read_text(encoding="utf-8")
    assert "Browser.getWindowForTarget" in source
    assert "Browser.setContentsSize" in source
    assert "Emulation.setDeviceMetricsOverride" not in source
    assert "process.stdout.write" in source
    assert "writeFile" not in source
