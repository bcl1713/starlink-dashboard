from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from github_retention import (
    GitHubRetentionError,
    inventory_ghcr_versions,
    select_expired_dockerbuild_artifacts,
)

WORKFLOW = ".github/workflows/publish-ghcr.yml"
CLI_PATH = Path(__file__).resolve().parents[1] / "github_retention_cli.py"
SHA_A = "a" * 40
SHA_B = "b" * 40


def _complete(items: list[dict[str, object]], key: str) -> dict[str, object]:
    return {key: items, "pagination": {"complete": True}}


def runs_fixture(*, has_next_page: bool = False) -> dict[str, object]:
    return {
        "workflow_runs": [
            {
                "id": 11,
                "path": WORKFLOW,
                "head_branch": "dev",
                "status": "completed",
                "created_at": "2026-09-27T12:00:00Z",
                "updated_at": "2026-09-27T12:00:00Z",
            },
            {
                "id": 12,
                "path": WORKFLOW,
                "head_branch": "dev",
                "status": "completed",
                "created_at": "2026-09-27T11:00:00Z",
                "updated_at": "2026-09-27T11:00:00Z",
            },
            {
                "id": 13,
                "path": WORKFLOW,
                "head_branch": "dev",
                "status": "completed",
                "created_at": "2026-09-27T10:00:00Z",
                "updated_at": "2026-09-27T10:00:00Z",
            },
            {
                "id": 14,
                "path": WORKFLOW,
                "head_branch": "dev",
                "status": "completed",
                "created_at": "2026-09-27T09:00:00Z",
                "updated_at": "2026-09-27T09:00:00Z",
            },
            {
                "id": 15,
                "path": WORKFLOW,
                "head_branch": "dev",
                "status": "completed",
                "created_at": "2026-09-27T08:00:00Z",
                "updated_at": "2026-09-27T08:00:00Z",
            },
        ],
        "pagination": {"complete": not has_next_page},
    }


def artifacts_fixture() -> dict[str, object]:
    return _complete(
        [
            {"id": 100, "name": "keep.dockerbuild", "workflow_run": {"id": 11}},
            {"id": 101, "name": "expired-one.dockerbuild", "workflow_run": {"id": 14}},
            {"id": 102, "name": "expired-two.dockerbuild", "workflow_run": {"id": 15}},
            {"id": 103, "name": "expired-log", "workflow_run": {"id": 14}},
        ],
        "artifacts",
    )


def package_versions_fixture() -> dict[str, object]:
    return _complete(
        [
            {
                "id": 1,
                "updated_at": "2026-09-27T12:00:00Z",
                "metadata": {"container": {"tags": [f"sha-{SHA_A}"]}},
            },
            {
                "id": 2,
                "updated_at": "2026-09-27T11:00:00Z",
                "metadata": {"container": {"tags": ["latest"]}},
            },
        ],
        "versions",
    )


def test_selector_keeps_current_plus_two_prior_dev_runs() -> None:
    selected = select_expired_dockerbuild_artifacts(
        runs_fixture(), artifacts_fixture(), WORKFLOW, "dev", current_run_id=11
    )

    assert [artifact.artifact_id for artifact in selected] == [101, 102]


def test_ghcr_inventory_never_returns_deletion() -> None:
    inventory = inventory_ghcr_versions(package_versions_fixture())

    assert inventory.old_sha_versions == ()
    assert [version.version_id for version in inventory.retained_sha_versions] == [1]
    assert inventory.non_sha_versions == ("latest",)
    assert inventory.anomalies == ()
    assert not hasattr(inventory, "delete")


def test_incomplete_pagination_blocks_partial_deletion() -> None:
    with pytest.raises(GitHubRetentionError, match="pagination"):
        select_expired_dockerbuild_artifacts(
            runs_fixture(has_next_page=True), {}, WORKFLOW, "dev", current_run_id=11
        )


def test_foreign_or_in_progress_run_blocks_selection() -> None:
    runs = runs_fixture()
    runs["workflow_runs"].append(
        {
            "id": 16,
            "path": WORKFLOW,
            "head_branch": "release",
            "status": "in_progress",
            "created_at": "2026-09-27T13:00:00Z",
        }
    )

    with pytest.raises(GitHubRetentionError, match="foreign or incomplete"):
        select_expired_dockerbuild_artifacts(
            runs, artifacts_fixture(), WORKFLOW, "dev", current_run_id=11
        )


def test_cli_emits_report_only_json_inventory(tmp_path: Path) -> None:
    versions_path = tmp_path / "versions.json"
    versions_path.write_text(json.dumps(package_versions_fixture()), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(CLI_PATH),
            "ghcr-inventory",
            "--versions",
            str(versions_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert json.loads(completed.stdout) == {
        "anomalies": [],
        "non_sha_versions": ["latest"],
        "old_sha_versions": [],
        "retained_sha_versions": [{"tags": [f"sha-{SHA_A}"], "version_id": 1}],
    }


def test_cli_returns_nonzero_when_ghcr_inventory_contains_anomalies(
    tmp_path: Path,
) -> None:
    versions = package_versions_fixture()
    versions["versions"][0].pop("updated_at")
    versions_path = tmp_path / "versions.json"
    versions_path.write_text(json.dumps(versions), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(CLI_PATH),
            "ghcr-inventory",
            "--versions",
            str(versions_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert json.loads(completed.stdout)["anomalies"] == [
        "GHCR version has a missing or invalid date"
    ]
