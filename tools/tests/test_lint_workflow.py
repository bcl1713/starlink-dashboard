"""Structural regression tests for the code-quality workflow."""

from pathlib import Path
from typing import Any

import yaml

WORKFLOW = Path(__file__).parents[2] / ".github" / "workflows" / "lint.yml"


def _triggers() -> dict[str, Any]:
    parsed = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # YAML 1.1 treats the unquoted workflow key `on` as boolean true.
    return parsed.get("on", parsed.get(True))


def test_lint_workflow_targets_current_branches_and_preserves_jobs() -> None:
    parsed = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = _triggers()

    assert set(triggers) == {"pull_request", "push"}
    assert triggers["pull_request"]["branches"] == ["main", "dev"]
    assert triggers["push"]["branches"] == ["main", "dev"]
    assert "develop" not in WORKFLOW.read_text(encoding="utf-8")
    assert set(parsed["jobs"]) == {"lint"}
    assert parsed["jobs"]["lint"]["steps"]
