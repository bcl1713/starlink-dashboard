# Corrected-A functional smoke: failed at frontend Finish

One corrected-A smoke executed; **no retry and no C**. Fresh preflight completed
in the same isolated Forge worktree, starting at
`dce002876b3b04316d3e1b1e0b1ba37b11bf3de6`, under the
[consolidated authorization](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6373144033).

The actual runtime failure was `frontend not drained` from `__perf391Finish`.
Finish was admitted but produced no successful final result. The last retained
pre-Finish summary had seq 59, lost/pending/inflight 0 and closed false; that
snapshot does not establish the state when Finish threw. No application fix or
root-cause conclusion is claimed. [Finish inputs/state](evidence/completed-a/runtime/browser/frontend-finalization.json)
and [actual failure](evidence/completed-a/runtime/browser/failure.json) are preserved.

- Host: all five scheduled observations completed with 1.000-second scheduled
  gaps, no skips. Source: four completed observations, then cancellation/abort;
  three observed wake gaps were 0.999905400, 1.000129000 and 0.999480482 seconds.
  The full five-observation requirement **failed**; the 1.5-second gate stayed intact.
- Chart: one correlated HTTP 200 gzip history response, parsed data, retained
  history, projection and actual uPlot inputs for latency commits `p/c29` and
  `p/c30` are retained. Both create and setData commits were observed. This partial
  evidence does not qualify the failed run as complete.
- One compositor attempt: unavailable because generation/viewport changed
  (`p/c29` → `p/c30`). The screenshot artifact and bracket metadata remain.
- Node closed with `complete=false`, dropped 0; browser observer reported lost 0,
  no pending/owned operations. Source was failed/cancelled after four completions.
  Backend final export was preserved before teardown, drained, with buffered,
  dropped, failures, invalid, token evictions and unavailable counters all 0.
  **Whole-run mandatory loss/Finish accounting fails.**

[Machine outcome](evidence/completed-a/outcome.json) contains the precise request,
commit/snapshot hashes, cadence, counters and capability limits.

The five launch paths were resolved to exact relative roles inside this worktree,
checked against starting-commit bytes and hashes with no symlink escape, and all
non-path fields compared exactly. Historical launch SHA remains
`f15d657727bd029e54233e783cfa1acdf18f6889c7180f9dba4158c4182ce0e2`.
All frozen identity guards, historical evidence, receipts, overlays and application
sources remain unchanged. Private pinned Python wheels, regenerated context,
eight immutable images, compiled asset/module closures, Node 22.22.2,
Playwright 1.63.0/Chromium 1243, three-layer Compose, Owner and bound executor
activation passed; runtime frontend HTTP readiness passed.

There were two local harness errors before activation: the inherited Owner check
used a non-synthetic run name, and continuation initially lacked a receipt local.
Their traces are retained. Only unexecuted prerequisites continued after correction;
context regeneration and the Owner exercise each occurred once. No guard was bypassed.
The unchanged executor ran through `binding.bound_executor()` with 78/90/10-second
work/outer/grace policy. No further approval checkpoint was requested.

[Host cleanup audit](evidence/completed-a/cleanup.json) checked 79 recorded entries;
[independent post-cleanup audit](evidence/completed-a/post-cleanup.json) also checked
41 distinct nested runtime PID/start identities. All absent; ports 38080–38083 free;
scoped containers/networks/volumes empty; private wheels/venv, generated context,
runtime root and lock removed. All eight image configurations/layers/tags unchanged.
Only open-PR worktree and evidence remain. No builds/pulls, production changes,
benchmarks, sustained tests, C runs, merge or deployment occurred.

[Outcome manifest](completed-a-manifest.json) hashes this report, the task harness
and the new evidence. The historical manifest and historical evidence remain unchanged.
