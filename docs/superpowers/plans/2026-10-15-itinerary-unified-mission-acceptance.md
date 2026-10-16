# Automatic itinerary import acceptance continuation

This is Task 8 of the
[implementation plan](2026-10-15-itinerary-unified-mission.md). Read its global
constraints, interfaces and the approved spec before execution.

## Task 8: Production qualification, review and documentation

**Files:** Extend repository-root
`tools/acceptance/itinerary-planning/{seed, runner,qualify,export_probes}.py`,
its runner tests under `tools/tests/`, and `docs/features/mission-planning.md`.
Add invented PDF/KML acceptance fixtures; retain legacy regression journeys
alongside the new shared-editor journey.

**Interfaces:** Extend existing acceptance proof schema with explicit booleans
for automatic import, ordinary editing, precision/offset association, migration,
revision merge/history, active protection and cleanup; missing proofs fail PASS.

- [ ] Write runner tests rejecting absent/false proof fields, wrong candidate
      provenance, missing artifact comparisons and incomplete cleanup; run their
      focused pytest selection with an explicit 10-minute timeout and confirm
      red.
- [ ] Implement journeys for one-upload creation, normal takeoff/route edits,
      revision PDF upload, conflict/concurrency handling and legacy conversion.
      Compare API preview/save/recompute, statistics, CSV, PDF and ZIP readback.
      Require actual ordinary editor interactions on desktop and mobile; no
      private source data enters committed fixtures or public artifacts.
- [ ] Run focused runner tests, then root
      `timeout --kill-after=10s 15m ./tools/verify backend` and
      `timeout --kill-after=10s 15m ./tools/verify static`; run frontend unit,
      lint/build gates and all existing planning regressions. Commit the
      candidate.
- [ ] Obtain independent whole-branch review; reproduce findings with failing
      regressions and repair them before acceptance. No self-review substitutes
      for the repository-required independent review.
- [ ] Run existing production `tools/acceptance/itinerary-planning/run.sh`
      against the exact committed SHA with isolated project/ports and its
      30-minute wall limit; update runner arguments only as documented in its
      guide. Preserve actor Docker endpoint, production Nginx/images and
      immutable input receipts. Inspect desktop/mobile screenshots and exported
      artifacts. A blocked gate remains reported; do not downgrade the
      acceptance claim.
- [ ] Verify host-owned processes, listeners, containers, networks and
      disposable volumes are gone immediately after checks. Retain evidence and
      open-PR worktree; push feature PR against dev with exact-candidate
      results. After authorized merge, remove task worktree/branches and
      temporary paths.
