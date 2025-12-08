# Development Workflow

This guide outlines the development workflow, testing practices, and pull
request guidelines for the Starlink Dashboard project.

## Git Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feat/your-feature-name
```

### 2. Make Code Changes

Edit files in your feature branch. The pre-commit hooks will run on commit.

### 3. Commit Changes

```bash
git add .
git commit -m "feat: description of changes"
```

If linting fails, pre-commit will:

1. Show violations and attempted fixes
2. Stage the fixed code
3. Require you to commit again

### 4. Push and Create PR

```bash
git push origin feat/your-feature-name
```

Create a pull request from your feature branch. CI/CD will automatically run
linting checks.

### 5. Merge to Main

Once CI passes and code is reviewed, merge the PR to main/develop.

---

## Testing

### Backend Tests (Python)

```bash
cd backend/starlink-location

# Run all tests
pytest

# Run tests with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_routes.py

# Run specific test
pytest tests/test_routes.py::test_get_routes
```

### Test Requirements

- New features should include corresponding tests
- Tests must pass before merge
- Maintain >80% code coverage for refactored code

### Frontend Tests (TypeScript/React)

```bash
cd frontend/mission-planner

# Run tests
npm test

# Run tests with coverage
npm test -- --coverage
```

---

## Pull Request Guidelines

### PR Title Format

```text
<type>: <description>

Types: feat, fix, refactor, docs, test, chore
```

### PR Description Template

```markdown
## Changes

Brief description of what changed and why.

## Testing

How was this tested? Include manual smoke tests or automated test commands.

## Checklist

- [ ] Code passes linting (Black, Ruff, Prettier, ESLint)
- [ ] Existing tests pass
- [ ] New tests added (if applicable)
- [ ] Documentation updated (if applicable)
- [ ] No breaking changes introduced
```

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

## Questions?

For questions about development process, code quality standards, or tooling,
open an issue or discussion on the project repository.
