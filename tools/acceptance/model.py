"""Pure, immutable contracts for acceptance-run evidence."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
_GIT_REF_FORBIDDEN = frozenset(" ~^:?*[\\")


class AcceptancePhase(StrEnum):
    PREFLIGHT = "preflight"
    STATIC = "static"
    BROWSER_CARD = "browser-card"
    RUNTIME_CACHED = "runtime-cached"
    FULL = "full"


@dataclass(frozen=True)
class AcceptanceInputs:
    sha: str
    ref: str
    evidence_root: Path
    phase: AcceptancePhase = AcceptancePhase.FULL

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> AcceptanceInputs:
        sha = mapping.get("sha")
        if not isinstance(sha, str) or not _SHA_PATTERN.fullmatch(sha):
            raise ValueError("sha must be a 40-character lowercase hexadecimal value")
        ref = mapping.get("ref")
        if not isinstance(ref, str) or not _is_git_refname(ref):
            raise ValueError("ref must be a named ref")
        evidence_root = mapping.get("evidence_root")
        if not isinstance(evidence_root, (str, Path)) or not str(evidence_root):
            raise ValueError("evidence_root is required")
        phase_value = mapping.get("phase", AcceptancePhase.FULL)
        try:
            phase = AcceptancePhase(phase_value)
        except (TypeError, ValueError) as error:
            raise ValueError("phase is invalid") from error
        return cls(sha=sha, ref=ref, evidence_root=Path(evidence_root), phase=phase)


@dataclass(frozen=True)
class PhaseResult:
    phase: AcceptancePhase | str
    status: str
    final_acceptance: bool = False
    detail: str | None = None

    def validate(self) -> None:
        try:
            phase = AcceptancePhase(self.phase)
        except ValueError as error:
            raise ValueError("phase is invalid") from error
        if self.status not in {
            "passed",
            "failed",
            "infrastructure_blocker",
            "coverage_gap",
        }:
            raise ValueError("status is invalid")
        if self.final_acceptance and phase is not AcceptancePhase.FULL:
            raise ValueError(f"{phase.value} is non-final")
        if self.final_acceptance and self.status != "passed":
            raise ValueError("only a passed result can be final")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "phase": AcceptancePhase(self.phase).value,
            "status": self.status,
            "final_acceptance": self.final_acceptance,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class RunManifest:
    sha: str
    ref: str
    phase: AcceptancePhase = AcceptancePhase.FULL
    primary_result: PhaseResult | None = None
    cleanup_result: PhaseResult | None = None

    @classmethod
    def minimal(cls, sha: str, ref: str) -> RunManifest:
        return cls(
            AcceptanceInputs.from_mapping(
                {"sha": sha, "ref": ref, "evidence_root": "."}
            ).sha,
            ref,
        )

    def with_outcomes(
        self, primary_result: PhaseResult, cleanup_result: PhaseResult
    ) -> RunManifest:
        primary_result.validate()
        cleanup_result.validate()
        updated = replace(
            self, primary_result=primary_result, cleanup_result=cleanup_result
        )
        updated._validate_outcome_phases()
        return updated

    def _validate_outcome_phases(self) -> None:
        manifest_phase = AcceptancePhase(self.phase)
        for result in (self.primary_result, self.cleanup_result):
            if result is None:
                continue
            result.validate()
            if AcceptancePhase(result.phase) is not manifest_phase:
                raise ValueError("result phase must match manifest phase")

    def to_dict(self) -> dict[str, Any]:
        inputs = AcceptanceInputs.from_mapping(
            {
                "sha": self.sha,
                "ref": self.ref,
                "evidence_root": ".",
                "phase": self.phase,
            }
        )
        self._validate_outcome_phases()
        primary = self.primary_result.to_dict() if self.primary_result else None
        cleanup = self.cleanup_result.to_dict() if self.cleanup_result else None
        return {
            "sha": inputs.sha,
            "ref": inputs.ref,
            "phase": inputs.phase.value,
            "classification": _classification(inputs.phase),
            "final_acceptance": bool(primary and primary["final_acceptance"]),
            "primary_result": primary,
            "primary_status": primary["status"] if primary else None,
            "cleanup_result": cleanup,
            "cleanup_status": cleanup["status"] if cleanup else None,
        }


def _classification(phase: AcceptancePhase) -> str:
    return {
        AcceptancePhase.PREFLIGHT: "preflight_only",
        AcceptancePhase.STATIC: "static_browser_suite",
        AcceptancePhase.BROWSER_CARD: "headed_cdp_card",
        AcceptancePhase.RUNTIME_CACHED: "cached_diagnostic",
        AcceptancePhase.FULL: "final_exact_sha",
    }[phase]


def _is_git_refname(ref: str) -> bool:
    """Implement ``git check-ref-format --allow-onelevel`` refname rules."""
    if (
        not ref
        or ref == "@"
        or ref.startswith("/")
        or ref.endswith(("/", "."))
        or "//" in ref
        or ".." in ref
        or "@{" in ref
        or _SHA_PATTERN.fullmatch(ref)
        or any(
            char in _GIT_REF_FORBIDDEN or ord(char) < 0x20 or ord(char) == 0x7F
            for char in ref
        )
    ):
        return False
    return all(
        not part.startswith(".") and not part.endswith(".lock")
        for part in ref.split("/")
    )
