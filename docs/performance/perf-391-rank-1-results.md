# 391 Rank 1 Task 3: blocked at runtime preflight

**Task 3 is incomplete. Retain NO-GO and stop for review.** On 2026-10-22,
source identity checks passed, but the available browser dependencies failed
the approved prerequisites. No component measurement, production benchmark,
timing diagnostic, or sustained test was started. There is no measured Rank 1
performance improvement or regression to report.

This report belongs to [draft PR #406](https://github.com/bcl1713/starlink-dashboard/pull/406).
It follows the approved
[measurement protocol](https://github.com/bcl1713/starlink-dashboard/blob/f7253c687041342ee080b0197f0b98f20eaefdfe/docs/performance/perf-391-rank-1-measurement.md),
[specification](https://github.com/bcl1713/starlink-dashboard/blob/f7253c687041342ee080b0197f0b98f20eaefdfe/docs/performance/perf-391-rank-1-specification.md),
[regression plan](https://github.com/bcl1713/starlink-dashboard/blob/f7253c687041342ee080b0197f0b98f20eaefdfe/docs/performance/perf-391-rank-1-tests.md),
and Task 3 of the
[implementation plan](https://github.com/bcl1713/starlink-dashboard/blob/f7253c687041342ee080b0197f0b98f20eaefdfe/docs/superpowers/plans/2026-10-22-perf-391-rank-1.md).
AGENTS.md was read. Application code and acceptance methodology are unchanged.

## Exact sources and isolation

| Role                                    | Commit                                     |
| --------------------------------------- | ------------------------------------------ |
| Original                                | `25e34168f0e2cecb149b0323f1f5a795cb28cae0` |
| Current dev, matching approved baseline | `33b60fa85c0d0b80d9b82ea5eac7d612a54f4c96` |
| Uncorrected candidate                   | `e1f657986f7b988a967ddd2bef8ca4626e30b5de` |
| Corrected Task 2 candidate              | `3cd79e2ac77557b7ef0ba7bc8bf60069bd260bbc` |
| Approved documents and diagnostic tools | `f7253c687041342ee080b0197f0b98f20eaefdfe` |
| Frozen availability-v2 harness          | `f3029024b5950a267645195476da5cbca326f16a` |
| Frozen strict harness                   | `13cbf1d54b526307747578ecd4fc691562846834` |

Git resolved these commits. The GitHub connector independently confirmed #403,
\#405 and #406 heads and their draft/open/unmerged states. The fetched dev ref
matches the approved baseline. A fresh isolated branch `perf/391-rank1-task3`
starts at the approved Task 2 commit in
`/workspace/starlink-dashboard/.worktrees/perf391-rank1-task3`. Supporting clean
documentation, frozen-harness and uncorrected worktrees were created without
editing their sources. The primary checkout arrived on branch `work` at
`bf7b49b75a7b96574c236ec0c52ebe32acf96189` and was left unchanged. No prior linked
agent worktrees were present in this environment's initial Git worktree list.

## Failed prerequisites and stop decision

| Check                                    | Observed result                                                              |
| ---------------------------------------- | ---------------------------------------------------------------------------- |
| Installed shared Playwright              | `1.56.1`                                                                     |
| Application Playwright pin               | `@playwright/test` `1.63.0`                                                  |
| Browser executable for installed package | `/home/agent/.cache/ms-playwright/chromium-1194/chrome-linux/chrome`, absent |
| Installed Node                           | `v24.19.0`                                                                   |
| Application Node requirement             | `^22.22.2`                                                                   |
| Docker readiness                         | `28.4.0`, `vfs`, 5 CPUs, 18,882,674,688 bytes daemon-visible memory          |
| Private Python setup                     | Python `3.11.16`; requirements-dev installation succeeded                    |

The browser package came from the existing primary checkout's node_modules;
no candidate dependency link was installed. Its browser identity cannot qualify
the prescribed workload. The private Python inventory is retained as setup
evidence, with no claim that it matches a historical baseline. No production
image was built, so production package inventories and workload identity remain
unverified. Hardware readiness alone does not establish comparability.

The protocol says: **"Verify browser runtime dependencies as in the original
runners; do not substitute software versions"** and **"Stop on ... missing
baseline dependencies ... workload/package mismatch ... or insufficient accepted
pairs."** The specification also requires stopping on missing baseline
dependencies. Accordingly, execution stopped before testing. No software version,
threshold, instrumentation boundary or acceptance condition was substituted.

The initial sandbox fetch could not reach the proxy; the subsequent fetch with
the execution tool's network permission succeeded. The default uv cache was
read-only; setup used the writable workspace cache. Python installation emitted
a read-only executable-link warning. A pip inventory attempt failed because uv
does not install pip; uv's inventory succeeded. These attempts, the successful
dependency-install log, and a recovered cleanup exception remain recorded.

## Measurement accounting and unavailable results

All prescribed cohorts have **zero started runs and zero accepted matched
repetitions**. No comparison was submitted to the unchanged comparability
validator. There are zero rejected measurement runs; the failed prerequisite is
recorded separately and must not be counted as a benchmark rejection. There are
no raw timing samples, outliers or performance distributions from this session.

| Required result                                           | Task 3 evidence                                      |
| --------------------------------------------------------- | ---------------------------------------------------- |
| Component tick CPU at 0/2/10/100/1,100 POIs               | Unavailable; candidate pair not measured             |
| Whole-backend CPU and run-to-run variability              | Unavailable; four-role off/counters controls not run |
| Producer tick CPU before/after consolidation              | Unavailable; no whole-tick samples                   |
| Repository admission wait/hold wall and thread CPU        | Unavailable; unloaded/loaded diagnostics not run     |
| Actual capture intervals and acquisition freshness        | Unavailable                                          |
| Scrape preparation and history-request latency            | Unavailable                                          |
| Observer scheduling and completion-delivery delay         | Unavailable                                          |
| CPU regression, event-loop contention, source correctness | Not evaluated by new measurements                    |

Instrumentation-off, counter-instrumented, and trace cohorts remain separate and
empty. Main's private admitted path bypasses public `producer_prepare` and
`source_binding_validation` spans: those spans are **unavailable**, never zero
processing cost. Future comparable producer results must use the complete tick
CPU boundary and depth-zero admission holds. Structural reductions from Task 2
are not evidence of performance improvement.

Canonical backend/static gates were not run after the prerequisite stop. The
GitHub connector returned one PR-triggered workflow for the exact Task 2 SHA:
[Code Quality run 39717733262](https://github.com/bcl1713/starlink-dashboard/actions/runs/39717733262),
completed successfully. This first-page workflow observation does not establish
that all required CI or frontend jobs passed; no waiver is implied.

Historical results are context only: the earlier 2.898 → 5.760 ms producer CPU,
+0.21% backend CPU with an interval crossing zero, and capture gaps of
1.754899/1.583978 seconds are not new corrected-candidate measurements. No net
backend savings are established. The 1.5-second source-observer limit and
historical cadence NO-GO remain unchanged.

## Evidence and cleanup verification

The tracked [evidence manifest](probes/perf391-rank1-task3-manifest.json) records
raw-file SHA-256 hashes, sizes, failures and zero accepted-pair counts. Private
evidence is retained under `/workspace/perf391-rank1-task3-evidence/`:
`preflight.json`, `preflight.py`, `dependency-setup.log`, `ci.json`, `attempts.md`
and `cleanup.json`. Preflight contains exact commands, exit codes, outputs,
package inventory and 132 source/evidence-file hashes across the four new
worktrees. All 132 hashes were rechecked unchanged before report generation.
Historical private raw evidence directories from earlier sessions are not mounted
here; their retention or hashes cannot be independently reverified in this
environment. Existing tracked evidence and its manifests were preserved.

No task Compose project, image, volume, server, browser, worker or listening port
was started. Docker inspection found no containers or volumes, and only the
three default networks. Listener inspection found only the existing platform
listener on port 1040. The temporary Python environment and downloaded Python
interpreter were removed after their inventory was saved; shared dependencies,
cache, Docker daemon/context and configuration were preserved. Worktrees and
evidence remain for review.

**Process cleanup has a limitation:** three defunct Git processes were observed
after setup: PID 628 (PGID 624), PID 658 (PGID 658), and PID 724 (PGID 724), all
adopted by PID 1. Their start times were 10:17:31, 10:17:51 and 10:18:09 UTC.
These coincide with fetch/setup activity and are retained as possible task-owned
remnants. They are already exited; only their parent can reap them. No live Git
helper remains. The task did not signal PID 1 or restart the environment.
Therefore a claim that every task process has been reaped is unavailable.

Task 3 remains blocked for review of the missing runtime dependencies and process
cleanup limitation. No further optimization, 60-minute soak, merge, deployment
or issue closure was performed or authorized by this report. Keep #403, #405
and #406 draft and unmerged, and #391 open.
