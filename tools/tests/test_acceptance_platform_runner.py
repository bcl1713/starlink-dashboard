from __future__ import annotations

import base64
import json
import struct
import zlib
from pathlib import Path

import pytest
from acceptance.platform import runner
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

    raw = b"\0" * (height * (width + 1))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
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
                "minimumScheduledRequests": 1,
                "observedScheduledRequests": 1,
            },
            "requests": [
                {
                    "id": "1",
                    "path": "/api/v2/missions",
                    "outcome": "finished",
                    "status": 200,
                }
            ],
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


def test_default_final_cleanup_runs_after_a_started_topology_substep_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    topology = object()
    executor = object()

    monkeypatch.setattr(runner, "SubprocessComposeExecutor", lambda: executor)
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

    result = run(
        _argv(tmp_path, "final"),
        dependencies=RunnerDependencies(
            load_profile=lambda _: object(),
            validate_health=lambda *_: _current_health(),
            static=lambda *_: None,
            browser_card=lambda *_: None,
        ),
    )

    assert result.manifest["outcome"] == Outcome.FAILED.value
    assert "topology failed" in result.manifest["primary"]["detail"]
    assert calls == ["cleanup"]


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
    with pytest.raises(ValueError, match="exact pre/post viewport"):
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
    assert observation["visible"]["routeName"] == "V2 Acceptance Route KAAA-KBBB"


def test_adapter_observation_rejects_unbounded_or_incomplete_lifecycle() -> None:
    payload = _adapter_payload()
    payload["lifecycle"] = {"frameId": "frame", "loaderId": "loader", "requests": []}
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
