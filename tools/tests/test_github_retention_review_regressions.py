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


def _complete(items: list[dict[str, object]], key: str) -> dict[str, object]:
    return {key: items, "pagination": {"complete": True}}


def _run(
    run_id: int,
    *,
    updated_at: str,
    created_at: str = "2026-09-01T00:00:00Z",
    status: str = "completed",
    ref: str = "dev",
) -> dict[str, object]:
    return {
        "id": run_id,
        "path": WORKFLOW,
        "head_branch": ref,
        "status": status,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def test_selector_protects_explicit_current_and_ranks_prior_by_completion_time() -> (
    None
):
    runs = _complete(
        [
            _run(
                50, updated_at="2026-09-27T05:00:00Z", created_at="2026-09-27T01:00:00Z"
            ),
            _run(
                40, updated_at="2026-09-27T04:00:00Z", created_at="2026-09-27T02:00:00Z"
            ),
            _run(
                30, updated_at="2026-09-27T03:00:00Z", created_at="2026-09-27T03:00:00Z"
            ),
            _run(
                20, updated_at="2026-09-27T02:00:00Z", created_at="2026-09-27T04:00:00Z"
            ),
            _run(
                10,
                updated_at="2026-09-27T01:00:00Z",
                created_at="2026-09-27T05:00:00Z",
                status="in_progress",
            ),
        ],
        "workflow_runs",
    )
    artifacts = _complete(
        [
            {
                "id": run_id,
                "name": f"{run_id}.dockerbuild",
                "workflow_run": {"id": run_id},
            }
            for run_id in (50, 40, 30, 20, 10)
        ],
        "artifacts",
    )

    selected = select_expired_dockerbuild_artifacts(
        runs, artifacts, WORKFLOW, "dev", current_run_id=10
    )

    assert [artifact.artifact_id for artifact in selected] == [20, 30]


@pytest.mark.parametrize("updated_at", [None, "2026-09-27T04:00:00Z"])
def test_selector_rejects_missing_or_tied_completed_completion_times(
    updated_at: str | None,
) -> None:
    runs = _complete(
        [
            _run(10, updated_at="2026-09-27T05:00:00Z"),
            _run(20, updated_at="2026-09-27T04:00:00Z"),
            _run(30, updated_at="2026-09-27T03:00:00Z"),
            _run(40, updated_at=updated_at or "2026-09-27T02:00:00Z"),
        ],
        "workflow_runs",
    )
    if updated_at is None:
        runs["workflow_runs"][3].pop("updated_at")
    else:
        runs["workflow_runs"][3]["updated_at"] = updated_at

    with pytest.raises(GitHubRetentionError, match="completion"):
        select_expired_dockerbuild_artifacts(
            runs, _complete([], "artifacts"), WORKFLOW, "dev", current_run_id=10
        )


def test_selector_rejects_current_run_with_wrong_workflow_or_ref() -> None:
    runs = _complete(
        [_run(10, updated_at="2026-09-27T05:00:00Z", ref="release")],
        "workflow_runs",
    )

    with pytest.raises(GitHubRetentionError, match="current"):
        select_expired_dockerbuild_artifacts(
            runs, _complete([], "artifacts"), WORKFLOW, "dev", current_run_id=10
        )


def test_ghcr_inventory_only_reports_sha_versions_beyond_newest_three() -> None:
    versions = _complete(
        [
            {
                "id": version_id,
                "updated_at": f"2026-09-27T0{version_id}:00:00Z",
                "metadata": {"container": {"tags": [f"sha-{str(version_id) * 40}"]}},
            }
            for version_id in range(1, 6)
        ]
        + [
            {
                "id": 99,
                "updated_at": "2026-09-27T12:00:00Z",
                "metadata": {"container": {"tags": ["latest"]}},
            }
        ],
        "versions",
    )

    inventory = inventory_ghcr_versions(versions)

    assert [version.version_id for version in inventory.retained_sha_versions] == [
        5,
        4,
        3,
    ]
    assert [version.version_id for version in inventory.old_sha_versions] == [2, 1]
    assert inventory.non_sha_versions == ("latest",)


@pytest.mark.parametrize("argv", [[], ["select-artifacts"], ["bad-command"]])
def test_cli_invalid_arguments_emit_json_error_envelope(argv: list[str]) -> None:
    completed = subprocess.run(
        [sys.executable, str(CLI_PATH), *argv],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert json.loads(completed.stdout)["error"]
    assert completed.stderr == ""
