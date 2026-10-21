# Task 5 checkpoint: read-only HTTP and publication health

Task 4 at `f3cf1f9b` passed
[checkpoint review 6314366138](https://github.com/bcl1713/starlink-dashboard/pull/403#issuecomment-6314366138).
Implementation commit: `69b6c92bd917b469129f44d50897b346417b7d47`. This report
covers Task 5 only. Stop for review before Task 6. PR #403 remains draft, open
and unmerged; #391 remains open. No deployment occurred.

## HTTP and health contracts

`/metrics` no longer imports or resolves route/POI managers. Both legacy manager
arguments remain accepted and ignored. Async `get_metrics(...)` still runs
`_prepare_metrics(route_manager=None, poi_manager=None) -> str` in the existing
threadpool. That frozen instrumentation entry point calls the existing standard
`generate_latest(REGISTRY)` serializer, followed by the unchanged single EOF
normalization. There is no source capture, storage read/write, simulator, ETA,
source validation, cache, retry, or frame publication on this path.

| Condition                                              | `/metrics`                                                       | `/health` after a recent scrape attempt                 |
| ------------------------------------------------------ | ---------------------------------------------------------------- | ------------------------------------------------------- |
| Ready observation or preflight frame                   | 200, committed values                                            | `ok`                                                    |
| Ready ordinary disconnected/unavailable frame          | 200, truthful NaNs plus valid planned fields                     | `ok`; existing live connection diagnostic remains false |
| Pending input refresh                                  | 200, masked coupled values, retained successful-observation time | `degraded`, state `pending`                             |
| Failed preparation                                     | 200, masked coupled values, retained successful-observation time | `degraded`, state `failed`                              |
| Uninitialized publication with initialized application | 200, unavailable samples                                         | `degraded`, state `uninitialized`                       |
| Coordinator not initialized                            | 200, unavailable publication                                     | Existing health 503                                     |
| Collector, serializer or threadpool/exporter failure   | 503 JSON error, no partial exposition or registry bypass         | `degraded`, bounded exception-class diagnostic          |

Health preserves `prometheus_last_scrape` as **attempt time** and its existing
30-second monitoring threshold. It adds only:

```json
{
  "metrics_publication": {
    "state": "ready",
    "reason": null,
    "exposition_error": null
  }
}
```

Publication diagnostics read one immutable head. Exposition diagnostics retain
one exception-class string, never an exception, traceback, frame, or history. A
separate short lock protects that string; serialization and registry collection
run outside it and outside the publication lock. An exporter failure remains
visible until a successful complete exposition. A successful scrape cannot make
pending/failed publication healthy; its producer must commit a complete frame.
Health's existing registry-count collection also latches actual collector faults
instead of silently reporting zero metrics and `ok`. A later health request
alone cannot clear that fault. Registration is never attempted during scraping;
registration repair remains controlled reinitialization/restart.

The old direct-registry exception fallback is removed, as required by the latest
review and the approved genuine-failure contract. It could hide an exporter
failure behind a second scrape. Ordinary source unavailability needs no
fallback: the registered frame collector already produces valid NaN exposition.

The existing scrape-duration Histogram accounts for HTTP attempts; the existing
generation-error Counter increments once per failed HTTP export. Neither renews
observation time or counts another telemetry observation. No instrument or
schema was replaced. Independent measurements remain outside coupled-frame
consistency.

`/position-table` already calls the compatibility mapping's `snapshot()` once;
Task 5 preserves its response schema and verifies all three position dimensions
remain from one generation during concurrent publication. No production change
to that endpoint was necessary.

## Verification

- Full backend: **4,477 passed, 20 existing skips, one existing Cartopy warning
  in 595.98 seconds**, exit 0 under a 20-minute hard timeout (ten-second kill
  grace).
- Final compatibility matrix: 601 passed, 18 existing fixture-dependent skips on
  each of prometheus-client **0.19.0 and 0.26.0**, with a six-minute timeout and
  ten-second kill grace.
- Seventeen new cases cover manager dependency overrides, all publication
  states, first startup, disconnect, helper/collector failures and recovery,
  custom registries, direct legacy helper calls, exact content type/EOF,
  independent instruments, source transitions and concurrent position reads.
- Each live/simulation disabled-background case runs **100 sequential and 100
  concurrent HTTP scrapes**, with constructor, manager, configuration, POI
  storage, ETA, detector and source/replay-collection traps. Acquisition
  payload, publication identity, ETA statistics, detector checkpoint and
  independent observation instruments must remain unchanged. Only scrape
  bookkeeping moves.
- Separate 100-concurrent-scrape tests overlap publication/dynamic-label changes
  and pending/failed source transitions. A scrape contains one complete
  generation or masked unavailable values, including the position alias.
- Existing schema, alias, client-type, replay ordering, lifecycle, preflight
  150-knot fallback, ETA-mode, finite-value and 70-export compatibility
  assertions remain intact. No existing test was removed or relaxed.
- Black, Ruff with the backend source root, and whitespace checks pass. The test
  environment includes declared ecCodes, eccodeslib and eckitlib dependencies.

Retained failures include expected RED dependency/health/export failures; a
custom-store fixture with old bound views; and an incorrectly named detector
spy. The fixture bindings and spy names were corrected without application
workarounds. New RED cases also caught swallowed health registry failures and an
unexpected collector exception escaping health. The first broad run was
deliberately stopped at 17% for that fix; its exit 124 reflects the termination
of its owned timeout group, not a completed acceptance run. Its log and verified
empty process group are retained. A Ruff blind-exception diagnostic was resolved
by logging the caught collector failure. The final purity assertion was
strengthened to compare all independent Counter/Histogram samples with full
label identities; final matrix runs validate that assertion. Full-suite
application bytes are unchanged by this test-only strengthening.

Required internal documentation links pass. The advisory external GitHub link
check reported a network/certificate error; the authenticated connector
successfully read the approval comment. No credentials or network configuration
were changed.

## Scope, evidence and rollback

Only `app/api/metrics.py`, `metrics_export.py` and `health.py` change
application code. Two integration files add HTTP/health/purity coverage. The
frame store, collector, registry definitions, serializer,
source/lifecycle/replay code and compatibility exports are unchanged. No
architecture, dependency, deployment, mission-cache (#392), label/cardinality
(#393), or periodic-worker change occurs.

No application CPU/RSS improvement or performance acceptance is claimed here.
The frozen original `25e34168`, instrumentation base `33b60fa8`, harness
`13cbf1d5`, original 2,072 files and before-change 128 files remain intact.
Together with Task 1–4 evidence, **2,468 earlier files verify unchanged**. Task
6 still requires matched controls, actual ingestion, production-path checks and
the minimum **60-minute acceptance soak**; the existing comparison methodology
and broader #390 acceptance requirements remain unchanged.

Rollback before integration is a revert of the Task 5 code commit, restoring
Task 4's HTTP behavior while retaining the earlier producer/lifecycle work. No
schema, storage or deployment migration needs reversal. Reverting restores the
old HTTP dependencies/fallback/health limitations, so rollback requires review
before any production use. Task 6 retains the full issue rollback procedure.

Raw commands, process ownership, RED/green/interrupted logs, source hashes,
environment metadata, frozen-evidence verification and cleanup are retained in
`.superpowers/sdd/2026-10-21-perf-391-metrics-publication-tasks/evidence/task5/`.
See [machine-readable results](probes/perf391-task5-results.json). Host checks
found no owned processes or listeners; the actor Docker context was preserved
and no owned containers, networks or volumes remain. All 38 Task 5 temporary
paths were removed. The open PR worktree and evidence are retained.
