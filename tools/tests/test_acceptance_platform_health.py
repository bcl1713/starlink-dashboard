from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from acceptance.platform.health import (
    HealthFingerprint,
    HealthProbeResult,
    PlatformHealthExecutor,
    run_platform_health,
    run_product_lane,
    validate_fingerprint,
)
from acceptance.platform.model import BrowserProfile, Outcome, PlatformProfile


class _Bundle:
    sha256 = "c" * 64
    version = "Chrome 124"
    byte_size = 1

    def launch_spec(self):
        return self

    def close(self) -> None:
        pass


PLATFORM_CARD = Path(__file__).parents[1] / "acceptance/browser/platform-card.mjs"


def _profile(*, checksum: str = "a" * 64) -> PlatformProfile:
    return PlatformProfile(
        version="test-profile",
        checksum=checksum,
        browser=BrowserProfile(
            store_root=Path("/opt/platform"),
            executable=Path("/opt/platform/chrome"),
            version="Chrome 124",
            byte_size=1,
            sha256="c" * 64,
        ),
    )


def _fingerprint(*, profile_checksum: str = "a" * 64) -> HealthFingerprint:
    return HealthFingerprint(
        outcome=Outcome.PASSED,
        profile_checksum=profile_checksum,
        card_checksum="d" * 64,
        docker_identity="Docker 25",
        compose_identity="Docker Compose 2",
        browser_sha256="c" * 64,
        browser_version="Chrome 124",
        metrics={"innerWidth": 1920, "innerHeight": 1080, "dpr": 1, "raster": [1920, 1080]},
        captured_at="2026-09-24T00:00:00Z",
        evidence_manifest_sha256="e" * 64,
    )


def _write_fingerprint(root: Path, fingerprint: HealthFingerprint) -> Path:
    root.mkdir(exist_ok=True)
    path = root / "fingerprint.json"
    path.write_text(json.dumps(fingerprint.to_dict()), encoding="utf-8")
    return path


def test_health_fingerprint_rejects_profile_checksum_drift(tmp_path: Path) -> None:
    path = _write_fingerprint(tmp_path, _fingerprint(profile_checksum="a" * 64))

    with pytest.raises(ValueError, match="profile checksum"):
        validate_fingerprint(_profile(checksum="b" * 64), path)


def test_health_failure_blocks_before_product_executor() -> None:
    calls: list[str] = []
    result = run_product_lane(
        health=lambda: HealthFingerprint.blocked("unprovisioned"),
        execute=lambda: calls.append("product"),
    )

    assert result.outcome is Outcome.ENVIRONMENT_BLOCKED
    assert calls == []


def test_unprovisioned_profile_blocks_before_probe_or_browser(tmp_path: Path) -> None:
    calls: list[str] = []
    profile = _profile()
    profile = PlatformProfile(
        version="unprovisioned-template",
        checksum="0" * 64,
        browser=BrowserProfile(profile.browser.store_root, profile.browser.executable, "UNPROVISIONED_BROWSER_DO_NOT_LAUNCH", 0, "0" * 64),
    )
    executor = PlatformHealthExecutor(
        probe=lambda command: calls.append(" ".join(command)) or "unexpected",
        run_card=lambda *_: (_ for _ in ()).throw(AssertionError("card must not run")),
        verify_bundle=lambda _: _Bundle(),
    )

    result = run_platform_health(profile, tmp_path / ("f" * 40), executor)

    assert result.outcome is Outcome.ENVIRONMENT_BLOCKED
    assert calls == []


def test_health_writes_sha_qualified_private_evidence_and_fingerprint(tmp_path: Path) -> None:
    card = PLATFORM_CARD.read_bytes()
    profile = _profile()
    executor = PlatformHealthExecutor(
        probe=lambda command: " ".join(command),
        run_card=lambda *_: HealthProbeResult(
            browser_version="Chrome 124",
            metrics={"innerWidth": 1920, "innerHeight": 1080, "dpr": 1, "raster": [1920, 1080]},
            artifacts={"neutral.png": b"PNG", "metrics.json": b"{}"},
        ),
        verify_bundle=lambda _: _Bundle(),
    )

    result = run_platform_health(profile, tmp_path / ("f" * 40), executor, card_path=PLATFORM_CARD)

    assert result.outcome is Outcome.PASSED
    assert result.card_checksum == hashlib.sha256(card).hexdigest()
    assert (tmp_path / ("f" * 40) / "fingerprint.json").exists()
    assert (tmp_path / ("f" * 40) / "manifest.json").exists()
    assert (tmp_path / ("f" * 40) / "fingerprint.json").stat().st_mode & 0o777 == 0o600
    assert validate_fingerprint(profile, tmp_path / ("f" * 40) / "fingerprint.json") == result


def test_platform_card_uses_native_window_protocol() -> None:
    source = PLATFORM_CARD.read_text(encoding="utf-8")

    assert "Browser.getWindowForTarget" in source
    assert "Browser.setContentsSize" in source
    assert "Emulation.setDeviceMetricsOverride" not in source
