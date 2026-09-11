# Development Workflow

This guide outlines the development workflow, testing practices, and pull
request guidelines for the Starlink Dashboard project.

## Git Workflow

### 1. Choose the Base Branch

Use `dev` as the default base for enhancements and non-urgent fixes. Keep `main`
reserved for stable mission use and release tags. Branch from `main` only for
urgent hotfixes that must reach active mission users before the next `dev`
validation cycle.

```bash
git checkout dev
git pull origin dev
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

### 5. Integrate Through `dev`

Open pull requests from feature branches to `dev`. Reviewer-passed PRs may merge
to `dev` only after the required exact-head checks and acceptance evidence pass.

`main` is a separate Brian-reviewed release gate. Do not open ordinary
development PRs against or merge them into `main`.

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

# Run one focused unit-test selection
npm run test:unit -- src/pages/status-projection.test.ts

# Run the unit-test suite
npm run test:unit
```

---

## Three-Tier Development Test Loop

Use the smallest tier that can answer the current development question. Faster
feedback supplements rather than replaces production-path and rendered-browser
acceptance.

### 1. Fast Focused Feedback

Run the backend command from `backend/starlink-location`:

```bash
./scripts/test-config.sh
```

This uses the tracked Python 3.11 selection and uv to run the focused
configuration test selection without Docker. It proves that focused backend
contract only; it does not prove container behavior, proxy behavior, or browser
rendering.

Run a focused frontend test from `frontend/mission-planner``:

```bash
npm run test:unit -- src/pages/status-projection.test.ts
```

This proves the selected Vitest contract only. It does not prove Vite proxy
behavior, Nginx behavior, or rendered-browser behavior.

### 2. Development Integration and Hot Reload

From repository root, start only the isolated development backend:

```bash
docker compose -p starlink-dashboard-dev \
  -f docker-compose.yml \
  -f docker-compose.dev.yml \
  up -d --build --no-deps starlink-location
```

### 3. Production-Path Controls and Final acceptance

For an ordinary backend-only source change with unchanged dependency manifests
and Dockerfiles, run this cached narrow rebuild from repository root:

```bash
docker compose up -d --build --no-deps starlink-location
```

This is a convenience control, not final acceptance. It does not replace
isolated exact-SHA production-image verification, and final or release-grade
verification. Before PR approval, retain the production Dockerfiles and Nginx
path, run fresh isolated exact-SHA Docker/browser acceptance, and require the
applicable rendered browser evidence.

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
