"""Fail-closed selectors for GitHub Actions build records and GHCR inventory."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

_SHA_TAG = re.compile(r"sha-[0-9a-f]{40}\Z")


class GitHubRetentionError(ValueError):
    """GitHub data is incomplete, ambiguous, or outside the requested boundary."""


@dataclass(frozen=True)
class DockerbuildArtifact:
    artifact_id: int
    name: str
    workflow_run_id: int


@dataclass(frozen=True)
class GhcrVersion:
    version_id: int
    tags: tuple[str, ...]


@dataclass(frozen=True)
class GhcrInventory:
    """Report-only GHCR classification; it deliberately has no mutation method."""

    old_sha_versions: tuple[GhcrVersion, ...]
    retained_sha_versions: tuple[GhcrVersion, ...]
    non_sha_versions: tuple[str, ...]
    anomalies: tuple[str, ...]


def select_expired_dockerbuild_artifacts(
    runs: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    workflow_path: str,
    ref: str,
    *,
    current_run_id: int,
) -> tuple[DockerbuildArtifact, ...]:
    """Select expired artifacts while retaining the current run and two prior runs."""
    if not isinstance(workflow_path, str) or not workflow_path:
        raise GitHubRetentionError("workflow path must be an exact nonempty string")
    if not isinstance(ref, str) or not ref:
        raise GitHubRetentionError("ref must be an exact nonempty string")
    _positive_id(current_run_id, "current run")
    run_records = _complete_list(runs, "workflow_runs", "runs")
    artifact_records = _complete_list(artifacts, "artifacts", "artifacts")

    completed_prior_runs: list[tuple[datetime, int]] = []
    seen_run_ids: set[int] = set()
    current_found = False
    for record in run_records:
        mapping = _mapping(record, "run")
        run_id = _positive_id(mapping.get("id"), "run")
        if run_id in seen_run_ids:
            raise GitHubRetentionError(f"duplicate run id: {run_id}")
        seen_run_ids.add(run_id)
        if mapping.get("path") != workflow_path or mapping.get("head_branch") != ref:
            if run_id == current_run_id:
                raise GitHubRetentionError(
                    "current workflow run does not match workflow or ref"
                )
            raise GitHubRetentionError("foreign or incomplete workflow run")
        if run_id == current_run_id:
            current_found = True
            if mapping.get("status") == "completed":
                _timestamp(mapping.get("updated_at"), "run completion")
            continue
        if mapping.get("status") != "completed":
            raise GitHubRetentionError("foreign or incomplete workflow run")
        completed_prior_runs.append(
            (_timestamp(mapping.get("updated_at"), "run completion"), run_id)
        )

    if not current_found:
        raise GitHubRetentionError("current workflow run is missing")
    completed_prior_runs.sort(reverse=True)
    if len(completed_prior_runs) != len({stamp for stamp, _ in completed_prior_runs}):
        raise GitHubRetentionError("ambiguous run completion dates")
    expired_ids = {run_id for _, run_id in completed_prior_runs[2:]}

    selected: list[DockerbuildArtifact] = []
    seen_artifact_ids: set[int] = set()
    for record in artifact_records:
        mapping = _mapping(record, "artifact")
        artifact_id = _positive_id(mapping.get("id"), "artifact")
        if artifact_id in seen_artifact_ids:
            raise GitHubRetentionError(f"duplicate artifact id: {artifact_id}")
        seen_artifact_ids.add(artifact_id)
        name = mapping.get("name")
        if not isinstance(name, str) or not name:
            raise GitHubRetentionError(f"artifact {artifact_id} has no name")
        workflow_run = _mapping(mapping.get("workflow_run"), "artifact workflow run")
        run_id = _positive_id(workflow_run.get("id"), "artifact workflow run")
        if run_id not in seen_run_ids:
            raise GitHubRetentionError(f"foreign artifact association: {artifact_id}")
        if run_id in expired_ids and name.endswith(".dockerbuild"):
            selected.append(DockerbuildArtifact(artifact_id, name, run_id))

    return tuple(sorted(selected, key=lambda artifact: artifact.artifact_id))


def inventory_ghcr_versions(versions: Mapping[str, Any]) -> GhcrInventory:
    """Classify exact immutable SHA tags without mutating GHCR."""
    records = _complete_list(versions, "versions", "GHCR versions")
    sha_versions: list[GhcrVersion] = []
    non_sha_tags: list[str] = []
    anomalies: list[str] = []
    seen_ids: set[int] = set()
    seen_tags: set[str] = set()

    for record in records:
        try:
            mapping = _mapping(record, "GHCR version")
            version_id = _positive_id(mapping.get("id"), "GHCR version")
            if version_id in seen_ids:
                raise GitHubRetentionError(f"duplicate GHCR version id: {version_id}")
            seen_ids.add(version_id)
            tags = _ghcr_tags(mapping)
            if len(tags) != len(set(tags)):
                raise GitHubRetentionError(
                    f"duplicate tags on GHCR version: {version_id}"
                )
            overlapping = seen_tags.intersection(tags)
            if overlapping:
                raise GitHubRetentionError(
                    f"duplicate GHCR tags: {', '.join(sorted(overlapping))}"
                )
            seen_tags.update(tags)
            exact_sha_tags = tuple(tag for tag in tags if _SHA_TAG.fullmatch(tag))
            other_tags = tuple(tag for tag in tags if not _SHA_TAG.fullmatch(tag))
            if other_tags:
                non_sha_tags.extend(other_tags)
            if exact_sha_tags and not other_tags:
                sha_versions.append(GhcrVersion(version_id, exact_sha_tags))
        except GitHubRetentionError as error:
            anomalies.append(str(error))

    # GitHub exposes mutable updated_at, not immutable publish completion.  It
    # may describe a tag or metadata edit, so it cannot select an expiry set.
    # Keep every SHA-only version report-only until a completion authority exists.
    if sha_versions:
        anomalies.append("GHCR updated_at is not authoritative publish completion time")
    return GhcrInventory(
        old_sha_versions=(),
        retained_sha_versions=tuple(
            sorted(sha_versions, key=lambda item: item.version_id)
        ),
        non_sha_versions=tuple(sorted(non_sha_tags)),
        anomalies=tuple(anomalies),
    )


def _complete_list(payload: Mapping[str, Any], key: str, label: str) -> Sequence[Any]:
    if not isinstance(payload, Mapping):
        raise GitHubRetentionError(f"{label} payload must be an object")
    pagination = payload.get("pagination")
    if not isinstance(pagination, Mapping) or pagination.get("complete") is not True:
        raise GitHubRetentionError(f"{label} pagination is incomplete or ambiguous")
    records = payload.get(key)
    if not isinstance(records, list):
        raise GitHubRetentionError(f"{label} payload must contain a list of {key}")
    return records


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GitHubRetentionError(f"{label} must be an object")
    return value


def _positive_id(value: Any, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise GitHubRetentionError(f"{label} id must be a positive integer")
    return value


def _timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise GitHubRetentionError(f"{label} has a missing or invalid date")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise GitHubRetentionError(f"{label} has a missing or invalid date") from error
    if parsed.tzinfo is None:
        raise GitHubRetentionError(f"{label} has a missing or invalid date")
    return parsed


def _ghcr_tags(version: Mapping[str, Any]) -> tuple[str, ...]:
    metadata = _mapping(version.get("metadata"), "GHCR version metadata")
    container = _mapping(metadata.get("container"), "GHCR container metadata")
    tags = container.get("tags")
    if not isinstance(tags, list) or not all(
        isinstance(tag, str) and tag for tag in tags
    ):
        raise GitHubRetentionError("GHCR version tags must be a nonempty string list")
    return tuple(tags)
