# Operator shell acceptance — issue 363

Latest requirement-ordering correction:
[review-fix evidence](review-fix/README.md).

Original product candidate: `3322a3677ac046aac369286a643340d4557694c8`.
Evidence-only commits after this SHA do not alter product or fixture code.

The production Docker/Nginx run passed both browser journeys, storage crash and
media-failure probes, projections, and export compatibility. The private Compose
network was internal; optional Prometheus was deliberately unreachable. All
mission names, records, positions and timestamps came from synthetic fixtures.
The injected backend clock was `2026-10-17T16:00:00Z`. No aircraft readiness or
measured transport-availability claim is made.

## Checks

- Frontend: 243 files / 1,723 unit tests passed; ESLint and production build
  passed. Node 22.22.2. The existing bundle-size advisory remains.
- Backend Operator: 195 contract, unit, integration, crash/recovery tests passed
  using Python 3.11.16 from `backend/starlink-location`.
- Harness: 22 fixture, admission, cleanup and candidate checks passed.
- Production browsers: 2 tests passed. Existing journal conflict, real media
  503, exact retry, two-client and baseline-page checks remain covered.
- Shell: preflight, leg and between-leg saved contexts at 1920×1080, 390×844 and
  844×390; empty mission; keyboard activation/focus; touch-sized navigation;
  dirty-draft retention; summary failure/reconnect; backend restart with
  unchanged records; zero summary requests over the existing 15-second health
  cadence.
- Overview: desktop/mobile baseline smoke and overflow checks passed; the full
  frontend suite includes existing Overview layout regressions. Overview source,
  global navigation and styles were unchanged. No new FPS benchmark was run.
- Export: synthetic telemetry ZIP checksum, capture identities and revisions
  stayed unchanged; structured synthetic projection/export examples are
  retained.

## Evidence

`summary.json` records image IDs and exact source revision; `qualification.json`
contains all five passing qualification groups. `shell-proof.json` lists the
nine state captures and restart/polling results. Empty-state and
unavailable-read captures are also included. `browser-proof.json` covers journal
regression and baseline pages. `failures.json`, `exports.json` and
`projections.json` contain sanitized synthetic examples. `ownership.json`
records command/process/project ownership and teardown; `verification.json`
records local tests and PNG sizes.

The first run passed browser/projection/export checks but failed the crash probe
because shell rows had been added to its shared six-record seed. Shell scenarios
are now opt-in for the browser backend. The complete corrected run passed. An
earlier local backend invocation from repository root could not import its
fault-worker module; the documented backend-directory invocation passed all 195
Operator tests. An outdated reused frontend dependency tree was replaced with
locked task-local dependencies, and the primary checkout dependencies restored.

## Reproduce and clean up

Run the existing bounded acceptance runner from a clean committed worktree:

```sh
timeout --kill-after=30s 65m python3 tools/acceptance/operator-journal/run.py \
  --candidate "$(git rev-parse HEAD)" \
  --project starlink-operator-363-review \
  --evidence /tmp/starlink-operator-363-review
```

Use the configured actor Docker daemon and Node 22.22.2 or another supported
22.x runtime. Provision locked frontend dependencies and the Playwright browser
before running; the runner performs no browser download. See
`docs/operations/operator-journal.md` for feature initialization and rollback.
There is no schema or infrastructure migration in this change.

Final cleanup verified no owned containers, networks, volumes, child groups,
loopback listener, image tags or extracted source trees remained. Open-PR
worktree and evidence are retained, without runtime services.
