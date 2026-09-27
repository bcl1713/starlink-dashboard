"""Emit report-only GitHub retention selections from complete JSON fixtures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from github_retention import (
    GitHubRetentionError,
    inventory_ghcr_versions,
    select_expired_dockerbuild_artifacts,
)


def _json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GitHubRetentionError(f"cannot read JSON input {path}: {error}") from error
    if not isinstance(payload, dict):
        raise GitHubRetentionError(f"JSON input {path} must be an object")
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    select = commands.add_parser("select-artifacts")
    select.add_argument("--runs", type=Path, required=True)
    select.add_argument("--artifacts", type=Path, required=True)
    select.add_argument("--workflow", required=True)
    select.add_argument("--ref", required=True)

    inventory = commands.add_parser("ghcr-inventory")
    inventory.add_argument("--versions", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "select-artifacts":
            selected = select_expired_dockerbuild_artifacts(
                _json_object(arguments.runs),
                _json_object(arguments.artifacts),
                arguments.workflow,
                arguments.ref,
            )
            output: dict[str, object] = {
                "expired_dockerbuild_artifacts": [
                    {
                        "artifact_id": artifact.artifact_id,
                        "name": artifact.name,
                        "workflow_run_id": artifact.workflow_run_id,
                    }
                    for artifact in selected
                ]
            }
        else:
            inventory = inventory_ghcr_versions(_json_object(arguments.versions))
            output = {
                "old_sha_versions": [
                    {"version_id": version.version_id, "tags": list(version.tags)}
                    for version in inventory.old_sha_versions
                ],
                "non_sha_versions": list(inventory.non_sha_versions),
                "anomalies": list(inventory.anomalies),
            }
    except GitHubRetentionError as error:
        print(json.dumps({"error": str(error)}, sort_keys=True))
        return 2
    print(json.dumps(output, sort_keys=True))
    if arguments.command == "ghcr-inventory" and output["anomalies"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
