# Epic #389 measurement ledger

The [original baseline](perf-390-baseline.md) is application commit
`25e34168f0e2cecb149b0323f1f5a795cb28cae0`. Preserve it throughout this epic.
Compare each change with the **same original workload and harness**, and also
with the preceding integrated application when useful. Never replace original
reference evidence with a rolling previous-PR baseline.

| Issue | Scope                             | Evidence                                                                                       | Measured change                                                            | State                                    |
| ----- | --------------------------------- | ---------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | ---------------------------------------- |
| #390  | Methodology and original controls | [Baseline and limitations](perf-390-baseline.md), [case index](baseline-2026-10-20/index.json) | No optimization; no claimed savings                                        | Kickoff only; final eight-hour gate open |
| #391  | Read-only metrics scrape          | Pending                                                                                        | Not measured                                                               | Pending                                  |
| #392  | Active mission/leg resolution     | [Matched context and 61-minute live-like evidence](perf-392-active-context.md)                 | Instrumented process CPU −79.8%; status p95 −94.9%; Operator p95 +1.350 ms | PR #422; physical/integrated gates open  |
| #393  | Metric label lifecycle            | Pending                                                                                        | Not measured                                                               | Pending                                  |
| #394  | Prometheus rollup queries         | Pending                                                                                        | Not measured                                                               | Pending                                  |
| #395  | Live archive batching             | Pending                                                                                        | Not measured                                                               | Pending                                  |
| #396  | Operator snapshot inputs          | Pending                                                                                        | Not measured                                                               | Pending                                  |
| #397  | Overview rendering                | Pending                                                                                        | Not measured                                                               | Pending                                  |
| #398  | Route geometry reuse              | Pending                                                                                        | Not measured                                                               | Pending                                  |
| #399  | Storage lifecycle                 | Pending                                                                                        | Not measured                                                               | Pending                                  |

Each dependent PR adds its application/harness SHA, original case IDs, matched
hardware/runtime, warm-up and measured spans; absolute and percentage
CPU/RAM/disk/latency deltas; correctness/freshness and negative results; CI
unit/integration proof; risk and rollback. Report different display modes,
workloads, source modes and instrumentation separately. Record unavailable
metrics explicitly. A reduced request count or storage snapshot alone is not
proof of a performance improvement.

Run at least 60 measured minutes for each major hot-path change. Final #390
acceptance requires the integrated eight-hour whole-stack report on
representative display hardware and coverage of the remaining workload matrix.
Do not close #390 on the kickoff PR. Completed #211, #224 and #327 provide
context; this ledger does not reopen their scopes or assign their old results to
this epic.
