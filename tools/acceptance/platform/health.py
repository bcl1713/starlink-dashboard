"""Descriptor-bound neutral browser health lifecycle and fingerprint authority."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
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
    cleanup_reason: str = ""

    @classmethod
    def blocked(cls, reason: str, **values: Any) -> HealthFingerprint:
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


@dataclass
class PlatformBrowserSession:
    """Platform-owned headed browser lifecycle retained through final evidence."""

    cdp_url: str
    display: str
    profile_dir: Path
    metrics: Mapping[str, Any]
    artifacts: dict[str, bytes]
    _bundle: BrowserBundle
    _launch: BrowserLaunchSpec
    _browser: Any
    _xvfb: Any
    _closed: bool = False

    def close(self) -> None:
        """Idempotently reap every task-owned browser resource and retain logs."""
        if self._closed:
            return
        self._closed = True
        cleanup_error = ""
        try:
            _terminate_browser_group(self._browser)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            cleanup_error = str(error)
        _terminate(self._xvfb)
        _retain_logs(self.artifacts, "browser", self._browser)
        _retain_logs(self.artifacts, "xvfb", self._xvfb)
        self._launch.close()
        self._bundle.close()
        shutil.rmtree(self.profile_dir, ignore_errors=True)
        try:
            _verify_browser_cleanup(
                self.display,
                int(self.cdp_url.rsplit(":", 1)[1]),
                self.profile_dir,
                _browser_group_id(self._browser),
            )
        except ValueError as error:
            cleanup_error = cleanup_error or str(error)
        if cleanup_error:
            raise ValueError(cleanup_error)


def start_final_browser_session(
    profile: PlatformProfile,
    task_root: Path,
    executor: PlatformHealthExecutor,
    *,
    card_path: Path = _CARD,
) -> PlatformBrowserSession:
    """Start and validate the sole headed browser authority for a final lane."""
    if _is_unprovisioned(profile):
        raise _Blocked("platform profile is deliberately unprovisioned")
    task_root.mkdir(parents=True, exist_ok=True)
    bundle: BrowserBundle | None = None
    launch: BrowserLaunchSpec | None = None
    browser = xvfb = None
    profile_dir: Path | None = None
    try:
        bundle = executor.verify_bundle(profile)
        launch = bundle.launch_spec()
        display, port, profile_dir = _allocate_browser_resources(task_root)
        xvfb = executor.start_xvfb(display)
        browser = launch.start(
            f"--display={display}",
            f"--remote-debugging-port={port}",
            "--remote-debugging-address=127.0.0.1",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank",
        )
        cdp_url = f"http://127.0.0.1:{port}"
        _wait_ready(browser, xvfb, cdp_url, executor)
        probe = (executor.run_card or _platform_card(card_path, cdp_url))(
            launch, task_root
        )
        _require_neutral_metrics(probe.metrics)
        return PlatformBrowserSession(
            cdp_url,
            display,
            profile_dir,
            dict(probe.metrics),
            dict(probe.artifacts),
            bundle,
            launch,
            browser,
            xvfb,
        )
    except BaseException:
        retained: dict[str, bytes] = {}
        if bundle is not None and launch is not None and profile_dir is not None:
            session = PlatformBrowserSession(
                f"http://127.0.0.1:{port}",
                display,
                profile_dir,
                {},
                retained,
                bundle,
                launch,
                browser,
                xvfb,
            )
            try:
                session.close()
            except ValueError as cleanup_failure:
                retained["cleanup-error.log"] = str(cleanup_failure).encode()
                cleanup_error = str(cleanup_failure)
        else:
            if launch is not None:
                launch.close()
            if bundle is not None:
                bundle.close()
        # Health retains these diagnostics after classifying the original fault.
        # The final runner receives the same artifacts from a successfully owned session.
        import sys

        error = sys.exception()
        if error is not None:
            error.platform_artifacts = retained  # type: ignore[attr-defined]
            if "cleanup_error" in locals() and cleanup_error:
                error.platform_cleanup_error = cleanup_error  # type: ignore[attr-defined]
        raise


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
    session: PlatformBrowserSession | None = None
    cleanup_error = ""
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
        session = start_final_browser_session(
            profile, root, executor, card_path=card_path
        )
        values["browser_sha256"] = session._bundle.sha256
        values.update(
            browser_version=session._bundle.version, metrics=dict(session.metrics)
        )
        artifacts.update(session.artifacts)
        outcome, reason = Outcome.PASSED, ""
    except _CardFailure as error:
        artifacts.update(getattr(error, "platform_artifacts", {}))
        cleanup_error = getattr(error, "platform_cleanup_error", "")
        artifacts["card.stdout.log"] = error.stdout
        artifacts["card.stderr.log"] = error.stderr
        outcome, reason = (
            Outcome.ENVIRONMENT_BLOCKED,
            f"platform health failed: {error}",
        )
    except _Blocked as error:
        artifacts.update(getattr(error, "platform_artifacts", {}))
        cleanup_error = getattr(error, "platform_cleanup_error", "")
        outcome, reason = Outcome.ENVIRONMENT_BLOCKED, str(error)
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        subprocess.SubprocessError,
    ) as error:
        artifacts.update(getattr(error, "platform_artifacts", {}))
        cleanup_error = getattr(error, "platform_cleanup_error", "")
        outcome, reason = (
            Outcome.ENVIRONMENT_BLOCKED,
            f"platform health failed: {error}",
        )
    finally:
        try:
            if session is not None:
                session.close()
                artifacts.update(session.artifacts)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            cleanup_error = str(error)
    if cleanup_error:
        outcome = Outcome.ENVIRONMENT_BLOCKED
        values["cleanup_reason"] = cleanup_error
        if not reason:
            reason = cleanup_error
    if outcome is not Outcome.PASSED:
        artifacts["blocked.json"] = json.dumps(
            {
                "cleanup_reason": values.get("cleanup_reason", ""),
                "profile_checksum": profile.checksum,
                "reason": reason,
            },
            sort_keys=True,
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
    *, profile: PlatformProfile, fingerprint_path: Path, execute: Callable[[], None]
) -> RunResult:
    """The product boundary consumes only sealed, validated health authority."""
    validate_fingerprint(profile, fingerprint_path)
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


def _allocate_browser_resources(evidence_root: Path) -> tuple[str, int, Path]:
    """Allocate a unique display, loopback CDP port, and private Chrome profile."""
    profile = Path(tempfile.mkdtemp(prefix="health-chrome-", dir=evidence_root))
    os.chmod(profile, 0o700)
    for _ in range(32):
        display_number = 100 + int.from_bytes(os.urandom(2), "big") % 50000
        if not Path(f"/tmp/.X11-unix/X{display_number}").exists():
            return f":{display_number}", _free_local_port(), profile
    shutil.rmtree(profile, ignore_errors=True)
    raise ValueError("unable to allocate a task-owned X display")


def _terminate(process: Any) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _browser_group_id(process: Any) -> int | None:
    pid = getattr(process, "pid", None)
    return pid if isinstance(pid, int) and pid > 0 else None


def _process_group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except OSError as error:
        raise ValueError(
            "unable to verify task browser process group cleanup"
        ) from error
    return True


def _terminate_browser_group(process: Any) -> None:
    """Terminate/reap Chrome's private session, including browser descendants."""
    if process is None:
        return
    if (pgid := _browser_group_id(process)) is None:
        _terminate(process)
        return
    try:
        os.killpg(pgid, 15)
    except ProcessLookupError:
        return
    except OSError as error:
        raise ValueError("unable to terminate task browser process group") from error
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    if _process_group_exists(pgid):
        try:
            os.killpg(pgid, 9)
        except ProcessLookupError:
            return
        except OSError as error:
            raise ValueError("unable to kill task browser process group") from error
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    if _process_group_exists(pgid):
        raise ValueError("task browser process group remains after cleanup")


def _verify_browser_cleanup(
    display: str, port: int, profile: Path, process_group: int | None
) -> None:
    """Fail closed if task-owned browser resources survive teardown."""
    if process_group is not None and _process_group_exists(process_group):
        raise ValueError("task browser process group remains after cleanup")
    if _cdp_version(f"http://127.0.0.1:{port}") is not None:
        raise ValueError("task CDP listener remains after cleanup")
    display_number = display.removeprefix(":")
    if display_number.isdigit() and Path(f"/tmp/.X11-unix/X{display_number}").exists():
        raise ValueError("task X display remains after cleanup")
    if profile.exists():
        raise ValueError("task browser profile remains after cleanup")


def _retain_logs(artifacts: dict[str, bytes], name: str, process: Any) -> None:
    if process is None:
        return
    for stream in ("stdout", "stderr"):
        value = getattr(process, stream, None)
        if value is None:
            continue
        content = _read_process_stream(value)
        if content is None:
            continue
        if isinstance(content, str):
            content = content.encode()
        if isinstance(content, bytes):
            artifacts[f"{name}.{stream}.log"] = content


def _read_process_stream(value: Any) -> Any | None:
    try:
        return value.read() if hasattr(value, "read") else value
    except (OSError, ValueError):
        return None


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(read_nofollow(path)).hexdigest()


class _Blocked(Exception):
    pass


class _CardFailure(Exception):
    def __init__(self, stdout: bytes, stderr: bytes) -> None:
        super().__init__("platform card failed")
        self.stdout = stdout
        self.stderr = stderr
