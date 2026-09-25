"""Fail-closed isolated Docker Compose build and runtime boundary."""

from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

import yaml

from .model import BuildLedgerKey, PlatformProfile, ProductContract, RuntimeControl

_PROJECT = re.compile(r"[a-z0-9][a-z0-9_-]{2,62}")
_PRIVATE_ENV_NAMES = frozenset({".env", ".env.local", ".env.production"})
_STAGE = re.compile(r"^#(?P<stage>\d+) (?P<message>.*)$")
_NO_BUILD_START_TIMEOUT_SECONDS = 120.0
_FINAL_BUILD_STALL_SECONDS = 600.0
_FINAL_BUILD_HARD_DEADLINE_SECONDS = 1800.0
_FINAL_BUILD_TERMINATE_GRACE_SECONDS = 5.0
_MAX_COMPOSE_DIAGNOSTIC_BYTES = 256 * 1024
_REDACT_COMPOSE_CREDENTIAL = re.compile(
    r"(?i)(token|password|passwd|secret|api[_-]?key)\s*([=:])\s*[^\s]+"
)
_REDACT_COMPOSE_AUTHORIZATION = re.compile(r"(?im)(authorization\s*[:=])\s*[^\r\n]*")
_COMPOSE_OUTPUT_TRUNCATED = b"\n[platform retained Compose output truncated]\n"
_TRANSFER_BYTES = re.compile(
    r"transferring [^:]+:\s*(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>B|kB|KB|MB|GB|TB)\b",
    re.IGNORECASE,
)
_RUN_STATUS_FRAME = re.compile(
    r"^\d+(?:\.\d+)?s\s+(?:\[[^\]]+\]\s+)?(?:[/\\|\-]\s+)?"
    r"(?:running|run\b|waiting|building|exporting|loading|resolving)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class BuildProgressEvent:
    kind: Literal["stage", "done", "bytes", "run_output"]
    elapsed_seconds: float
    detail: str


class BuildSupervisionFailure(RuntimeError):
    def __init__(
        self,
        kind: Literal["build_stalled", "build_deadline_exceeded"],
        last_event: BuildProgressEvent | None,
        output: str,
    ) -> None:
        super().__init__(kind)
        self.kind = kind
        self.last_event = last_event
        self.output = output


class BuildProgressMonitor:
    """Classify BuildKit output so incidental activity cannot mask a stalled build."""

    def __init__(self, monotonic: Callable[[], float] = time.monotonic) -> None:
        self._monotonic = monotonic
        self._started = monotonic()
        self._last_event: BuildProgressEvent | None = None
        self._stages: set[str] = set()
        self._done_stages: set[str] = set()
        self._transfer_bytes: dict[str, float] = {}
        self._run_stages: set[str] = set()
        self._run_output: set[tuple[str, str]] = set()

    @property
    def last_event(self) -> BuildProgressEvent | None:
        return self._last_event

    def observe(self, output: str) -> BuildProgressEvent | None:
        event: BuildProgressEvent | None = None
        for line in output.splitlines():
            observed = self._observe_line(line)
            if observed is not None:
                event = observed
        return event

    def check(self, output: str = "") -> None:
        elapsed = self._monotonic() - self._started
        if elapsed >= _FINAL_BUILD_HARD_DEADLINE_SECONDS:
            raise BuildSupervisionFailure(
                "build_deadline_exceeded", self._last_event, output
            )
        reference = self._last_event.elapsed_seconds if self._last_event else 0.0
        if elapsed - reference >= _FINAL_BUILD_STALL_SECONDS:
            raise BuildSupervisionFailure("build_stalled", self._last_event, output)

    def _observe_line(self, line: str) -> BuildProgressEvent | None:
        match = _STAGE.match(line)
        if not match:
            return None
        stage, message = match["stage"], match["message"].strip()
        elapsed = self._monotonic() - self._started
        if message.startswith("DONE") and stage not in self._done_stages:
            self._done_stages.add(stage)
            return self._record("done", elapsed, line)
        transfer = _TRANSFER_BYTES.search(message)
        if transfer:
            value = float(transfer["amount"]) * _byte_multiplier(transfer["unit"])
            if value > self._transfer_bytes.get(stage, -1.0):
                self._transfer_bytes[stage] = value
                return self._record("bytes", elapsed, line)
            return None
        if stage not in self._stages:
            self._stages.add(stage)
            if " RUN " in f" {message} ":
                self._run_stages.add(stage)
                self._run_output.add((stage, message))
            return self._record("stage", elapsed, line)
        if (
            stage in self._run_stages
            and message
            and "warning" not in message.lower()
            and message != _COMPOSE_OUTPUT_TRUNCATED.decode().strip()
            and not _RUN_STATUS_FRAME.match(message)
            and (stage, message) not in self._run_output
        ):
            self._run_output.add((stage, message))
            return self._record("run_output", elapsed, line)
        return None

    def _record(
        self,
        kind: Literal["stage", "done", "bytes", "run_output"],
        elapsed: float,
        detail: str,
    ) -> BuildProgressEvent:
        self._last_event = BuildProgressEvent(kind, elapsed, detail.rstrip())
        return self._last_event


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    output: str


class BoundedComposeDiagnostics:
    """Retain bounded, credential-redacted final Compose diagnostics."""

    def __init__(self, max_bytes: int = _MAX_COMPOSE_DIAGNOSTIC_BYTES) -> None:
        if max_bytes < 0:
            raise ValueError("compose diagnostic budget cannot be negative")
        self._max_bytes = max_bytes
        self._output = bytearray()
        self._truncated = False

    def retain(self, line: str) -> None:
        if self._truncated:
            return
        redacted = _REDACT_COMPOSE_AUTHORIZATION.sub(r"\1<redacted>", line)
        redacted = _REDACT_COMPOSE_CREDENTIAL.sub(r"\1\2<redacted>", redacted).encode(
            errors="replace"
        )
        if len(self._output) + len(redacted) <= self._max_bytes:
            self._output.extend(redacted)
            return
        sentinel = _COMPOSE_OUTPUT_TRUNCATED[: self._max_bytes]
        remaining = self._max_bytes - len(sentinel)
        if len(self._output) > remaining:
            del self._output[remaining:]
        remaining -= len(self._output)
        if remaining > 0:
            self._output.extend(redacted[:remaining])
        self._output.extend(sentinel)
        self._truncated = True

    @property
    def output(self) -> bytes:
        return bytes(self._output)


class ComposeExecutor(Protocol):
    def run(
        self, argv: tuple[str, ...], *, timeout_seconds: float | None = None
    ) -> CommandResult: ...

    def inspect_image(self, tag: str) -> str | None: ...


@dataclass(frozen=True)
class SubprocessComposeExecutor:
    retain: Callable[[str], None] = lambda _: None

    def run(
        self, argv: tuple[str, ...], *, timeout_seconds: float | None = None
    ) -> CommandResult:
        if "build" in argv and "--progress=plain" in argv:
            return self._run_final_build(argv)
        process = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        )
        try:
            output, _ = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as error:
            process.terminate()
            try:
                output, _ = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                output, _ = process.communicate()
            self._retain_output(output)
            raise subprocess.TimeoutExpired(
                argv, timeout_seconds, output=output
            ) from error
        self._retain_output(output)
        return CommandResult(process.returncode, output)

    def _run_final_build(self, argv: tuple[str, ...]) -> CommandResult:
        process = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        assert process.stdout is not None
        lines: queue.Queue[str | None] = queue.Queue()
        reader = threading.Thread(
            target=_read_compose_stream, args=(process.stdout, lines)
        )
        reader.start()
        monitor = BuildProgressMonitor()
        diagnostics = BoundedComposeDiagnostics()
        output: list[str] = []
        stream_closed = False
        try:
            while not (stream_closed and process.poll() is not None):
                try:
                    line = lines.get(timeout=0.1)
                except queue.Empty:
                    monitor.check(diagnostics.output.decode(errors="replace"))
                    continue
                if line is None:
                    stream_closed = True
                    continue
                _retain_stream_line(line, output, diagnostics, self.retain)
                monitor.observe(line)
                monitor.check(diagnostics.output.decode(errors="replace"))
        except BuildSupervisionFailure as error:
            _terminate_process_group(process)
            _drain_compose_stream(lines, reader, output, diagnostics, self.retain)
            raise BuildSupervisionFailure(
                error.kind,
                error.last_event,
                diagnostics.output.decode(errors="replace"),
            ) from error
        reader.join()
        returncode = process.wait()
        return CommandResult(returncode, "".join(output))

    def _retain_output(self, output: str) -> None:
        for line in output.splitlines(keepends=True):
            self.retain(line)

    def inspect_image(self, tag: str) -> str | None:
        result = self.run(("docker", "image", "inspect", "--format", "{{.Id}}", tag))
        return result.output.strip() if result.returncode == 0 else None


@dataclass(frozen=True)
class TaskTopology:
    repository: Path
    project: str
    candidate_sha: str
    services: tuple[str, ...]
    env_file: Path
    override_path: Path
    root_override_path: Path
    validation_path: Path
    ports: Mapping[str, int]

    @property
    def argv(self) -> tuple[str, ...]:
        """The final, self-contained two-service Compose configuration only."""
        return (
            "docker",
            "compose",
            "--project-name",
            self.project,
            "--env-file",
            str(self.env_file),
            "-f",
            str(self.override_path),
        )

    @property
    def root_argv(self) -> tuple[str, ...]:
        """Read-only root topology extraction using public input only."""
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
            str(self.root_override_path),
        )


@dataclass(frozen=True)
class ResolvedTopology:
    project: str
    services: tuple[str, ...]
    digest: str


@dataclass(frozen=True)
class BuildReconciliation:
    usable: bool
    wrapper_anomaly: bool
    image_ids: Mapping[str, str]
    reason: str = ""
    supervision: Mapping[str, object] = field(default_factory=dict)


class BuildLedger:
    """O_EXCL ledger: one final build and one no-build startup per immutable tuple."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def claim(self, key: BuildLedgerKey) -> Path:
        key.validate()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self.path_for(key)
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

    def path_for(self, key: BuildLedgerKey) -> Path:
        return self.root / f"{_key_digest(key)}.json"

    def close(
        self, path: Path, result: BuildReconciliation, topology_digest: str
    ) -> None:
        payload = self.read_path(path)
        payload.update(
            state="usable" if result.usable else "closed",
            wrapper_anomaly=result.wrapper_anomaly,
            image_ids=dict(result.image_ids),
            reason=result.reason,
            supervision=dict(result.supervision),
            topology_digest=topology_digest,
        )
        _atomic_json(path, payload)

    def read(self, key: BuildLedgerKey) -> dict[str, object]:
        path = self.path_for(key)
        if not path.is_file():
            raise ValueError("final build ledger is not usable")
        return self.read_path(path)

    @staticmethod
    def read_path(path: Path) -> dict[str, object]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("build ledger record is invalid") from error
        if not isinstance(data, dict):
            raise TypeError("build ledger record is invalid")
        return data


def render_task_override(
    repository: Path,
    contract: ProductContract,
    task_root: Path,
    project: str,
    ports: Mapping[str, int],
    *,
    candidate_sha: str,
) -> TaskTopology:
    """Prepare public input and a root env replacement; final config is rendered on resolve."""
    _validate_project(project)
    _validate_candidate_sha(candidate_sha)
    if set(ports) != set(contract.services) or any(
        not 1 <= value <= 65535 for value in ports.values()
    ):
        raise ValueError("task ports must declare every contract service exactly once")
    example = repository / ".env.example"
    root = repository / "docker-compose.yml"
    if not example.is_file() or not root.is_file():
        raise ValueError(
            "tracked public .env.example and root docker-compose.yml are required"
        )
    task_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    env_file = task_root / "compose.env"
    env_file.write_bytes(example.read_bytes())
    os.chmod(env_file, 0o600)
    root_override_path = task_root / "compose.root-public-env.yml"
    root_override_path.write_text(
        _public_env_replacement(root, env_file), encoding="utf-8"
    )
    os.chmod(root_override_path, 0o600)
    override_path = task_root / "compose.acceptance.json"
    validation_path = task_root / "topology.validated.json"
    return TaskTopology(
        repository,
        project,
        candidate_sha,
        contract.services,
        env_file,
        override_path,
        root_override_path,
        validation_path,
        dict(ports),
    )


def resolve_topology(
    topology: TaskTopology, contract: ProductContract, executor: ComposeExecutor
) -> ResolvedTopology:
    """Extract a real root config without private .env, then seal a two-service config."""
    result = executor.run((*topology.root_argv, "config", "--format", "json"))
    if result.returncode:
        raise ValueError("compose config resolution failed")
    config = _json_config(result.output)
    services = config.get("services")
    if not isinstance(services, dict) or not set(contract.services) <= set(services):
        raise ValueError("root topology omits a contract service")
    final: dict[str, object] = {"name": topology.project, "services": {}}
    selected = final["services"]
    assert isinstance(selected, dict)
    for name in contract.services:
        service = services[name]
        if not isinstance(service, dict):
            raise TypeError("resolved service is invalid")
        isolated = _isolated_service(service, topology, name)
        _bind_candidate_build(isolated, topology.candidate_sha)
        selected[name] = isolated
    _allocate_task_resources(final, topology)
    _validate_final_config(final, topology, contract)
    encoded = json.dumps(final, sort_keys=True, indent=2) + "\n"
    topology.override_path.write_text(encoded, encoding="utf-8")
    os.chmod(topology.override_path, 0o600)
    final_result = executor.run((*topology.argv, "config", "--format", "json"))
    if final_result.returncode:
        raise ValueError("final task compose config resolution failed")
    _validate_final_config(_json_config(final_result.output), topology, contract)
    digest = _sha256(encoded.encode())
    _atomic_json(
        topology.validation_path,
        {
            "project": topology.project,
            "services": list(contract.services),
            "contract_checksum": contract.checksum,
            "digest": digest,
        },
    )
    return ResolvedTopology(topology.project, contract.services, digest)


def reconcile_build(
    returncode: int,
    output: str,
    tags: tuple[str, ...],
    inspect_image: Callable[[str], str | None],
) -> BuildReconciliation:
    """A nonzero wrapper is usable only after tag-local BuildKit completion and inspection."""
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
    profile.validate()
    key.validate()
    if profile.checksum != key.profile_checksum:
        raise ValueError("profile checksum does not match build ledger key")
    _validate_contract_checksum(contract, key)
    if topology.candidate_sha != key.candidate_sha:
        raise ValueError("topology candidate SHA does not match build ledger key")
    resolved = _validated_topology(topology, contract)
    try:
        claim = ledger.claim(key)
    except ValueError:
        return BuildReconciliation(False, False, {}, "final build already claimed")
    tags = tuple(
        f"{topology.project}-{service}:latest" for service in contract.services
    )
    try:
        result = executor.run(
            (*topology.argv, "build", "--pull", "--progress=plain", *contract.services),
        )
    except BuildSupervisionFailure as error:
        supervision = _supervision_summary(error)
        reason = f"{error.kind}: {supervision['last_event']}"
        reconciled = BuildReconciliation(False, False, {}, reason, supervision)
        ledger.close(claim, reconciled, resolved.digest)
        raise
    except subprocess.TimeoutExpired as error:
        retained = _bounded_compose_diagnostic(error.output)
        reason = (
            "final compose build timed out after "
            f"{int(_FINAL_BUILD_HARD_DEADLINE_SECONDS)} seconds: {retained}"
        )
        reconciled = BuildReconciliation(False, False, {}, reason)
        ledger.close(claim, reconciled, resolved.digest)
        raise ValueError(reason) from error
    try:
        reconciled = reconcile_build(
            result.returncode, result.output, tags, executor.inspect_image
        )
    except Exception:
        ledger.close(
            claim,
            BuildReconciliation(
                False, False, {}, "final compose build reconciliation failed"
            ),
            resolved.digest,
        )
        raise
    ledger.close(claim, reconciled, resolved.digest)
    return reconciled


def start_no_build(
    topology: TaskTopology,
    contract: ProductContract,
    key: BuildLedgerKey,
    ledger: BuildLedger,
    executor: ComposeExecutor,
) -> CommandResult:
    """Start exactly once only from the sealed topology and matching usable build record."""
    _validate_contract_checksum(contract, key)
    resolved = _validated_topology(topology, contract)
    record = ledger.read(key)
    if record.get("state") != "usable":
        raise ValueError("final build ledger is not usable; startup is blocked")
    if record.get("topology_digest") != resolved.digest:
        raise ValueError("final build proof is stale for the validated topology")
    claim = topology.override_path.parent / f"startup-{_key_digest(key)}.claim"
    try:
        fd = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise ValueError("no-build startup already claimed") from error
    else:
        os.close(fd)
    try:
        result = executor.run(
            (*topology.argv, "up", "-d", "--no-build", "--wait", *contract.services),
            timeout_seconds=_NO_BUILD_START_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        retained = _bounded_compose_diagnostic(error.output)
        raise ValueError(
            "no-build compose startup timed out after "
            f"{int(_NO_BUILD_START_TIMEOUT_SECONDS)} seconds: {retained}"
        ) from error
    if result.returncode:
        raise ValueError(f"no-build compose startup failed: {result.output.strip()}")
    return result


def run_controls(
    controls: tuple[RuntimeControl, ...], request: Callable[[RuntimeControl], int]
) -> None:
    for control in controls:
        if request(control) != control.expected_status:
            raise ValueError(f"runtime control failed: {control.name}")


def cleanup_compose(topology: TaskTopology, executor: ComposeExecutor) -> CommandResult:
    """Teardown is successful only when task containers/networks are absent; volumes remain."""
    result = executor.run((*topology.argv, "down", "--remove-orphans"))
    if result.returncode:
        raise ValueError(f"compose teardown failed: {result.output.strip()}")
    filters = ("--filter", f"label=com.docker.compose.project={topology.project}")
    containers = executor.run(("docker", "ps", "-aq", *filters))
    networks = executor.run(("docker", "network", "ls", "-q", *filters))
    if containers.returncode or networks.returncode:
        raise ValueError("compose cleanup verification failed")
    if containers.output.strip() or networks.output.strip():
        raise ValueError("task compose resources remain after teardown")
    return result


def _public_env_replacement(root: Path, env_file: Path) -> str:
    try:
        raw = yaml.safe_load(root.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as error:
        raise ValueError("root docker-compose.yml is invalid") from error
    services = raw.get("services") if isinstance(raw, dict) else None
    if not isinstance(services, dict):
        raise TypeError("root docker-compose.yml has no services")
    names = [
        name
        for name, service in services.items()
        if isinstance(service, dict) and _has_private_env(service.get("env_file"))
    ]
    lines = ["services:"]
    for name in names:
        lines.extend(
            (
                f"  {name}:",
                "    env_file: !override",
                f"      - {json.dumps(str(env_file))}",
            )
        )
    return "\n".join(lines) + "\n"


def _isolated_service(
    service: dict[str, object], topology: TaskTopology, name: str
) -> dict[str, object]:
    """Render only product execution semantics; never inherit host authority."""
    result = {
        field: service[field]
        for field in (
            "build",
            "command",
            "entrypoint",
            "environment",
            "healthcheck",
            "image",
            "working_dir",
        )
        if field in service
    }
    result["env_file"] = [str(topology.env_file)]
    result["ports"] = [
        {
            "mode": "ingress",
            "host_ip": "127.0.0.1",
            "published": str(topology.ports[name]),
            "target": _container_port(name),
            "protocol": "tcp",
        }
    ]
    result["networks"] = {"acceptance": {}}
    result["volumes"] = _task_volumes(service.get("volumes"), name)
    if "depends_on" in service:
        result["depends_on"] = service["depends_on"]
    return result


def _bind_candidate_build(service: dict[str, object], candidate_sha: str) -> None:
    build = service.get("build")
    if not isinstance(build, dict):
        raise ValueError("contract service has no resolved build mapping")
    args = build.get("args")
    if args not in (None, {}):
        raise ValueError("resolved service build arguments are not permitted")
    service["build"] = {**build, "args": {"ACCEPTANCE_CANDIDATE_SHA": candidate_sha}}


def _allocate_task_resources(final: dict[str, object], topology: TaskTopology) -> None:
    services = final["services"]
    assert isinstance(services, dict)
    volume_names: set[str] = set()
    for service in services.values():
        assert isinstance(service, dict)
        volume_names.update(_resource_sources(service.get("volumes")))
    final["networks"] = {"acceptance": {"name": f"{topology.project}-network"}}
    final["volumes"] = {
        name: {"name": f"{topology.project}-{name}"} for name in sorted(volume_names)
    }


def _resource_sources(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value)
    if not isinstance(value, list):
        return set()
    sources: set[str] = set()
    for item in value:
        if (
            isinstance(item, dict)
            and isinstance(item.get("source"), str)
            and item.get("type", "volume") == "volume"
        ):
            sources.add(item["source"])
        elif isinstance(item, str) and ":" in item and not item.startswith(("/", ".")):
            sources.add(item.split(":", 1)[0])
    return sources


def _validate_final_config(
    config: dict[str, object], topology: TaskTopology, contract: ProductContract
) -> None:
    if config.get("name") != topology.project:
        raise ValueError("resolved compose project is not task-owned")
    services = config.get("services")
    if not isinstance(services, dict) or set(services) != set(contract.services):
        raise ValueError("resolved topology contains undeclared services")
    for name, service in services.items():
        if not isinstance(service, dict):
            raise TypeError("resolved service is invalid")
        if service.get("container_name"):
            raise ValueError("resolved topology inherits a fixed container name")
        _validate_env_files(service.get("env_file"), topology.env_file)
        _validate_ports(
            service.get("ports"), topology.ports[name], _container_port(name)
        )
        _validate_dependencies(service.get("depends_on"), contract.services)
        _validate_candidate_build(service.get("build"), topology.candidate_sha)
        if any(
            field in service
            for field in (
                "configs",
                "extra_hosts",
                "network_mode",
                "restart",
                "secrets",
            )
        ):
            raise ValueError(
                "resolved topology retains host or unmanaged runtime authority"
            )
        _validate_task_mounts(service.get("volumes"))
    _validate_resources(config.get("networks"), topology.project)
    _validate_resources(config.get("volumes"), topology.project)


def _validated_topology(
    topology: TaskTopology, contract: ProductContract
) -> ResolvedTopology:
    if not topology.validation_path.is_file() or not topology.override_path.is_file():
        raise ValueError("topology is not validated")
    try:
        record = json.loads(topology.validation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("topology is not validated") from error
    digest = _sha256(topology.override_path.read_bytes())
    if (
        not isinstance(record, dict)
        or record.get("project") != topology.project
        or record.get("services") != list(contract.services)
        or record.get("contract_checksum") != contract.checksum
    ):
        raise ValueError("topology is not validated")
    if record.get("digest") != digest:
        raise ValueError("validated topology is stale")
    return ResolvedTopology(topology.project, contract.services, digest)


def _validate_contract_checksum(contract: ProductContract, key: BuildLedgerKey) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", contract.checksum):
        raise ValueError("contract checksum is not platform-derived")
    if contract.checksum != key.contract_checksum:
        raise ValueError("contract checksum does not match build ledger key")


def _validate_candidate_build(value: object, candidate_sha: str) -> None:
    if not isinstance(value, dict) or value.get("args") != {
        "ACCEPTANCE_CANDIDATE_SHA": candidate_sha
    }:
        raise ValueError("resolved topology has invalid candidate build binding")


def _task_volumes(value: object, service: str) -> list[dict[str, object]]:
    mounts = value if isinstance(value, list) else []
    result: list[dict[str, object]] = []
    for index, mount in enumerate(mounts):
        if isinstance(mount, dict):
            target = mount.get("target")
            read_only = mount.get("read_only") is True
        elif isinstance(mount, str) and ":" in mount:
            parts = mount.split(":")
            target = parts[1]
            read_only = len(parts) > 2 and parts[2] == "ro"
        else:
            raise ValueError("resolved topology contains an invalid mount")
        if not isinstance(target, str) or not target.startswith("/"):
            raise ValueError("resolved topology contains an invalid mount")
        result.append(
            {
                "type": "volume",
                "source": f"{service}-data-{index}",
                "target": target,
                "read_only": read_only,
            }
        )
    return result


def _validate_task_mounts(value: object) -> None:
    # Compose omits an empty mount list for services that need no persisted input.
    if value is None:
        return
    if not isinstance(value, list):
        raise TypeError("resolved topology has invalid task volumes")
    for mount in value:
        if not isinstance(mount, dict) or mount.get("type") != "volume":
            raise ValueError("resolved topology retains a host bind mount")
        if not isinstance(mount.get("source"), str) or not mount.get("source"):
            raise ValueError("resolved topology has invalid task volumes")


def _complete_buildkit_tag(output: str, tag: str) -> bool:
    stages: dict[str, list[str]] = {}
    for line in output.splitlines():
        match = _STAGE.match(line)
        if match:
            stages.setdefault(match["stage"], []).append(match["message"])
    qualified = re.compile(
        rf"(?:[a-z0-9.-]+(?::\d+)?/)?(?:[a-z0-9._-]+/)?{re.escape(tag)}(?:\s|$)"
    )
    candidates = [
        messages
        for messages in stages.values()
        if any(
            "naming to " in message and qualified.search(message)
            for message in messages
        )
    ]
    if len(candidates) != 1:
        return False
    messages = candidates[0]
    return (
        any(message.startswith("exporting to image") for message in messages)
        and any(
            "naming to " in message and qualified.search(message)
            for message in messages
        )
        and any(
            "unpacking to " in message and qualified.search(message)
            for message in messages
        )
        and any(message.startswith("DONE") for message in messages)
    )


def _validate_env_files(value: object, expected: Path) -> None:
    # `docker compose config` resolves env_file into environment and omits its path.
    if value is None:
        return
    files = value if isinstance(value, list) else [value]
    if not files or any(
        Path(str(item)) != expected or Path(str(item)).name in _PRIVATE_ENV_NAMES
        for item in files
    ):
        raise ValueError("resolved topology inherits a private environment file")


def _validate_ports(value: object, expected: int, target: int) -> None:
    if not isinstance(value, list) or len(value) != 1:
        raise ValueError("resolved topology has invalid port mappings")
    port = value[0]
    if isinstance(port, dict):
        valid = (
            port.get("host_ip") == "127.0.0.1"
            and str(port.get("published")) == str(expected)
            and int(port.get("target", -1)) == target
        )
    else:
        valid = str(port) == f"127.0.0.1:{expected}:{target}"
    if not valid:
        raise ValueError("resolved topology has invalid port mappings")


def _validate_dependencies(value: object, services: tuple[str, ...]) -> None:
    if value is None:
        return
    dependencies = (
        set(value)
        if isinstance(value, dict)
        or (isinstance(value, list) and all(isinstance(item, str) for item in value))
        else None
    )
    if dependencies is None:
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
        if resource.get("external") is True:
            raise ValueError("resolved topology uses an external resource")
        name = resource.get("name")
        if name and not str(name).startswith((f"{project}-", f"{project}_")):
            raise ValueError("resolved resource escapes task namespace")
        labels = resource.get("labels")
        if labels is not None and (
            not isinstance(labels, dict)
            or labels.get("com.docker.compose.project") not in {None, project}
        ):
            raise ValueError("resolved resource is not task-owned")


def _has_private_env(value: object) -> bool:
    values = value if isinstance(value, list) else [value]
    return any(Path(str(item)).name in _PRIVATE_ENV_NAMES for item in values if item)


def _json_config(value: str) -> dict[str, object]:
    try:
        config = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("compose config was not JSON") from error
    if not isinstance(config, dict):
        raise TypeError("compose config was not an object")
    return config


def _container_port(service: str) -> int:
    return 80 if service == "mission-planner" else 8000


def _byte_multiplier(unit: str) -> float:
    return {
        "b": 1.0,
        "kb": 1_000.0,
        "mb": 1_000_000.0,
        "gb": 1_000_000_000.0,
        "tb": 1_000_000_000_000.0,
    }[unit.lower()]


def _validate_project(project: str) -> None:
    if not _PROJECT.fullmatch(project):
        raise ValueError("compose project must be a task-safe identifier")


def _validate_candidate_sha(candidate_sha: str) -> None:
    if not isinstance(candidate_sha, str) or not re.fullmatch(
        r"[0-9a-f]{40}", candidate_sha
    ):
        raise ValueError(
            "candidate SHA must be a full 40-character lowercase hexadecimal value"
        )


def _key_digest(key: BuildLedgerKey) -> str:
    return _sha256(
        f"{key.candidate_sha}\0{key.profile_checksum}\0{key.contract_checksum}".encode()
    )


def _bounded_compose_diagnostic(output: str | bytes | None) -> str:
    if isinstance(output, bytes):
        output = output.decode(errors="replace")
    diagnostics = BoundedComposeDiagnostics()
    diagnostics.retain(str(output or ""))
    return diagnostics.output.decode(errors="replace").strip()


def _supervision_summary(error: BuildSupervisionFailure) -> dict[str, object]:
    event = error.last_event
    return {
        "kind": error.kind,
        "last_event": (
            {
                "kind": event.kind,
                "elapsed_seconds": event.elapsed_seconds,
                "detail": _bounded_compose_diagnostic(event.detail),
            }
            if event
            else None
        ),
    }


def _retain_stream_line(
    line: str,
    output: list[str],
    diagnostics: BoundedComposeDiagnostics,
    retain: Callable[[str], None],
) -> None:
    output.append(line)
    diagnostics.retain(line)
    retain(line)


def _drain_compose_stream(
    lines: queue.Queue[str | None],
    reader: threading.Thread,
    output: list[str],
    diagnostics: BoundedComposeDiagnostics,
    retain: Callable[[str], None],
) -> None:
    while True:
        line = lines.get()
        if line is None:
            break
        _retain_stream_line(line, output, diagnostics, retain)
    reader.join()


def _read_compose_stream(stream: object, lines: queue.Queue[str | None]) -> None:
    try:
        for line in stream:  # type: ignore[union-attr]
            lines.put(line)
    finally:
        lines.put(None)


def _process_group_exists(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    try:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except OSError:
            process.terminate()
        deadline = time.monotonic() + _FINAL_BUILD_TERMINATE_GRACE_SECONDS
        while _process_group_exists(process.pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        if _process_group_exists(process.pid):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError:
                process.kill()
    finally:
        try:
            process.wait()
        except ChildProcessError:
            pass


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
