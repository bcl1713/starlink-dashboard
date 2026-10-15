# SIGMET planned passage timing

Route-intersecting SIGMET attention now shows planned passage UTC and a separate
time-overlap result. Waypoint timing is interpolated on the effective selected
route; unavailable, invalid and partial evidence stays explicit. Timing edits
reuse geographic results and preserve notice acknowledgement and attention
order. Selected-only reports never receive manufactured route spans.

No planned-altitude source exists. This feature performs no altitude comparison
or filtering; reported SIGMET vertical bounds remain visible. An altitude-free
KML with waypoint times supports passage timing normally. Current-aircraft
altitude changes do not alter notices or timing evidence.

## Verification

- Independent calculator controls cover fractional passage, midnight, validity
  start/end contact, one-millisecond boundaries, missing/invalid times, disjoint
  spans, partial results and immutable route capture.
- Final route-SIGMET backend/API and acceptance-runner selection: **245
  passed**.
- Frontend: **223 files, 1634 tests passed** after the review fixes.
- Canonical static gate passed: formatting/lint, documentation links and typing
  policy. Production TypeScript/Vite build passed. Existing satellite.js browser
  externalization and large-chunk warnings remain.
- Independent whole-branch review found a fallback observation-ordering race, an
  incomplete live-altitude test and a rounded-midnight date issue. Each is
  resolved; the original reviewer verified the fixes with no remaining findings.
- Exact production candidate: `599543758aba0497c2edb9a4c3cae641211ee23b`. All
  **five production browser scenarios passed** in 3.9 minutes through Nginx,
  including the dated AWC replay and independent Overview/Configuration
  contexts.
- The timing journey verifies altitude-free route ingestion, nonoverlap without
  suppression, acknowledgement-preserving plan edits, missing waypoint times,
  selected-only unknowns and two-screen convergence within eight seconds.
- The live-altitude control verifies `/api/status` changes from 1,000 to 40,000
  ft and compares complete identities, acknowledgements and encounter evidence.
  Route-point height changes are a separate control.
- Desktop/mobile screenshots were visually inspected: timing summaries and
  unknown counts remain readable, and expanded details retain exact UTC,
  assumptions, provenance and reported vertical bounds.

## Preserved evidence

Relative to the retained feature worktree:

```text
test-results/route-sigmets-43106af76442/599543758aba0497c2edb9a4c3cae641211ee23b/
```

This directory retains `PASS.json`, `proofs.json`, candidate/image/browser
provenance, screenshots, source replay and cleanup receipts. Focused red/green,
full frontend and static/build logs remain under
`test-results/sigmet-encounter-context/`.

The first production run is preserved under
`test-results/route-sigmets-202056e37511/f7e4a1a9acba3c2c66cdd4116552a4f7a534823f/`.
It exposed residual camera damping in an excessively precise test assertion and
cross-scenario bulletin cancellation memory. The final run uses the existing
shared camera comparison tolerance and independent E1–E4 bulletin fixtures. Both
runs' cleanup receipts show no containers, networks, disposable volumes,
processes or errors; ports are free and disposable source directories removed.
An approved host check independently verified both project inventories, recorded
PID/start-time identities, free ports and absence of worktree test workers.

## Contracts and limitations

The strict read payload is now `route-sigmets-v2`; deploy its backend and
frontend together. Endpoint paths and mutation contracts are unchanged. See the
[API timing contract](../api/route-sigmet-timing.md) and
[approved design](../superpowers/specs/2026-10-15-sigmet-encounter-context-design.md).

Timing is planned evidence under constant segment-speed interpolation. It does
not predict future advisory motion or renew report validity. Actual UTC still
controls weather eligibility, including for historical simulation routes. Source
precision remains unknown where the route model has not preserved it. Exact
validity boundaries are covered by independent backend fixtures; the production
proof separately checks classification against admitted validity.

Production acceptance uses synthetic controls and a pinned dated upstream
capture with software WebGL. It does not establish current upstream availability
or target-workstation performance. Subsequent documentation-only commits cite
the tested product candidate; they claim no separate production image run.
