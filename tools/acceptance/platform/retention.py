"""Fail-closed retention planning and deletion for sealed acceptance evidence."""

from __future__ import annotations

import ctypes
import fcntl
import hashlib
import json
import os
import platform
import stat
import uuid
from dataclasses import dataclass, field
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


class RetentionLockUnavailable(RuntimeError):
    """A repository-owned runner already holds the state-root lease."""


@dataclass
class _RetentionLease:
    """Own the cooperative state-root flock until reporting is complete."""

    fd: int | None

    @property
    def held(self) -> bool:
        return self.fd is not None

    def release(self) -> None:
        if self.fd is None:
            return
        try:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            os.close(self.fd)
            self.fd = None


@dataclass(frozen=True)
class RetentionPlan:
    root: Path
    policy: RetentionPolicy
    protected_final: RetentionEntry | None
    entries: tuple[RetentionEntry, ...]
    anomalies: tuple[str, ...]
    _lease: _RetentionLease = field(repr=False, compare=False)

    @property
    def has_anomalies(self) -> bool:
        return bool(self.anomalies)

    def close(self) -> None:
        """Release an unused planning lease without applying retention."""
        self._lease.release()

    def __del__(self) -> None:
        self.close()


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
    planned_report_prunes: int
    anomalies: tuple[str, ...]


_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
_SHA_LENGTH = 40
_REPORT_TOOL_VERSION = "acceptance-retention-v1"
_RENAME_EXCHANGE = 0x2
_RENAMEAT2_NUMBERS = {"x86_64": 316, "aarch64": 276, "armv7l": 382}
_ALLOWED_TOP_LEVEL = frozenset({lane.value for lane in Lane}) | {
    "maintenance",
    "logs",
    "ledgers",
    "tasks",
    ".retention-quarantine",
    ".retention.lock",
}


def canonical_root(path: Path) -> Path:
    """Return an absolute existing directory only after no-follow traversal."""
    root = Path(os.path.abspath(path))
    root_fd = _open_confined_directory(root)
    os.close(root_fd)
    return root


def _acquire_lease(root: Path) -> _RetentionLease:
    """Create/open the runner-owned no-follow lock and take it without waiting."""
    root_fd = _open_confined_directory(root)
    lock_fd = None
    try:
        lock_fd = os.open(
            ".retention.lock",
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=root_fd,
        )
        identity = os.fstat(lock_fd)
        if not stat.S_ISREG(identity.st_mode):
            raise RetentionLockUnavailable("retention lock is not a regular file")
        os.fchmod(lock_fd, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RetentionLockUnavailable("retention lock is already held") from error
        lease = _RetentionLease(lock_fd)
        lock_fd = None
        return lease
    except OSError as error:
        raise RetentionLockUnavailable(
            f"cannot open retention lock: {error}"
        ) from error
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        os.close(root_fd)


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
    """Acquire the root lease, then classify sealed unambiguous evidence."""
    root = canonical_root(state_root)
    lease = _acquire_lease(root)
    try:
        return _plan_retention_locked(root, policy, lease)
    except BaseException:
        lease.release()
        raise


def _plan_retention_locked(
    root: Path, policy: RetentionPolicy, lease: _RetentionLease
) -> RetentionPlan:
    """Classify only sealed, unambiguous evidence while the lease is held."""
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
        elif child.name == "maintenance":
            _validate_maintenance(child, root, policy, anomalies)
        elif child.name == ".retention-quarantine":
            if _children(child, anomalies):
                anomalies.append(f"retained quarantine content: {child}")
    known = {entry.sha for generations in valid.values() for _, entry, _ in generations}
    for name, path in auxiliary.items():
        _validate_auxiliary(name, path, known, anomalies)
    protected = _protected_final(
        valid[Lane.FINAL],
        anomalies,
        final_lane_present=(root / Lane.FINAL.value).is_dir(),
    )
    if anomalies:
        return RetentionPlan(
            root, policy, protected, tuple(entries), tuple(anomalies), lease
        )
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
            planned_st_dev=entry.planned_st_dev,
            planned_st_ino=entry.planned_st_ino,
            planned_st_type=entry.planned_st_type,
            planned_st_mode=entry.planned_st_mode,
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
    return RetentionPlan(root, policy, protected, resolved, (), lease)


def apply_retention(plan: RetentionPlan, apply: bool) -> RetentionReport:
    """Apply one leased plan, seal its report, and then release the lease."""
    if not plan._lease.held:
        raise ValueError("retention plan no longer holds its state-root lease")
    try:
        started = _utc_now()
        deletions: list[RetentionDeletion] = []
        reclaimed = 0
        anomalies = list(plan.anomalies)
        if apply and not anomalies:
            for entry in plan.entries:
                if entry.disposition is not RetentionDisposition.DELETE:
                    continue
                try:
                    _delete_planned_entry(plan.root, entry)
                    deletions.append(RetentionDeletion(entry.path, entry.sha, "absent"))
                    reclaimed += entry.byte_size
                except _AtomicExchangeUnavailable as error:
                    anomalies.append(f"atomic exchange unavailable: {error}")
                    break
                except (OSError, ValueError) as error:
                    anomalies.append(f"retained {entry.path}: {error}")
        planned_prunes = _valid_report_prunes(
            plan.root, plan.policy, include_current=True
        )
        pruned = 0
        if apply and not anomalies:
            for report in planned_prunes:
                try:
                    _delete_planned_report(plan.root, report, plan.policy)
                    pruned += 1
                except (OSError, ValueError) as error:
                    anomalies.append(
                        f"retained maintenance report {report.name}: {error}"
                    )
        ended = _utc_now()
        verified = not anomalies and (
            not apply
            or (
                len(deletions) == _delete_count(plan.entries)
                and pruned == len(planned_prunes)
            )
        )
        report_path = _write_report(
            plan.root,
            plan.policy,
            started,
            ended,
            plan.entries,
            deletions,
            reclaimed,
            verified,
            pruned,
            len(planned_prunes),
            tuple(anomalies),
            mode="apply" if apply else "report",
            protected_final=plan.protected_final,
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
            verified,
            pruned,
            len(planned_prunes),
            tuple(anomalies),
        )
    finally:
        plan.close()


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
        fingerprint_sha, fingerprint_ref = validate_candidate_inputs(
            fingerprint.get("sha"), fingerprint.get("ref")
        )
        sha, ref = validate_candidate_inputs(manifest.get("sha"), manifest.get("ref"))
        if (
            sha != generation.name
            or manifest.get("lane") != lane.value
            or not isinstance(ref, str)
        ):
            raise ValueError("runner manifest association mismatch")
        if fingerprint_sha != sha or fingerprint_ref != ref:
            raise ValueError("fingerprint ref mismatch")
        final = manifest.get("final_acceptance") is True
        if final and lane is not Lane.FINAL:
            raise ValueError("only final lane can claim final acceptance")
        if lane is Lane.FINAL and not final:
            raise ValueError("final lane must claim final acceptance")
        capture = manifest.get("capture")
        if not isinstance(capture, dict):
            raise TypeError("missing capture authority")
        ended = _parse_utc(capture.get("ended_at"))
        if manifest.get("outcome") != "passed":
            raise ValueError("incomplete runner outcome")
        identity = os.stat(generation, follow_symlinks=False)
        if not stat.S_ISDIR(identity.st_mode):
            raise ValueError("generation must be a directory")
        return (
            RetentionEntry(
                path,
                lane,
                sha,
                RetentionDisposition.RETAIN,
                "valid sealed generation",
                size,
                identity.st_dev,
                identity.st_ino,
                stat.S_IFMT(identity.st_mode),
                stat.S_IMODE(identity.st_mode),
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


def _validate_maintenance(
    path: Path, root: Path, policy: RetentionPolicy, anomalies: list[str]
) -> None:
    """Permit only current-root, current-policy retention reports under maintenance."""
    for child in _children(path, anomalies):
        if child.name != "retention" or not child.is_dir():
            anomalies.append(f"unknown maintenance content: {child.name}")
            continue
        for report in _children(child, anomalies):
            if not report.is_file() or report.suffix != ".json":
                anomalies.append(
                    f"invalid maintenance retention content: {report.name}"
                )
                continue
            try:
                payload = json.loads(read_nofollow(report))
                _validate_report_payload(payload, root, policy)
            except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
                anomalies.append(
                    f"invalid maintenance retention report: {report.name}: {error}"
                )


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


def _report_protected_final(entry: RetentionEntry | None) -> dict[str, str] | None:
    if entry is None:
        return None
    return {
        "path": str(entry.path),
        "lane": entry.lane.value,
        "sha": entry.sha,
        "reason": entry.reason,
    }


def _validate_report_payload(payload: Any, root: Path, policy: RetentionPolicy) -> None:
    """Recognize only the complete, typed report layout emitted by this module."""
    expected_keys = {
        "root",
        "policy_digest",
        "tool_version",
        "mode",
        "started_at",
        "ended_at",
        "protected_final",
        "entries",
        "deletions",
        "totals",
        "counts",
        "post_run_verification",
        "anomalies",
    }
    if not isinstance(payload, dict) or set(payload) != expected_keys:
        raise ValueError("report schema mismatch")
    if (
        payload["root"] != str(root)
        or payload["policy_digest"] != policy.digest
        or payload["tool_version"] != _REPORT_TOOL_VERSION
        or payload["mode"] not in {"report", "apply"}
    ):
        raise ValueError("report authority mismatch")
    started, ended = _parse_utc(payload["started_at"]), _parse_utc(payload["ended_at"])
    if ended < started:
        raise ValueError("report UTC bounds are invalid")
    protected = payload["protected_final"]
    if protected is not None:
        _validate_report_entry(protected, protected=True)
    entries, deletions, anomalies = (
        payload["entries"],
        payload["deletions"],
        payload["anomalies"],
    )
    if (
        not isinstance(entries, list)
        or not isinstance(deletions, list)
        or not isinstance(anomalies, list)
    ):
        raise TypeError("report collection types are invalid")
    for item in entries:
        _validate_report_entry(item, protected=False)
    for item in deletions:
        if (
            not isinstance(item, dict)
            or set(item) != {"path", "sha", "post_action"}
            or not isinstance(item["path"], str)
            or not _is_sha(item["sha"])
            or item["post_action"] != "absent"
        ):
            raise ValueError("report deletion layout is invalid")
    if not all(isinstance(item, str) for item in anomalies):
        raise ValueError("report anomalies are invalid")
    totals, counts = payload["totals"], payload["counts"]
    if (
        not isinstance(totals, dict)
        or set(totals) != {"bytes_reclaimed"}
        or type(totals["bytes_reclaimed"]) is not int
        or totals["bytes_reclaimed"] < 0
        or not isinstance(counts, dict)
        or set(counts)
        != {
            "entries",
            "deletions",
            "anomalies",
            "pruned_reports",
            "planned_report_prunes",
        }
        or any(type(value) is not int or value < 0 for value in counts.values())
        or counts["entries"] != len(entries)
        or counts["deletions"] != len(deletions)
        or counts["anomalies"] != len(anomalies)
        or type(payload["post_run_verification"]) is not bool
    ):
        raise ValueError("report counts, totals, or verification are invalid")
    _validate_report_semantics(payload, entries, deletions, anomalies)


def _validate_report_semantics(
    payload: dict[str, Any],
    entries: list[Any],
    deletions: list[Any],
    anomalies: list[Any],
) -> None:
    """Reject typed reports whose declared facts cannot all be true together."""
    entry_by_identity: dict[tuple[str, str, str], dict[str, Any]] = {}
    for entry in entries:
        identity = (entry["path"], entry["lane"], entry["sha"])
        if identity in entry_by_identity:
            raise ValueError("report entries are duplicated")
        entry_by_identity[identity] = entry
    protected = payload["protected_final"]
    protected_entries = [
        entry for entry in entries if entry["reason"] == "protected final authority"
    ]
    if protected is None:
        if protected_entries:
            raise ValueError("report protected final is missing")
    else:
        protected_identity = (
            protected["path"],
            protected["lane"],
            protected["sha"],
        )
        if (
            len(protected_entries) != 1
            or tuple(protected_entries[0][key] for key in ("path", "lane", "sha"))
            != protected_identity
            or protected_entries[0]["disposition"] != RetentionDisposition.RETAIN.value
            or protected_entries[0]["reason"] != protected["reason"]
        ):
            raise ValueError("report protected final does not match one retained entry")
    deletion_identities: set[tuple[str, str]] = set()
    reclaimed = 0
    for deletion in deletions:
        matching = [
            entry
            for entry in entries
            if entry["path"] == deletion["path"] and entry["sha"] == deletion["sha"]
        ]
        if (
            len(matching) != 1
            or matching[0]["disposition"] != RetentionDisposition.DELETE.value
        ):
            raise ValueError("report deletion does not match a delete entry")
        identity = (deletion["path"], deletion["sha"])
        if identity in deletion_identities:
            raise ValueError("report deletions are duplicated")
        deletion_identities.add(identity)
        reclaimed += matching[0]["bytes"]
    if payload["totals"]["bytes_reclaimed"] != reclaimed:
        raise ValueError("report reclaimed bytes do not match deletions")
    delete_entries = [
        entry
        for entry in entries
        if entry["disposition"] == RetentionDisposition.DELETE.value
    ]
    if payload["mode"] == "report" and (
        deletions or reclaimed or payload["counts"]["pruned_reports"]
    ):
        raise ValueError("report-only mode claims completed mutation")
    if (
        payload["mode"] == "apply"
        and not anomalies
        and len(deletions) != len(delete_entries)
    ):
        raise ValueError("successful apply omits planned deletion reconciliation")
    if payload["counts"]["pruned_reports"] > payload["counts"]["planned_report_prunes"]:
        raise ValueError("report prunes exceed planned prunes")
    if payload["post_run_verification"] != (not anomalies):
        raise ValueError("report verification disagrees with anomalies")


def _validate_report_entry(item: Any, *, protected: bool) -> None:
    expected = {"path", "lane", "sha", "reason"}
    if not protected:
        expected |= {"disposition", "bytes"}
    if not isinstance(item, dict) or set(item) != expected:
        raise ValueError("report entry layout is invalid")
    lane, sha = item["lane"], item["sha"]
    if (
        lane not in {member.value for member in Lane}
        or not _is_sha(sha)
        or item["path"] != f"{lane}/{sha}"
        or not isinstance(item["reason"], str)
    ):
        raise ValueError("report entry authority is invalid")
    if protected:
        if lane != Lane.FINAL.value or item["reason"] != "protected final authority":
            raise ValueError("protected final report identity is invalid")
    elif (
        item["disposition"] not in {member.value for member in RetentionDisposition}
        or type(item["bytes"]) is not int
        or item["bytes"] < 0
    ):
        raise ValueError("report entry values are invalid")


def _byte_size(path: Path) -> int:
    total = 0
    for base, dirs, files in os.walk(path, followlinks=False):
        if any(os.path.islink(os.path.join(base, name)) for name in dirs + files):
            return 0
        total += sum(os.lstat(os.path.join(base, name)).st_size for name in files)
    return total


class _AtomicExchangeUnavailable(RuntimeError):
    """The host cannot provide the required atomic renameat2 exchange."""


def _renameat2_exchange(
    old_dir_fd: int, old_name: str, new_dir_fd: int, new_name: str
) -> None:
    """Call Linux renameat2(RENAME_EXCHANGE) without a third-party dependency."""
    number = _RENAMEAT2_NUMBERS.get(platform.machine().lower())
    if os.name != "posix" or number is None:
        raise _AtomicExchangeUnavailable("renameat2 is unsupported on this host")
    libc = ctypes.CDLL(None, use_errno=True)
    result = libc.syscall(
        number,
        old_dir_fd,
        os.fsencode(old_name),
        new_dir_fd,
        os.fsencode(new_name),
        _RENAME_EXCHANGE,
    )
    if result != 0:
        error = ctypes.get_errno()
        if error in {38, 22, 95}:
            raise _AtomicExchangeUnavailable(os.strerror(error))
        raise OSError(error, os.strerror(error))


def _after_exchange(_quarantined: Path, _entry: RetentionEntry) -> None:
    """Deterministic test seam after exchange and before identity inspection."""


def _delete_planned_entry(root: Path, entry: RetentionEntry) -> None:
    """Exchange the mutable source with an empty sentinel before deleting it."""
    root_fd = _open_confined_directory(root)
    lane_fd = quarantine_fd = None
    sentinel = str(uuid.uuid4())
    quarantine_path = root / ".retention-quarantine" / sentinel
    try:
        lane_fd = os.open(entry.lane.value, _DIRECTORY_FLAGS, dir_fd=root_fd)
        quarantine_fd = _mkdir_open(".retention-quarantine", root_fd)
        os.mkdir(sentinel, 0o700, dir_fd=quarantine_fd)
        _renameat2_exchange(lane_fd, entry.sha, quarantine_fd, sentinel)
        _after_exchange(quarantine_path, entry)
        quarantined = os.stat(sentinel, dir_fd=quarantine_fd, follow_symlinks=False)
        if not _matches_planned_identity(quarantined, entry):
            _renameat2_exchange(lane_fd, entry.sha, quarantine_fd, sentinel)
            raise ValueError("atomic exchange identity mismatch; replacement restored")
        _remove_tree_at(quarantine_fd, sentinel)
        os.rmdir(entry.sha, dir_fd=lane_fd)
        _assert_absent(lane_fd, entry.sha)
        _assert_absent(quarantine_fd, sentinel)
    finally:
        for fd in (quarantine_fd, lane_fd, root_fd):
            if fd is not None:
                os.close(fd)


def _matches_planned_identity(identity: os.stat_result, entry: RetentionEntry) -> bool:
    return (
        identity.st_dev == entry.planned_st_dev
        and identity.st_ino == entry.planned_st_ino
        and stat.S_IFMT(identity.st_mode) == entry.planned_st_type
        and stat.S_IMODE(identity.st_mode) == entry.planned_st_mode
    )


def _remove_tree_at(parent_fd: int, name: str) -> None:
    directory_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
    try:
        for child in os.scandir(directory_fd):
            if child.is_dir(follow_symlinks=False):
                _remove_tree_at(directory_fd, child.name)
            else:
                os.unlink(child.name, dir_fd=directory_fd)
    finally:
        os.close(directory_fd)
    os.rmdir(name, dir_fd=parent_fd)


def _assert_absent(parent_fd: int, name: str) -> None:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    raise ValueError("post-action path remains present")


def _delete_count(entries: tuple[RetentionEntry, ...]) -> int:
    return sum(entry.disposition is RetentionDisposition.DELETE for entry in entries)


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
            _validate_report_payload(payload, root, policy)
            valid.append(path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
    limit = policy.maintenance_report_count - (1 if include_current else 0)
    return sorted(valid)[: max(0, len(valid) - limit)]


def _delete_planned_report(root: Path, report: Path, policy: RetentionPolicy) -> None:
    """Revalidate and remove one regular, root-confined maintenance report."""
    if report.parent != root / "maintenance" / "retention":
        raise ValueError("maintenance report escapes retention root")
    root_fd = _open_confined_directory(root)
    maintenance_fd = retention_fd = report_fd = None
    try:
        maintenance_fd = os.open("maintenance", _DIRECTORY_FLAGS, dir_fd=root_fd)
        retention_fd = os.open("retention", _DIRECTORY_FLAGS, dir_fd=maintenance_fd)
        report_fd = os.open(report.name, _FILE_FLAGS, dir_fd=retention_fd)
        if not stat.S_ISREG(os.fstat(report_fd).st_mode):
            raise ValueError("maintenance report is not regular")
        payload = json.loads(os.read(report_fd, 10_000_000))
        _validate_report_payload(payload, root, policy)
        os.unlink(report.name, dir_fd=retention_fd)
        _assert_absent(retention_fd, report.name)
    finally:
        for fd in (report_fd, retention_fd, maintenance_fd, root_fd):
            if fd is not None:
                os.close(fd)


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
    planned_prunes: int,
    anomalies: tuple[str, ...],
    *,
    mode: str,
    protected_final: RetentionEntry | None,
) -> Path:
    root_fd = _open_confined_directory(root)
    maintenance_fd = retention_fd = None
    try:
        maintenance_fd = _mkdir_open("maintenance", root_fd)
        retention_fd = _mkdir_open("retention", maintenance_fd)
        name = f"{ended.replace(':', '-')}-{uuid.uuid4()}.json"
        path = root / "maintenance" / "retention" / name
        payload = {
            "root": str(root),
            "policy_digest": policy.digest,
            "tool_version": _REPORT_TOOL_VERSION,
            "mode": mode,
            "started_at": started,
            "ended_at": ended,
            "protected_final": _report_protected_final(protected_final),
            "entries": [
                {
                    "path": str(entry.path),
                    "lane": entry.lane.value,
                    "sha": entry.sha,
                    "disposition": entry.disposition.value,
                    "reason": entry.reason,
                    "bytes": entry.byte_size,
                }
                for entry in entries
            ],
            "deletions": [
                {
                    "path": str(item.path),
                    "sha": item.sha,
                    "post_action": item.post_action,
                }
                for item in deletions
            ],
            "totals": {"bytes_reclaimed": reclaimed},
            "counts": {
                "entries": len(entries),
                "deletions": len(deletions),
                "anomalies": len(anomalies),
                "pruned_reports": pruned,
                "planned_report_prunes": planned_prunes,
            },
            "post_run_verification": verified,
            "anomalies": list(anomalies),
        }
        fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o700,
            dir_fd=retention_fd,
        )
        try:
            os.write(fd, (json.dumps(payload, sort_keys=True) + "\n").encode())
            os.fchmod(fd, 0o700)
        finally:
            os.close(fd)
        return path
    finally:
        for fd in (retention_fd, maintenance_fd, root_fd):
            if fd is not None:
                os.close(fd)


def _mkdir_open(name: str, parent_fd: int) -> int:
    try:
        os.mkdir(name, 0o700, dir_fd=parent_fd)
    except FileExistsError:
        pass
    directory_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
    os.fchmod(directory_fd, 0o700)
    return directory_fd


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
