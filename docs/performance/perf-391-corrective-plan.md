# Proposed corrective plan for #391 — approval required

Based on the [independent investigation](perf-391-independent-investigation.md)
of PR #403 at `e1f65798`. No application implementation is authorized by this
plan. Preserve the frozen harnesses, 1.5-second threshold, source provenance,
observation clocks, replay ordering and atomic publication.

The user subsequently authorized the diagnostic prerequisite only. Its
[implementation and short matched results](perf-391-diagnostic-phase.md) are now
submitted for review. Optimization ranks below remain unimplemented; historical
cadence attribution is unresolved and #403 remains NO-GO.

## Ranked remediation options

Expected benefits below are hypotheses grounded in measured work, not promised
whole-service improvements. Implement one option at a time and measure it.

| Rank | Narrow option                                                                                                                                                                                                             | Expected benefit                                                                                                                                                | Risk / safeguards                                                                                                                                                                                               | Ownership                                                                                               |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| 1    | Consolidate repeated source capture/admission within one producer operation; avoid adjacent duplicate checks and repeated gate lookup/route resolution when an already-held authoritative admission proves the same input | Best small-fixture target: 9 extra gate lookups, 4 extra active-route reads and 3 overlapping source checks per tick. Exact saved CPU needs a matched prototype | Medium. Keep final authoritative revalidation, external-edit detection, mutation admission and stale-source rejection. Do not introduce a cross-tick mission cache                                              | #391 for duplication introduced here; general repository filesystem optimization separately if needed   |
| 2    | Give producer preparation one clearly owned detached POI snapshot; let internal ETA derivation consume it without copying again                                                                                           | Largest measured scaling target. Two avoidable POI copy layers cost approximately 37–38 ms at 1,100 POIs, versus an 88.6-ms tick; about 0.33 ms at 10 POIs      | Low–medium with explicit ownership. Preserve defensive copying at public/untrusted boundaries and prove source models cannot mutate prepared inputs                                                             | #391                                                                                                    |
| 3    | Compute input identity alongside owned capture and reuse it within that operation; rehash the current authoritative source only at required validation boundaries                                                         | Modest at two POIs; each 1,100-POI JSON/hash pass costs about 3.6 ms. Config/route duplication also exists                                                      | Medium. Keep current semantic identity rules, route timing exclusions, authoritative final checks and replay revision checks. No long-lived revision-only shortcut                                              | #391                                                                                                    |
| 4    | Reduce repeated label normalization/schema scans and duplicate frame validation through a narrow trusted sealed-frame path                                                                                                | Small typical-workload gain; one validation is 0.005 ms at two POIs, 0.184 ms at 1,100. Freeze itself is under 1 ms at 1,100                                    | Medium. Preserve complete-schema validation for arbitrary external frames, immutable scalar storage, one-head collection and stale-head CAS. Do after larger targets                                            | #391 only if measurement justifies added API complexity                                                 |
| 5    | Move detached calculation out of repository admission, with capture and final revalidation/commit inside it                                                                                                               | Could reduce observer blocking without changing scrape authority; CPU saving itself is uncertain                                                                | High. Accepted observation accounting, phase/speed mutation, replay commit ordering and obsolete completion require new race proofs. Start only if timing traces identify hold time as material after ranks 1–3 | #391 architectural follow-up, requiring explicit review                                                 |
| 6    | Change ordinary producer cadence to a monotonic deadline with a defined overrun policy                                                                                                                                    | Removes work-plus-sleep drift; does not itself remove CPU or identify either historical failure                                                                 | Medium–high. Shared pre-existing behavior, live polling semantics and replay wakeups require separate design. Never synthesize catch-up observations or change replay mission time                              | Track under #390/epic scheduling follow-up; bring a bounded #391 correction only if traced as a blocker |

Diagnostic boundary instrumentation is the first prerequisite for the cadence
decision, irrespective of optimization ranking. A new diagnostic wrapper can
record those boundaries without editing either frozen harness or changing its
validator. Do not “fix” acceptance by increasing observer frequency, extending
the 1.5-second bound or replacing missing captures with interpolation.

Do not start #392's active-mission cache or #398's geometry sharing to make #391
look faster. Mission enumeration/loading remains #392; a versioned shared
geometry artifact remains #398. Operator's broader cache validation is #396,
history computation is #394, and display/browser work is #397. If those paths
cause common scheduling stalls, record the independent blocker and coordinate
its issue rather than bundle an unrelated redesign into #391. A serialized
exposition cache is also unjustified by these measurements and outside the
approved architecture.

## Proposed corrective implementation plan — approval required

1. **Keep the acceptance verdict and frozen evidence.** Agree on this report's
   distinction between capture coverage, published freshness and acquisition.
   Keep #403 draft, #391 open and the total-CPU improvement gate unchanged.
2. **Add a separate bounded diagnostic wrapper**, without changing frozen
   runners: record planned wake, actual observer send, headers/body receipt,
   Node loop lag, ASGI entry/response, worker dispatch, repository wait/hold and
   owner, tick dispatch/start/end, actual source acquisition and frame commit.
   Include config/route/input/replay identity tokens. Record cgroup throttling,
   host PSI/runnable delay and thread CPU; avoid payloads/secrets. Use one
   request identifier across boundaries. Retain raw per-event data.
3. **Run short matched diagnostic controls**, first original/candidate with no
   viewers, then two Overview clients plus Operator, under identical runtime
   packages/limits and fixture. Keep profiling, counters and off controls
   separate. Exercise one controlled delay at each boundary to verify
   attribution, then collect natural tails. A short run without a recurrence
   leaves historical attribution unresolved; it does not pass sustained
   acceptance. Stop owned processes after every run.
4. **Implement ranks 1–3 incrementally after approval**, beginning with the
   lowest-risk measured duplication. Keep public defensive-copy APIs and one
   immutable published head. Add meaningful ownership/mutation and race tests:
   changed route/config/POI/source during capture and calculation, external
   reload, phase/timing changes, unavailable source, cancelled work, failure and
   stale CAS. Prove exactly-once observation accounting and unchanged
   acquisition/publication clocks. Replay frames still publish only after
   successful existing `commit_tick`; derived refreshes never advance source,
   smoothing, passage, evidence or counters.
5. **Review measured CPU and timing before architecture changes.** Recheck all
   29 families/position alias, independent instruments, read-only scrapes,
   preflight estimates and compatibility. Repeat warmed matched original/dev/
   corrected-candidate comparisons, instrumentation off and counters separate,
   with three or more accepted repetitions. Require net backend saving beyond
   variability; do not add overlapping component times or subtract estimated
   observer overhead. If insufficient, return to review before ranks 4–6.
6. **Seek a separate sustained-acceptance go-ahead.** Only then repeat required
   original/candidate sustained qualification and operational/rollback checks
   using the unchanged acceptance contract. No 60-minute soak is authorized by
   this investigation. The integrated eight-hour gate remains #390. Submit
   results for review without merge, deployment or closure.

## Reproducing these diagnostics

Use a private Python 3.11 environment with the candidate's requirements and
record installed versions. The submitted probe scripts accept a separate
candidate source checkout; they do not require application changes on this
documentation branch. Choose a new output directory for each run. For example,
from this documentation worktree, with `perf391_source` pointing to an unchanged
checkout of `e1f65798` and `perf391_output` to private task-owned storage:

```bash
PYTHONDONTWRITEBYTECODE=1 timeout --kill-after=5s 180s python \
  docs/performance/probes/perf391_independent.py component \
  --root "$perf391_source" --output "$perf391_output/component"
PYTHONDONTWRITEBYTECODE=1 timeout --kill-after=5s 70s python \
  docs/performance/probes/perf391_independent.py timing \
  --root "$perf391_source" --output "$perf391_output/timing"
```

The `retained` mode instead takes the private Task 6 evidence directory as
`--root` and its frozen `perf391-task6-manifest.json` as `--manifest`. It reads
and hashes those files without rewriting them. The timing mode requires Node
with built-in fetch, opens one ephemeral loopback listener, reuses the source
checkout's unchanged v2 monitor, and injects three explicit stalls. Its output
is diagnostic evidence, never a substitute for acceptance. Preserve profiles,
JSON traces and ownership records; remove only the run's private storage and
environment after checking all recorded PIDs and listeners have stopped.
