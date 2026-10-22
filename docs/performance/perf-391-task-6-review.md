# #391 Task 6 final review and rulings

Disposition: **NO-GO**. PR #403 remains draft/unmerged. Task 6 acceptance, #391
closure, deployment and #390's eight-hour gate are not complete.

A fresh read-only reviewer examined the whole branch from `33b60fa8` through
`dcef4b8e`, plus the Task 6 report and result digest. It reviewed frame
ownership, producer/replay admission, lifecycle refresh/shutdown, HTTP/health,
tests and key failure evidence. It started no services and changed no files.

## Findings and action

- **Important: sustained candidate gate failed.** Capture gaps of 1.754899 and
  1.583978 seconds exceed the frozen 1.5-second bound. Preserve both failures;
  do not salvage acceptance from passing history/scrape subgates.
- **Important: net CPU benefit unproven.** Uninstrumented paired backend change
  is +0.21%, with the descriptive interval crossing zero. Preparation savings
  are offset by producer work. Preserve NO-GO rather than changing architecture
  or acceptance policy without review.
- **Evidence wording corrected:** ready publication is established at the two
  captures bracketing the missed interval, not continuously inside it. This
  factual correction changes no application or validator behavior.

No confirmed new product defect or causal explanation for the cadence failures
was established. The review supports immutable coupled ownership, one-head
collection, independent instruments, public Prometheus APIs, postcommit replay
publication, coalesced lifecycle updates and the retained regression coverage.
It confirms application bytes match measured `aa05a00a`. No deferred cosmetic
minor was left unresolved.

## Rulings on every behavior the reviewer set aside

| Subject                                   | Ruling                                                                                                                       | Cost or remaining risk                                                        |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Capture-gap cause                         | Unresolved; require request/admission/scheduling trace before selecting a fix.                                               | Candidate sustained acceptance remains blocked.                               |
| Changing 1.5 seconds                      | No change; separate acceptance-policy approval required.                                                                     | A genuine measurement-contract defect may require a new frozen cohort.        |
| Exact producer frequency                  | Report sampled distinct acquisition timestamps, not a complete observation census.                                           | Intermediate acquisitions may be missed by the observer.                      |
| Production CPU savings                    | No claim and no speculative observer-overhead subtraction.                                                                   | The performance objective remains unproven.                                   |
| Eight-hour memory/process behavior        | Retain positive PSS trends and bounded startup zombie observations; do not infer long-term bounds.                           | Slow growth may become operationally material.                                |
| Physical dish/GPU/display                 | Explicitly unmeasured.                                                                                                       | Synthetic software-rendered qualification cannot establish hardware behavior. |
| Independent-domain transactions           | Preserve the approved 29-family consistency boundary; mission/GEP instruments remain independent.                            | Cross-domain values do not promise one publication generation.                |
| Fresh tests in reviewer context           | Reviewer inspected retained evidence; executor owns actual timed verification.                                               | Review is not an independent test replication.                                |
| Every raw hash/value/screenshot           | Preserve raw evidence and manifest; executor verifies hashes and selected visuals.                                           | The reviewer did not independently reconstruct every measurement.             |
| Final static/baseline/cleanup bookkeeping | Complete and attach executor checks separately.                                                                              | Those checks were pending when review began.                                  |
| Callback-detachment interleaving          | Static double-read concern in `metrics_changes.py` was not confirmed by a runtime reproducer; no speculative product change. | A shutdown notification interleaving remains a possible diagnostic target.    |
| Merge/deploy/closure/rollback deployment  | None authorized or performed.                                                                                                | Human review and the unmet acceptance gates remain mandatory.                 |

Full review text, exact commands, failed attempts, expanded statistics and
cleanup records are retained in the Task 6 evidence workspace. See the
[performance report](perf-391-results.md) and
[result digest](probes/perf391-task6-results.json). The final path/hash manifest
identifies those artifacts without replacing earlier evidence.
