# Phase 3: Exact-Head Runtime Acceptance

## Identity, input, and objective

Repository `bcl1713/starlink-dashboard`; PR
`https://github.com/bcl1713/starlink-dashboard/pull/143`; base `dev`; feature
`feature/react-operations-overview`. Clean baseline is
`07593c69040ad447000bf526d6453ec5c6faacfa`; old historical head
`e649ce169cd5adcbdd83d6264290b30d5221599e` belongs at
`archive/pr-143-pre-simplification-e649ce1`.

Input is Oracle's published and reviewed Phase 2 SHA from `SESSION-HANDOFF.md`.
An independent, non-writing session reviews that exact clean head and proves it
through built Nginx against the real simulation stack in Chromium. Oracle owns
publication; acceptance does not push or alter GitHub.

## Scope and acceptance contract

Follow [the product contract](00-product-contract.md). Prove:

- built Mission Planner Nginx, real FastAPI, and simulation data—not Vite mocks;
- browser-originated `/api/status` traffic for at least ten continuous seconds;
- selected `1/2/5/10/30/paused` behavior as sampled, completion-anchored
  cadence, no overlap/catch-up burst, and a deliberately slow independent lane
  that does not delay status;
- bounded local history, last-good/stale/error/recovery behavior, same-origin
  traffic, CSP/security headers, safe GEP label with no public IP, and no
  browser Grafana requests;
- exact native-fullscreen 1920x1080 no-scroll, in-viewport non-overlapping
  bounding boxes, state retention, focus, exit, and rejection fallback;
- Grafana remains available as operational fallback, not a parity oracle.

**Out:** feature edits, generated shadow Compose as a mandatory mechanism,
retired six-viewport/object-mutation gates, Grafana retirement, user docs, and
integration. If a product defect appears, stop and return it to the Phase 1 or 2
writer with a failing regression requirement; do not patch in acceptance.

## Likely resources after inspection

Advisory only: `docker-compose.yml`, `.env.example`, Mission Planner Dockerfile/
Nginx config, `frontend/mission-planner/playwright.config.ts`, overview E2E
tests, `backend/starlink-location/tests/integration/test_status.py`, and
task-owned external evidence storage. Inspect exact published files and existing
resource names before starting.

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
   time, Compose/tool/browser versions, and prove no later commit is accepted
   under this evidence root.
2. **Run static/full gates first.** Run repository backend/frontend/lint/build/
   unit/browser checks declared below. Any failure makes acceptance FAIL; later
   browser work is diagnostic only.
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
7. **Ten-second request pass.** Arm browser network capture before navigation or
   refresh. For at least ten seconds after bootstrap, retain request IDs, start/
   finish/failure monotonic timestamps, status, and lane. Prove selected cadence
   tolerance, max in-flight one, no early/burst dispatch, and status progress
   while an independent lane is intentionally slow. Exercise pause/resume and
   one additional cadence without claiming all values from one short window.
8. **Failure/recovery pass.** Boundably delay/fail only task-owned sources;
   prove last-good, source-specific stale/error, recovery, fixed ring bounds, no
   secret/IP leakage, and no Grafana request.
9. **Fullscreen pass.** At native 1920x1080 record root/document dimensions and
   every required bounding box before, during, and after fullscreen plus API
   rejection. Assert no scroll/overlap/out-of-viewport box, retained state,
   usable controls, focus return, and no console/page/request failure.
10. **Fallback check.** Verify Grafana service availability separately, then
    prove React HAR/network contains no Grafana/3000/datasource/plugin/dashboard
    request. Grafana visual parity is not required.
11. **Evidence and cleanup.** Write a bounded redacted SHA-qualified manifest,
    checksums, commands/results, screenshots, dimensions, request ledger, image/
    runtime identity, gaps, and cleanup result. Tear down only owned resources,
    verify names/labels/ports/processes absent, then reverify evidence
    checksums.

## Exact checks

Focused checks are the health/status, ten-second cadence, slow-lane, security,
and 1920x1080 browser procedures in Tasks 5–10. The commands below plus all
focused runtime/browser procedures are the full exact-head gate.

Adapt only where inspected scripts differ and record every substitution:

```bash
git status --porcelain
git rev-parse HEAD
python -m pytest tools/tests -q
cd backend/starlink-location
python -m pytest -q
python -m ruff check app tests
cd ../../frontend/mission-planner
npm run lint
npm run build
npx vitest run
npx playwright test
cd ../..
pre-commit run --all-files
git diff --check
```

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

**Quality review:** only after spec PASS, another independent pass evaluates
evidence reproducibility, bounded/redacted retention, timing math, test oracle
quality, runtime isolation, checksum integrity, and cleanup proof. No branch
edits are allowed.

A defect returns to one writer and creates a new SHA. All Phase 3 exact-head
runtime evidence must then be regenerated; old evidence remains superseded.

## Public handoff, docs, cleanup, and stop

Oracle posts PR/base/feature, exact SHA, changed paths (normally none),
commands, image/runtime identity, ten-second request results, fullscreen
dimensions, security/Grafana results, evidence manifest/checksum location,
spec/quality reviews, gaps, docs impact, cleanup, and next action.

Documentation impact remains pending Phase 4 unless acceptance finds a contract
change. Completion requires exact-head real-stack PASS, both ordered reviews,
verified cleanup, and immutable evidence. Stop. Phase 4 starts in a new writer
session from Oracle's accepted Phase 3 SHA and produces reviewed docs plus a
`dev` integration candidate; release to `main` remains Brian-gated.
