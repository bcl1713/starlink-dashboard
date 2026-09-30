# Chart-only left-edge retention report

Base: `0da64f4a3f60488d203217ed610af2b19820e93b`, PR #212 to `dev`.
Scope: chart-only in-memory real samples; no API, backend, aircraft, or Grafana changes.

## Implementation and self-review

- Each panel retains only its own observed and three five-minute series. The
  authoritative newer bundle replaces the entire covered interval, including
  missing values; unavailable aggregates discard every prior rollup sample.
  Older same-window bundles are ignored; window changes clear the cache.
- Pruning uses the earliest possible clipped left edge (`end - window - 7.5`)
  at every accepted refresh. A compositor's positive elapsed time can only move
  the actual edge right, so this never discards a still-visible point. The
  per-trace cap is 1,820 real samples, against the shared API's 1,801-sample
  cap plus the short left margin. Synthetic null gap markers are created only
  by the downstream projector, never retained. A stalled/hidden/error graph
  still uses its existing frozen motion/status path; old points outside the
  viewport are not presented as new samples.
- The selected window remains the visible x span; the existing right margin,
  five-second shared fetch, and aircraft bundle remain unchanged. First load
  cannot supply older samples it has never received.
- Review of same-timestamp revisions, omitted overlapping timestamps,
  unavailable-to-available state, missing-poll gap, window reset, out-of-order
  responses, cap over long uptime and render-time ref updates found no
  remaining chart-contract violations. The ref remains panel-local and is
  updated only on a new accepted response object, avoiding merging every
  250ms render tick. Follow-up acceptance against real backend remains a
  separate gate, not claimed by route fixtures.

## RED / GREEN

1. `npm run test:unit -- src/pages/overview-metric-retention.test.ts`:
   initial module-not-found (before the minimal seam existed); with the seam
   returning only the incoming bundle, **3 of 5 failed** for the precise
   left-edge loss, missing-poll retention and older-bundle rejection.
   After implementation, **5 passed**. A subsequent test assertion was
   corrected: a raw observation before the new query start properly remains
   even when its aggregate becomes unavailable.
2. On Forge, focused Chromium route-fixtured regression against the prior
   `OverviewMetricHistoryPanel.tsx` (`git show HEAD:...` copied into the
   task-owned source checkout) failed at **poll 1**: expected the cyan real
   left-edge stroke, received no painted pixel. Restoring the source-identical
   candidate passed **1/1** (27.8s). This visual oracle correlates each
   fulfilled poll's UTC axis with projected cyan canvas pixels near the edge,
   checks two refreshes and disappearance after the marker exits. The existing
   interior-spike/motion browser test is retained.

## Verification

- Local `npm run test:unit`: **55 files, 200 tests passed** (21.03s).
- Local `npm run lint`: **exit 0**.
- Local `npx tsc -b --pretty false`: **exit 0**.
- Scoped `npx prettier --check` (four TS/TSX files and Overview doc): **exit 0**.
- `markdownlint-cli2 docs/features/overview.md`: **0 issues**.
- `git diff --check`: **exit 0**.
- Forge `npx playwright test tests/e2e/overview-metric-history.spec.ts
  --project=chromium --reporter=line`: **5 passed** (1.2m).
- Forge `npx playwright test --project=chromium --workers=1
  --reporter=line`: **45 passed** (2.1m), all 11 spec files, Chromium 1.63.0,
  production build/preview via Playwright webServer. Source identity for all
  touched files verified by matching SHA-256 in local worktree and Forge
  task-owned checkout. Port 5173 had no listener after both runs.

Warnings: Vite reports a >500kB chunk. Local Vitest emitted Node
`module.register()` deprecation, Radix Dialog description and mock Three.js
unknown-tag warnings. Forge's unfixtured ancillary Overview requests to an
absent backend emitted `ECONNREFUSED 127.0.0.1:8000`; all browser tests passed,
but these fixtures do not constitute real-backend integration evidence. Forge
Node 22.12.0 also emitted npm dependency engine warnings at `npm ci`; the
browser production build and tests succeeded.

Forge workspace: `/home/oracle-worker/left-buffer-149-2026`, owned by this
verification task, not reused as another lane's evidence. The task-owned
checkout is removed after evidence recording; no process or port remains.
