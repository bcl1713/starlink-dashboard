# Development Workflow

[Back to Contributing](../../CONTRIBUTING.md)

---

## Development Workflow Steps

### 1. Create an Isolated Feature Worktree

Keep the primary checkout on `dev` and start each task in its own worktree:

```bash
git fetch origin --prune
git worktree add .worktrees/your-feature-name -b feat/your-feature-name origin/dev
cd .worktrees/your-feature-name
```

See [Development Workflow](../development/workflow.md#git-workflow) for the
complete workflow and cleanup commands.

---

### 2. Make Code Changes

Edit files in your feature branch. The pre-commit hooks will run on commit.

---

### 3. Commit Changes

```bash
git add .
git commit -m "feat: description of changes"
```

If linting fails, pre-commit will:

1. Show violations and attempted fixes
2. Stage the fixed code
3. Require you to commit again

---

### 4. Push and Create PR

```bash
git push -u origin feat/your-feature-name
gh pr create --base dev
```

Create a pull request from your feature branch against `dev`. CI/CD will
automatically run linting checks.

---

### 5. Merge to `dev` and Clean Up

Once required checks pass and code is reviewed, merge the PR to `dev`. Remove
its worktree, local and remote feature branches, and task-owned temporary test
resources after merge. Keep the worktree while the PR is open. See the
[cleanup commands](../development/workflow.md#6-clean-up-after-merge).

---

## Pre-commit Hooks

The project uses pre-commit hooks to automatically run linting tools before each
commit, ensuring code quality is enforced locally.

### Installation

```bash
# Install pre-commit framework
pip install pre-commit

# Install git hooks in this repository
pre-commit install
```

### What Runs on Commit

When you run `git commit`, the following tools run automatically:

- Black (Python formatting)
- Ruff (Python linting)
- Prettier (JavaScript/TypeScript/Markdown formatting)
- ESLint (JavaScript/TypeScript linting)
- Markdownlint (Markdown linting)

### Bypassing Pre-commit Hooks

If necessary, you can bypass pre-commit hooks (not recommended):

```bash
git commit --no-verify
```

---

## CI/CD Linting Pipeline

GitHub Actions automatically runs linting checks on all pull requests and
pushes. Checks are defined in `.github/workflows/lint.yml`.

**CI Pipeline includes:**

- Black formatting check
- Ruff linting check
- Prettier formatting check
- ESLint check
- Markdownlint check

**Status Checks:**

- All checks must pass before merging to `dev`
- Check status appears in PR conversation

---

## Common Tasks

### Format All Code

Run from the repository root after installing the
[Quality Gates prerequisites](quality-gates.md#prerequisites).

```bash
# Python
black backend/starlink-location/app
ruff check --fix backend/starlink-location/app

# JavaScript/TypeScript
npm --prefix frontend/mission-planner exec -- prettier --write "frontend/mission-planner/src/**/*.{ts,tsx,js,jsx}"

# Markdown
npm --prefix frontend/mission-planner exec -- prettier --write "docs/**/*.md"
```

---

### Check Linting Without Formatting

For the complete local/CI checks, use `./tools/verify static` from the
repository root as documented in [Quality Gates](quality-gates.md). The
following focused commands also run from the repository root:

```bash
# Python
black --check backend/starlink-location/app
ruff check backend/starlink-location/app

# JavaScript/TypeScript
npm --prefix frontend/mission-planner exec -- prettier --check "frontend/mission-planner/src/**/*.{ts,tsx,js,jsx}"
npm --prefix frontend/mission-planner run lint

# Markdown
npm --prefix frontend/mission-planner exec -- prettier --check "docs/**/*.md"
markdownlint-cli2 "docs/**/*.md"
```

---

### Run Local Pre-commit Checks

```bash
# Run all hooks on staged files
pre-commit run

# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files
```

---

[Back to Contributing](../../CONTRIBUTING.md)
