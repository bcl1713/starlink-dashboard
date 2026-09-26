import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/lint.yml"
VERIFY = ROOT / "tools/verify"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def job_block(workflow: str, job_id: str, next_job_id: str | None = None) -> str:
    start = workflow.index(f"  {job_id}:\n")
    end = workflow.index(f"  {next_job_id}:\n", start) if next_job_id else len(workflow)
    return workflow[start:end]


def static_gate_script() -> str:
    static = job_block(workflow_text(), "static", "backend")
    match = re.search(r"        run: \|\n((?:          .*\n?)+)", static)
    assert match is not None
    return "\n".join(line[10:] for line in match.group(1).splitlines())


def git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def commit(repository: Path, name: str, content: str) -> str:
    (repository / name).write_text(content, encoding="utf-8")
    git(repository, "add", name)
    git(repository, "commit", "-m", name)
    return git(repository, "rev-parse", "HEAD")


def repository_with_origin(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
    repository = tmp_path / "repository"
    git(repository.parent, "clone", str(origin), str(repository))
    git(repository, "config", "user.email", "ci@example.test")
    git(repository, "config", "user.name", "CI test")
    git(repository, "checkout", "-b", "main")
    commit(repository, "base.txt", "base\n")
    git(repository, "push", "-u", "origin", "main")
    return repository


def run_static_gate(repository: Path, **environment: str) -> subprocess.CompletedProcess[str]:
    verifier = repository / "tools/verify"
    verifier.parent.mkdir(exist_ok=True)
    verifier.write_text(
        "#!/usr/bin/env bash\n"
        "git cat-file -e \"${ACCEPTANCE_POLICY_BASE_SHA}^{commit}\"\n"
        "git merge-base --is-ancestor \"$ACCEPTANCE_POLICY_BASE_SHA\" HEAD\n"
        "printf '%s\\n' \"$ACCEPTANCE_POLICY_BASE_SHA\"\n",
        encoding="utf-8",
    )
    verifier.chmod(0o755)
    return subprocess.run(
        ["bash", "-c", static_gate_script()],
        cwd=repository,
        text=True,
        capture_output=True,
        env={**os.environ, **environment},
    )


def test_workflow_uses_only_canonical_quality_commands():
    workflow = workflow_text()

    assert "./tools/verify static" in workflow
    assert "./tools/verify backend" in workflow
    assert "./tools/verify frontend" in workflow
    assert "continue-on-error" not in workflow
    assert "black --check" not in workflow
    assert "ruff check" not in workflow


def test_workflow_has_three_named_thin_caller_jobs():
    workflow = workflow_text()
    static = job_block(workflow, "static", "backend")
    backend = job_block(workflow, "backend", "frontend")
    frontend = job_block(workflow, "frontend")

    assert "name: Static Quality Gate" in static
    assert "name: Backend Test Gate" in backend
    assert "name: Frontend Test and Build Gate" in frontend
    assert static.count("./tools/verify") == 1
    assert backend.count("./tools/verify") == 1
    assert frontend.count("./tools/verify") == 1
    assert "./tools/verify static" in static
    assert "./tools/verify backend" in backend
    assert "./tools/verify frontend" in frontend


def test_static_job_installs_its_runner_prerequisites():
    static = job_block(workflow_text(), "static", "backend")

    assert "actions/setup-python@v5" in static
    assert 'python-version: "3.13"' in static
    assert "astral-sh/setup-uv@v6" in static
    assert (
        "python -m pip install -r backend/starlink-location/requirements-dev.txt"
        in static
    )
    assert "actions/setup-node@v4" in static
    assert 'node-version: "22.12.0"' in static
    assert "npm ci --legacy-peer-deps" in static
    assert "npm install --global markdownlint-cli2" in static
    assert "taiki-e/install-action@v2" in static
    assert "lychee@0.20.1" in static


def test_static_job_exports_a_reachable_policy_base_for_pull_requests(tmp_path: Path):
    repository = repository_with_origin(tmp_path)
    base = git(repository, "rev-parse", "HEAD")
    git(repository, "checkout", "-b", "feature")
    commit(repository, "feature.txt", "feature\n")

    result = run_static_gate(
        repository,
        EVENT_NAME="pull_request",
        PR_BASE_REF="main",
        PUSH_BASE_SHA="",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == base


def test_static_job_exports_push_before_when_it_is_an_ancestor(tmp_path: Path):
    repository = repository_with_origin(tmp_path)
    before = git(repository, "rev-parse", "HEAD")
    commit(repository, "next.txt", "next\n")

    result = run_static_gate(
        repository,
        EVENT_NAME="push",
        PR_BASE_REF="",
        PUSH_BASE_SHA=before,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == before


def test_static_job_uses_merge_base_for_a_nonancestor_push_before(tmp_path: Path):
    repository = repository_with_origin(tmp_path)
    base = git(repository, "rev-parse", "HEAD")
    git(repository, "checkout", "-b", "previous")
    before = commit(repository, "previous.txt", "previous\n")
    git(repository, "checkout", "main")
    commit(repository, "replacement.txt", "replacement\n")

    result = run_static_gate(
        repository,
        EVENT_NAME="push",
        PR_BASE_REF="",
        PUSH_BASE_SHA=before,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == base


def test_static_job_uses_head_parent_for_a_zero_push_before(tmp_path: Path):
    repository = repository_with_origin(tmp_path)
    parent = git(repository, "rev-parse", "HEAD")
    commit(repository, "next.txt", "next\n")

    result = run_static_gate(
        repository,
        EVENT_NAME="push",
        PR_BASE_REF="",
        PUSH_BASE_SHA="0" * 40,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == parent


def test_static_job_fails_closed_when_a_zero_push_before_has_no_parent(tmp_path: Path):
    repository = tmp_path / "repository"
    git(repository.parent, "init", str(repository))
    git(repository, "config", "user.email", "ci@example.test")
    git(repository, "config", "user.name", "CI test")
    commit(repository, "root.txt", "root\n")

    result = run_static_gate(
        repository,
        EVENT_NAME="push",
        PR_BASE_REF="",
        PUSH_BASE_SHA="0" * 40,
    )

    assert result.returncode == 1
    assert result.stderr.strip() == (
        "Unable to derive a comparable policy base for this push event"
    )


def test_static_runner_invokes_the_markdownlint_executable_ci_installs():
    runner = VERIFY.read_text(encoding="utf-8")

    assert '["markdownlint-cli2", "docs/**/*.md"]' in runner
    assert '["npx", "markdownlint-cli2"' not in runner


def test_backend_and_frontend_jobs_install_their_runner_prerequisites():
    workflow = workflow_text()
    backend = job_block(workflow, "backend", "frontend")
    frontend = job_block(workflow, "frontend")

    assert "actions/setup-python@v5" in backend
    assert 'python-version: "3.13"' in backend
    assert "astral-sh/setup-uv@v6" in backend
    assert "requirements-dev.txt" in backend
    assert "actions/setup-node@v4" in frontend
    assert 'node-version: "22.12.0"' in frontend
    assert "npm ci --legacy-peer-deps" in frontend
