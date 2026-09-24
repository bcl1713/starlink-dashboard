from __future__ import annotations

import base64
import hashlib
import json
import struct
import subprocess
import zlib
from pathlib import Path

import pytest
from acceptance.platform import runner
from acceptance.platform.contracts import load_product_contract
from acceptance.platform.evidence import read_fingerprint_authority, verify_manifest
from acceptance.platform.model import Lane, Outcome
from acceptance.platform.runner import RunnerDependencies, main, run

SHA = "a" * 40
ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "tools/acceptance/contracts/v2-mission-retirement.toml"
PROFILE = ROOT / "tools/acceptance/platform/profiles/default.toml"
V2_ADAPTER = ROOT / "tools/acceptance/journeys/v2-mission-retirement.mjs"


def _argv(tmp_path: Path, lane: str, fingerprint: str = "current") -> list[str]:
    return [
        "--lane",
        lane,
        "--sha",
        SHA,
        "--ref",
        "refs/heads/feat/acceptance",
        "--profile",
        str(PROFILE),
        "--contract",
        str(CONTRACT),
        "--fingerprint",
        fingerprint,
        "--evidence-root",
        str(tmp_path / "evidence"),
        "--task-root",
        str(tmp_path / "task"),
    ]


def _current_health() -> object:
    return object()


def _png(width: int = 1920, height: int = 1080) -> bytes:
    """Small, structurally decoded 8-bit grayscale PNG for boundary tests."""

    def chunk(kind: bytes, content: bytes) -> bytes:
        return (
            struct.pack(">I", len(content))
            + kind
            + content
            + struct.pack(">I", zlib.crc32(kind + content) & 0xFFFFFFFF)
        )

    raw = b"\0" * (height * (width * 4 + 1))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _adapter_payload(png: bytes | None = None) -> dict[str, object]:
    image = png or _png()
    encoded = base64.b64encode(image).decode()
    metrics = base64.b64encode(
        json.dumps(
            {**runner._VIEWPORT, "raster": {"width": 1920, "height": 1080}}
        ).encode()
    ).decode()
    return {
        "status": "passed",
        "activation": "browser-observed-200",
        "lifecycle": {
            "frameId": "frame",
            "loaderId": "loader",
            "polling": {
                "navigationScoped": True,
                "endpoint": "/api/overview-history",
                "periodMs": 5000,
                "cadenceMinMs": 4500,
                "cadenceMaxMs": 7500,
                "windowStart": 10.1,
                "windowEnd": 15.1,
                "minimumScheduledRequests": 1,
                "observedScheduledRequests": 1,
            },
            "requests": [
                {
                    "id": "1",
                    "path": "/api/overview-history",
                    "outcome": "finished",
                    "status": 200,
                    "startedAt": 10.0,
                    "finishedAt": 10.1,
                    "cycle": "bootstrap",
                },
                {
                    "id": "2",
                    "path": "/api/overview-history",
                    "outcome": "finished",
                    "status": 200,
                    "startedAt": 15.0,
                    "finishedAt": 15.1,
                    "cycle": "scheduled",
                },
            ],
            "overflow": False,
        },
        "visible": {
            "routeName": "V2 Acceptance Route KAAA-KBBB",
            "firstPoi": "KAAA",
            "poiRows": 2,
        },
        "artifacts": {
            "journey-pre.png": encoded,
            "journey-post.png": encoded,
            "journey-pre-metrics.json": metrics,
            "journey-post-metrics.json": metrics,
        },
    }


@pytest.mark.parametrize("lane", ["static", "diagnostic"])
def test_nonfinal_lanes_cannot_serialize_final_pass(tmp_path: Path, lane: str) -> None:
    manifest = run(
        _argv(tmp_path, lane),
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
        ),
    ).manifest

    assert manifest["final_acceptance"] is False
    assert manifest["maximum_evidence_claim"] != "final_acceptance"


def test_missing_health_fingerprint_skips_product_executor(tmp_path: Path) -> None:
    calls: list[str] = []
    result = main(
        _argv(tmp_path, "static", fingerprint="missing"),
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: (_ for _ in ()).throw(ValueError("missing")),
            static=lambda *_: calls.append("static"),
        ),
    )

    assert result == 2
    assert calls == []


def test_final_requires_every_required_result(tmp_path: Path) -> None:
    result = run(
        _argv(tmp_path, "final"),
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
            browser_card=lambda *_: None,
            final_steps=lambda *_: (_ for _ in ()).throw(ValueError("control failed")),
            cleanup=lambda *_: None,
        ),
    )

    assert result.manifest["final_acceptance"] is False
    assert result.manifest["outcome"] == Outcome.FAILED.value


def test_cleanup_failure_preserves_product_failure(tmp_path: Path) -> None:
    result = run(
        _argv(tmp_path, "final"),
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
            browser_card=lambda *_: None,
            final_steps=lambda *_: (_ for _ in ()).throw(ValueError("build failed")),
            cleanup=lambda *_: (_ for _ in ()).throw(RuntimeError("cleanup failed")),
        ),
    )

    assert result.manifest["outcome"] == Outcome.FAILED.value
    assert result.manifest["cleanup"]["outcome"] == Outcome.FAILED.value
    assert "build failed" in result.manifest["primary"]["detail"]


def test_cleanup_failure_revokes_an_otherwise_successful_final_claim(
    tmp_path: Path,
) -> None:
    result = run(
        _argv(tmp_path, "final"),
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
            browser_card=lambda *_: None,
            final_steps=lambda *_: object(),
            cleanup=lambda *_: (_ for _ in ()).throw(RuntimeError("cleanup failed")),
        ),
    )

    assert result.exit_code == 1
    assert result.manifest["outcome"] == Outcome.FAILED.value
    assert result.manifest["final_acceptance"] is False
    assert result.manifest["maximum_evidence_claim"] != "final_acceptance"
    assert result.manifest["cleanup"]["outcome"] == Outcome.FAILED.value


def test_final_compose_diagnostics_are_sealed_after_a_build_failure(tmp_path: Path) -> None:
    def failed_final_steps(*_: object) -> object:
        error = ValueError("final compose build timed out")
        error.platform_artifacts = {"compose.output.log": b"bounded BuildKit output"}  # type: ignore[attr-defined]
        raise error

    result = run(
        _argv(tmp_path, "final"),
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
            browser_card=lambda *_: None,
            final_steps=failed_final_steps,
            cleanup=lambda *_: None,
        ),
    )

    root = tmp_path / "evidence" / "candidates" / SHA
    assert result.exit_code == 1
    assert (root / "compose.output.log").read_bytes() == b"bounded BuildKit output"
    verify_manifest(root)
    read_fingerprint_authority(root)


def test_default_final_cleanup_runs_after_a_started_topology_substep_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    topology = object()
    executor = object()

    monkeypatch.setattr(runner, "SubprocessComposeExecutor", lambda *_: executor)
    monkeypatch.setattr(runner, "render_task_override", lambda *_: topology)
    monkeypatch.setattr(
        runner,
        "resolve_topology",
        lambda *_: (_ for _ in ()).throw(ValueError("topology failed")),
    )
    monkeypatch.setattr(
        runner,
        "cleanup_compose",
        lambda actual, actual_executor: calls.append("cleanup"),
    )

    class Session:
        def __init__(self) -> None:
            self.cdp_url = "http://127.0.0.1:9222"
            self.artifacts: dict[str, bytes] = {}

        def close(self) -> None:
            calls.append("browser-cleanup")

    result = run(
        _argv(tmp_path, "final"),
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
            browser_card=lambda *_: None,
            start_browser_session=lambda *_: Session(),
        ),
    )

    assert result.manifest["outcome"] == Outcome.FAILED.value
    assert "topology failed" in result.manifest["primary"]["detail"]
    assert calls == ["cleanup", "browser-cleanup"]


def test_final_interrupt_after_browser_and_topology_allocation_drains_composite_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    task_root = tmp_path / "task"
    task_root.mkdir()
    (task_root / "generated-topology.json").write_text("{}", encoding="utf-8")
    topology, executor = object(), object()

    class Session:
        cdp_url = "http://127.0.0.1:9222"

        def __init__(self) -> None:
            self.artifacts: dict[str, bytes] = {}

        def close(self) -> None:
            calls.append("browser-cleanup")
            self.artifacts["browser.stderr.log"] = b"interrupted browser log"
            self.artifacts["xvfb.stderr.log"] = b"interrupted xvfb log"

    class Adapter:
        sha256 = "a" * 64

        def close(self) -> None:
            pass

    def interrupt_after_allocation(*args: object) -> dict[str, bytes]:
        resource_ready = args[4]
        assert callable(resource_ready)
        resource_ready((topology, executor))
        raise KeyboardInterrupt("operator interrupt")

    monkeypatch.setattr(runner, "_open_adapter_source", lambda *_: Adapter())
    monkeypatch.setattr(runner, "_final_steps", interrupt_after_allocation)
    monkeypatch.setattr(
        runner,
        "cleanup_compose",
        lambda actual_topology, actual_executor: calls.append("compose-cleanup"),
    )

    result = run(
        _argv(tmp_path, "final"),
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
            browser_card=lambda *_: None,
            start_browser_session=lambda *_: Session(),
        ),
    )

    assert result.exit_code == 1
    assert "operator interrupt" in result.manifest["primary"]["detail"]
    assert result.manifest["cleanup"]["outcome"] == Outcome.PASSED.value
    assert calls == ["compose-cleanup", "browser-cleanup"]
    assert not task_root.exists()
    evidence = tmp_path / "evidence" / "candidates" / SHA
    assert (evidence / "browser.stderr.log").read_bytes() == b"interrupted browser log"
    assert (evidence / "xvfb.stderr.log").read_bytes() == b"interrupted xvfb log"


@pytest.mark.parametrize(
    ("sha", "ref"),
    [
        ("../../escape", "refs/heads/feat/acceptance"),
        (SHA, "refs/heads/../escape"),
    ],
)
def test_candidate_identity_is_rejected_before_paths_are_constructed(
    tmp_path: Path, sha: str, ref: str
) -> None:
    argv = _argv(tmp_path, "static")
    argv[argv.index("--sha") + 1] = sha
    argv[argv.index("--ref") + 1] = ref

    with pytest.raises(ValueError):
        runner._parse(argv)

    assert not (tmp_path / "escape").exists()


def test_wrapper_resolves_explicit_relative_contract_from_repository_root(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            str(ROOT / "tools/run-acceptance-platform.sh"),
            "--lane",
            "health",
            "--sha",
            SHA,
            "--ref",
            "refs/heads/feat/acceptance",
            "--profile",
            str(PROFILE),
            "--contract",
            "tools/acceptance/contracts/v2-mission-retirement.toml",
            "--evidence-root",
            str(tmp_path / "evidence"),
            "--task-root",
            str(tmp_path / "task"),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    manifest = json.loads(
        (
            tmp_path / "evidence" / "candidates" / SHA / "runner-manifest.json"
        ).read_text()
    )
    assert manifest["contract_checksum"] is not None
    assert manifest["outcome"] == Outcome.ENVIRONMENT_BLOCKED.value


def test_runner_manifest_is_sealed_under_a_candidate_nofollow_root(
    tmp_path: Path,
) -> None:
    result = run(
        _argv(tmp_path, "static"),
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
        ),
    )

    root = tmp_path / "evidence" / "candidates" / SHA
    verify_manifest(root)
    assert result.manifest["sha"] == SHA
    assert result.manifest["ref"] == "refs/heads/feat/acceptance"
    assert b'"sha":"' + SHA.encode() in read_fingerprint_authority(root)


def test_adapter_output_without_exact_pre_and_post_viewport_proof_is_rejected() -> None:
    with pytest.raises(ValueError, match="allowlist"):
        runner._decode_adapter_artifacts({"status": "passed", "artifacts": {}})


def test_adapter_rejects_header_forged_png_even_when_dimensions_match() -> None:
    forged = b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR" + struct.pack(">II", 1920, 1080)
    with pytest.raises(ValueError, match="decoded PNG"):
        runner._decode_adapter_artifacts(_adapter_payload(forged))


def test_adapter_observation_is_schema_validated_and_retained() -> None:
    artifacts = runner._decode_adapter_artifacts(_adapter_payload())

    observation = json.loads(artifacts["adapter-observation.json"])
    assert observation["activation"] == "browser-observed-200"
    assert observation["lifecycle"]["requests"][0]["outcome"] == "finished"
    assert observation["lifecycle"]["requests"][0]["startedAt"] == 10.0
    assert observation["lifecycle"]["requests"][1]["cycle"] == "scheduled"
    assert observation["lifecycle"]["polling"] == {
        "cadenceMaxMs": 7500,
        "cadenceMinMs": 4500,
        "endpoint": "/api/overview-history",
        "minimumScheduledRequests": 1,
        "navigationScoped": True,
        "observedScheduledRequests": 1,
        "periodMs": 5000,
        "windowEnd": 15.1,
        "windowStart": 10.1,
    }
    assert observation["visible"]["routeName"] == "V2 Acceptance Route KAAA-KBBB"


def test_final_manifest_seals_adapter_checksum_and_capture_interval(
    tmp_path: Path,
) -> None:
    result = run(
        _argv(tmp_path, "final"),
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
            browser_card=lambda *_: None,
            final_steps=lambda *_: object(),
            cleanup=lambda *_: None,
        ),
    )

    manifest = result.manifest
    capture = manifest["capture"]
    assert capture["started_at"] <= capture["ended_at"]
    assert capture["adapter_sha256"] == runner._adapter_checksum(
        load_product_contract(CONTRACT)
    )
    sealed = json.loads(
        (
            tmp_path / "evidence" / "candidates" / SHA / "runner-manifest.json"
        ).read_text()
    )
    assert sealed["capture"] == capture
    assert runner._candidate_is_discoverable(tmp_path / "evidence", SHA)


def test_final_manifest_binds_adapter_digest_captured_before_final_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    adapter = repository / "tools/acceptance/journeys/v2-mission-retirement.mjs"
    adapter.parent.mkdir(parents=True)
    adapter.write_text("before launch")
    package = repository / "frontend/mission-planner/package.json"
    package.parent.mkdir(parents=True)
    package.write_text("{}\n", encoding="utf-8")
    before = hashlib.sha256(adapter.read_bytes()).hexdigest()
    monkeypatch.setattr(runner, "_REPOSITORY", repository)

    result = run(
        _argv(tmp_path, "final"),
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
            browser_card=lambda *_: None,
            final_steps=lambda *_: adapter.write_text("after launch"),
            cleanup=lambda *_: None,
        ),
    )

    assert result.exit_code == 0
    assert result.manifest["capture"]["adapter_sha256"] == before
    assert (
        result.manifest["capture"]["adapter_sha256"]
        != hashlib.sha256(adapter.read_bytes()).hexdigest()
    )


def test_journey_launches_prehashed_real_esm_adapter_after_source_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    adapter = repository / "tools/acceptance/journeys/v2-mission-retirement.mjs"
    asset = repository / "asset.kml"
    adapter.parent.mkdir(parents=True)
    adapter.write_text(V2_ADAPTER.read_text(encoding="utf-8"), encoding="utf-8")
    asset.write_text("asset")
    package = repository / "frontend/mission-planner/package.json"
    package.parent.mkdir(parents=True)
    package.write_text('{"name":"acceptance-adapter-test"}\n', encoding="utf-8")
    (package.parent / "node_modules").symlink_to(
        ROOT / "frontend/mission-planner/node_modules", target_is_directory=True
    )
    contract = load_product_contract(CONTRACT)
    contract = contract.__class__(
        **{
            **contract.__dict__,
            "journey_adapter": Path(
                "tools/acceptance/journeys/v2-mission-retirement.mjs"
            ),
            "assets": (Path("asset.kml"),),
        }
    )
    monkeypatch.setattr(runner, "_REPOSITORY", repository)
    argv = _argv(tmp_path, "final") + [
        "--browser-session",
        "http://127.0.0.1:9",
        "--deployed-origin",
        "http://127.0.0.1:9",
    ]
    inputs = runner._parse(argv)
    source = runner._open_adapter_source(inputs, contract)
    before = source.sha256
    adapter.write_text("this replacement must never execute\n", encoding="utf-8")
    try:
        with pytest.raises(
            ValueError, match="product journey adapter exited non-zero"
        ) as error:
            runner._run_journey(inputs, contract, source)
    finally:
        source.close()

    assert source.executable_path.endswith(".mjs")
    assert source.executable_path != str(adapter)
    assert (
        hashlib.sha256(Path(source.executable_path).read_bytes()).hexdigest() == before
    )
    assert "ECONNREFUSED" in str(error.value)
    assert "Cannot find module" not in str(error.value)


def test_adapter_nonzero_exit_retains_stderr_and_is_not_classified_as_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A disposed adapter attachment must preserve its original failure evidence."""
    adapter = tmp_path / "adapter.mjs"
    adapter.write_text(
        """const handle = setInterval(() => {}, 1_000);
const attachment = { dispose() { clearInterval(handle); } };
try {
  throw new Error('exact failure');
} catch (error) {
  process.stderr.write(`${error.stack.split('\\n')[0]}\\n`);
} finally {
  attachment.dispose();
}
process.exit(1);
""",
        encoding="utf-8",
    )
    source = runner._AdapterSource(adapter, "a" * 64, ROOT)
    monkeypatch.setattr(runner, "_open_adapter_source", lambda *_: source)

    def final_steps(
        inputs: runner.RunnerInputs, profile: object, contract: object
    ) -> object:
        return runner._run_journey(inputs, contract, source)  # type: ignore[arg-type]

    result = run(
        _argv(tmp_path, "final")
        + [
            "--browser-session",
            "http://127.0.0.1:9",
            "--deployed-origin",
            "http://127.0.0.1:9",
        ],
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
            browser_card=lambda *_: None,
            final_steps=final_steps,
            cleanup=lambda *_: None,
        ),
    )

    failure_root = tmp_path / "evidence" / "candidates" / SHA
    assert "exact failure" in result.manifest["primary"]["detail"]
    assert "timed out" not in result.manifest["primary"]["detail"]
    assert "adapter exited non-zero" in result.manifest["primary"]["detail"]
    assert (
        failure_root / "adapter.stderr.log"
    ).read_bytes() == b"Error: exact failure\n"


def test_adapter_deadline_retains_bounded_partial_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = tmp_path / "adapter.mjs"
    adapter.write_text(
        """import { writeSync } from 'node:fs';
writeSync(2, 'partial adapter stderr\\n');
setInterval(() => {}, 1_000);
""",
        encoding="utf-8",
    )
    source = runner._AdapterSource(adapter, "a" * 64, ROOT)
    monkeypatch.setattr(runner, "_open_adapter_source", lambda *_: source)
    calls = 0

    def deadline_clock() -> float:
        nonlocal calls
        calls += 1
        return 0.0 if calls <= 3 else 181.0

    monkeypatch.setattr(runner.time, "monotonic", deadline_clock)

    def final_steps(
        inputs: runner.RunnerInputs, profile: object, contract: object
    ) -> object:
        return runner._run_journey(inputs, contract, source)  # type: ignore[arg-type]

    result = run(
        _argv(tmp_path, "final")
        + [
            "--browser-session",
            "http://127.0.0.1:9",
            "--deployed-origin",
            "http://127.0.0.1:9",
        ],
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
            browser_card=lambda *_: None,
            final_steps=final_steps,
            cleanup=lambda *_: None,
        ),
    )

    retained_stderr = (
        tmp_path / "evidence" / "candidates" / SHA / "adapter.stderr.log"
    ).read_bytes()
    assert "adapter timed out" in result.manifest["primary"]["detail"]
    assert retained_stderr == b"partial adapter stderr\n"
    assert len(retained_stderr) <= runner._MAX_ADAPTER_STDERR_BYTES


def test_adapter_nonzero_overflow_retains_bounded_initial_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Overflow must not replace an adapter's classified original failure."""
    monkeypatch.setattr(runner, "_MAX_ADAPTER_STDOUT_BYTES", 64)
    monkeypatch.setattr(runner, "_MAX_ADAPTER_STDERR_BYTES", 64)
    adapter = tmp_path / "adapter.mjs"
    adapter.write_text(
        """import { writeSync } from 'node:fs';
writeSync(1, 'stdout begins: ' + 'x'.repeat(128));
writeSync(2, 'Error: exact overflow failure\\n' + 'y'.repeat(128));
process.exit(1);
""",
        encoding="utf-8",
    )
    source = runner._AdapterSource(adapter, "a" * 64, ROOT)

    def final_steps(
        inputs: runner.RunnerInputs, profile: object, contract: object
    ) -> object:
        return runner._run_journey(inputs, contract, source)  # type: ignore[arg-type]

    result = run(
        _argv(tmp_path, "final")
        + [
            "--browser-session",
            "http://127.0.0.1:9",
            "--deployed-origin",
            "http://127.0.0.1:9",
        ],
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
            browser_card=lambda *_: None,
            final_steps=final_steps,
            cleanup=lambda *_: None,
        ),
    )

    failure_root = tmp_path / "evidence" / "candidates" / SHA
    stdout = (failure_root / "adapter.stdout.log").read_bytes()
    stderr = (failure_root / "adapter.stderr.log").read_bytes()
    assert "adapter exited non-zero" in result.manifest["primary"]["detail"]
    assert "exact overflow failure" in result.manifest["primary"]["detail"]
    assert len(stdout) == runner._MAX_ADAPTER_STDOUT_BYTES
    assert len(stderr) == runner._MAX_ADAPTER_STDERR_BYTES
    assert stdout.startswith(b"stdout begins: ")
    assert stderr.startswith(b"Error: exact overflow failure\n")


def test_adapter_deadline_overflow_retains_bounded_initial_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deadline cleanup keeps both stream prefixes through platform evidence."""
    monkeypatch.setattr(runner, "_MAX_ADAPTER_STDOUT_BYTES", 64)
    monkeypatch.setattr(runner, "_MAX_ADAPTER_STDERR_BYTES", 64)
    adapter = tmp_path / "adapter.mjs"
    adapter.write_text(
        """import { writeSync } from 'node:fs';
writeSync(1, 'stdout before deadline: ' + 'x'.repeat(128));
writeSync(2, 'Error: deadline diagnostic\\n' + 'y'.repeat(128));
setInterval(() => {}, 1_000);
""",
        encoding="utf-8",
    )
    source = runner._AdapterSource(adapter, "a" * 64, ROOT)
    calls = 0

    def deadline_clock() -> float:
        nonlocal calls
        calls += 1
        return 0.0 if calls <= 4 else 181.0

    monkeypatch.setattr(runner.time, "monotonic", deadline_clock)

    def final_steps(
        inputs: runner.RunnerInputs, profile: object, contract: object
    ) -> object:
        return runner._run_journey(inputs, contract, source)  # type: ignore[arg-type]

    result = run(
        _argv(tmp_path, "final")
        + [
            "--browser-session",
            "http://127.0.0.1:9",
            "--deployed-origin",
            "http://127.0.0.1:9",
        ],
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
            browser_card=lambda *_: None,
            final_steps=final_steps,
            cleanup=lambda *_: None,
        ),
    )

    failure_root = tmp_path / "evidence" / "candidates" / SHA
    stdout = (failure_root / "adapter.stdout.log").read_bytes()
    stderr = (failure_root / "adapter.stderr.log").read_bytes()
    assert "adapter timed out" in result.manifest["primary"]["detail"]
    assert "deadline diagnostic" in result.manifest["primary"]["detail"]
    assert len(stdout) == runner._MAX_ADAPTER_STDOUT_BYTES
    assert len(stderr) == runner._MAX_ADAPTER_STDERR_BYTES
    assert stdout.startswith(b"stdout before deadline: ")
    assert stderr.startswith(b"Error: deadline diagnostic\n")


def test_adapter_rejects_extra_or_aggregate_oversize_artifacts() -> None:
    payload = _adapter_payload()
    payload["artifacts"]["unexpected.bin"] = "eA=="  # type: ignore[index]
    with pytest.raises(ValueError, match="allowlist"):
        runner._decode_adapter_artifacts(payload)


def test_adapter_rejects_png_with_wrong_ihdr_before_inflation() -> None:
    with pytest.raises(ValueError, match="decoded PNG"):
        runner._decode_adapter_artifacts(_adapter_payload(_png(1, 1)))


def test_adapter_observation_rejects_unbounded_or_incomplete_lifecycle() -> None:
    payload = _adapter_payload()
    payload["lifecycle"] = {"frameId": "frame", "loaderId": "loader", "requests": []}
    with pytest.raises(ValueError, match="adapter observation"):
        runner._decode_adapter_artifacts(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [("cadenceMinMs", 0), ("cadenceMaxMs", 9_000)],
)
def test_adapter_observation_rejects_unproven_polling_cadence(
    field: str, value: int
) -> None:
    payload = _adapter_payload()
    payload["lifecycle"]["polling"][field] = value  # type: ignore[index]

    with pytest.raises(ValueError, match="adapter observation"):
        runner._decode_adapter_artifacts(payload)


def test_adapter_observation_rejects_overlapping_scheduled_history_request() -> None:
    payload = _adapter_payload()
    payload["lifecycle"]["requests"][1]["startedAt"] = 10.05  # type: ignore[index]

    with pytest.raises(ValueError, match="adapter observation"):
        runner._decode_adapter_artifacts(payload)


def test_finalization_failure_returns_nonfinal_result_with_primary_and_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        runner,
        "_write_manifest",
        lambda *_: (_ for _ in ()).throw(OSError("seal failed")),
    )
    result = run(
        _argv(tmp_path, "final"),
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
            browser_card=lambda *_: None,
            final_steps=lambda *_: object(),
            cleanup=lambda *_: None,
        ),
    )

    assert result.exit_code == 1
    assert result.manifest["final_acceptance"] is False
    assert "final evidence failed: seal failed" in result.manifest["primary"]["detail"]
    assert result.manifest["cleanup"]["outcome"] == Outcome.PASSED.value


@pytest.mark.parametrize("stage", ["write", "seal", "verify"])
def test_finalization_stage_failure_never_publishes_final_candidate_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    original_write = runner.write_artifacts
    original_seal = runner.seal_fingerprint
    original_verify = runner.verify_manifest
    calls = 0

    if stage == "write":

        def fail_candidate_write(root: Path, *args: object) -> str:
            if ".pending" in root.parts:
                raise OSError("artifact write failed")
            return original_write(root, *args)  # type: ignore[arg-type]

        monkeypatch.setattr(runner, "write_artifacts", fail_candidate_write)
    elif stage == "seal":

        def fail_candidate_seal(root: Path, *args: object) -> None:
            if ".pending" in root.parts:
                raise OSError("seal failed")
            original_seal(root, *args)  # type: ignore[arg-type]

        monkeypatch.setattr(runner, "seal_fingerprint", fail_candidate_seal)
    else:

        def fail_final_verify(root: Path) -> None:
            nonlocal calls
            calls += 1
            original_verify(root)
            if calls == 2:
                raise ValueError("final verify failed")

        monkeypatch.setattr(runner, "verify_manifest", fail_final_verify)

    result = run(
        _argv(tmp_path, "final"),
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
            browser_card=lambda *_: None,
            final_steps=lambda *_: object(),
            cleanup=lambda *_: None,
        ),
    )

    assert result.exit_code == 1
    assert result.manifest["final_acceptance"] is False
    candidate = tmp_path / "evidence" / "candidates" / SHA
    assert not candidate.exists()
    failure = tmp_path / "evidence" / "failures" / SHA
    verify_manifest(failure)
    assert (
        json.loads((failure / "runner-manifest.json").read_text())["final_acceptance"]
        is False
    )


def test_post_publication_fault_fails_closed_when_revoke_destination_is_poisoned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_rename = runner.os.rename

    def rename_then_fail(source: Path, destination: Path) -> None:
        original_rename(source, destination)
        if ".pending" in source.parts:
            raise OSError("post-rename fault")

    monkeypatch.setattr(runner.os, "rename", rename_then_fail)
    revoked = tmp_path / "evidence" / "candidates" / ".revoked" / SHA
    revoked.mkdir(parents=True)
    result = run(
        _argv(tmp_path, "final"),
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
            browser_card=lambda *_: None,
            final_steps=lambda *_: object(),
            cleanup=lambda *_: None,
        ),
    )

    candidate = tmp_path / "evidence" / "candidates" / SHA
    failure = tmp_path / "evidence" / "failures" / SHA
    assert result.exit_code == 1
    assert result.manifest["final_acceptance"] is False
    assert candidate.exists()
    assert not runner._candidate_is_discoverable(tmp_path / "evidence", SHA)
    verify_manifest(failure)
    retained = json.loads((failure / "runner-manifest.json").read_text())
    assert retained["final_acceptance"] is False
    assert retained["maximum_evidence_claim"] == "non_final"


def test_post_discovery_rename_fault_is_not_discoverable_when_revocation_is_poisoned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_rename = runner.os.rename

    def rename_discovery_then_fail(source: Path, destination: Path) -> None:
        original_rename(source, destination)
        if ".discoverable" in source.parts:
            raise OSError("post-discovery-rename fault")

    monkeypatch.setattr(runner.os, "rename", rename_discovery_then_fail)
    revoked = tmp_path / "evidence" / "candidates" / ".revoked" / SHA
    revoked.mkdir(parents=True)
    result = run(
        _argv(tmp_path, "final"),
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
            browser_card=lambda *_: None,
            final_steps=lambda *_: object(),
            cleanup=lambda *_: None,
        ),
    )

    evidence_root = tmp_path / "evidence"
    candidate = evidence_root / "candidates" / SHA
    discovery = evidence_root / "candidates" / ".discoverable" / SHA
    failure = evidence_root / "failures" / SHA
    assert result.exit_code == 1
    assert result.manifest["final_acceptance"] is False
    assert candidate.is_dir()
    assert discovery.is_dir()
    assert revoked.is_dir()
    assert not runner._candidate_is_discoverable(evidence_root, SHA)
    verify_manifest(failure)
    retained = json.loads((failure / "runner-manifest.json").read_text())
    assert retained["final_acceptance"] is False
    assert retained["maximum_evidence_claim"] == "non_final"


def test_default_unprovisioned_profile_blocks_before_static_product_work(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    result = run(
        _argv(tmp_path, "final"),
        dependencies=RunnerDependencies(static=lambda *_: calls.append("static")),
    )

    assert result.exit_code == 2
    assert result.manifest["outcome"] == Outcome.ENVIRONMENT_BLOCKED.value
    assert calls == []


def test_default_unprovisioned_health_returns_environment_blocked(
    tmp_path: Path,
) -> None:
    result = run(_argv(tmp_path, "health"))

    assert result.exit_code == 2
    assert result.manifest["outcome"] == Outcome.ENVIRONMENT_BLOCKED.value


def test_v2_adapter_has_no_platform_authority() -> None:
    source = V2_ADAPTER.read_text(encoding="utf-8")
    assert "spawn(" not in source
    assert "--remote-debugging-port" not in source
    assert "Create New Mission" in source
    assert "Upload KML" in source
    assert "getAnimations({ subtree: true })" in source
    assert "node:fs" not in source
    assert "writeEvidence" not in source
    assert "Network.requestWillBeSent" in source
    assert "Object.assign(record, { outcome:" in source
    assert "record budget exceeded" in source
    assert "navigationScoped: true" in source
    assert "loaderId" in source
    assert "Upcoming POIs" in source


def test_v2_adapter_declares_navigation_scoped_history_polling_window() -> None:
    source = V2_ADAPTER.read_text(encoding="utf-8")

    assert "const POLLING_ENDPOINT = '/api/overview-history';" in source
    assert "const POLLING_PERIOD_MS = 5_000;" in source
    assert "beginPollingWindow" in source
    assert "waitForScheduledPoll" in source
    assert "cadenceMinMs" in source
    assert "cadenceMaxMs" in source
    assert "record.startedAt < previous.finishedAt" in source


def test_final_executes_static_before_final_product_steps(tmp_path: Path) -> None:
    calls: list[str] = []
    result = run(
        _argv(tmp_path, "final"),
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: calls.append("static"),
            browser_card=lambda *_: None,
            final_steps=lambda *_: calls.append("final"),
            cleanup=lambda *_: calls.append("cleanup"),
        ),
    )

    assert result.exit_code == 0
    assert result.manifest["final_acceptance"] is True
    assert calls == ["static", "final", "cleanup"]
    assert result.manifest["lane"] == Lane.FINAL.value


def test_compose_cleanup_failure_still_closes_browser_and_writes_its_logs(
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    class Session:
        cdp_url = "http://127.0.0.1:9222"

        def __init__(self) -> None:
            self.artifacts: dict[str, bytes] = {}

        def close(self) -> None:
            calls.append("browser-close")
            self.artifacts.update(
                {
                    "browser.stderr.log": b"browser log",
                    "xvfb.stderr.log": b"xvfb log",
                }
            )

    result = run(
        _argv(tmp_path, "final"),
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
            browser_card=lambda *_: None,
            start_browser_session=lambda *_: Session(),
            final_steps=lambda *_: object(),
            cleanup=lambda _: (_ for _ in ()).throw(
                RuntimeError("compose cleanup failed")
            ),
        ),
    )

    assert calls == ["browser-close"]
    assert result.manifest["final_acceptance"] is False
    assert "compose cleanup failed" in result.manifest["cleanup"]["detail"]
    assert (
        tmp_path / "evidence" / "candidates" / SHA / "browser.stderr.log"
    ).read_bytes() == b"browser log"
    assert (
        tmp_path / "evidence" / "candidates" / SHA / "xvfb.stderr.log"
    ).read_bytes() == b"xvfb log"


def test_default_final_platform_session_precedes_build_uses_its_cdp_and_closes_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    class Session:
        def __init__(self) -> None:
            self.cdp_url = "http://127.0.0.1:9222"
            self.metrics = {"raster": [1920, 1080]}
            self.artifacts = {"browser.stderr.log": b"browser log"}

        def close(self) -> None:
            calls.append("browser-close")

    session = Session()

    class Adapter:
        sha256 = "a" * 64

        def close(self) -> None:
            pass

    monkeypatch.setattr(runner, "_open_adapter_source", lambda *_: Adapter())
    monkeypatch.setattr(
        runner,
        "_final_steps",
        lambda inputs, *_: calls.append(f"build:{inputs.browser_session}")
        or (_ for _ in ()).throw(ValueError("build failed")),
    )

    result = run(
        _argv(tmp_path, "final"),
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
            start_browser_session=lambda *_: calls.append("browser-start") or session,
        ),
    )

    assert result.exit_code == 1
    assert calls == ["browser-start", "build:http://127.0.0.1:9222", "browser-close"]
    assert (
        tmp_path / "evidence" / "candidates" / SHA / "browser.stderr.log"
    ).read_bytes() == b"browser log"


def test_static_maps_named_frontend_test_scripts_to_npm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(words: list[str], **_: object) -> subprocess.CompletedProcess[object]:
        calls.append(words)
        return subprocess.CompletedProcess(words, 0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    runner._run_static(load_product_contract(CONTRACT))

    assert calls[-2:] == [["npm", "run", "lint"], ["npm", "run", "test:unit"]]
