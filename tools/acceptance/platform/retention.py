"""Fail-closed retention planning and deletion for sealed acceptance evidence."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import tomllib

from .evidence import read_fingerprint_authority, read_nofollow, verify_manifest
from .model import Lane, RetentionDisposition, RetentionEntry, validate_candidate_inputs


@dataclass(frozen=True)
class RetentionPolicy:
    """The immutable retention limits approved for acceptance evidence."""

    version: int
    completed_generations_per_lane: int
    maintenance_report_count: int
    digest: str

    @classmethod
    def parse(cls, path: Path) -> RetentionPolicy:
        """Read one exact, no-follow TOML policy and bind its raw-byte digest."""
        raw = read_nofollow(path)
        try:
            values = tomllib.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
            raise ValueError("retention policy must be valid TOML") from error
        expected = {
            "version": 1,
            "completed_generations_per_lane": 3,
            "maintenance_report_count": 90,
        }
        if values != expected or any(type(values[key]) is not int for key in expected):
            raise ValueError("retention policy must match the fixed contract")
        return cls(**expected, digest=hashlib.sha256(raw).hexdigest())


@dataclass(frozen=True)
class RetentionPlan:
    root: Path
    policy: RetentionPolicy
    protected_final: RetentionEntry | None
    entries: tuple[RetentionEntry, ...]
    anomalies: tuple[str, ...]

    @property
    def has_anomalies(self) -> bool:
        return bool(self.anomalies)


@dataclass(frozen=True)
class RetentionDeletion:
    path: PurePosixPath
    sha: str
    post_action: str


@dataclass(frozen=True)
class RetentionReport:
    path: Path
    root: Path
    policy_digest: str
    started_at: str
    ended_at: str
    dispositions: tuple[RetentionEntry, ...]
    deletions: tuple[RetentionDeletion, ...]
    bytes_reclaimed: int
    post_action_verified: bool
    pruned_reports: int
    anomalies: tuple[str, ...]


_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
_SHA_LENGTH = 40
_ALLOWED_TOP_LEVEL = frozenset({lane.value for lane in Lane}) | {
    "maintenance",
    "logs",
    "ledgers",
    "tasks",
    ".retention-quarantine",
}


def canonical_root(path: Path) -> Path:
    """Return an absolute existing directory only after no-follow traversal."""
    root = Path(os.path.abspath(path))
    root_fd = _open_confined_directory(root)
    os.close(root_fd)
    return root


def safe_relative(root: Path, candidate: Path) -> PurePosixPath:
    """Validate a candidate remains within root without traversing symlinks."""
    root = canonical_root(root)
    candidate = candidate.absolute()
    try:
        relative = candidate.relative_to(root)
    except ValueError as error:
        raise ValueError("candidate escapes retention root") from error
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError("candidate escapes retention root")
    root_fd = _open_confined_directory(root)
    _walk_existing_components(root_fd, relative)
    return PurePosixPath(relative.as_posix())


def plan_retention(state_root: Path, policy: RetentionPolicy) -> RetentionPlan:
    """Classify only sealed, unambiguous evidence; anything else is retained."""
    root = canonical_root(state_root)
    entries: list[RetentionEntry] = []
    anomalies: list[str] = []
    valid: dict[Lane, list[tuple[datetime, RetentionEntry, bool]]] = {
        lane: [] for lane in Lane
    }
    auxiliary: dict[str, Path] = {}
    for child in _children(root, anomalies):
        if child.name not in _ALLOWED_TOP_LEVEL:
            anomalies.append(f"unknown nonempty parent: {child.name}")
            continue
        if child.name in {lane.value for lane in Lane}:
            lane = Lane(child.name)
            for generation in _children(child, anomalies):
                if not _is_sha(generation.name) or generation.is_symlink():
                    anomalies.append(f"invalid generation path: {generation}")
                    continue
                classified = _classify_generation(root, generation, lane)
                entries.append(classified[0])
                if classified[1] is None:
                    anomalies.append(classified[2])
                else:
                    ended, final = classified[1]
                    valid[lane].append((ended, classified[0], final))
        elif child.name in {"logs", "ledgers"} or child.name == "tasks":
            auxiliary[child.name] = child
    known = {entry.sha for generations in valid.values() for _, entry, _ in generations}
    for name, path in auxiliary.items():
        _validate_auxiliary(name, path, known, anomalies)
    protected = _protected_final(
        valid[Lane.FINAL],
        anomalies,
        final_lane_present=(root / Lane.FINAL.value).is_dir(),
    )
    if anomalies:
        return RetentionPlan(root, policy, protected, tuple(entries), tuple(anomalies))
    selected: dict[tuple[Lane, str], RetentionDisposition] = {}
    for lane, generations in valid.items():
        newest = sorted(generations, key=lambda item: item[0], reverse=True)[
            : policy.completed_generations_per_lane
        ]
        for _, entry, _ in newest:
            selected[(lane, entry.sha)] = RetentionDisposition.RETAIN
    if protected is not None:
        selected[(protected.lane, protected.sha)] = RetentionDisposition.RETAIN
    resolved = tuple(
        RetentionEntry(
            path=entry.path,
            lane=entry.lane,
            sha=entry.sha,
            disposition=selected.get(
                (entry.lane, entry.sha), RetentionDisposition.DELETE
            ),
            reason=(
                "protected final authority"
                if protected == entry
                else "newest completed generation"
            ),
            byte_size=entry.byte_size,
        )
        for entry in entries
    )
    protected = next(
        (
            entry
            for entry in resolved
            if protected and entry.sha == protected.sha and entry.lane is Lane.FINAL
        ),
        None,
    )
    return RetentionPlan(root, policy, protected, resolved, ())


def apply_retention(plan: RetentionPlan, apply: bool) -> RetentionReport:
    """Write a private report; apply mode quarantines only prevalidated entries."""
    started = _utc_now()
    deletions: list[RetentionDeletion] = []
    reclaimed = 0
    anomalies = list(plan.anomalies)
    if apply and not anomalies:
        for entry in plan.entries:
            if entry.disposition is not RetentionDisposition.DELETE:
                continue
            candidate = plan.root / Path(entry.path)
            try:
                safe_relative(plan.root, candidate)
                quarantine = _quarantine_path(plan.root)
                os.rename(candidate, quarantine)
                _delete_tree(quarantine)
                if candidate.exists() or os.path.lexists(quarantine):
                    raise ValueError("post-action absence verification failed")
                reclaimed += entry.byte_size
                deletions.append(RetentionDeletion(entry.path, entry.sha, "absent"))
            except (OSError, ValueError) as error:
                anomalies.append(f"delete failed for {entry.path}: {error}")
    planned_prunes = _valid_report_prunes(plan.root, plan.policy, include_current=True)
    if apply:
        for report in planned_prunes:
            try:
                report.unlink()
            except OSError as error:
                anomalies.append(f"report prune failed for {report.name}: {error}")
    ended = _utc_now()
    report_path = _write_report(
        plan.root,
        plan.policy,
        started,
        ended,
        plan.entries,
        deletions,
        reclaimed,
        not anomalies and all(item.post_action == "absent" for item in deletions),
        len(planned_prunes),
        tuple(anomalies),
    )
    return RetentionReport(
        report_path,
        plan.root,
        plan.policy.digest,
        started,
        ended,
        plan.entries,
        tuple(deletions),
        reclaimed,
        not anomalies and all(item.post_action == "absent" for item in deletions),
        len(planned_prunes),
        tuple(anomalies),
    )


def _classify_generation(
    root: Path, generation: Path, lane: Lane
) -> tuple[RetentionEntry, tuple[datetime, bool] | None, str]:
    path = PurePosixPath(generation.relative_to(root).as_posix())
    size = _byte_size(generation)
    fallback = RetentionEntry(
        path,
        lane,
        generation.name,
        RetentionDisposition.ANOMALY,
        "invalid sealed evidence",
        size,
    )
    try:
        safe_relative(root, generation)
        verify_manifest(generation)
        fingerprint = json.loads(read_fingerprint_authority(generation))
        manifest = json.loads(read_nofollow(generation / "runner-manifest.json"))
        if (
            not isinstance(fingerprint, dict)
            or fingerprint.get("sha") != generation.name
        ):
            raise ValueError("fingerprint SHA mismatch")
        sha, ref = validate_candidate_inputs(manifest.get("sha"), manifest.get("ref"))
        if (
            sha != generation.name
            or manifest.get("lane") != lane.value
            or not isinstance(ref, str)
        ):
            raise ValueError("runner manifest association mismatch")
        final = manifest.get("final_acceptance") is True
        if lane is Lane.FINAL and not final:
            raise ValueError("final lane must claim final acceptance")
        capture = manifest.get("capture")
        if not isinstance(capture, dict):
            raise TypeError("missing capture authority")
        ended = _parse_utc(capture.get("ended_at"))
        if manifest.get("outcome") != "passed":
            raise ValueError("incomplete runner outcome")
        return (
            RetentionEntry(
                path,
                lane,
                sha,
                RetentionDisposition.RETAIN,
                "valid sealed generation",
                size,
            ),
            (ended, final),
            "",
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        return fallback, None, f"invalid evidence {path}: {error}"


def _protected_final(
    generations: list[tuple[datetime, RetentionEntry, bool]],
    anomalies: list[str],
    *,
    final_lane_present: bool,
) -> RetentionEntry | None:
    finalists = [(ended, entry) for ended, entry, final in generations if final]
    if not finalists:
        if final_lane_present:
            anomalies.append("missing protected final authority")
        return None
    latest = max(ended for ended, _ in finalists)
    winners = [entry for ended, entry in finalists if ended == latest]
    if len(winners) != 1:
        anomalies.append("ambiguous protected final authority")
        return None
    return winners[0]


def _children(path: Path, anomalies: list[str]) -> list[Path]:
    try:
        values = list(path.iterdir())
    except OSError as error:
        anomalies.append(f"cannot inspect {path}: {error}")
        return []
    for value in values:
        if value.is_symlink():
            anomalies.append(f"symlink refused: {value}")
    return [value for value in values if not value.is_symlink()]


def _validate_auxiliary(
    name: str, path: Path, known: set[str], anomalies: list[str]
) -> None:
    """Accept only task-local auxiliary trees with an exact sealed SHA parent."""
    children = _children(path, anomalies)
    if name == "logs":
        for lane_path in children:
            if (
                lane_path.name not in {lane.value for lane in Lane}
                or not lane_path.is_dir()
            ):
                anomalies.append("unassociated logs content")
                continue
            for sha_path in _children(lane_path, anomalies):
                if not sha_path.is_dir() or sha_path.name not in known:
                    anomalies.append("unassociated logs content")
        return
    for sha_path in children:
        if not sha_path.is_dir() or sha_path.name not in known:
            anomalies.append(f"unassociated {name} content")


def _has_any_child(path: Path) -> bool:
    return any(path.iterdir())


def _is_sha(value: str) -> bool:
    return len(value) == _SHA_LENGTH and all(
        char in "0123456789abcdef" for char in value
    )


def _parse_utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TypeError("UTC capture timestamp is required")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("capture timestamp must be UTC")
    return parsed


def _byte_size(path: Path) -> int:
    total = 0
    for base, dirs, files in os.walk(path, followlinks=False):
        if any(os.path.islink(os.path.join(base, name)) for name in dirs + files):
            return 0
        total += sum(os.lstat(os.path.join(base, name)).st_size for name in files)
    return total


def _quarantine_path(root: Path) -> Path:
    directory = root / ".retention-quarantine"
    directory.mkdir(mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)
    return directory / str(uuid.uuid4())


def _delete_tree(path: Path) -> None:
    if path.is_symlink():
        raise ValueError("quarantine must not be a symlink")
    for child in path.iterdir():
        if child.is_symlink():
            raise ValueError("quarantine contains symlink")
        if child.is_dir():
            _delete_tree(child)
        else:
            child.unlink()
    path.rmdir()


def _valid_report_prunes(
    root: Path, policy: RetentionPolicy, *, include_current: bool
) -> list[Path]:
    directory = root / "maintenance" / "retention"
    if not directory.is_dir() or directory.is_symlink():
        return []
    valid: list[Path] = []
    for path in directory.iterdir():
        try:
            if path.is_symlink() or not path.is_file():
                continue
            payload = json.loads(read_nofollow(path))
            if (
                payload.get("root") == str(root)
                and payload.get("policy_digest") == policy.digest
            ):
                valid.append(path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
    limit = policy.maintenance_report_count - (1 if include_current else 0)
    return sorted(valid)[: max(0, len(valid) - limit)]


def _write_report(
    root: Path,
    policy: RetentionPolicy,
    started: str,
    ended: str,
    entries: tuple[RetentionEntry, ...],
    deletions: list[RetentionDeletion],
    reclaimed: int,
    verified: bool,
    pruned: int,
    anomalies: tuple[str, ...],
) -> Path:
    directory = root / "maintenance" / "retention"
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)
    path = directory / f"{ended.replace(':', '-')}-{uuid.uuid4()}.json"
    payload = {
        "root": str(root),
        "policy_digest": policy.digest,
        "started_at": started,
        "ended_at": ended,
        "dispositions": [
            {
                "path": str(entry.path),
                "disposition": entry.disposition.value,
                "bytes": entry.byte_size,
            }
            for entry in entries
        ],
        "deletions": [
            {"path": str(item.path), "sha": item.sha, "post_action": item.post_action}
            for item in deletions
        ],
        "bytes_reclaimed": reclaimed,
        "post_action_verified": verified,
        "pruned_reports": pruned,
        "anomalies": list(anomalies),
    }
    fd = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o700
    )
    try:
        os.write(fd, (json.dumps(payload, sort_keys=True) + "\n").encode())
        os.fchmod(fd, 0o700)
    finally:
        os.close(fd)
    return path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _open_confined_directory(path: Path) -> int:
    fd = os.open("/", _DIRECTORY_FLAGS)
    try:
        for part in path.parts[1:]:
            next_fd = os.open(part, _DIRECTORY_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = next_fd
    except OSError as error:
        os.close(fd)
        raise ValueError("retention root must be a non-symlink directory") from error
    return fd


def _walk_existing_components(root_fd: int, relative: Path) -> None:
    fd = root_fd
    try:
        parts = relative.parts
        for index, part in enumerate(parts):
            flags = _FILE_FLAGS if index == len(parts) - 1 else _DIRECTORY_FLAGS
            try:
                next_fd = os.open(part, flags, dir_fd=fd)
            except FileNotFoundError:
                if index == len(parts) - 1:
                    return
                raise ValueError("candidate has a missing parent") from None
            except OSError as error:
                raise ValueError("candidate must not traverse a symlink") from error
            if index == len(parts) - 1:
                os.close(next_fd)
            else:
                os.close(fd)
                fd = next_fd
    finally:
        os.close(fd)
