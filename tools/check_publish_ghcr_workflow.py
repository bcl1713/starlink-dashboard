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
}
IMAGE_PATTERN = re.compile(r"^\s*-\s*image:\s*(?P<image>.+?)\s*$")
FIELD_PATTERN = re.compile(r"^\s+(?P<field>context|file):\s*(?P<value>\S+)\s*$")
PUBLISH_JOB_PATTERN = re.compile(r"^  publish:\s*$")
JOB_PATTERN = re.compile(r"^  [A-Za-z0-9_-]+:\s*$")
RUNNER_PATTERN = re.compile(r"^\s+runs-on:\s*(?P<runner>\S+)\s*$")
USES_PATTERN = re.compile(r"^\s+(?:-\s+)?uses:\s*(?P<action>\S+)\s*$")
EXPECTED_CANDIDATE_SHA_BUILD_ARG = (
    "          build-args: |\n"
    "            ACCEPTANCE_CANDIDATE_SHA=${{ github.sha }}"
)
EXPECTED_PUBLISH_ACTIONS = (
    "actions/checkout@v7",
    "docker/login-action@v4",
    "docker/setup-buildx-action@v4",
    "docker/metadata-action@v6",
    "docker/build-push-action@v7",
)


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


def job_lines(workflow_text: str, job_name: str) -> list[str]:
    """Return only lines belonging to an enabled top-level job."""
    lines: list[str] = []
    in_job = False

    for line in workflow_text.splitlines():
        if line == f"  {job_name}:":
            in_job = True
            continue
        if in_job and JOB_PATTERN.match(line):
            break
        if in_job:
            lines.append(line)

    return lines


def publish_job_lines(workflow_text: str) -> list[str]:
    """Return only lines belonging to the publish job."""
    return job_lines(workflow_text, "publish")


def publish_actions(workflow_text: str) -> list[str]:
    """Return action references from steps in the publish job only."""
    return [
        match.group("action")
        for line in publish_job_lines(workflow_text)
        if (match := USES_PATTERN.match(line))
    ]


def publish_runners(workflow_text: str) -> list[str]:
    """Return runner labels configured for the publish job only."""
    return [
        match.group("runner")
        for line in publish_job_lines(workflow_text)
        if (match := RUNNER_PATTERN.match(line))
    ]


def build_action_with_text(workflow_text: str) -> str:
    """Return the ``with`` block for the named Docker Buildx publish step."""
    publish_lines = publish_job_lines(workflow_text)
    step_start = None
    for index, line in enumerate(publish_lines):
        if line == "      - name: Build and publish image":
            step_start = index
            break

    if step_start is None:
        return ""

    step_lines = []
    for line in publish_lines[step_start:]:
        if step_lines and line.startswith("      - "):
            break
        step_lines.append(line)

    if "        uses: docker/build-push-action@v7" not in step_lines:
        return ""

    try:
        with_start = step_lines.index("        with:") + 1
    except ValueError:
        return ""

    return "\n".join(step_lines[with_start:])


def named_step_lines(workflow_text: str, job_name: str, step_name: str) -> list[str]:
    """Return an enabled named step from its job, never a commented decoy."""
    lines = job_lines(workflow_text, job_name)
    header = f"      - name: {step_name}"
    try:
        start = lines.index(header)
    except ValueError:
        return []
    step: list[str] = []
    for line in lines[start:]:
        if step and line.startswith("      - "):
            break
        step.append(line)
    if any(_is_disabled_if_line(line) for line in step):
        return []
    return step


def _without_inline_comment(value: str) -> str:
    """Remove a YAML inline comment without treating quoted hashes as comments."""
    quote: str | None = None
    for index, character in enumerate(value):
        if character in {"'", '"'}:
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
        elif character == "#" and quote is None:
            return value[:index].rstrip()
    return value.rstrip()


def _strip_outer_parentheses(expression: str) -> str:
    """Remove one wrapping parenthesis pair, but not a partial grouping."""
    if not (expression.startswith("(") and expression.endswith(")")):
        return expression

    depth = 0
    quote: str | None = None
    for index, character in enumerate(expression):
        if character in {"'", '"'}:
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
        elif quote is None and character == "(":
            depth += 1
        elif quote is None and character == ")":
            depth -= 1
            if depth == 0:
                return expression[1:-1] if index == len(expression) - 1 else expression
    return expression


def _compact_expression(expression: str) -> str:
    """Drop whitespace outside quotes while preserving literal values."""
    compacted: list[str] = []
    quote: str | None = None
    for character in expression:
        if character in {"'", '"'}:
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
        if quote is not None or not character.isspace():
            compacted.append(character)
    return "".join(compacted).lower()


def _split_top_level(expression: str, operator: str) -> list[str] | None:
    """Split an expression only at unquoted, ungrouped boolean operators."""
    operands: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    index = 0
    while index < len(expression):
        character = expression[index]
        if character in {"'", '"'}:
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
        elif quote is None:
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
            elif depth == 0 and expression.startswith(operator, index):
                operands.append(expression[start:index])
                start = index + len(operator)
                index += len(operator)
                continue
        index += 1
    if not operands:
        return None
    operands.append(expression[start:])
    return operands


def _constant_boolean(expression: str) -> bool | None:
    """Evaluate the small, literal-only subset of GitHub ``if`` expressions."""
    expression = expression.strip()
    if expression.startswith("${{") and expression.endswith("}}"):
        expression = expression[3:-2].strip()
    expression = _compact_expression(expression)
    expression = _strip_outer_parentheses(expression)

    if expression in {"true", "false"}:
        return expression == "true"
    if expression.startswith("!"):
        operand = _constant_boolean(expression[1:])
        return None if operand is None else not operand
    for operator, identity, short_circuit in (
        ("||", False, True),
        ("&&", True, False),
    ):
        operands = _split_top_level(expression, operator)
        if operands is not None:
            values = [_constant_boolean(operand) for operand in operands]
            if short_circuit in values:
                return short_circuit
            return identity if all(value is identity for value in values) else None

    comparison = re.fullmatch(
        r"(?P<left>true|false|[0-9]+|'[^']*'|\"[^\"]*\")"
        r"(?P<operator>==|!=)"
        r"(?P<right>true|false|[0-9]+|'[^']*'|\"[^\"]*\")",
        expression,
    )
    if comparison is None:
        return None
    equal = comparison.group("left") == comparison.group("right")
    return equal if comparison.group("operator") == "==" else not equal


def _is_disabled_if_line(line: str) -> bool:
    """Return whether a step's literal ``if`` condition is structurally disabled."""
    stripped = line.strip()
    if not stripped.startswith("if:"):
        return False
    return _constant_boolean(_without_inline_comment(stripped[3:])) is False


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

    runners = publish_runners(workflow_text)
    if runners != ["ubuntu-latest"]:
        errors.append(f"publish runner must be ubuntu-latest, got {runners!r}")

    if publish_actions(workflow_text) != list(EXPECTED_PUBLISH_ACTIONS):
        errors.append(
            "publish actions must be " + ", ".join(EXPECTED_PUBLISH_ACTIONS)
        )

    if EXPECTED_CANDIDATE_SHA_BUILD_ARG not in build_action_with_text(workflow_text):
        errors.append(
            "build action must pass ACCEPTANCE_CANDIDATE_SHA=${{ github.sha }}"
        )

    if "matrix.file || 'Dockerfile'" in workflow_text:
        errors.append("build action must not fall back to an ambiguous Dockerfile")

    retention_lines = job_lines(workflow_text, "retention")
    if "    needs: publish" not in retention_lines:
        errors.append("retention job must depend on successful publish")
    if (
        "    if: ${{ github.ref == 'refs/heads/dev' && needs.publish.result == 'success' }}"
        not in retention_lines
    ):
        errors.append("retention job must run only for a successful publish on dev")
    retention_permissions = (
        retention_lines[retention_lines.index("    permissions:") + 1 :][:3]
        if "    permissions:" in retention_lines
        else []
    )
    if retention_permissions != [
        "      actions: write",
        "      contents: read",
        "      packages: read",
    ]:
        errors.append("retention job permissions must be least-privileged")
    if "    env:\n      GH_TOKEN: ${{ github.token }}" not in "\n".join(
        retention_lines
    ):
        errors.append("retention gh commands must receive GH_TOKEN")

    selection_step = named_step_lines(
        workflow_text, "retention", "Select exact expired artifact IDs"
    )
    selection_text = "\n".join(selection_step)
    if (
        selection_step == []
        or selection_text.count("gh api --paginate --slurp") < 2
        or "--current-run-id \"$GITHUB_RUN_ID\"" not in selection_text
        or "pagination: {complete: true}" not in selection_text
    ):
        errors.append("retention selection step must paginate complete JSON inputs")
    if 'map(.workflow_runs[] | .path |= split("@")[0])' not in selection_text:
        errors.append(
            "retention selection step must normalize workflow paths for the CLI plan"
        )

    deletion_step = named_step_lines(
        workflow_text, "retention", "Delete only selected artifact IDs"
    )
    deletion_text = "\n".join(deletion_step)
    if (
        deletion_step == []
        or ".expired_dockerbuild_artifacts[].artifact_id" not in deletion_text
        or 'gh api --method DELETE "repos/${{ github.repository }}/actions/artifacts/$artifact_id"'
        not in deletion_text
    ):
        errors.append("retention deletion step must delete only selected artifact IDs")

    ghcr_step = named_step_lines(
        workflow_text, "retention", "Inventory GHCR versions without mutation"
    )
    ghcr_text = "\n".join(ghcr_step)
    if (
        ghcr_step == []
        or "python tools/github_retention_cli.py ghcr-inventory" not in ghcr_text
        or "gh api --paginate --slurp" not in ghcr_text
        or "gh api --method" in ghcr_text
    ):
        errors.append("GHCR inventory step must be report-only")
    expected_ghcr_query = (
        'gh api --paginate --slurp "users/${{ github.repository_owner }}/packages/'
        'container/starlink-dashboard%2F$package/versions?per_page=100" |'
    )
    # Check the live shell pipeline, not substrings in comments or disabled commands.
    ghcr_commands: list[str] = []
    if "        run: |" in ghcr_step:
        ghcr_commands = [
            line.strip()
            for line in ghcr_step[ghcr_step.index("        run: |") + 1 :]
            if line.strip() and not line.lstrip().startswith("#")
        ]
    expected_commands = [
        "set -euo pipefail",
        "for package in starlink-location mission-planner prometheus; do",
        expected_ghcr_query,
        (
            "jq '{versions: flatten, pagination: {complete: true}}'"
            ' > "retention/$package-versions.json"'
        ),
        "python tools/github_retention_cli.py ghcr-inventory \\",
        ('--versions "retention/$package-versions.json" | '
         'tee "retention/$package-ghcr-inventory.json"'),
        "done",
    ]
    # The fixed loop is a small shell contract: arbitrary commands can short-circuit
    # classification, and an absent terminator can silently skip later packages.
    if ghcr_commands != expected_commands:
        errors.append("GHCR inventory must query complete user package versions")

    upload_step = named_step_lines(workflow_text, "retention", "Upload retention plan")
    if upload_step != [
        "      - name: Upload retention plan",
        "        uses: actions/upload-artifact@v7",
        "        with:",
        "          name: publish-retention-plan-${{ github.run_id }}",
        "          path: retention/artifact-plan.json",
        "          if-no-files-found: error",
        "",
    ]:
        errors.append("retention job must upload the selected artifact plan")

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
