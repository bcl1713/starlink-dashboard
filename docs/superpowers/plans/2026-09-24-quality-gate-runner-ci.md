# Quality-Gate Runner and CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give local developers and GitHub Actions one pinned, root-derived
verification interface for static, backend, and frontend gates.

**Architecture:** `tools/verify` owns allowed tiers, child command order,
working directories, and exit propagation. GitHub Actions only installs each
job's prerequisites and invokes that interface. Documentation and exact-head
evidence are owned by the linked [documentation plan](2026-09-24-quality-gate-docs-verification.md).

**Tech Stack:** Python 3.13, `uv`, Black 26.5.1, Ruff 0.16.8, pytest, Node
22.12.0, npm, Vitest, TypeScript, Vite, GitHub Actions, Markdownlint, Lychee.

**Spec:**
`docs/superpowers/specs/2026-09-24-quality-gate-contract-design.md`

## Global Constraints

- `tools/verify` accepts exactly `static`, `backend`, `frontend`, and `all`.
- It derives paths from repository root, regardless of caller cwd.
- Static/frontend commands run from root; backend pytest runs from
  `backend/starlink-location`.
- Pin Black 26.5.1 and Ruff 0.16.8 only in
  `backend/starlink-location/requirements-dev.txt`.
- Do not modify production requirements, Dockerfiles, test discovery, or the
  unrelated `test` script.
- CI must call the interface and must not mask a required-check failure.
- Browser acceptance remains a scoped exact-SHA 1920x1080 CDP requirement;
  this tooling work does not create a generic browser CI job.

## Review Focus

- Unsupported tier returns status 2 and runs no child command.
- A child failure stops its tier and returns the same nonzero status.
- Nested invocation uses root paths, but backend pytest uses its intentional
  backend cwd.
- CI contains no Black/Ruff/frontend-test command copies or
  `continue-on-error` aggregation.
- Production dependencies and Dockerfiles remain untouched.

---

### Task 1: Dispatcher Contract and Development Tool Pins

**Files:**

- Create: `tools/verify`
- Create: `tools/tests/test_verify.py`
- Create: `backend/starlink-location/requirements-dev.txt`

**Interfaces:**

- `tools/verify {static|backend|frontend|all}` returns 0 on success, status 2
  for invalid input, or the first failed child status.
- `tier_commands(tier: str) -> list[tuple[list[str], Path]]` maps commands to
  their explicit cwd.

- [ ] **Step 1: Write failing subprocess contract tests**

```python
import importlib.machinery
import importlib.util
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT / "tools/verify"

def run(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VERIFY), *args], cwd=cwd, text=True,
        capture_output=True, check=False,
    )

def test_invalid_tier_returns_usage_without_running_child():
    result = run("invalid")
    assert result.returncode == 2
    assert "static|backend|frontend|all" in result.stderr

def load_verify():
    loader = importlib.machinery.SourceFileLoader("verify", str(VERIFY))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_backend_command_uses_backend_directory(monkeypatch):
    module = load_verify()
    calls = []
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda command, cwd, check: calls.append((command, cwd))
        or types.SimpleNamespace(returncode=0),
    )
    assert module.main(["tools/verify", "backend"]) == 0
    assert calls == [
        (module.tier_commands("backend")[0][0], module.BACKEND),
    ]
```

- [ ] **Step 2: Confirm the tests fail**

Run:

```bash
uv run --with-requirements backend/starlink-location/requirements.txt \
  pytest tools/tests/test_verify.py -v
```

Expected: FAIL because `tools/verify` does not exist.

- [ ] **Step 3: Add pins and minimal dispatcher**

Create `backend/starlink-location/requirements-dev.txt`:

```text
-r requirements.txt
black==26.5.1
ruff==0.16.8
```

Implement `tools/verify` with this command model:

```python
ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend/starlink-location"
Command = tuple[list[str], Path]

static: list[Command] = [
    (["uv", "run", "--with-requirements", "backend/starlink-location/requirements-dev.txt", "black", "--check", "--diff", "backend/starlink-location/app", "backend/starlink-location/tests"], ROOT),
    (["uv", "run", "--with-requirements", "backend/starlink-location/requirements-dev.txt", "ruff", "check", "backend/starlink-location/app", "backend/starlink-location/tests"], ROOT),
    (["python", "tools/check_filename_convention.py"], ROOT),
    (["npm", "--prefix", "frontend/mission-planner", "exec", "--", "prettier", "--check", "frontend/mission-planner/src/**/*.{ts,tsx,js,jsx,json,md}"], ROOT),
    (["npm", "--prefix", "frontend/mission-planner", "run", "lint"], ROOT),
    (["npx", "markdownlint-cli2", "docs/**/*.md"], ROOT),
    (["lychee", "--no-progress", "docs/"], ROOT),
]
backend: list[Command] = [
    (["uv", "run", "--with-requirements", "backend/starlink-location/requirements-dev.txt", "pytest", "tests/", "-q"], BACKEND),
]
frontend: list[Command] = [
    (["npm", "--prefix", "frontend/mission-planner", "run", "test:unit"], ROOT),
    (["npm", "--prefix", "frontend/mission-planner", "run", "build"], ROOT),
]
```

Use `subprocess.run(command, cwd=cwd, check=False)`, print the command with
its cwd, and stop at the first nonzero result. Mark it executable.

- [ ] **Step 4: Run dispatcher tests from root and nested cwd**

```bash
uv run --with-requirements backend/starlink-location/requirements.txt \
  pytest tools/tests/test_verify.py -v
(cd backend/starlink-location && ../../tools/verify invalid; test $? -eq 2)
```

Expected: PASS; the second command prints supported tiers and exits 2.

- [ ] **Step 5: Commit the contract**

```bash
git add tools/verify tools/tests/test_verify.py \
  backend/starlink-location/requirements-dev.txt
git commit -m "feat(quality): add canonical verification runner"
```

### Task 2: CI Delegation Contract

**Files:**

- Modify: `.github/workflows/lint.yml`
- Create: `tools/tests/test_quality_gate_workflow.py`

**Interfaces:**

- CI jobs are named `Static Quality Gate`, `Backend Test Gate`, and
  `Frontend Test and Build Gate`.
- Each job calls exactly one matching `./tools/verify` tier after setup.

- [ ] **Step 1: Write failing workflow contract tests**

```python
WORKFLOW = Path(".github/workflows/lint.yml").read_text()

def test_workflow_uses_only_canonical_quality_commands():
    assert "./tools/verify static" in WORKFLOW
    assert "./tools/verify backend" in WORKFLOW
    assert "./tools/verify frontend" in WORKFLOW
    assert "continue-on-error" not in WORKFLOW
    assert "black --check" not in WORKFLOW
    assert "ruff check" not in WORKFLOW
```

Also assert pinned `uv` setup for static/backend and Node `22.12.0` setup for
frontend, and that the static job installs Markdownlint and Lychee.

- [ ] **Step 2: Confirm the workflow test fails**

```bash
uv run --with-requirements backend/starlink-location/requirements.txt \
  pytest tools/tests/test_quality_gate_workflow.py -v
```

Expected: FAIL because existing CI duplicates commands and masks failures.

- [ ] **Step 3: Replace `lint.yml` with three thin caller jobs**

- Static: checkout, Python 3.13, `uv`, Node 22.12.0, `npm ci` in frontend,
  install `markdownlint-cli2` and Lychee, then `./tools/verify static`.
- Backend: checkout, Python 3.13, `uv`, install backend requirements, then
  `./tools/verify backend`.
- Frontend: checkout, Node 22.12.0, `npm ci` in frontend, then
  `./tools/verify frontend`.

Do not retain advisory-summary logic or copies of the dispatcher-owned checks.

- [ ] **Step 4: Run contract tests and static tier**

```bash
uv run --with-requirements backend/starlink-location/requirements.txt \
  pytest tools/tests/test_quality_gate_workflow.py -v
./tools/verify static
```

Expected: PASS. If Markdownlint reports only this plan, defer its publication
until the linked documentation plan is committed, then rerun static.

- [ ] **Step 5: Commit CI migration**

```bash
git add .github/workflows/lint.yml tools/tests/test_quality_gate_workflow.py
git commit -m "ci(quality): delegate checks to canonical runner"
```
