# Phase 3: Exact-Head Runtime Acceptance

## Identity, input, and objective

Repository `bcl1713/starlink-dashboard`; PR
`https://github.com/bcl1713/starlink-dashboard/pull/143`; base `dev`; feature
`feature/react-operations-overview`. Clean baseline is
`07593c69040ad447000bf526d6453ec5c6faacfa`; old historical head
`e649ce169cd5adcbdd83d6264290b30d5221599e` belongs at
`archive/pr-143-pre-simplification-e649ce1`.

Input is Oracle's published and reviewed Phase 2 SHA from `session-handoff.md`.
An independent, non-writing session reviews that exact clean head and proves it
through built Nginx against the real simulation stack in Chromium. Oracle owns
publication; acceptance does not push or alter GitHub.

## Scope and acceptance contract

Follow [the product contract](00-product-contract.md). Prove:

- built Mission Planner Nginx, real FastAPI, and simulation data—not Vite mocks;
- browser-originated `/api/status` traffic for at least ten continuous seconds;
- exactly `1/2/5/10/30/paused`, with `1s` the default and fastest; one recursive
  monotonic timer; bounded browser timeout; prompt post-settlement scheduling;
  hidden pause and exactly one immediate resume; no overlap/replay/burst; and a
  deliberately slow independent lane that does not delay status;
- timing oracles: `1s` starts 0.8–1.3s apart and gives at least four
  successes/5s; `5s` starts none before 4.5s and one by 5.5s; `5s`→`1s` starts
  next within 1.3s after settlement; paused manual refresh makes exactly one
  request; a real ten-second `1s` run gives at least eight successes and median
  start interval 0.8–1.3s;
- history bootstrap once, resume/reconnect only on detected gap, explicit manual
  reconciliation, optional 30–60s polling only with runtime justification, and
  backfill that repairs 30-minute buffers without replacing current values;
  fixed allow-listed queries, point/body bounds, bounded timeout/safe errors,
  and the tested Phase 1 disposition of constant identity;
- bounded local history, last-good/stale/error/recovery behavior, same-origin
  traffic, CSP/security headers, safe GEP label with no public IP, and no
  browser Grafana requests;
- exact native-fullscreen 1920x1080 with `document.fullscreenElement` equal to
  the overview root; every exact inventory region non-zero, wholly in viewport,
  and simultaneously visible without scroll/disclosure; state retention, focus,
  exit, and rejection fallback;
- Grafana remains available as operational fallback, not a parity oracle.

**Out:** feature edits, generated shadow Compose as a mandatory mechanism,
retired six-viewport/object-mutation gates, Grafana retirement, user docs, and
integration. If a product defect appears, stop and return it to the Phase 1 or 2
writer with a failing regression requirement; do not patch in acceptance.

## Likely resources after inspection

Advisory only: `docker-compose.yml`, `.env.example`, Mission Planner Dockerfile/
Nginx config, `frontend/mission-planner/playwright.config.ts`, overview E2E
tests, and `backend/starlink-location/tests/integration/test_status.py`. Inspect
exact published files and existing resource names before starting.

Use a unique Compose project and collision-free host ports. Do not use existing
credentials, `.env`, containers, networks, or volumes. A minimal task-owned
override for names/ports is acceptable if required, but generating and proving a
shadow copy of all Compose configuration is explicitly not a core gate.

## Bounded task order

**TDD expectation:** This is a non-writing acceptance phase. It does not create
an artificial RED. A reproducible defect is a RED regression requirement sent to
the owning Phase 1 or 2 writer; only a new implementation SHA that proves GREEN
may return for a complete Phase 3 rerun.

1. **Pin exact head.** Require clean status, record full SHA/ref/base, commit
   time, Compose/tool/browser versions, and prove every result names that exact
   candidate SHA.
2. **Run static/full gates first.** Keep the candidate read-only. Run check-only
   commands there; run builds, tests, or anything potentially mutating only in a
   disposable isolated copy of the pinned SHA. Fail if the candidate ever gains
   a diff; never format, fix, or repair it.
3. **Preflight isolation.** Choose unique project/name/ports, verify them free,
   create a non-secret environment from `.env.example`, and record owned
   resources. Never inspect/reuse production secrets.
4. **Build exact source.** Perform required no-cache backend and frontend
   builds, record image IDs/labels and Compose model, start only task-owned
   services, and prove running images came from the pinned worktree.
5. **Health and Nginx.** Verify container health, backend health/status, Nginx
   SPA route, origin-relative proxying, CSP/security headers, and simulation
   mode.
6. **Chromium nominal pass.** Load the Nginx-served overview, await valid data,
   exercise controls/overlays, and record console/page/request failures.
7. **Scheduler request pass.** Arm browser capture before navigation. Retain
   only bounded raw start/completion/failure timing/results for a real
   ten-second `1s` run and focused `5s`, `5s`→`1s`, paused-manual,
   hidden/resume, timeout, and slow-lane passes. Apply every numeric oracle
   above and max in-flight one.
8. **Failure/recovery pass.** Boundably delay/fail only task-owned sources;
   prove last-good, source-specific stale/error, recovery, fixed ring bounds, no
   secret/IP leakage, and no Grafana request.
9. **Fullscreen pass.** At native 1920x1080 prove the fullscreen element is the
   overview root. Record root/document dimensions and every exact inventory
   bounding box. Assert every region is non-zero, wholly in viewport, and
   visible simultaneously without scroll/disclosure. Retain state/focus results
   and exactly one viewport screenshot, never a full-page screenshot.
10. **Fallback check.** Verify Grafana service availability separately, then
    prove React HAR/network contains no Grafana/3000/datasource/plugin/dashboard
    request. Grafana visual parity is not required.
11. **Results and cleanup.** Retain only bounded raw ten-second request timings/
    results, console/page/first-party errors, dimensions/bounding boxes, exactly
    one viewport screenshot, and ordinary concise logs if useful. Do not create
    a task-owned evidence repository, manifest, checksum set, or certification.
    Tear down only owned resources and verify names/labels/ports/processes
    absent.

## Exact checks

Focused checks are the health/status, ten-second cadence, slow-lane, security,
and 1920x1080 browser procedures in Tasks 5–10. The commands below plus all
focused runtime/browser procedures are the full exact-head gate.

The candidate worktree is read-only. From its repository root, use these exact
commands; all potentially mutating checks and runtime work happen in the
disposable copy:

```bash
set -euo pipefail
CANDIDATE_ROOT=$(git rev-parse --show-toplevel)
CANDIDATE_SHA=$(git rev-parse HEAD)
test -z "$(git status --porcelain --untracked-files=all)"
git diff --check "${CANDIDATE_SHA}^..${CANDIDATE_SHA}"

ROADMAP_DOCS=(
  docs/plans/2026-09-02-react-operations-overview-rebuild.md
  docs/plans/react-operations-overview-rebuild/00-product-contract.md
  docs/plans/react-operations-overview-rebuild/01-phase-0-contract-reset.md
  docs/plans/react-operations-overview-rebuild/02-phase-1-live-data.md
  docs/plans/react-operations-overview-rebuild/03-phase-2-fullscreen-layout.md
  docs/plans/react-operations-overview-rebuild/04-phase-3-runtime-acceptance.md
  docs/plans/react-operations-overview-rebuild/05-phase-4-docs-and-integration.md
  docs/plans/react-operations-overview-rebuild/session-handoff.md
)
test "$(git ls-files -- \
  docs/plans/2026-09-02-react-operations-overview-rebuild.md \
  docs/plans/react-operations-overview-rebuild | sort)" = \
  "$(printf '%s\n' "${ROADMAP_DOCS[@]}" | sort)"
python tools/check_filename_convention.py

DISPOSABLE=$(mktemp -d)
trap 'rm -rf "$DISPOSABLE"' EXIT
git archive "$CANDIDATE_SHA" | tar -x -C "$DISPOSABLE"
cd "$DISPOSABLE"
python -m pytest tools/tests -q
cd backend/starlink-location
python -m pytest -q
python -m ruff check app tests
cd ../../frontend/mission-planner
npm ci
npm run lint
npm run build
npx prettier --check "src/**/*.{js,jsx,ts,tsx,md,json,yaml,yml}"
npx vitest run
npx playwright test
cd "$CANDIDATE_ROOT"
test -z "$(git status --porcelain --untracked-files=all)"
test "$(git rev-parse HEAD)" = "$CANDIDATE_SHA"
```

The repository filename checker runs and must pass. The exact tracked-path
assertion above separately enforces the roadmap names.

Then run the repository-required no-cache Docker rebuild/start/health sequence
in the isolated project and the Phase 3 browser procedure above. Runtime
evidence must identify exact image IDs and SHA. Do not call an endpoint-only
test browser acceptance.

## Independent spec then quality gate

**Specification review:** the independent accepter compares exact input SHA,
clean tree, real-stack provenance, all product acceptance bullets, raw request
math/counts, slow-lane isolation, fullscreen dimensions, security/no-IP/
no-Grafana evidence, and cleanup. Declare `PASS`, `FAIL`, or explicit coverage
gap; do not average failures into a pass.

**Quality review:** only after spec PASS, another independent pass evaluates raw
result reproducibility, bounded/redacted retention, timing math, test-oracle
quality, runtime isolation, and cleanup proof. No branch edits are allowed.

A defect returns to one writer and creates a new SHA. All Phase 3 exact-head
runtime evidence must then be regenerated; old evidence remains superseded.

## Public handoff, docs, cleanup, and stop

Oracle posts PR/base/feature, exact SHA, changed paths (normally none),
commands, image/runtime identity, bounded raw ten-second request results,
fullscreen dimensions and single viewport screenshot disposition,
security/Grafana results, reviews, gaps, docs impact, cleanup, and next action.

Documentation impact remains pending Phase 4 unless acceptance finds a contract
change. Completion requires exact-head real-stack PASS, both ordered reviews,
verified cleanup, and immutable raw results. Stop. Phase 4 starts in a new
writer session from Oracle's accepted Phase 3 SHA and produces reviewed docs
plus a `dev` integration candidate; release to `main` remains Brian-gated.
