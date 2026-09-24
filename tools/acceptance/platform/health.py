"""Neutral platform health and fingerprint authority; never runs product work."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .browser_bundle import BrowserBundle, BrowserLaunchSpec, verify_browser_bundle
from .evidence import prepare_evidence_root, write_artifacts
from .model import Lane, Outcome, PlatformProfile, RunResult

_CARD = Path(__file__).parents[1] / "browser/platform-card.mjs"


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
    def blocked(cls, reason: str) -> "HealthFingerprint":
        return cls(outcome=Outcome.ENVIRONMENT_BLOCKED, reason=reason)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "outcome": self.outcome.value}


@dataclass(frozen=True)
class HealthProbeResult:
    browser_version: str
    metrics: Mapping[str, Any]
    artifacts: Mapping[str, bytes]


@dataclass(frozen=True)
class PlatformHealthExecutor:
    """Injectable operational boundary; product commands are intentionally absent."""

    probe: Callable[[tuple[str, ...]], str]
    run_card: Callable[[BrowserLaunchSpec, Path], HealthProbeResult]
    verify_bundle: Callable[[PlatformProfile], BrowserBundle] = verify_browser_bundle


def run_platform_health(
    profile: PlatformProfile,
    evidence_root: Path,
    executor: PlatformHealthExecutor,
    *,
    card_path: Path = _CARD,
) -> HealthFingerprint:
    """Certify only neutral platform capabilities, returning a fail-closed result."""
    if _is_unprovisioned(profile):
        return HealthFingerprint.blocked("platform profile is deliberately unprovisioned")
    try:
        root = prepare_evidence_root(evidence_root)
        card_checksum = hashlib.sha256(card_path.read_bytes()).hexdigest()
        # These probes are fixed platform identity controls, never product/static commands.
        docker_identity = executor.probe(("docker", "--version"))
        compose_identity = executor.probe(("docker", "compose", "version"))
        bundle = executor.verify_bundle(profile)
        try:
            launch_spec = bundle.launch_spec()
            try:
                probe = executor.run_card(launch_spec, root)
            finally:
                launch_spec.close()
        finally:
            bundle.close()
        _require_neutral_metrics(probe.metrics)
        manifest_hash = write_artifacts(root, probe.artifacts)
        result = HealthFingerprint(
            outcome=Outcome.PASSED,
            profile_checksum=profile.checksum,
            card_checksum=card_checksum,
            docker_identity=docker_identity,
            compose_identity=compose_identity,
            browser_sha256=bundle.sha256,
            browser_version=probe.browser_version,
            metrics=dict(probe.metrics),
            captured_at=datetime.now(UTC).isoformat(),
            evidence_manifest_sha256=manifest_hash,
        )
        _write_fingerprint(root, result)
        return result
    except Exception as error:
        return HealthFingerprint.blocked(f"platform health failed: {error}")


def validate_fingerprint(profile: PlatformProfile, fingerprint_path: Path) -> HealthFingerprint:
    """Reject fingerprint reuse across a profile or evidence/card mutation."""
    try:
        raw = json.loads(fingerprint_path.read_text(encoding="utf-8"))
        result = HealthFingerprint(outcome=Outcome(raw.pop("outcome")), **raw)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("invalid platform health fingerprint") from error
    if result.outcome is not Outcome.PASSED:
        raise ValueError("fingerprint is not a passed health result")
    if result.profile_checksum != profile.checksum:
        raise ValueError("profile checksum drift")
    root = fingerprint_path.parent
    manifest_hash = hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest()
    if result.evidence_manifest_sha256 != manifest_hash:
        raise ValueError("evidence manifest checksum drift")
    _require_neutral_metrics(result.metrics or {})
    return result


def run_product_lane(*, health: Callable[[], HealthFingerprint], execute: Callable[[], None]) -> RunResult:
    """Single reusable gate: never invoke a product executor after health failure."""
    result = health()
    if result.outcome is not Outcome.PASSED:
        return RunResult(lane=Lane.HEALTH, outcome=Outcome.ENVIRONMENT_BLOCKED)
    execute()
    return RunResult(lane=Lane.FINAL, outcome=Outcome.PASSED, final=True)


def _is_unprovisioned(profile: PlatformProfile) -> bool:
    browser = profile.browser
    return (
        profile.version == "unprovisioned-template"
        and profile.checksum == "0" * 64
        and browser.version == "UNPROVISIONED_BROWSER_DO_NOT_LAUNCH"
        and browser.byte_size == 0
        and browser.sha256 == "0" * 64
    )


def _require_neutral_metrics(metrics: Mapping[str, Any]) -> None:
    if metrics.get("innerWidth") != 1920 or metrics.get("innerHeight") != 1080:
        raise ValueError("neutral viewport must be exactly 1920x1080")
    if metrics.get("dpr") != 1 or metrics.get("raster") != [1920, 1080]:
        raise ValueError("neutral DPR/raster metrics are invalid")


def _write_fingerprint(root: Path, fingerprint: HealthFingerprint) -> None:
    path = root / "fingerprint.json"
    path.write_text(json.dumps(fingerprint.to_dict(), sort_keys=True), encoding="utf-8")
    path.chmod(0o600)
