# Development Workflow

[Back to Contributing](../CONTRIBUTING.md)

---

## Development Workflow Steps

### 1. Create a Feature Branch

```bash
git checkout -b feat/your-feature-name
```

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
git push origin feat/your-feature-name
```

Create a pull request from your feature branch. CI/CD will automatically run
linting checks.

---

### 5. Merge to Main

Once CI passes and code is reviewed, merge the PR to main/develop.

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

- All checks must pass before merging to main/develop branches
- Check status appears in PR conversation

---

## Common Tasks

### Format All Code

```bash
# Python
black backend/starlink-location/app
ruff check --fix backend/starlink-location/app

# JavaScript/TypeScript
cd frontend/mission-planner
npx prettier --write "src/**/*.{ts,tsx,js,jsx}"

# Markdown
npx prettier --write "docs/**/*.md"
```

---

### Check Linting Without Formatting

```bash
# Python
black --check backend/starlink-location/app
ruff check backend/starlink-location/app

# JavaScript/TypeScript
cd frontend/mission-planner
npx prettier --check "src/**/*.{ts,tsx,js,jsx}"
npx eslint src

# Markdown
npx prettier --check "docs/**/*.md"
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

[Back to Contributing](../CONTRIBUTING.md)
