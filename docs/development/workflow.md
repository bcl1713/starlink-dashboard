# Development Workflow

This guide outlines the development workflow, testing practices, and pull
request guidelines for the Starlink Dashboard project.

## Git Workflow

### 1. Create an Isolated Feature Worktree

Keep the primary checkout on `dev`. Start each task in a separate worktree and
feature branch based on the latest `origin/dev`:

```bash
git fetch origin --prune
git worktree add .worktrees/your-feature-name -b feat/your-feature-name origin/dev
cd .worktrees/your-feature-name
```

The `.worktrees/` directory is ignored by Git. Run edits, commits and checks in
that task's worktree. Keep `main` reserved for reviewed releases.

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
git push -u origin feat/your-feature-name
gh pr create --base dev
```

Create a pull request from your feature branch against `dev`. CI/CD will run
linting checks.

### 5. Integrate Through `dev`

Open pull requests from feature branches to `dev`. Reviewer-passed PRs may merge
to `dev` only after the required exact-head checks and acceptance evidence pass.

`main` is a separate Brian-reviewed release gate. Do not open ordinary
development PRs against or merge them into `main`.

### 6. Clean Up After Merge

Keep the worktree while the PR is open. Stop its workers and remove its
task-owned acceptance projects as soon as checks finish, including failed or
cancelled runs. An open PR does not require a running acceptance environment.
After the PR merges, return to the primary checkout:

```bash
cd ../..
git pull --ff-only origin dev
git worktree remove .worktrees/your-feature-name
git branch -d feat/your-feature-name
git push origin --delete feat/your-feature-name
git fetch origin --prune
git worktree prune
```

Skip remote branch deletion if GitHub already deleted it. For a squash merge,
verify the PR merged into `dev` before using `git branch -D`. If worktree
removal reports uncommitted files, preserve them or obtain permission to discard
them before using `--force`. Remove the task's temporary files and test
resources; preserve shared runtime configuration, credentials and other tasks'
resources.

---

## Testing and Three-Tier Development Loop

Use the smallest tier that can answer the current development question. Faster
feedback supplements rather than replaces production-path and rendered-browser
acceptance.

### Resource Lifecycle for Every Tier

Before starting a check, record its command/session handle, PID and process
group, task-specific Compose project, private volumes, and temporary paths. Use
GNU `timeout` around the entire test command, including `uv` or `npm`, as shown
below. Choose an explicit longer limit for builds or acceptance when needed.
Tool output-yield limits and pytest's `faulthandler_timeout` do not terminate
hung tests. Treat timeouts as failed checks and verify the old process tree is
gone before retrying.

Resource-owning runners must install cleanup handlers for normal exit and
`INT`/`TERM`, close browser contexts, terminate and reap their workers, and tear
down their Compose project. Cleanup handlers cannot handle `SIGKILL`, so always
verify cleanup after forced termination. Stop temporary servers before handing
work back unless the user explicitly requests that they stay running.

Follow [Cloud Docker runtime](cloud-docker.md#task-teardown-verification) for
scoped teardown and host verification. Preserve evidence and open-PR worktrees
without keeping their processes alive. Report any resources left behind.

### 1. Fast Focused Feedback

From `backend/starlink-location`, run the tracked backend command:

```bash
timeout --kill-after=10s 10m ./scripts/test-config.sh
```

It uses the tracked Python 3.11 selection and uv to run the focused
configuration test selection without Docker. It proves that focused backend
contract only; it does not prove container behavior, proxy behavior, or browser
rendering.

From `frontend/mission-planner`, run a focused frontend test:

```bash
timeout --kill-after=10s 10m npm run test:unit -- src/pages/status-projection.test.ts
```

Run the unit-test suite from the same directory with:

```bash
timeout --kill-after=10s 10m npm run test:unit
```

These commands prove selected Vitest contracts only. They do not prove Vite
proxy behavior, Nginx behavior, or rendered-browser behavior.

### 2. Development Integration and Hot Reload

From repository root, start only the isolated development backend:

```bash
./scripts/compose.sh -p starlink-dashboard-dev-your-feature-name \
  -f docker-compose.yml \
  -f docker-compose.dev.yml \
  up -d --build --no-deps starlink-location
```

From `frontend/mission-planner`, run Vite against that backend:

```bash
STARLINK_DEV_BACKEND_ORIGIN=http://127.0.0.1:18000 \
  timeout --kill-after=10s 30m npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

The development override bind-mounts backend source at `/app` and runs Uvicorn
with `--reload`. Vite proxies `/api` requests to the isolated backend. Verify
the real proxy path from any directory:

```bash
curl --fail --show-error http://127.0.0.1:5174/api/status
```

This tier proves exploratory integration, reload configuration, and Vite proxy
behavior. It does not prove the production image, Nginx path, CI, or
rendered-browser acceptance.

After the task-owned control, stop Vite and, from repository root, remove only
the development project:

```bash
docker compose -p starlink-dashboard-dev-your-feature-name \
  -f docker-compose.yml \
  -f docker-compose.dev.yml \
  down
```

### 3. Production-Path Controls and Final Acceptance

For an ordinary backend-only source change with unchanged dependency manifests
and Dockerfiles, run this cached narrow rebuild from repository root:

```bash
./scripts/compose.sh up -d --build --no-deps starlink-location
```

This is a convenience control, not final acceptance. It does not replace
isolated exact-SHA production-image verification, the Nginx proxy path, required
CI, or rendered-browser evidence.

After `git pull`, run `./scripts/compose.sh up -d --build` for the ordinary
stack, including the NOAA GFS worker from the base Compose configuration.
The wrapper sets `ACCEPTANCE_CANDIDATE_SHA` to the full checked-out HEAD before
forwarding Compose flags. Local overrides and custom file selection retain
Docker's normal behavior. The targeted development backend command above still
starts only `starlink-location`; a full-stack `up` also starts GFS.
Raw `docker compose build` requires an explicit SHA, for example:

```bash
ACCEPTANCE_CANDIDATE_SHA=$(git rev-parse HEAD) docker compose build
```

Without it, the Dockerfile guards reject the build. A dirty working tree is not
an exact acceptance candidate. The final acceptance runner injects its own
reviewed candidate SHA independently.

Use `--no-cache` when dependency manifests or Dockerfile instructions change,
for explicit cache-integrity investigation, and when final or release-grade
verification requires rebuilding Dockerfile layers. `--no-cache` does not
refresh a locally cached base-image tag; when base-image freshness matters, also
pull the referenced base image. Before PR approval, preserve the production
Dockerfiles and Nginx path, run fresh isolated exact-SHA Docker/browser
acceptance, and require the applicable rendered browser evidence.

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
