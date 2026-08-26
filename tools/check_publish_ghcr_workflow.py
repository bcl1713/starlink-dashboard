#!/usr/bin/env python3
"""Validate the Docker build contract in the GHCR publish workflow."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path


EXPECTED_IMAGES = {
    "starlink-location": (
        "./backend/starlink-location",
        "./backend/starlink-location/Dockerfile",
    ),
    "mission-planner": (
        "./frontend/mission-planner",
        "./frontend/mission-planner/Dockerfile",
    ),
    "prometheus": (".", "./deployment/prometheus/Dockerfile"),
    "grafana": (".", "./deployment/grafana/Dockerfile"),
}
IMAGE_PATTERN = re.compile(r"^\s*-\s*image:\s*(?P<image>.+?)\s*$")
FIELD_PATTERN = re.compile(r"^\s+(?P<field>context|file):\s*(?P<value>\S+)\s*$")


def workflow_entries(workflow_path: Path) -> list[dict[str, str]]:
    """Return the publish matrix entries without requiring a YAML dependency."""
    entries: list[dict[str, str]] = []
    current_entry: dict[str, str] | None = None

    for line in workflow_path.read_text(encoding="utf-8").splitlines():
        image_match = IMAGE_PATTERN.match(line)
        if image_match:
            current_entry = {"image": image_match.group("image")}
            entries.append(current_entry)
            continue

        field_match = FIELD_PATTERN.match(line)
        if current_entry is not None and field_match:
            current_entry[field_match.group("field")] = field_match.group("value")

    return entries


def resolve_from_repo(repo_root: Path, value: str) -> Path:
    """Resolve a repository-relative workflow value without following outside it."""
    resolved = (repo_root / value).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError:
        raise ValueError(f"must stay within the checkout: {value}") from None
    return resolved


def validate_publish_workflow(repo_root: Path, workflow_path: Path) -> list[str]:
    """Validate each expected GHCR image has an explicit, usable build contract."""
    errors: list[str] = []
    entries = workflow_entries(workflow_path)
    image_names = [entry["image"].rsplit("/", maxsplit=1)[-1] for entry in entries]
    image_counts = Counter(image_names)
    found_images = set(image_names)
    workflow_text = workflow_path.read_text(encoding="utf-8")

    if "matrix.file || 'Dockerfile'" in workflow_text:
        errors.append("build action must not fall back to an ambiguous Dockerfile")

    expected_entry_count = len(EXPECTED_IMAGES)
    if len(entries) != expected_entry_count:
        errors.append(
            "publish matrix must contain exactly "
            f"{expected_entry_count} entries, got {len(entries)}"
        )

    duplicate_images = sorted(
        image_name
        for image_name, count in image_counts.items()
        if image_name in EXPECTED_IMAGES and count > 1
    )
    if duplicate_images:
        errors.append(
            "duplicate publish matrix images: "
            f"{', '.join(duplicate_images)}"
        )

    for entry in entries:
        image_name = entry["image"].rsplit("/", maxsplit=1)[-1]
        expected = EXPECTED_IMAGES.get(image_name)
        if expected is None:
            errors.append(f"unexpected publish matrix image: {image_name}")
            continue

        expected_context, expected_file = expected
        context = entry.get("context")
        dockerfile = entry.get("file")
        if context != expected_context:
            errors.append(
                f"{image_name} context must be {expected_context}, got {context!r}"
            )
        if dockerfile != expected_file:
            errors.append(
                f"{image_name} Dockerfile must be {expected_file}, got {dockerfile!r}"
            )
        if context is not None:
            try:
                context_path = resolve_from_repo(repo_root, context)
            except ValueError as error:
                errors.append(f"{image_name} context {error}")
            else:
                if not context_path.is_dir():
                    errors.append(f"{image_name} context does not exist: {context}")
        if dockerfile is not None:
            try:
                dockerfile_path = resolve_from_repo(repo_root, dockerfile)
            except ValueError as error:
                errors.append(f"{image_name} Dockerfile {error}")
            else:
                if not dockerfile_path.is_file():
                    errors.append(f"{image_name} Dockerfile does not exist: {dockerfile}")

    missing_images = sorted(set(EXPECTED_IMAGES) - found_images)
    if missing_images:
        errors.append(f"missing publish matrix images: {', '.join(missing_images)}")

    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    workflow_path = repo_root / ".github" / "workflows" / "publish-ghcr.yml"
    errors = validate_publish_workflow(repo_root, workflow_path)
    if errors:
        print("GHCR publish workflow contract failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("GHCR publish workflow contract passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
