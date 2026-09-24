"""Generic, fail-closed acceptance runner for product contracts."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import selectors
import shlex
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import pairwise
from pathlib import Path
from typing import Any

import tomllib

from .compose import (
    BuildLedger,
    SubprocessComposeExecutor,
    build_final,
    cleanup_compose,
    render_task_override,
    resolve_topology,
    start_no_build,
)
from .contracts import load_product_contract
from .evidence import (
    prepare_evidence_parent,
    read_fingerprint_authority,
    read_nofollow,
    seal_fingerprint,
    verify_manifest,
    write_artifacts,
)
from .health import run_platform_health, validate_fingerprint
from .model import (
    BrowserProfile,
    BuildLedgerKey,
    Lane,
    Outcome,
    PlatformProfile,
    ProductContract,
    RuntimeControl,
    validate_candidate_inputs,
)

_REPOSITORY = Path(__file__).resolve().parents[3]
_VIEWPORT = {
    "innerWidth": 1920,
    "innerHeight": 1080,
    "visualWidth": 1920,
    "visualHeight": 1080,
    "dpr": 1,
}
_MAX_ADAPTER_ARTIFACT_BYTES = 12 * 1024 * 1024
_MAX_ADAPTER_STDOUT_BYTES = 24 * 1024 * 1024
_MAX_ADAPTER_STDERR_BYTES = 32 * 1024
_MAX_ADAPTER_ENCODED_BYTES = 20 * 1024 * 1024
_MAX_ADAPTER_DECODED_BYTES = 20 * 1024 * 1024
_MAX_ADAPTER_OBSERVATION_BYTES = 32 * 1024
_MAX_LIFECYCLE_RECORDS = 50
_VIEWPORT_ARTIFACTS = frozenset(
    {
        "journey-pre.png",
        "journey-post.png",
        "journey-pre-metrics.json",
        "journey-post-metrics.json",
    }
)


@dataclass(frozen=True)
class RunnerResult:
    exit_code: int
    manifest: dict[str, Any]


@dataclass
class _AdapterSource:
    """A prehashed task-owned ESM adapter retained through the adapter launch."""

    path: Path
    sha256: str
    repository_root: Path

    @property
    def executable_path(self) -> str:
        return str(self.path)

    def close(self) -> None:
        """Keep the sealed task artifact available for provenance inspection."""


@dataclass(frozen=True)
class RunnerInputs:
    lane: Lane
    sha: str
    ref: str
    profile_path: Path
    contract_path: Path
    fingerprint: Path
    evidence_root: Path
    task_root: Path
    ledger_root: Path
    backend_port: int
    frontend_port: int
    browser_session: str
    deployed_origin: str


@dataclass
class RunnerDependencies:
    """Narrow orchestration seams; adapters never receive platform authority."""

    load_profile: Callable[[Path], PlatformProfile] | None = None
    health: Callable[[PlatformProfile, Path], object] | None = None
    validate_health: Callable[[PlatformProfile, Path], object] | None = None
    static: Callable[[ProductContract], None] | None = None
    final_steps: (
        Callable[[RunnerInputs, PlatformProfile, ProductContract], object] | None
    ) = None
    browser_card: Callable[[RunnerInputs], None] | None = None
    cleanup: Callable[[object | None], None] | None = None


def _parse(argv: Sequence[str]) -> RunnerInputs:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", required=True, choices=[lane.value for lane in Lane])
    parser.add_argument("--sha", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument(
        "--profile",
        type=Path,
        default=_REPOSITORY / "tools/acceptance/platform/profiles/default.toml",
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=_REPOSITORY / "tools/acceptance/contracts/v2-mission-retirement.toml",
    )
    parser.add_argument("--fingerprint", type=Path, default=Path("current"))
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--task-root", type=Path, required=True)
    parser.add_argument("--ledger-root", type=Path)
    parser.add_argument("--backend-port", type=int, default=18000)
    parser.add_argument("--frontend-port", type=int, default=15173)
    parser.add_argument("--browser-session", default="")
    parser.add_argument("--deployed-origin", default="")
    parsed = parser.parse_args(list(argv))
    sha, ref = validate_candidate_inputs(parsed.sha, parsed.ref)
    evidence_root = parsed.evidence_root.absolute()
    fingerprint = parsed.fingerprint
    if fingerprint == Path("current"):
        fingerprint = evidence_root / sha / "fingerprint.json"
    return RunnerInputs(
        lane=Lane(parsed.lane),
        sha=sha,
        ref=ref,
        profile_path=parsed.profile.absolute(),
        contract_path=parsed.contract.absolute(),
        fingerprint=fingerprint.absolute(),
        evidence_root=evidence_root,
        task_root=parsed.task_root.absolute(),
        ledger_root=(
            parsed.ledger_root or parsed.task_root / "build-ledger"
        ).absolute(),
        backend_port=parsed.backend_port,
        frontend_port=parsed.frontend_port,
        browser_session=parsed.browser_session,
        deployed_origin=parsed.deployed_origin,
    )


def _load_profile(path: Path) -> PlatformProfile:
    with path.open("rb") as handle:
        raw = tomllib.load(handle)
    browser = raw.get("browser")
    if not isinstance(browser, dict):
        raise TypeError("platform profile browser descriptor is required")
    return PlatformProfile(
        version=str(raw["version"]),
        checksum=str(raw["checksum"]),
        browser=BrowserProfile(
            store_root=Path(str(browser["store_root"])),
            executable=Path(str(browser["executable"])),
            version=str(browser["version"]),
            byte_size=int(browser["byte_size"]),
            sha256=str(browser["sha256"]),
        ),
    )


def _run_health(profile: PlatformProfile, root: Path) -> object:
    from .health import PlatformHealthExecutor

    return run_platform_health(profile, root, PlatformHealthExecutor(probe=_probe))


def _probe(argv: tuple[str, ...]) -> str:
    completed = subprocess.run(
        argv, check=True, capture_output=True, text=True, timeout=15
    )
    return completed.stdout.strip() or completed.stderr.strip()


def _run_static(contract: ProductContract) -> None:
    for group in contract.static_groups:
        cwd = _REPOSITORY / group.working_directory
        for command in group.commands:
            words = shlex.split(command)
            if words and words[0] in {"lint", "test"}:
                words = ["npm", "run", *words]
            completed = subprocess.run(words, cwd=cwd, check=False)
            if completed.returncode:
                raise ValueError(f"static group {group.name} failed: {command}")


def _request(control: RuntimeControl, inputs: RunnerInputs) -> int:
    base = f"http://127.0.0.1:{inputs.backend_port}"
    if control.path == "/":
        base = f"http://127.0.0.1:{inputs.frontend_port}"
    try:
        with urllib.request.urlopen(base + control.path, timeout=15) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def _verify_browser_card(inputs: RunnerInputs) -> None:
    if not inputs.browser_session.startswith(
        ("http://127.0.0.1:", "http://localhost:")
    ):
        raise ValueError(
            "final lane requires a platform-supplied loopback browser session"
        )
    if not inputs.deployed_origin.startswith(
        ("http://127.0.0.1:", "http://localhost:")
    ):
        raise ValueError("final lane requires a deployed origin")


def _run_journey(
    inputs: RunnerInputs, contract: ProductContract, adapter: _AdapterSource
) -> dict[str, bytes]:
    asset = _REPOSITORY / contract.assets[0]
    if not asset.is_file():
        raise ValueError("declared journey asset is unavailable")
    stdout, stderr, returncode = _bounded_adapter_process(
        [
            "node",
            adapter.executable_path,
            "--repository-root",
            str(adapter.repository_root),
            "--session",
            inputs.browser_session,
            "--origin",
            inputs.deployed_origin,
            "--kml",
            str(asset),
        ],
        _REPOSITORY,
    )
    if returncode:
        raise ValueError(
            "product journey adapter failed: "
            f"{stderr.decode(errors='replace') or stdout.decode(errors='replace')}"
        )
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise ValueError("product journey adapter emitted invalid JSON") from error
    return _decode_adapter_artifacts(payload)


def _bounded_adapter_process(
    argv: list[str], cwd: Path, *, pass_fds: tuple[int, ...] = ()
) -> tuple[bytes, bytes, int]:
    """Collect adapter IPC without allocating an unbounded stdout/stderr payload."""
    process = subprocess.Popen(
        argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, pass_fds=pass_fds
    )
    assert process.stdout is not None and process.stderr is not None
    limits = {
        process.stdout: _MAX_ADAPTER_STDOUT_BYTES,
        process.stderr: _MAX_ADAPTER_STDERR_BYTES,
    }
    collected = {process.stdout: bytearray(), process.stderr: bytearray()}
    selector = selectors.DefaultSelector()
    for stream in limits:
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ)
    deadline = time.monotonic() + 180
    try:
        while selector.get_map():
            if time.monotonic() >= deadline:
                raise TimeoutError("product journey adapter timed out")
            for key, _ in selector.select(max(0, deadline - time.monotonic())):
                chunk = os.read(key.fd, 64 * 1024)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                output = collected[key.fileobj]
                if len(output) + len(chunk) > limits[key.fileobj]:
                    raise ValueError(
                        "product journey adapter output exceeds byte budget"
                    )
                output.extend(chunk)
        return (
            bytes(collected[process.stdout]),
            bytes(collected[process.stderr]),
            process.wait(timeout=1),
        )
    except BaseException:
        process.kill()
        process.wait()
        raise
    finally:
        selector.close()


def _decode_adapter_artifacts(payload: object) -> dict[str, bytes]:
    if not isinstance(payload, Mapping) or payload.get("status") != "passed":
        raise ValueError("product journey adapter did not report a passed result")
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise TypeError("product journey adapter omitted bounded artifacts")
    if set(artifacts) != _VIEWPORT_ARTIFACTS:
        raise ValueError("product journey adapter artifacts violate exact allowlist")
    decoded: dict[str, bytes] = {}
    encoded_total = decoded_total = 0
    for name, encoded in artifacts.items():
        if not isinstance(name, str) or not isinstance(encoded, str):
            raise TypeError("product journey adapter artifact is invalid")
        encoded_total += len(encoded)
        if encoded_total > _MAX_ADAPTER_ENCODED_BYTES:
            raise ValueError(
                "product journey adapter encoded artifacts exceed byte budget"
            )
        try:
            decoded[name] = base64.b64decode(encoded, validate=True)
        except ValueError as error:
            raise ValueError(
                "product journey adapter artifact is not base64"
            ) from error
        if len(decoded[name]) > _MAX_ADAPTER_ARTIFACT_BYTES:
            raise ValueError("product journey adapter artifact exceeds byte budget")
        decoded_total += len(decoded[name])
        if decoded_total > _MAX_ADAPTER_DECODED_BYTES:
            raise ValueError(
                "product journey adapter decoded artifacts exceed byte budget"
            )
    _verify_viewport_artifacts(decoded)
    decoded["adapter-observation.json"] = _adapter_observation(payload)
    return decoded


def _verify_viewport_artifacts(artifacts: Mapping[str, bytes]) -> None:
    for phase in ("journey-pre", "journey-post"):
        metrics_name, image_name = f"{phase}-metrics.json", f"{phase}.png"
        if metrics_name not in artifacts or image_name not in artifacts:
            raise ValueError(
                "final journey evidence lacks exact pre/post viewport artifacts"
            )
        try:
            metrics = json.loads(artifacts[metrics_name])
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("viewport metrics artifact is invalid") from error
        if not isinstance(metrics, Mapping) or any(
            metrics.get(key) != value for key, value in _VIEWPORT.items()
        ):
            raise ValueError("exact viewport metrics are invalid")
        width, height = _png_dimensions(artifacts[image_name])
        raster = metrics.get("raster")
        if (width, height) != (1920, 1080) or raster != {"width": 1920, "height": 1080}:
            raise ValueError("decoded viewport raster is invalid")


def _png_dimensions(content: bytes) -> tuple[int, int]:
    """Decode a complete PNG stream; an IHDR prefix is not raster evidence."""
    if (
        len(content) > _MAX_ADAPTER_ARTIFACT_BYTES
        or content[:8] != b"\x89PNG\r\n\x1a\n"
    ):
        raise ValueError("viewport artifact is not a decoded PNG")
    offset, width, height, channels, depth = 8, 0, 0, 0, 0
    ihdr = iend = False
    compressed: list[bytes] = []
    while offset < len(content):
        if offset + 12 > len(content):
            raise ValueError("viewport artifact is not a decoded PNG")
        length = int.from_bytes(content[offset : offset + 4], "big")
        end = offset + 12 + length
        if end > len(content):
            raise ValueError("viewport artifact is not a decoded PNG")
        kind, data = (
            content[offset + 4 : offset + 8],
            content[offset + 8 : offset + 8 + length],
        )
        if zlib.crc32(kind + data) & 0xFFFFFFFF != int.from_bytes(
            content[offset + 8 + length : end], "big"
        ):
            raise ValueError("viewport artifact is not a decoded PNG")
        if kind == b"IHDR":
            if ihdr or length != 13:
                raise ValueError("viewport artifact is not a decoded PNG")
            width, height, depth, color, compression, filtering, interlace = (
                int.from_bytes(data[:4], "big"),
                int.from_bytes(data[4:8], "big"),
                data[8],
                data[9],
                data[10],
                data[11],
                data[12],
            )
            channels = {6: 4}.get(color, 0)
            if (width, height, depth, compression, filtering, interlace) != (
                1920,
                1080,
                8,
                0,
                0,
                0,
            ) or not channels:
                raise ValueError("viewport artifact is not a decoded PNG")
            ihdr = True
        elif kind == b"IDAT":
            if not ihdr or iend:
                raise ValueError("viewport artifact is not a decoded PNG")
            compressed.append(data)
        elif kind == b"IEND":
            if not ihdr or length or iend or end != len(content):
                raise ValueError("viewport artifact is not a decoded PNG")
            iend = True
        offset = end
    if not ihdr or not iend or not compressed:
        raise ValueError("viewport artifact is not a decoded PNG")
    row_bytes = (width * channels * depth + 7) // 8
    expected = height * (row_bytes + 1)
    inflater = zlib.decompressobj()
    decoded = bytearray()
    try:
        for chunk in compressed:
            while chunk:
                decoded.extend(inflater.decompress(chunk, expected - len(decoded) + 1))
                if len(decoded) > expected:
                    raise ValueError("viewport artifact is not a decoded PNG")
                chunk = inflater.unconsumed_tail
        decoded.extend(inflater.flush(expected - len(decoded) + 1))
    except zlib.error as error:
        raise ValueError("viewport artifact is not a decoded PNG") from error
    if (
        not inflater.eof
        or inflater.unused_data
        or len(decoded) != expected
        or any(decoded[index] > 4 for index in range(0, len(decoded), row_bytes + 1))
    ):
        raise ValueError("viewport artifact is not a decoded PNG")
    return width, height


def _adapter_observation(payload: Mapping[str, object]) -> bytes:
    """Project only bounded terminal browser observations into sealed evidence."""
    lifecycle, visible = payload.get("lifecycle"), payload.get("visible")
    if (
        payload.get("activation") != "browser-observed-200"
        or not isinstance(lifecycle, Mapping)
        or not isinstance(visible, Mapping)
    ):
        raise ValueError("adapter observation is invalid")
    frame, loader, polling, requests = (
        lifecycle.get("frameId"),
        lifecycle.get("loaderId"),
        lifecycle.get("polling"),
        lifecycle.get("requests"),
    )
    if (
        not all(isinstance(value, str) and value for value in (frame, loader))
        or not isinstance(polling, Mapping)
        or not isinstance(requests, list)
        or not 1 <= len(requests) <= _MAX_LIFECYCLE_RECORDS
    ):
        raise ValueError("adapter observation is invalid")
    minimum, observed = polling.get("minimumScheduledRequests"), polling.get(
        "observedScheduledRequests"
    )
    cadence_min, cadence_max = polling.get("cadenceMinMs"), polling.get("cadenceMaxMs")
    if (
        lifecycle.get("overflow") is not False
        or polling.get("navigationScoped") is not True
        or polling.get("endpoint") != "/api/overview-history"
        or polling.get("periodMs") != 5000
        or (cadence_min, cadence_max) != (4500, 7500)
        or not all(
            isinstance(polling.get(key), (int, float))
            for key in ("windowStart", "windowEnd")
        )
        or polling["windowEnd"] < polling["windowStart"]
        or not isinstance(minimum, int)
        or not isinstance(observed, int)
        or minimum < 1
        or observed < minimum
    ):
        raise ValueError("adapter observation is invalid")
    records: list[dict[str, object]] = []
    for record in requests:
        if (
            not isinstance(record, Mapping)
            or not isinstance(record.get("id"), str)
            or record.get("path") != "/api/overview-history"
            or record.get("outcome") != "finished"
            or record.get("status") != 200
            or record.get("cycle") not in {"bootstrap", "scheduled"}
            or not all(
                isinstance(record.get(key), (int, float))
                for key in ("startedAt", "finishedAt")
            )
            or record["finishedAt"] < record["startedAt"]
        ):
            raise ValueError("adapter observation is invalid")
        records.append(
            {
                key: record[key]
                for key in (
                    "id",
                    "path",
                    "outcome",
                    "status",
                    "startedAt",
                    "finishedAt",
                    "cycle",
                )
            }
        )
    bootstrap = [record for record in records if record["cycle"] == "bootstrap"]
    scheduled = [record for record in records if record["cycle"] == "scheduled"]
    if len(bootstrap) != 1 or len(scheduled) < minimum or len(scheduled) != observed:
        raise ValueError("adapter observation is invalid")
    ordered = [bootstrap[0], *sorted(scheduled, key=lambda record: record["startedAt"])]
    for previous, record in pairwise(ordered):
        cadence_ms = (record["startedAt"] - previous["startedAt"]) * 1000
        if (
            record["startedAt"] < previous["finishedAt"]
            or cadence_ms < cadence_min
            or cadence_ms > cadence_max
        ):
            raise ValueError("adapter observation is invalid")
    if (
        polling["windowStart"] != bootstrap[0]["finishedAt"]
        or polling["windowEnd"] != ordered[-1]["finishedAt"]
    ):
        raise ValueError("adapter observation is invalid")
    if (
        not isinstance(visible.get("routeName"), str)
        or not isinstance(visible.get("firstPoi"), str)
        or not isinstance(visible.get("poiRows"), int)
        or visible["poiRows"] < 2
    ):
        raise ValueError("adapter observation is invalid")
    encoded = json.dumps(
        {
            "activation": payload["activation"],
            "lifecycle": {
                "frameId": frame,
                "loaderId": loader,
                "polling": {
                    "navigationScoped": True,
                    "endpoint": polling["endpoint"],
                    "periodMs": polling["periodMs"],
                    "cadenceMinMs": cadence_min,
                    "cadenceMaxMs": cadence_max,
                    "windowStart": polling["windowStart"],
                    "windowEnd": polling["windowEnd"],
                    "minimumScheduledRequests": minimum,
                    "observedScheduledRequests": observed,
                },
                "requests": records,
            },
            "visible": {
                "routeName": visible["routeName"],
                "firstPoi": visible["firstPoi"],
                "poiRows": visible["poiRows"],
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if len(encoded) > _MAX_ADAPTER_OBSERVATION_BYTES:
        raise ValueError("adapter observation exceeds byte budget")
    return encoded


def _final_steps(
    inputs: RunnerInputs,
    profile: PlatformProfile,
    contract: ProductContract,
    browser_card: Callable[[RunnerInputs], None],
    resource_ready: Callable[[object], None],
    adapter: _AdapterSource,
) -> dict[str, bytes]:
    executor = SubprocessComposeExecutor()
    topology = render_task_override(
        _REPOSITORY,
        contract,
        inputs.task_root,
        f"accept-{inputs.sha[:12]}",
        {
            "starlink-location": inputs.backend_port,
            "mission-planner": inputs.frontend_port,
        },
    )
    resource_ready((topology, executor))
    resolve_topology(topology, contract, executor)
    key = BuildLedgerKey(inputs.sha, profile.checksum, contract.checksum)
    ledger = BuildLedger(inputs.ledger_root)
    built = build_final(topology, profile, contract, key, ledger, executor)
    if not built.usable:
        raise ValueError(f"final build is unusable: {built.reason}")
    start_no_build(topology, contract, key, ledger, executor)
    control_results: list[dict[str, object]] = []
    for control in contract.controls:
        status = _request(control, inputs)
        control_results.append(
            {
                "name": control.name,
                "path": control.path,
                "expected_status": control.expected_status,
                "status": status,
            }
        )
        if status != control.expected_status:
            raise ValueError(f"runtime control failed: {control.name}")
    browser_card(inputs)
    artifacts = _run_journey(inputs, contract, adapter)
    artifacts["runtime-observation.json"] = json.dumps(
        {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "browser": {
                "session": inputs.browser_session,
                "origin": inputs.deployed_origin,
                "profile_version": profile.version,
                "profile_checksum": profile.checksum,
                "viewport": _VIEWPORT,
            },
            "build": {"image_ids": dict(built.image_ids)},
            "controls": control_results,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return artifacts


def _cleanup_default(resource: object) -> None:
    topology, executor = resource
    cleanup_compose(topology, executor)


def _outcome_for(error: BaseException) -> Outcome:
    return (
        Outcome.ENVIRONMENT_BLOCKED
        if isinstance(error, _EnvironmentBlocked)
        else Outcome.FAILED
    )


class _EnvironmentBlocked(ValueError):
    pass


def _manifest(
    inputs: RunnerInputs,
    outcome: Outcome,
    final: bool,
    primary: str,
    cleanup: str,
    cleanup_failed: bool,
    profile: object | None,
    contract: object | None,
    capture_started_at: str,
    capture_ended_at: str,
    adapter_sha256: str | None,
) -> dict[str, Any]:
    return {
        "sha": inputs.sha,
        "ref": inputs.ref,
        "lane": inputs.lane.value,
        "outcome": outcome.value,
        "final_acceptance": final,
        "maximum_evidence_claim": (
            "final_acceptance"
            if final
            else ("diagnostic_only" if inputs.lane is Lane.DIAGNOSTIC else "non_final")
        ),
        "profile_checksum": getattr(profile, "checksum", None),
        "contract_checksum": getattr(contract, "checksum", None),
        "capture": {
            "started_at": capture_started_at,
            "ended_at": capture_ended_at,
            "adapter_sha256": adapter_sha256,
        },
        "primary": {"outcome": outcome.value, "detail": primary},
        "cleanup": {
            "outcome": Outcome.FAILED.value if cleanup_failed else Outcome.PASSED.value,
            "detail": cleanup,
        },
    }


def _open_adapter_source(
    inputs: RunnerInputs, contract: object | None
) -> _AdapterSource:
    """Copy no-follow bytes to a task-owned ESM path before the browser launch."""
    adapter = getattr(contract, "journey_adapter", None)
    if not isinstance(adapter, Path) or adapter.suffix != ".mjs":
        raise TypeError("contract-selected journey adapter is invalid")
    try:
        source = _REPOSITORY / adapter
        source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            if not stat.S_ISREG(os.fstat(source_fd).st_mode):
                raise ValueError("contract-selected journey adapter is unavailable")
            destination = (
                inputs.task_root / ".acceptance-adapters" / inputs.sha / adapter.name
            )
            prepare_evidence_parent(destination.parent)
            destination_fd = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o500,
            )
            try:
                digest = hashlib.sha256()
                while chunk := os.read(source_fd, 1024 * 1024):
                    digest.update(chunk)
                    view = memoryview(chunk)
                    while view:
                        view = view[os.write(destination_fd, view) :]
                os.fsync(destination_fd)
                os.fchmod(destination_fd, 0o500)
            except BaseException:
                os.close(destination_fd)
                destination.unlink(missing_ok=True)
                raise
            else:
                os.close(destination_fd)
                os.chmod(destination.parent, 0o500)
                repository_root = _REPOSITORY.resolve(strict=True)
                if not (
                    repository_root.is_dir()
                    and (
                        repository_root / "frontend/mission-planner/package.json"
                    ).is_file()
                ):
                    raise ValueError("repository root is unavailable")
                return _AdapterSource(destination, digest.hexdigest(), repository_root)
        finally:
            os.close(source_fd)
    except OSError as error:
        raise ValueError("contract-selected journey adapter is unavailable") from error


def _adapter_checksum(contract: object | None) -> str | None:
    """Return the no-follow adapter digest for non-executing lanes and tests."""
    adapter = getattr(contract, "journey_adapter", None)
    if not isinstance(adapter, Path):
        return None
    try:
        return hashlib.sha256(read_nofollow(_REPOSITORY / adapter)).hexdigest()
    except ValueError:
        return None


def _write_manifest(
    inputs: RunnerInputs, manifest: dict[str, Any], artifacts: Mapping[str, bytes]
) -> None:
    """Seal a root, then publish its separate discovery authority last."""
    root = inputs.evidence_root / "candidates" / inputs.sha
    staging = inputs.evidence_root / "candidates" / ".pending" / inputs.sha
    discovery = inputs.evidence_root / "candidates" / ".discoverable" / inputs.sha
    discovery_staging = (
        inputs.evidence_root / "candidates" / ".discoverable" / ".pending" / inputs.sha
    )
    prepare_evidence_parent(staging.parent)
    if any(path.exists() for path in (root, staging, discovery, discovery_staging)):
        raise ValueError("candidate evidence root already exists")
    retained = dict(artifacts)
    retained["runner-manifest.json"] = (
        json.dumps(manifest, sort_keys=True) + "\n"
    ).encode()
    write_artifacts(staging, retained)
    verify_manifest(staging)
    envelope = json.dumps(
        {
            "sha": inputs.sha,
            "ref": inputs.ref,
            "health_fingerprint_sha256": _fingerprint_digest(inputs.fingerprint),
            "runner_manifest_sha256": hashlib.sha256(
                retained["runner-manifest.json"]
            ).hexdigest(),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    seal_fingerprint(staging, envelope)
    read_fingerprint_authority(staging)
    verify_manifest(staging)
    prepare_evidence_parent(root.parent)
    os.rename(staging, root)
    _write_candidate_discovery(inputs, retained["runner-manifest.json"])


def _write_candidate_discovery(inputs: RunnerInputs, runner_manifest: bytes) -> None:
    """Atomically make an already-sealed candidate discoverable to final readers."""
    root = inputs.evidence_root / "candidates" / inputs.sha
    discovery = inputs.evidence_root / "candidates" / ".discoverable" / inputs.sha
    staging = (
        inputs.evidence_root / "candidates" / ".discoverable" / ".pending" / inputs.sha
    )
    authority = json.dumps(
        {
            "sha": inputs.sha,
            "runner_manifest_sha256": hashlib.sha256(runner_manifest).hexdigest(),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    prepare_evidence_parent(staging.parent)
    write_artifacts(staging, {"candidate-authority.json": authority})
    seal_fingerprint(staging, authority)
    if read_fingerprint_authority(staging) != authority:
        raise ValueError("candidate discovery authority is invalid")
    verify_manifest(staging)
    if not root.is_dir():
        raise ValueError("candidate evidence root disappeared before discovery")
    prepare_evidence_parent(discovery.parent)
    os.rename(staging, discovery)


def _candidate_is_discoverable(evidence_root: Path, sha: str) -> bool:
    """Return true only for unrevoked roots bound by final discovery authority."""
    root = evidence_root / "candidates" / sha
    discovery = evidence_root / "candidates" / ".discoverable" / sha
    revoked = evidence_root / "candidates" / ".revoked" / sha
    try:
        # A revocation namespace entry is an invalidation signal even if moving
        # the root into it could not complete.  This keeps a post-rename fault
        # from leaving the separate discovery marker authoritative.
        if os.path.lexists(revoked):
            return False
        authority = json.loads(read_fingerprint_authority(discovery))
        manifest = read_nofollow(root / "runner-manifest.json")
        if authority != {
            "sha": sha,
            "runner_manifest_sha256": hashlib.sha256(manifest).hexdigest(),
        }:
            return False
        verify_manifest(root)
        return json.loads(manifest).get("final_acceptance") is True
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return False


def _revoke_published_candidate(inputs: RunnerInputs) -> None:
    """Remove a partially published candidate root before recording failure evidence."""
    root = inputs.evidence_root / "candidates" / inputs.sha
    if not root.exists():
        return
    revoked = inputs.evidence_root / "candidates" / ".revoked" / inputs.sha
    prepare_evidence_parent(revoked.parent)
    if revoked.exists():
        raise ValueError("revoked candidate root already exists")
    os.rename(root, revoked)


def _write_finalization_failure(
    inputs: RunnerInputs, manifest: dict[str, Any], artifacts: Mapping[str, bytes]
) -> None:
    """Retain a sealed non-final classification without publishing candidate authority."""
    root = inputs.evidence_root / "failures" / inputs.sha
    prepare_evidence_parent(root.parent)
    retained = dict(artifacts)
    retained["runner-manifest.json"] = (
        json.dumps(manifest, sort_keys=True) + "\n"
    ).encode()
    write_artifacts(root, retained)
    verify_manifest(root)
    seal_fingerprint(
        root,
        json.dumps({"sha": inputs.sha, "outcome": "failed"}, sort_keys=True).encode(),
    )
    read_fingerprint_authority(root)
    verify_manifest(root)


def _fingerprint_digest(path: Path) -> str | None:
    try:
        return hashlib.sha256(read_nofollow(path)).hexdigest()
    except ValueError:
        return None


def run(
    argv: Sequence[str], *, dependencies: RunnerDependencies | None = None
) -> RunnerResult:
    dependencies = dependencies or RunnerDependencies()
    inputs = _parse(argv)
    capture_started_at = datetime.now(timezone.utc).isoformat()
    profile: PlatformProfile | object | None = None
    contract: ProductContract | object | None = None
    primary = ""
    cleanup_detail = "not required"
    cleanup_failed = False
    outcome = Outcome.FAILED
    final = False
    resource: object | None = None
    resource_holder: list[object] = []
    artifacts: dict[str, bytes] = {}
    adapter_source: _AdapterSource | None = None
    adapter_sha256: str | None = None
    try:
        profile = (dependencies.load_profile or _load_profile)(inputs.profile_path)
        contract = load_product_contract(inputs.contract_path)
        if inputs.lane is Lane.HEALTH:
            health_root = inputs.evidence_root / inputs.sha
            prepare_evidence_parent(health_root.parent)
            health = (dependencies.health or _run_health)(profile, health_root)
            health_outcome = getattr(health, "outcome", Outcome.PASSED)
            outcome = (
                health_outcome
                if isinstance(health_outcome, Outcome)
                else Outcome(str(health_outcome))
            )
            primary = getattr(health, "reason", "platform health completed")
        else:
            try:
                (dependencies.validate_health or validate_fingerprint)(
                    profile, inputs.fingerprint
                )
            except ValueError as error:
                raise _EnvironmentBlocked(str(error)) from error
            (dependencies.static or _run_static)(contract)
            if inputs.lane is Lane.DIAGNOSTIC:
                outcome, primary = (
                    Outcome.DIAGNOSTIC_ONLY,
                    "static contract diagnostics completed",
                )
            elif inputs.lane is Lane.STATIC:
                outcome, primary = Outcome.PASSED, "static contract checks completed"
            else:
                browser_card = dependencies.browser_card or _verify_browser_card
                adapter_source = _open_adapter_source(inputs, contract)
                adapter_sha256 = adapter_source.sha256
                if dependencies.final_steps is None:
                    artifacts = _final_steps(
                        inputs,
                        profile,
                        contract,
                        browser_card,
                        resource_holder.append,
                        adapter_source,
                    )
                    resource = resource_holder[0]
                else:
                    browser_card(inputs)
                    resource = dependencies.final_steps(inputs, profile, contract)
                outcome, primary = Outcome.PASSED, "final product contract completed"
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        subprocess.SubprocessError,
    ) as error:
        outcome, primary, final = _outcome_for(error), str(error), False
    finally:
        if inputs.lane is Lane.FINAL:
            if resource is None and resource_holder:
                resource = resource_holder[0]
            try:
                if dependencies.cleanup is not None:
                    dependencies.cleanup(resource)
                elif resource is not None:
                    _cleanup_default(resource)
                cleanup_detail = "final lane cleanup completed"
            except (
                OSError,
                RuntimeError,
                TypeError,
                ValueError,
                subprocess.SubprocessError,
            ) as error:
                cleanup_failed, cleanup_detail = True, str(error)
                outcome, final = Outcome.FAILED, False
        final = (
            inputs.lane is Lane.FINAL
            and outcome is Outcome.PASSED
            and not cleanup_failed
        )
        if adapter_source is not None:
            adapter_source.close()
    capture_ended_at = datetime.now(timezone.utc).isoformat()
    manifest = _manifest(
        inputs,
        outcome,
        final,
        primary,
        cleanup_detail,
        cleanup_failed,
        profile,
        contract,
        capture_started_at,
        capture_ended_at,
        adapter_sha256,
    )
    try:
        _write_manifest(inputs, manifest, artifacts)
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        outcome, final = Outcome.FAILED, False
        primary = f"{primary}; final evidence failed: {error}".strip("; ")
        try:
            _revoke_published_candidate(inputs)
        except (OSError, RuntimeError, TypeError, ValueError) as revoke_error:
            primary += f"; candidate authority revocation failed: {revoke_error}"
        manifest = _manifest(
            inputs,
            outcome,
            final,
            primary,
            cleanup_detail,
            cleanup_failed,
            profile,
            contract,
            capture_started_at,
            capture_ended_at,
            adapter_sha256,
        )
        try:
            _write_finalization_failure(inputs, manifest, artifacts)
        except (OSError, RuntimeError, TypeError, ValueError) as failure_error:
            manifest["primary"][
                "detail"
            ] += f"; failure evidence unavailable: {failure_error}"
    exit_code = (
        0
        if outcome in {Outcome.PASSED, Outcome.DIAGNOSTIC_ONLY} and not cleanup_failed
        else (2 if outcome is Outcome.ENVIRONMENT_BLOCKED else 1)
    )
    return RunnerResult(exit_code, manifest)


def main(
    argv: Sequence[str] | None = None, *, dependencies: RunnerDependencies | None = None
) -> int:
    return run(
        sys.argv[1:] if argv is None else argv, dependencies=dependencies
    ).exit_code


if __name__ == "__main__":
    raise SystemExit(main())
