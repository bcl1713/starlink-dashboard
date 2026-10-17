# Operator Overview controls and presets — #364

Product candidate: `bc0a02b58e2919ca4dc4410f58fd946f58d7d0c6`, based on
`origin/dev` (`e02e11fb21fbccd363fcbe0fbdcab51227494357`). Subsequent evidence
commits contain reports and captures only. Product source is unchanged.

Operator reuses the existing Configuration controls for same-browser display
selection/recenter/open Overview, shared visibility switches, and history.
Normal, Communications and Weather are saved bundles of existing visibility
switches. Presets are initially empty, use explicit saved versions and contain
no new weather layer, transport measurement or fullscreen capability. Advanced
settings remain in Configuration. See the
[operational and backout contract](../../operations/operator-journal.md#operator-overview-display-controls-364).

## Production simulation results

The exact committed source archive produced the normal backend and frontend
production images with matching revision labels. Desktop and touch-enabled
mobile browsers traversed the production Nginx proxy. Runtime networking was
internal-only; browser requests outside the local origin were denied. The
synthetic mission, journal and clock fixture reused the existing #362/#363
acceptance harness, fixed at `2026-10-17T16:00:00Z`. The deliberately
unreachable optional provider did not prevent the display controls from working.

All three production browser workflows passed:

- Display controls: acknowledged same-browser recenter; separate-browser
  inability to recenter; concurrent disjoint edits; rejected stale edit; shared
  history window and actual rendered Overview metric-panel visibility; all three
  preset saves; preset apply roundtrip; held server acknowledgment; offline
  write failure; silent command timeout and stale display expiry; backend
  restart persistence; desktop 1920×1080 and mobile 390×844/844×390 captures
  with no horizontal overflow or uncaught browser errors.
- Existing journal: desktop/mobile edits, corrections, conflict reconciliation,
  real read-only media 503, exact retries and lost acknowledgment handling.
- Existing shell: preflight, leg and between-leg summaries, requirement
  ordering, retained drafts, network failure/reconnect and restart recovery.

Actual disposable-media and process-crash probes passed: read-only and full
private tmpfs; before/after-commit interruption; unchanged counts on rejected
writes; idempotent retry; backup/restore; rotated epoch; unsupported schema and
missing-store failure closure. Projection checks passed. Existing planning CSV
semantics, telemetry ZIP bytes, component identities and archive revisions
remained unchanged around the Operator mutations. `exports.json` includes the
sanitized synthetic archive manifest and before/after hashes. #370 retains
ownership of production operations-package wiring.

## Automated checks

- Frontend: 1,731 tests passed; production build and ESLint passed.
- Acceptance ownership/fixture/runner tests: 22 passed.
- Backend Black: all 704 files unchanged; repository-wide Ruff passed.
- Backend canonical gate: 3,937 passed, 20 skipped in 591.17 seconds; no
  failures. One existing Cartopy facecolor warning is retained in
  `backend-final.log`.
- Product-commit CI frontend gate passed. Static source formatting, lint and
  Markdown checks passed; its link checker failed on 11 existing ADS-B
  documentation timeouts, as in parent #361. See `static-ci-limitations.txt`.
  The gate is reported as failed; no merge or waiver is claimed.
- Independent read-only review found no critical or important product issues.
  Its minor offline-state test suggestion was added; preset snapshot semantics
  and visible saved versions are documented.

The first browser run exposed an exact-label test selector mismatch, reproduced
in an isolated synthetic document (`getByLabel` found 0, combobox accessibility
query found 1). The selector was corrected and both subsequent production runs
passed. The initial full backend invocation omitted the optional scientific
requirements and reached GFS failures because `eccodes` was unavailable. Its
verified owned process group was terminated and reaped before starting the
canonical gate with `requirements-dev.txt` and `requirements-gfs.txt`.

## Reproduction

From a clean checkout of the product candidate with provisioned frontend and
browser dependencies:

```sh
timeout --kill-after=10s 30m ./tools/verify backend
timeout --kill-after=10s 15m npm --prefix frontend/mission-planner run test:unit
timeout --kill-after=20s 65m python3 tools/acceptance/operator-journal/run.py \
  --candidate bc0a02b58e2919ca4dc4410f58fd946f58d7d0c6 \
  --project starlink-operator-364-reproduction \
  --evidence /tmp/operator-364-reproduction
```

The runner records each child PID/process group, command deadline, image,
Compose project, private volume and temporary path before starting it. Exit and
signal handling stop only owned resources. `summary.json` records empty
container/network/volume inventories, reaped child groups, removed listeners,
removed temporary archives and removed image tags. Both earlier runs also
completed scoped cleanup. No task service is retained for review; the open-PR
worktree is retained.

This evidence uses wholly synthetic software fixtures. It establishes no
physical aircraft, Starshield terminal, power-loss durability, actual routing,
or operational-readiness claim. Operator remains disabled by default.
