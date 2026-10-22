# Rank 1 Task 3: fixed Forge continuation schedule

Declared before execution on 2026-10-22 under the
[bounded continuation review](https://github.com/bcl1713/starlink-dashboard/pull/406#issuecomment-6339790818).
Preserve accepted off r1, rejected off r2, both blocked preflights and every
historical/raw artifact. This schedule adds no component runs or application
changes. No run is selected or excluded for its CPU result.

## Immutable identities and workload

Use the approved protocol at `f7253c687041342ee080b0197f0b98f20eaefdfe` and
unchanged availability-v2 at `f3029024b5950a267645195476da5cbca326f16a`.

| Role        | Application SHA                            |
| ----------- | ------------------------------------------ |
| Original    | `25e34168f0e2cecb149b0323f1f5a795cb28cae0` |
| Dev         | `33b60fa85c0d0b80d9b82ea5eac7d612a54f4c96` |
| Uncorrected | `e1f657986f7b988a967ddd2bef8ca4626e30b5de` |
| Corrected   | `3cd79e2ac77557b7ef0ba7bc8bf60069bd260bbc` |

Reverify Forge/runtime/browser identity and the production lane's historical
89-package appuser inventory before measuring. Preserve dependency layers and
all frozen source bytes. The prior 93-package component environment and three
accepted pairs remain evidence; no new component measurement is scheduled.
Production runs retain 120 s warmup, 180 s measurement, two Overview viewers
plus Operator, 1920×1080/DPR 1, 1 Hz scrape/evaluation, 1,800 s history and 2
CPU/2 GB per service. Use the frozen runner's explicit 1,300 s deadline inside
GNU `timeout --kill-after=110s 25m`, with its ownership and cleanup handlers.

## Fixed order and stop conditions

All runs are sequential. Complete each four-role repetition before comparing
corrected/uncorrected, corrected/original and corrected/dev, in that order.
Retain all three comparison dispositions. Do not pair across repetitions or
choose pairings by result. Run every scheduled repetition unless a stop rule
fires; no replacement repetitions or result-driven extension.

| Cohort   | Repetition | Role execution order                  |
| -------- | ---------- | ------------------------------------- |
| Off      | r3         | Uncorrected, Corrected, Original, Dev |
| Off      | r4         | Corrected, Original, Dev, Uncorrected |
| Off      | r5         | Original, Dev, Uncorrected, Corrected |
| Counters | r1         | Corrected, Uncorrected, Dev, Original |
| Counters | r2         | Original, Corrected, Uncorrected, Dev |
| Counters | r3         | Dev, Original, Corrected, Uncorrected |

Off r3–r5 continue the earlier rotation; counters use the approved reverse
rotation. At most three new complete repetitions per cohort are authorized.
Compare with the frozen validator, including its sparse-resource coverage checks
and 1.5 s cadence threshold. If sparse TSDB coverage blocks any comparison
again, stop after that repetition, preserve raw sampling timestamps and all
rejections, and return for a separately reviewed, separately versioned
validator-contract decision. Never edit the frozen harness, remove metrics or
reconstruct spans. Other correctness, identity, timeout, availability or cleanup
failures also stop execution. Preserve partial/failed runs; do not complete a
repetition across a safety failure.

Counters start only after the off cohort finishes with at least three accepted
pairs per comparison (including retained r1). Diagnostics start only after both
production cohorts establish sufficient coverage. CPU benefit is assessed only
from accepted off pairs, with all accepted scheduled pairs included, paired
variability and confidence limitations. An interval overlapping zero means
savings remain unproven. Missing private-path public instrumentation is
unavailable, never zero.

## Conditional short diagnostics and final checks

If production coverage qualifies, run exactly three uncorrected/corrected pairs
for each unloaded/loaded workload and each trace/off calibration mode, in order:
unloaded trace, unloaded off, loaded trace, loaded off. Each group uses
uncorrected/corrected in r1 and r3, corrected/uncorrected in r2. Preserve the
approved diagnostic tools at `f7253c68`, 5 s warmup, 30 s measurement, 800 s
runner deadline and `timeout --kill-after=110s 15m`. Unloaded has zero viewers
and no Operator; loaded has two viewers plus Operator. No hardcoded historical
matrix runner. Zero dropped events and verified cleanup are required.

Run bounded exact-head canonical backend/static checks separately from
performance work. Rehash historical and new evidence, update the Task 3 report
and manifest in draft PR #406, verify all owned runtime resources gone, and stop
for review. Keep #403/#405/#406 draft/unmerged and #391 open/NO-GO. No 60-minute
soak, application edits, merge or deployment.
