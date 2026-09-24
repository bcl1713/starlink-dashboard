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
