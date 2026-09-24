"""Immutable data models for the acceptance platform."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

_SHA = re.compile(r"[0-9a-f]{40}")
_CHECKSUM = re.compile(r"[0-9a-f]{64}")
_REF_FORBIDDEN = frozenset(" ~^:?*[\\")


class Lane(StrEnum):
    HEALTH = "health"
    STATIC = "static"
    DIAGNOSTIC = "diagnostic"
    FINAL = "final"


class Outcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ENVIRONMENT_BLOCKED = "environment_blocked"
    COVERAGE_GAP = "coverage_gap"
    DIAGNOSTIC_ONLY = "diagnostic_only"


@dataclass(frozen=True)
class StaticGroup:
    name: str
    working_directory: Path
    commands: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeControl:
    name: str
    path: str
    expected_status: int


@dataclass(frozen=True)
class ProductContract:
    name: str
    services: tuple[str, ...]
    static_groups: tuple[StaticGroup, ...]
    controls: tuple[RuntimeControl, ...]
    journey_adapter: Path
    assets: tuple[Path, ...]


@dataclass(frozen=True)
class BrowserProfile:
    store_root: Path
    executable: Path
    version: str
    byte_size: int
    sha256: str


@dataclass(frozen=True)
class PlatformProfile:
    version: str
    checksum: str
    browser: BrowserProfile

    def validate(self) -> None:
        if not self.version:
            raise ValueError("platform profile version is required")
        if not _CHECKSUM.fullmatch(self.checksum):
            raise ValueError("platform profile checksum must be a SHA-256 value")


@dataclass(frozen=True)
class RunResult:
    lane: Lane
    outcome: Outcome
    final: bool = False

    def validate(self) -> None:
        if self.final and self.lane is not Lane.FINAL:
            raise ValueError("only the final lane can claim final acceptance")
        if self.final and self.outcome is not Outcome.PASSED:
            raise ValueError("only a passed result can claim final acceptance")
        if self.lane is Lane.DIAGNOSTIC and self.outcome is Outcome.PASSED:
            raise ValueError("diagnostic results must be diagnostic_only")


@dataclass(frozen=True)
class BuildLedgerKey:
    candidate_sha: str
    profile_checksum: str
    contract_checksum: str

    def validate(self) -> None:
        validate_candidate_inputs(self.candidate_sha, "ledger")
        if not _CHECKSUM.fullmatch(self.profile_checksum):
            raise ValueError("profile checksum must be a SHA-256 value")
        if not _CHECKSUM.fullmatch(self.contract_checksum):
            raise ValueError("contract checksum must be a SHA-256 value")


def validate_candidate_inputs(sha: str, ref: str) -> tuple[str, str]:
    """Validate exact CLI candidate identity without normalizing either value."""
    if not isinstance(sha, str) or not _SHA.fullmatch(sha):
        raise ValueError("sha must be a full 40-character lowercase hexadecimal value")
    if not isinstance(ref, str) or not _is_named_ref(ref):
        raise ValueError("ref must be a named git ref")
    return sha, ref


def _is_named_ref(ref: str) -> bool:
    if (
        not ref
        or ref == "@"
        or ref.startswith("/")
        or ref.endswith(("/", "."))
        or "//" in ref
        or ".." in ref
        or "@{" in ref
        or _SHA.fullmatch(ref)
        or any(
            char in _REF_FORBIDDEN or ord(char) < 32 or ord(char) == 127 for char in ref
        )
    ):
        return False
    return all(
        not part.startswith(".") and not part.endswith(".lock")
        for part in ref.split("/")
    )
