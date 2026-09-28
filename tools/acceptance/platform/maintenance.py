"""Repository-owned maintenance commands for acceptance evidence."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import NoReturn, Protocol

from .compose import AcceptanceOwnershipLabels
from .model import Lane, validate_candidate_inputs
from .retention import (
    RetentionLockUnavailable,
    RetentionPolicy,
    apply_retention,
    canonical_root,
    plan_retention,
)


class _JsonArgumentParser(argparse.ArgumentParser):
    """Convert parser and validation failures into the maintenance JSON contract."""

    def error(self, message: str) -> NoReturn:
        raise ValueError(f"invalid arguments: {message}")

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        if status == 2:
            raise ValueError(message.strip() if message else "invalid arguments")
        super().exit(status, message)


@dataclass(frozen=True)
class CheckoutRecoveryReport:
    removed: tuple[Path, ...]
    anomalies: tuple[str, ...]

    @property
    def has_anomalies(self) -> bool:
        return bool(self.anomalies)


@dataclass(frozen=True)
class DockerResource:
    kind: str
    identifier: str


class DockerCommand(Protocol):
    def run(self, argv: tuple[str, ...]) -> str: ...


@dataclass(frozen=True)
class DockerImage:
    """A listed image and its exact post-list inspection identity."""

    identifier: str
    inspected_id: str
    labels: dict[str, str]
    container_references: tuple[str, ...] = ()
    ledger_references: tuple[str, ...] = ()


class DockerRetentionDocker(Protocol):
    def list_images(self) -> tuple[DockerImage, ...]: ...

    def inspect_image(self, identifier: str) -> DockerImage | None: ...

    def remove_image(self, inspected_id: str) -> None: ...


@dataclass(frozen=True)
class DockerRetentionReport:
    removed: tuple[str, ...]
    anomalies: tuple[str, ...]

    @property
    def has_anomalies(self) -> bool:
        return bool(self.anomalies)


def remove_scoped_docker_resource(
    docker: DockerRetentionDocker,
    image: DockerImage,
    eligible_shas: set[str],
    *,
    apply: bool,
) -> str | None:
    """Remove only an unchanged, fully-owned, unreferenced inspected image ID."""
    inspected = docker.inspect_image(image.identifier)
    if inspected is None or inspected.inspected_id != image.inspected_id:
        return f"retained image {image.identifier}: exact inspected ID is unavailable"
    labels = inspected.labels
    required = {
        "io.starlink.acceptance.owner",
        "io.starlink.acceptance.lane",
        "io.starlink.acceptance.sha",
        "io.starlink.acceptance.task",
    }
    ownership_labels = {
        key: value
        for key, value in labels.items()
        if key.startswith("io.starlink.acceptance.")
    }
    if (
        ownership_labels != {key: labels[key] for key in required}
        or labels.get("io.starlink.acceptance.owner") != "runner"
        or not all(labels.get(key) for key in required)
        or labels.get("io.starlink.acceptance.sha") not in eligible_shas
        or labels != image.labels
    ):
        return f"retained image {image.identifier}: ownership labels are not eligible"
    if inspected.container_references or inspected.ledger_references:
        return (
            f"retained image {image.identifier}: container or ledger reference remains"
        )
    if not apply:
        return None
    docker.remove_image(inspected.inspected_id)
    remaining = docker.inspect_image(image.identifier)
    if remaining is not None and remaining.inspected_id == inspected.inspected_id:
        return f"retained image {image.identifier}: exact ID remains after removal"
    return None


def retain_docker_resources(
    docker: DockerRetentionDocker, eligible_shas: set[str], *, apply: bool
) -> DockerRetentionReport:
    """Apply eligibility only to exact inspected images; volumes remain inventory-only."""
    removed: list[str] = []
    anomalies: list[str] = []
    for image in docker.list_images():
        anomaly = remove_scoped_docker_resource(
            docker, image, eligible_shas, apply=apply
        )
        if anomaly:
            anomalies.append(anomaly)
        elif apply:
            removed.append(image.inspected_id)
    return DockerRetentionReport(tuple(removed), tuple(anomalies))


def scoped_docker_inventory(
    docker: DockerCommand, labels: AcceptanceOwnershipLabels
) -> tuple[DockerResource, ...]:
    """List, but never prune, only resources with the full runner label set."""
    filters = tuple(
        item
        for label in labels.as_docker_args()
        for item in ("--filter", f"label={label}")
    )
    resources: list[DockerResource] = []
    for kind, argv in (
        ("container", ("docker", "ps", "-aq", *filters)),
        ("image", ("docker", "image", "ls", "-q", *filters)),
        ("network", ("docker", "network", "ls", "-q", *filters)),
        # Volumes are retained for evidence inspection; inventory is intentionally read-only.
        ("volume", ("docker", "volume", "ls", "-q", *filters)),
    ):
        resources.extend(
            DockerResource(kind, identifier)
            for identifier in docker.run(argv).splitlines()
            if identifier
        )
    return tuple(resources)


def _read_marker(path: Path) -> dict[str, str]:
    identity = os.lstat(path)
    if not stat.S_ISREG(identity.st_mode) or stat.S_IMODE(identity.st_mode) != 0o600:
        raise ValueError("ownership marker must be a regular mode-0600 file")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        payload = json.loads(os.read(fd, 16 * 1024))
    finally:
        os.close(fd)
    required = {"lane", "sha", "ref", "task", "creator", "time"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError("ownership marker fields are invalid")
    if not all(isinstance(payload[name], str) and payload[name] for name in required):
        raise ValueError("ownership marker values are invalid")
    sha, ref = validate_candidate_inputs(payload["sha"], payload["ref"])
    if payload["lane"] not in {lane.value for lane in Lane}:
        raise ValueError("ownership marker lane is invalid")
    if not payload["creator"].startswith("acceptance-runner-"):
        raise ValueError("ownership marker creator is invalid")
    parsed = datetime.fromisoformat(payload["time"])
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("ownership marker time is invalid")
    return {**payload, "sha": sha, "ref": ref}


def _git(checkout: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(checkout), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _task_is_live(task: str) -> bool:
    """Treat only an exact repository task label as runner liveness."""
    proc = Path("/proc")
    for entry in proc.iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            arguments = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if f"--acceptance-task={task}".encode() in arguments:
            return True
    return False


def _validate_checkout(checkout: Path, marker: dict[str, str]) -> None:
    if _task_is_live(marker["task"]):
        raise ValueError("task-labelled process is still live")
    if _git(checkout, "symbolic-ref", "-q", "HEAD").returncode == 0:
        raise ValueError("checkout is not detached")
    head = _git(checkout, "rev-parse", "HEAD")
    if head.returncode or head.stdout.strip() != marker["sha"]:
        raise ValueError("checkout HEAD does not match marker SHA")
    status = _git(
        checkout,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        ".",
        ":(exclude).acceptance-runner-owner.json",
    )
    if status.returncode or status.stdout:
        raise ValueError("checkout is not clean")


def validate_runner_checkout(
    root: Path, checkout: Path, *, lane: str, sha: str, ref: str, task: str
) -> None:
    """Validate the exact runner-owned checkout before wrapper deletion."""
    checkout_root = canonical_root(root)
    candidate = Path(os.path.abspath(checkout))
    if candidate.parent != checkout_root:
        raise ValueError("checkout escapes configured root")
    identity = os.lstat(candidate)
    if not stat.S_ISDIR(identity.st_mode):
        raise ValueError("checkout is not a regular directory")
    marker = _read_marker(candidate / ".acceptance-runner-owner.json")
    if marker != {
        "lane": lane,
        "sha": sha,
        "ref": ref,
        "task": task,
        "creator": "acceptance-runner-v1",
        "time": marker["time"],
    }:
        raise ValueError("ownership marker does not match this runner")
    _validate_checkout(candidate, marker)


def _remove_checkout(checkout: Path) -> None:
    git_metadata = checkout / ".git"
    identity = os.lstat(git_metadata)
    if stat.S_ISDIR(identity.st_mode):
        shutil.rmtree(checkout)
        return
    if not stat.S_ISREG(identity.st_mode):
        raise ValueError("checkout Git metadata is invalid")
    common = _git(checkout, "rev-parse", "--git-common-dir")
    if common.returncode or not common.stdout.strip():
        raise ValueError("checkout Git common directory is unavailable")
    subprocess.run(
        [
            "git",
            f"--git-dir={common.stdout.strip()}",
            "worktree",
            "remove",
            "--force",
            str(checkout),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def recover_abandoned_checkouts(
    root: Path, policy: RetentionPolicy
) -> CheckoutRecoveryReport:
    """Remove only fully validated, interrupted runner-owned checkouts."""
    del policy  # The fixed policy type makes this API consistent with retention.
    checkout_root = canonical_root(root)
    removed: list[Path] = []
    anomalies: list[str] = []
    for checkout in checkout_root.iterdir():
        marker_path = checkout / ".acceptance-runner-owner.json"
        try:
            os.lstat(marker_path)
        except FileNotFoundError:
            anomalies.append(
                f"retained checkout {checkout.name}: ownership marker is missing"
            )
            continue
        except OSError as error:
            anomalies.append(f"retained checkout {checkout.name}: {error}")
            continue
        try:
            identity = os.lstat(checkout)
            if not stat.S_ISDIR(identity.st_mode):
                raise ValueError("checkout is not a regular directory")
            marker = _read_marker(marker_path)
            _validate_checkout(checkout, marker)
            _remove_checkout(checkout)
            if checkout.exists():
                raise ValueError("checkout remains after removal")
            removed.append(checkout)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            anomalies.append(f"retained checkout {checkout.name}: {error}")
    return CheckoutRecoveryReport(tuple(removed), tuple(anomalies))


def _parse(argv: Sequence[str]) -> argparse.Namespace:
    parser = _JsonArgumentParser(description=__doc__)
    commands = parser.add_subparsers(
        dest="command", required=True, parser_class=_JsonArgumentParser
    )
    retention = commands.add_parser("retention")
    retention.add_argument("--state-root", type=Path, required=True)
    retention.add_argument("--policy", type=Path, required=True)
    retention.add_argument("--apply", action="store_true")
    retention.add_argument("--checkout-root", type=Path)
    return parser.parse_args(list(argv))


def _retention(argv: argparse.Namespace) -> int:
    policy = RetentionPolicy.parse(argv.policy)
    try:
        plan = plan_retention(argv.state_root, policy)
    except RetentionLockUnavailable as error:
        print(
            json.dumps(
                {"anomalies": [str(error)], "mode": "apply" if argv.apply else "report"}
            )
        )
        return 1
    checkout_anomalies: tuple[str, ...] = ()
    if argv.checkout_root is not None:
        try:
            checkout_anomalies = recover_abandoned_checkouts(
                argv.checkout_root, policy
            ).anomalies
        except (OSError, ValueError) as error:
            checkout_anomalies = (f"checkout recovery unavailable: {error}",)
    report = apply_retention(plan, apply=argv.apply)
    payload = json.loads(report.path.read_text(encoding="utf-8"))
    if checkout_anomalies:
        payload["checkout_anomalies"] = list(checkout_anomalies)
    print(json.dumps(payload, sort_keys=True))
    return 1 if report.anomalies or checkout_anomalies else 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parsed = _parse(sys.argv[1:] if argv is None else argv)
        if parsed.command == "retention":
            return _retention(parsed)
    except ValueError as error:
        print(json.dumps({"error": str(error)}, sort_keys=True))
        return 2
    raise AssertionError("unreachable command")


if __name__ == "__main__":
    raise SystemExit(main())
