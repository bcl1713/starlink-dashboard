# Metric lifecycle implementation plan

**Goal:** Implement issue #393 against origin/dev f0c1bd49. **Spec:**
[Issue #393](https://github.com/bcl1713/starlink-dashboard/issues/393)
**Architecture:** Keep the existing immutable telemetry frames for POI, route,
mode and service labels. Give the seven independent mission gauges one lifecycle
owner and collector snapshot lock. Preserve names, labels, counters and
histograms. **Tech stack:** Python, prometheus-client, pytest, Prometheus.

## Constraints and decisions

- Scrapes remain read only. Remove children only at authoritative transitions.
- Use native Gauge.remove with exact labels; never edit registry internals.
- Mission activation replaces the previous owner; delayed writes for a different
  mission are ignored. Replay values publish after runtime commit.
- Keep genuine zero, unavailable NaN and absent identities distinct.
- Exporter removal does not erase TSDB history or recover retained disk space.
- Ruling: implement inline under the user's issue execution request. No new
  product decisions or changes to metric keys are required.

## Tasks

- [x] Reproduce A/deactivate/B/A and route edits through exposition; cover all
      mission gauges, repeated clears, delayed writes and 200 transitions.
- [x] Implement lifecycle ownership, exact child removal and a synchronized
      mission collector. Wire successful activation/deactivation/deletion,
      replay commit and terminal cleanup. Preserve aggregates.
- [x] Exercise real POI CRUD, category/name/ETA-mode and route-name transitions,
      missing measurements, preflight, replay and concurrent scrapes.
- [x] Add a bounded before/after benchmark and real Prometheus scrape control;
      document all mutable/high-cardinality families and consumer compatibility.
- [x] Run scoped and adjacent tests, formatting and review; commit, push and
      open a PR to dev. Stop all task resources and retain open-PR
      worktree/evidence.

## Review focus

Failed activation must not replace the previous mission; clearing an old mission
must not clear its successor. Cancelled replay must not resurrect via a delayed
write. Collection must see one mission snapshot. Unknown POI measurements must
stay NaN. Retained Prometheus history must remain queryable after label changes.

## Resource ownership

Task worktree: `.worktrees/issue-393-metric-lifecycle`. Test command: timeout
--kill-after=10s 10m uv run --with-requirements requirements.txt pytest. Test
storage: `/tmp/issue393-tests`; baseline session 4547 completed successfully.
Future benchmark/acceptance resources use `issue393` names and cleanup handlers.

## Verification record

- 312 focused and adjacent tests passed in 31.64 seconds.
- Independent review completed; committed-publication failure and restored
  simulation selection findings were fixed and regression-tested.
- Real Prometheus 1 Hz before/after controls passed, including preserved
  aggregate count and historical label identities. Both projects have empty
  cleanup records.
- Scoped Black/Ruff and Markdown checks passed. No frontend behavior changed.
- Exact production-image/Nginx/browser and sustained-soak gates remain outside
  this scoped evidence; do not treat this branch as approved to merge.

PR: [#432](https://github.com/bcl1713/starlink-dashboard/pull/432), draft
against `dev`; implementation and scoped controls are complete. The worktree is
retained for review. All task runtime resources are stopped.

## Review follow-up: service mode round trip

[Review finding](https://github.com/bcl1713/starlink-dashboard/pull/432#issuecomment-6464401442)
reproduced for cancelled and failed replay: live reconciliation republished an
owner that remained present on returning to terminal simulation. Terminal replay
reconciliation now clears the current owner under repository admission.

- Both round-trip regressions failed before the fix and passed afterward.
- Tests cover live publication between mode changes, raw external persisted
  deactivation, and preservation of running/completed replay values.
- 316 affected tests passed in 32.17 seconds; scoped Black/Ruff checks passed.
- Independent follow-up review found no actionable issues.
- Test ownership and retained logs: `/tmp/issue393-review-roundtrip`; disposable
  data and pytest paths are removed after checks. No Compose projects or
  listening services were started for this follow-up.
