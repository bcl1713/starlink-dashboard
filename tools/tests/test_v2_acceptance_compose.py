from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from acceptance.artifacts import EvidenceWriter
from acceptance.compose import (
    compose_build_argv,
    parse_buildkit_log,
    reconcile_build,
    render_override,
    run_full_build,
)
from acceptance.model import AcceptanceInputs

SHA = "a" * 40
TAGS = ("accept-backend:sha", "accept-frontend:sha")


def _inputs(tmp_path: Path) -> AcceptanceInputs:
    return AcceptanceInputs.from_mapping(
        {"sha": SHA, "ref": "feat/acceptance", "evidence_root": tmp_path}
    )


def _writer(tmp_path: Path) -> EvidenceWriter:
    return EvidenceWriter(tmp_path / "evidence", SHA)


def _complete_log(*tags: str) -> str:
    blocks = []
    for index, tag in enumerate(tags, start=10):
        blocks.extend(
            (
                f"#{index} exporting to image",
                f"#{index} naming to docker.io/library/{tag}",
                f"#{index} unpacking to docker.io/library/{tag}",
                f"#{index} DONE 0.0s",
            )
        )
    return "\n".join(blocks) + "\n"


def _log_without_unpack() -> str:
    return (
        _complete_log(TAGS[0])
        + "#11 exporting to image\n#11 naming to docker.io/library/accept-frontend:sha\n#11 DONE 0.0s\n"
    )


def _inspect(tag: str) -> str:
    return "sha256:" + tag


def test_override_replaces_root_fixed_ports_and_private_env_file(
    tmp_path: Path,
) -> None:
    override = render_override(
        _inputs(tmp_path), backend_port=18_000, frontend_port=15_173
    )

    assert "!override" in override
    assert '      - "5173:80"' not in override
    assert "container_name:" not in override
    assert "env_file:" not in override
    assert "STARLINK_MODE=simulation" in override
    assert set(override.splitlines()) >= {
        "services: !override",
        "  starlink-location:",
        "  mission-planner:",
    }


def test_override_replaces_root_bindings_with_task_loopback_ports(
    tmp_path: Path,
) -> None:
    override = render_override(
        _inputs(tmp_path), backend_port=18_000, frontend_port=15_173
    )

    assert '      - "127.0.0.1:18000:8000"' in override
    assert '      - "127.0.0.1:15173:80"' in override
    assert "ports: !override []" not in override


def test_build_argv_targets_only_backend_and_mission_planner(tmp_path: Path) -> None:
    argv = compose_build_argv(
        _inputs(tmp_path), [Path("base.yml"), Path("override.yml")]
    )

    assert argv[-4:] == [
        "--no-cache",
        "--progress=plain",
        "starlink-location",
        "mission-planner",
    ]
    assert argv[:4] == ["docker", "compose", "--project-name", "accept-" + SHA[:12]]
    assert "up" not in argv


def test_parse_buildkit_log_requires_every_completion_marker() -> None:
    records = parse_buildkit_log(_complete_log(*TAGS), TAGS)

    assert [record.tag for record in records] == list(TAGS)
    assert all(record.complete for record in records)


def test_nonzero_wrapper_with_two_completed_images_is_reconciled() -> None:
    disposition = reconcile_build(
        returncode=124,
        log_text=_complete_log(*TAGS),
        expected_tags=TAGS,
        inspect_tag=_inspect,
    )

    assert disposition.usable is True
    assert disposition.wrapper_anomaly is True


def test_missing_unpack_is_not_reconciled() -> None:
    assert reconcile_build(124, _log_without_unpack(), TAGS, _inspect).usable is False


def test_missing_image_inspection_is_not_reconciled() -> None:
    disposition = reconcile_build(124, _complete_log(*TAGS), TAGS, lambda _tag: "")

    assert disposition.usable is False


def test_genuine_build_failure_never_starts_stack(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []

    def fake_run(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        calls.append(" ".join(argv))
        if " build " in f" {' '.join(argv)} ":
            return SimpleNamespace(returncode=2, stdout="build failed\n")
        raise AssertionError(f"unexpected Docker command: {argv}")

    monkeypatch.setattr("acceptance.compose.subprocess.run", fake_run)

    result = run_full_build(
        _inputs(tmp_path),
        _writer(tmp_path),
        override_path=tmp_path / "task-override.yml",
        backend_port=18_000,
        frontend_port=15_173,
    )

    assert result.status == "failed"
    assert all(" up " not in call for call in calls)


def test_full_build_writes_task_override_and_avoids_private_root_env_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        calls.append(argv)
        return SimpleNamespace(returncode=2, stdout="build failed\n")

    monkeypatch.setattr("acceptance.compose.subprocess.run", fake_run)
    override_path = tmp_path / "task-override.yml"

    result = run_full_build(
        _inputs(tmp_path),
        _writer(tmp_path),
        override_path=override_path,
        backend_port=18_000,
        frontend_port=15_173,
    )

    assert result.status == "failed"
    assert calls == [
        [
            "docker",
            "compose",
            "--project-name",
            "accept-" + SHA[:12],
            "--file",
            "docker-compose.yml",
            "--file",
            str(override_path),
            "build",
            "--no-cache",
            "--progress=plain",
            "starlink-location",
            "mission-planner",
        ]
    ]
    override = override_path.read_text(encoding="utf-8")
    assert "services: !override" in override
    assert "env_file:" not in override
    assert ".env" not in override
    assert "image: accept-backend:" + SHA[:12] in override
    assert "image: accept-frontend:" + SHA[:12] in override
