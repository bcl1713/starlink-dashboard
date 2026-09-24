"""Descriptor-bound neutral browser health lifecycle and fingerprint authority."""

from __future__ import annotations

import base64
import hashlib
import json
import socket
import subprocess
import time
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .browser_bundle import BrowserBundle, BrowserLaunchSpec, verify_browser_bundle
from .evidence import (
    prepare_evidence_root,
    read_fingerprint_authority,
    read_nofollow,
    seal_fingerprint,
    verify_manifest,
    write_artifacts,
)
from .model import Lane, Outcome, PlatformProfile, RunResult

_CARD = Path(__file__).parents[1] / "browser/platform-card.mjs"
_TEMPLATE = (
    "unprovisioned-template",
    "0" * 64,
    "/opt/acceptance-platform/browser",
    "/opt/acceptance-platform/browser/chrome",
    "UNPROVISIONED_BROWSER_DO_NOT_LAUNCH",
    0,
    "0" * 64,
)


@dataclass(frozen=True)
class HealthFingerprint:
    outcome: Outcome
    profile_checksum: str = ""
    card_checksum: str = ""
    docker_identity: str = ""
    compose_identity: str = ""
    browser_sha256: str = ""
    browser_version: str = ""
    metrics: Mapping[str, Any] | None = None
    captured_at: str = ""
    evidence_manifest_sha256: str = ""
    reason: str = ""

    @classmethod
    def blocked(cls, reason: str, **values: Any) -> "HealthFingerprint":
        return cls(outcome=Outcome.ENVIRONMENT_BLOCKED, reason=reason, **values)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "outcome": self.outcome.value}


@dataclass(frozen=True)
class HealthProbeResult:
    browser_version: str
    metrics: Mapping[str, Any]
    artifacts: Mapping[str, bytes]


@dataclass(frozen=True)
class PlatformHealthExecutor:
    """Test seams for platform operations; no product command is representable here."""

    probe: Callable[[tuple[str, ...]], str]
    run_card: Callable[[BrowserLaunchSpec, Path], HealthProbeResult] | None = None
    verify_bundle: Callable[[PlatformProfile], BrowserBundle] = verify_browser_bundle
    start_xvfb: Callable[[str], Any] = lambda display: subprocess.Popen(
        ("Xvfb", display, "-screen", "0", "1920x1080x24"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    cdp_version: Callable[[str], Mapping[str, Any] | None] = lambda url: _cdp_version(
        url
    )
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep


def run_platform_health(
    profile: PlatformProfile,
    evidence_root: Path,
    executor: PlatformHealthExecutor,
    *,
    card_path: Path = _CARD,
) -> HealthFingerprint:
    """Run only platform-owned neutral health, retaining evidence on every classified fault."""
    root = prepare_evidence_root(evidence_root)
    artifacts: dict[str, bytes] = {}
    bundle: BrowserBundle | None = None
    launch: BrowserLaunchSpec | None = None
    xvfb = browser = None
    values: dict[str, Any] = {
        "profile_checksum": profile.checksum,
        "captured_at": datetime.now(UTC).isoformat(),
    }
    try:
        if _is_unprovisioned(profile):
            raise _Blocked("platform profile is deliberately unprovisioned")
        card_checksum = _sha256_file(card_path)
        values["card_checksum"] = card_checksum
        values["docker_identity"] = executor.probe(("docker", "--version"))
        values["compose_identity"] = executor.probe(("docker", "compose", "version"))
        bundle = executor.verify_bundle(profile)
        values["browser_sha256"] = bundle.sha256
        launch = bundle.launch_spec()
        display, port = ":91", _free_local_port()
        xvfb = executor.start_xvfb(display)
        browser = launch.start(
            f"--display={display}",
            f"--remote-debugging-port={port}",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank",
        )
        cdp_url = f"http://127.0.0.1:{port}"
        _wait_ready(browser, xvfb, cdp_url, executor)
        probe = (executor.run_card or _platform_card(card_path, cdp_url))(launch, root)
        _require_neutral_metrics(probe.metrics)
        values.update(
            browser_version=probe.browser_version, metrics=dict(probe.metrics)
        )
        artifacts.update(probe.artifacts)
        outcome, reason = Outcome.PASSED, ""
    except _CardFailure as error:
        artifacts["card.stdout.log"] = error.stdout
        artifacts["card.stderr.log"] = error.stderr
        outcome, reason = (
            Outcome.ENVIRONMENT_BLOCKED,
            f"platform health failed: {error}",
        )
    except _Blocked as error:
        outcome, reason = Outcome.ENVIRONMENT_BLOCKED, str(error)
    except Exception as error:
        outcome, reason = (
            Outcome.ENVIRONMENT_BLOCKED,
            f"platform health failed: {error}",
        )
    finally:
        _terminate(browser)
        _terminate(xvfb)
        _retain_logs(artifacts, "browser", browser)
        _retain_logs(artifacts, "xvfb", xvfb)
        if launch is not None:
            launch.close()
        if bundle is not None:
            bundle.close()
    if outcome is not Outcome.PASSED:
        artifacts["blocked.json"] = json.dumps(
            {"reason": reason, "profile_checksum": profile.checksum}, sort_keys=True
        ).encode()
    manifest = write_artifacts(root, artifacts)
    values["evidence_manifest_sha256"] = manifest
    result = HealthFingerprint(outcome=outcome, reason=reason, **values)
    seal_fingerprint(root, json.dumps(result.to_dict(), sort_keys=True).encode())
    return result


def validate_fingerprint(
    profile: PlatformProfile, fingerprint_path: Path, *, card_path: Path = _CARD
) -> HealthFingerprint:
    """Verify profile, card and every retained artifact instead of trusting metadata."""
    try:
        if fingerprint_path.name != "fingerprint.json":
            raise ValueError("invalid fingerprint authority path")
        raw = json.loads(read_fingerprint_authority(fingerprint_path.parent))
        result = HealthFingerprint(outcome=Outcome(raw.pop("outcome")), **raw)
    except (OSError, KeyError, ValueError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("invalid platform health fingerprint") from error
    if result.outcome is not Outcome.PASSED:
        raise ValueError("fingerprint is not a passed health result")
    if result.profile_checksum != profile.checksum:
        raise ValueError("profile checksum drift")
    if result.card_checksum != _sha256_file(card_path):
        raise ValueError("card checksum drift")
    root = fingerprint_path.parent
    try:
        verify_manifest(root)
        manifest_hash = hashlib.sha256(
            read_nofollow(root / "manifest.json")
        ).hexdigest()
    except (OSError, ValueError) as error:
        raise ValueError("evidence verification failed") from error
    if result.evidence_manifest_sha256 != manifest_hash:
        raise ValueError("evidence manifest checksum drift")
    _require_neutral_metrics(result.metrics or {})
    return result


def run_product_lane(
    *, health: Callable[[], HealthFingerprint], execute: Callable[[], None]
) -> RunResult:
    result = health()
    if result.outcome is not Outcome.PASSED:
        return RunResult(lane=Lane.HEALTH, outcome=Outcome.ENVIRONMENT_BLOCKED)
    execute()
    return RunResult(lane=Lane.FINAL, outcome=Outcome.PASSED, final=True)


def _is_unprovisioned(profile: PlatformProfile) -> bool:
    browser = profile.browser
    return (
        profile.version,
        profile.checksum,
        str(browser.store_root),
        str(browser.executable),
        browser.version,
        browser.byte_size,
        browser.sha256,
    ) == _TEMPLATE


def _require_neutral_metrics(metrics: Mapping[str, Any]) -> None:
    expected = {
        "innerWidth": 1920,
        "innerHeight": 1080,
        "visualWidth": 1920,
        "visualHeight": 1080,
        "dpr": 1,
        "raster": [1920, 1080],
        "nativeResize": True,
    }
    if any(metrics.get(key) != value for key, value in expected.items()):
        raise ValueError(
            "neutral viewport, DPR, native resize, or decoded raster is invalid"
        )


def _wait_ready(
    browser: Any, xvfb: Any, url: str, executor: PlatformHealthExecutor
) -> None:
    deadline = executor.clock() + 120.0
    while executor.clock() <= deadline:
        if browser.poll() is not None or xvfb.poll() is not None:
            raise ValueError("browser readiness child exited")
        if executor.cdp_version(url):
            return
        executor.sleep(0.25)
    raise ValueError("browser readiness timed out")


def _platform_card(
    card_path: Path, cdp_url: str
) -> Callable[[BrowserLaunchSpec, Path], HealthProbeResult]:
    """Run the generic card with only the platform-selected CDP endpoint."""

    def run(_: BrowserLaunchSpec, __: Path) -> HealthProbeResult:
        stdout = stderr = b""
        try:
            completed = subprocess.run(
                ("node", str(card_path), cdp_url),
                check=True,
                capture_output=True,
                timeout=120,
            )
            stdout, stderr = completed.stdout, getattr(completed, "stderr", b"")
            payload = json.loads(stdout)
            artifacts = {
                name: base64.b64decode(value, validate=True)
                for name, value in payload["artifacts"].items()
            }
            return HealthProbeResult(
                payload["browserVersion"], payload["metrics"], artifacts
            )
        except subprocess.CalledProcessError as error:
            raise _CardFailure(error.stdout or b"", error.stderr or b"") from error
        except subprocess.TimeoutExpired as error:
            raise _CardFailure(error.stdout or b"", error.stderr or b"") from error
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise _CardFailure(stdout, stderr) from error

    return run


def _cdp_version(url: str) -> Mapping[str, Any] | None:
    try:
        with urllib.request.urlopen(f"{url}/json/version", timeout=1) as response:
            return json.loads(response.read())
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def _free_local_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _terminate(process: Any) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except Exception:
        process.kill()
        process.wait(timeout=5)


def _retain_logs(artifacts: dict[str, bytes], name: str, process: Any) -> None:
    if process is None:
        return
    for stream in ("stdout", "stderr"):
        value = getattr(process, stream, None)
        if value is None:
            continue
        try:
            content = value.read() if hasattr(value, "read") else value
        except Exception:
            continue
        if isinstance(content, str):
            content = content.encode()
        if isinstance(content, bytes):
            artifacts[f"{name}.{stream}.log"] = content


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(read_nofollow(path)).hexdigest()


class _Blocked(Exception):
    pass


class _CardFailure(Exception):
    def __init__(self, stdout: bytes, stderr: bytes) -> None:
        super().__init__("platform card failed")
        self.stdout = stdout
        self.stderr = stderr
