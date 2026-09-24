"""Isolated Docker Compose execution with one final-build ledger authority."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .model import BuildLedgerKey, PlatformProfile, ProductContract, RuntimeControl

_PROJECT = re.compile(r"[a-z0-9][a-z0-9_-]{2,62}")
_PRIVATE_ENV_NAMES = frozenset({".env", ".env.local", ".env.production"})


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    output: str


class ComposeExecutor(Protocol):
    """Injectable Docker boundary; tests never need a daemon."""

    def run(self, argv: tuple[str, ...]) -> CommandResult: ...

    def inspect_image(self, tag: str) -> str | None: ...


@dataclass(frozen=True)
class SubprocessComposeExecutor:
    """Plain-output subprocess adapter with an explicit retained-output sink."""

    retain: Callable[[str], None] = lambda _: None

    def run(self, argv: tuple[str, ...]) -> CommandResult:
        process = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        output: list[str] = []
        assert process.stdout is not None
        for line in process.stdout:
            output.append(line)
            self.retain(line)
        return CommandResult(process.wait(), "".join(output))

    def inspect_image(self, tag: str) -> str | None:
        result = self.run(("docker", "image", "inspect", "--format", "{{.Id}}", tag))
        return result.output.strip() if result.returncode == 0 else None


@dataclass(frozen=True)
class TaskTopology:
    repository: Path
    project: str
    services: tuple[str, ...]
    env_file: Path
    override_path: Path
    ports: Mapping[str, int]

    @property
    def argv(self) -> tuple[str, ...]:
        return (
            "docker",
            "compose",
            "--project-name",
            self.project,
            "--env-file",
            str(self.env_file),
            "-f",
            str(self.repository / "docker-compose.yml"),
            "-f",
            str(self.override_path),
        )


@dataclass(frozen=True)
class ResolvedTopology:
    project: str
    services: tuple[str, ...]


@dataclass(frozen=True)
class BuildReconciliation:
    usable: bool
    wrapper_anomaly: bool
    image_ids: Mapping[str, str]
    reason: str = ""


class BuildLedger:
    """A filesystem O_EXCL ledger: any tuple may receive one final build attempt."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def claim(self, key: BuildLedgerKey) -> Path:
        key.validate()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self.root / f"{_key_digest(key)}.json"
        payload = json.dumps(
            {
                "candidate_sha": key.candidate_sha,
                "profile_checksum": key.profile_checksum,
                "contract_checksum": key.contract_checksum,
                "state": "claimed",
            },
            sort_keys=True,
        ).encode()
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as error:
            raise ValueError("final build already claimed for ledger tuple") from error
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        return path

    def close(self, path: Path, result: BuildReconciliation) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.update(
            state="usable" if result.usable else "closed",
            wrapper_anomaly=result.wrapper_anomaly,
            image_ids=dict(result.image_ids),
            reason=result.reason,
        )
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)


def render_task_override(
    repository: Path,
    contract: ProductContract,
    task_root: Path,
    project: str,
    ports: Mapping[str, int],
) -> TaskTopology:
    """Render isolated override solely from the tracked public example configuration."""
    _validate_project(project)
    if set(ports) != set(contract.services) or any(
        not 1 <= value <= 65535 for value in ports.values()
    ):
        raise ValueError("task ports must declare every contract service exactly once")
    example = repository / ".env.example"
    if not example.is_file():
        raise ValueError("tracked public .env.example is required")
    task_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    env_file = task_root / "compose.env"
    env_file.write_bytes(example.read_bytes())
    os.chmod(env_file, 0o600)
    override_path = task_root / "compose.acceptance.yml"
    lines = ["services:"]
    for service in contract.services:
        _validate_service(service)
        lines.extend(
            (
                f"  {service}:",
                "    container_name: null",
                "    env_file:",
                f"      - {json.dumps(str(env_file))}",
                "    ports:",
                f"      - {json.dumps(f'127.0.0.1:{ports[service]}:{_container_port(service)}')}",
            )
        )
    override_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(override_path, 0o600)
    return TaskTopology(
        repository, project, contract.services, env_file, override_path, dict(ports)
    )


def resolve_topology(
    topology: TaskTopology, contract: ProductContract, executor: ComposeExecutor
) -> ResolvedTopology:
    """Reject config inherited outside the task namespace before it can be started."""
    result = executor.run((*topology.argv, "config", "--format", "json"))
    if result.returncode:
        raise ValueError("compose config resolution failed")
    try:
        config = json.loads(result.output)
    except json.JSONDecodeError as error:
        raise ValueError("compose config was not JSON") from error
    if not isinstance(config, dict):
        raise TypeError("compose config was not an object")
    if config.get("name") not in {None, topology.project}:
        raise ValueError("resolved compose project is not task-owned")
    services = config.get("services")
    if not isinstance(services, dict) or set(services) != set(contract.services):
        raise ValueError("resolved topology contains undeclared services")
    for name, service in services.items():
        if not isinstance(service, dict):
            raise TypeError("resolved service is invalid")
        container_name = service.get("container_name")
        if container_name and not str(container_name).startswith(
            f"{topology.project}-"
        ):
            raise ValueError("resolved topology inherits a fixed container name")
        _validate_env_files(service.get("env_file"), topology.env_file)
        _validate_ports(service.get("ports"), topology.ports[name])
        _validate_dependencies(service.get("depends_on"), contract.services)
    _validate_resources(config.get("networks"), topology.project)
    _validate_resources(config.get("volumes"), topology.project)
    return ResolvedTopology(topology.project, contract.services)


def reconcile_build(
    returncode: int,
    output: str,
    tags: tuple[str, ...],
    inspect_image: Callable[[str], str | None],
) -> BuildReconciliation:
    """Allow wrapper anomalies only after complete BuildKit completion plus inspection."""
    if returncode == 0:
        ids = {tag: inspect_image(tag) for tag in tags}
        if any(not image_id for image_id in ids.values()):
            return BuildReconciliation(
                False, False, {}, "built image inspection failed"
            )
        return BuildReconciliation(
            True, False, {tag: image_id for tag, image_id in ids.items() if image_id}
        )
    ids: dict[str, str] = {}
    for tag in tags:
        if not _complete_buildkit_tag(output, tag):
            return BuildReconciliation(False, True, ids, "incomplete BuildKit export")
        image_id = inspect_image(tag)
        if not image_id:
            return BuildReconciliation(False, True, ids, "inspected image is missing")
        ids[tag] = image_id
    return BuildReconciliation(True, True, ids)


def build_final(
    topology: TaskTopology,
    profile: PlatformProfile,
    contract: ProductContract,
    key: BuildLedgerKey,
    ledger: BuildLedger,
    executor: ComposeExecutor,
) -> BuildReconciliation:
    """Claim and execute exactly one no-cache plain final build for the immutable tuple."""
    profile.validate()
    key.validate()
    if profile.checksum != key.profile_checksum:
        raise ValueError("profile checksum does not match build ledger key")
    try:
        claim = ledger.claim(key)
    except ValueError:
        return BuildReconciliation(False, False, {}, "final build already claimed")
    tags = tuple(
        f"{topology.project}-{service}:latest" for service in contract.services
    )
    result = executor.run(
        (*topology.argv, "build", "--no-cache", "--progress=plain", *contract.services)
    )
    reconciled = reconcile_build(
        result.returncode, result.output, tags, executor.inspect_image
    )
    ledger.close(claim, reconciled)
    return reconciled


def start_no_build(
    topology: TaskTopology,
    contract: ProductContract,
    executor: ComposeExecutor,
    build: BuildReconciliation | None = None,
) -> CommandResult:
    """Perform the sole task startup and never permit Compose to build."""
    if build is not None and not build.usable:
        raise ValueError("final build is not usable; startup is blocked")
    claim = topology.override_path.parent / "startup.claim"
    try:
        fd = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise ValueError("no-build startup already claimed") from error
    else:
        os.close(fd)
    result = executor.run(
        (*topology.argv, "up", "-d", "--no-build", "--wait", *contract.services)
    )
    if result.returncode:
        raise ValueError("no-build compose startup failed")
    return result


def run_controls(
    controls: tuple[RuntimeControl, ...], request: Callable[[RuntimeControl], int]
) -> None:
    """Exercise product-declared controls without extending product authority."""
    for control in controls:
        if request(control) != control.expected_status:
            raise ValueError(f"runtime control failed: {control.name}")


def cleanup_compose(topology: TaskTopology, executor: ComposeExecutor) -> CommandResult:
    """Remove task project containers/networks only; persistent volumes are retained."""
    return executor.run((*topology.argv, "down", "--remove-orphans"))


def _complete_buildkit_tag(output: str, tag: str) -> bool:
    escaped = re.escape(tag)
    qualified = rf"(?:[a-z0-9.-]+(?::\d+)?/)?(?:[a-z0-9._-]+/)?{escaped}"
    return bool(
        re.search(
            rf"exporting to image[\s\S]*?naming to {qualified}[\s\S]*?unpacking to {qualified}[\s\S]*?DONE",
            output,
        )
    )


def _validate_env_files(value: object, expected: Path) -> None:
    files = value if isinstance(value, list) else ([value] if value else [])
    for item in files:
        path = Path(str(item))
        if path.name in _PRIVATE_ENV_NAMES or path != expected:
            raise ValueError("resolved topology inherits a private environment file")


def _validate_ports(value: object, expected: int) -> None:
    ports = value if isinstance(value, list) else []
    if not ports or any(f"127.0.0.1:{expected}:" not in str(port) for port in ports):
        raise ValueError("resolved topology has inherited fixed port mappings")


def _validate_dependencies(value: object, services: tuple[str, ...]) -> None:
    if value is None:
        return
    if isinstance(value, dict) or (
        isinstance(value, list) and all(isinstance(item, str) for item in value)
    ):
        dependencies = set(value)
    else:
        raise TypeError("resolved dependencies are invalid")
    if not dependencies <= set(services):
        raise ValueError("resolved topology contains an undeclared dependency")


def _validate_resources(value: object, project: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise TypeError("resolved resources are invalid")
    for resource in value.values():
        if not isinstance(resource, dict):
            raise TypeError("resolved resource is invalid")
        name = resource.get("name")
        if name and not str(name).startswith(f"{project}-"):
            raise ValueError("resolved resource escapes task namespace")


def _container_port(service: str) -> int:
    return 80 if service == "mission-planner" else 8000


def _validate_project(project: str) -> None:
    if not _PROJECT.fullmatch(project):
        raise ValueError("compose project must be a task-safe identifier")


def _validate_service(service: str) -> None:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", service):
        raise ValueError("service name is invalid")


def _key_digest(key: BuildLedgerKey) -> str:
    value = f"{key.candidate_sha}\0{key.profile_checksum}\0{key.contract_checksum}"
    return hashlib.sha256(value.encode()).hexdigest()
