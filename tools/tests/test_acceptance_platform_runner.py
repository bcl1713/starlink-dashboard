from __future__ import annotations

from pathlib import Path

import pytest

from acceptance.platform.model import Lane, Outcome
from acceptance.platform.runner import RunnerDependencies, main, run

SHA = "a" * 40
ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "tools/acceptance/contracts/v2-mission-retirement.toml"
PROFILE = ROOT / "tools/acceptance/platform/profiles/default.toml"
V2_ADAPTER = ROOT / "tools/acceptance/journeys/v2-mission-retirement.mjs"


def _argv(tmp_path: Path, lane: str, fingerprint: str = "current") -> list[str]:
    return [
        "--lane", lane,
        "--sha", SHA,
        "--ref", "refs/heads/feat/acceptance",
        "--profile", str(PROFILE),
        "--contract", str(CONTRACT),
        "--fingerprint", fingerprint,
        "--evidence-root", str(tmp_path / "evidence"),
        "--task-root", str(tmp_path / "task"),
    ]


def _current_health() -> object:
    return object()


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


def test_default_unprovisioned_profile_blocks_before_static_product_work(tmp_path: Path) -> None:
    calls: list[str] = []
    result = run(
        _argv(tmp_path, "final"),
        dependencies=RunnerDependencies(static=lambda *_: calls.append("static")),
    )

    assert result.exit_code == 2
    assert result.manifest["outcome"] == Outcome.ENVIRONMENT_BLOCKED.value
    assert calls == []


def test_default_unprovisioned_health_returns_environment_blocked(tmp_path: Path) -> None:
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
