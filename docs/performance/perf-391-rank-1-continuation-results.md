# Rank 1 Task 3: bounded Forge continuation results

**Approved short measurements completed; retain NO-GO and stop for review.** The
matched uninstrumented runs do not establish whole-backend CPU savings beyond
ordinary variation. Producer tick CPU and depth-zero repository hold CPU fell
locally. These short controls do not qualify historical cadence or authorize a
sustained soak.

This is the current Task 3 report for
[draft PR #406](https://github.com/bcl1713/starlink-dashboard/pull/406), under
the
[continuation review](https://github.com/bcl1713/starlink-dashboard/pull/406#issuecomment-6339790818).
The [fixed schedule](perf-391-rank-1-continuation-schedule.md) was committed at
`eef47f41` before measurements and pushed unchanged while the fixed runs were
underway. [Results](probes/perf391-rank1-continuation-results.json) and the
[raw-evidence manifest](probes/perf391-rank1-continuation-manifest.json) retain
every run and comparison.

## Scope and identity

All 24 new production runs passed their individual availability checks and all
18 new comparisons passed the unchanged frozen v2 validator. All 24
diagnostic/calibration runs completed with verified cleanup; each of the 12
trace runs had zero dropped events. No replacement runs were selected. Accepted
off r1 and rejected/partially cancelled r2 remain unchanged in the
[recovery report](perf-391-rank-1-dependency-recovery.md). The
[cloud preflight](perf-391-rank-1-results.md),
[Forge preflight](perf-391-rank-1-forge-results.md), their manifests, and
historical evidence remain preserved.

| Role/input                    | Exact revision                             |
| ----------------------------- | ------------------------------------------ |
| Original                      | `25e34168f0e2cecb149b0323f1f5a795cb28cae0` |
| Dev                           | `33b60fa85c0d0b80d9b82ea5eac7d612a54f4c96` |
| Uncorrected                   | `e1f657986f7b988a967ddd2bef8ca4626e30b5de` |
| Corrected application         | `3cd79e2ac77557b7ef0ba7bc8bf60069bd260bbc` |
| Approved protocol/diagnostics | `f7253c687041342ee080b0197f0b98f20eaefdfe` |
| Frozen availability-v2        | `f3029024b5950a267645195476da5cbca326f16a` |

Four new preflight production builds and every measured image matched the
historical 89-package appuser inventory hash
`03cf956e500c08952d7b1a1747f24e391f6d0c5cf32a675a93c55847c92e9a40` (FastAPI
0.156.8). A separate private Python 3.11.16 environment reproduced all 93
component packages (FastAPI 0.158.1); no component runs were repeated.
Production Python remained 3.11.17. Forge i9-10900K/20 logical CPUs, kernel
7.0.0-34-generic, Docker 29.8.1/overlayfs, daemon memory, Node v22.12.0,
Playwright 1.63.0, Chromium 153.0.8010.12/SwiftShader and actual headless-shell
hash matched retained controls. Actor parent quota remained `1000000 100000`;
session quota was unlimited.

Production runs used 120 s warmup and 180 s measurement, two Overview viewers
plus Operator, 1920×1080/DPR 1, 1 Hz scrape/evaluation, 30-minute history, and 2
CPU/2 GB per service. Diagnostics used 5 s warmup/30 s measurement, three paired
repetitions per unloaded/loaded trace and separate off calibration group,
reversing application order in r2. All performance jobs were sequential;
regressions started after the last calibration.

## Backend CPU and variation

Off pairs are retained r1 plus all new r3/r4/r5 pairs. Counter pairs are new
r1/r2/r3 only. Values below are means of per-run CPU cores; changes are
corrected minus baseline. Percentages average the per-pair percentages.
Intervals are descriptive Student-t intervals over paired run differences, not
thousands of independent tick samples. With four/three runs and host/order
variation, confidence is limited. No observer-overhead subtraction or
off/counter pooling was used.

| Cohort   | Baseline    | Pairs | Before → corrected cores | Paired delta cores | Mean paired change | Descriptive 95% delta |
| -------- | ----------- | ----- | ------------------------ | ------------------ | ------------------ | --------------------- |
| off      | uncorrected | 4     | 0.231624 → 0.229636      | -0.001988          | -0.86%             | [-0.007120, 0.003145] |
| off      | original    | 4     | 0.233582 → 0.229636      | -0.003946          | -1.68%             | [-0.011856, 0.003965] |
| off      | dev         | 4     | 0.234078 → 0.229636      | -0.004442          | -1.90%             | [-0.009677, 0.000792] |
| counters | uncorrected | 3     | 0.246655 → 0.246875      | 0.000220           | 0.09%              | [-0.010004, 0.010444] |
| counters | original    | 3     | 0.247308 → 0.246875      | -0.000433          | -0.17%             | [-0.012886, 0.012021] |
| counters | dev         | 3     | 0.247731 → 0.246875      | -0.000856          | -0.34%             | [-0.014185, 0.012474] |

Every backend interval crosses zero. Corrected/uncorrected off changes ranged
from −0.004679 to +0.002662 cores; r5 increased CPU by +1.15%, while the other
three pairs decreased it. Whole-backend savings and regression remain unproven.
The result does not support a system-wide savings claim. Individual values, all
raw variability and original/dev comparisons remain in the results artifact.

## Producer CPU and repository admission

The retained three component pairs showed two-POI mean tick CPU 2.455 → 2.161 ms
(mean paired −11.99%, descriptive 95% delta [−0.427, −0.163] ms); no new
component measurements were added. In production counters, complete-tick CPU is
the common boundary:

| Tick CPU, ms; mean run quantile | Uncorrected | Corrected | Paired delta | Descriptive 95% delta |
| ------------------------------- | ----------- | --------- | ------------ | --------------------- |
| p50                             | 5.729       | 5.084     | -0.645       | [-0.779, -0.512]      |
| p95                             | 7.231       | 6.153     | -1.078       | [-2.111, -0.045]      |
| p99                             | 8.615       | 7.818     | -0.797       | [-5.099, 3.504]       |

Trace admission results below use real depth-zero producer acquisitions/holds.
Admission starts carry depth; their emitted span IDs join to ends for wait
wall/thread CPU. Release records carry depth and measured hold wall/thread CPU
directly. Durations are process-local; no clock-origin subtraction or
reconstructed resource spans. Cells show the mean of three per-run p50 / p95 /
p99 / maximum values in ms, not pooled percentiles.

| Trace workload | Depth-zero boundary | Uncorrected p50 / p95 / p99 / max, ms | Corrected p50 / p95 / p99 / max, ms |
| -------------- | ------------------- | ------------------------------------- | ----------------------------------- |
| unloaded       | Wait wall           | 0.114 / 0.205 / 0.952 / 0.952         | 0.110 / 0.205 / 23.839 / 23.839     |
| unloaded       | Wait thread CPU     | 0.110 / 0.188 / 0.246 / 0.246         | 0.110 / 0.187 / 0.267 / 0.267       |
| unloaded       | Hold wall           | 0.387 / 4.227 / 56.192 / 56.192       | 0.389 / 2.929 / 4.753 / 4.753       |
| unloaded       | Hold thread CPU     | 0.386 / 3.996 / 4.798 / 4.798         | 0.387 / 2.839 / 4.144 / 4.144       |
| loaded         | Wait wall           | 0.155 / 3.665 / 57.281 / 57.281       | 0.164 / 1.662 / 28.510 / 28.510     |
| loaded         | Wait thread CPU     | 0.152 / 0.281 / 0.397 / 0.397         | 0.154 / 0.277 / 0.369 / 0.369       |
| loaded         | Hold wall           | 0.551 / 9.958 / 29.534 / 29.534       | 0.585 / 7.887 / 53.415 / 53.415     |
| loaded         | Hold thread CPU     | 0.526 / 5.266 / 7.052 / 7.052         | 0.535 / 4.387 / 5.716 / 5.716       |

| Trace workload | Mean hold CPU before, ms | After, ms | Paired delta, ms | Descriptive 95% delta, ms |
| -------------- | ------------------------ | --------- | ---------------- | ------------------------- |
| unloaded       | 1.353                    | 1.103     | -0.250           | [-0.364, -0.137]          |
| loaded         | 1.894                    | 1.591     | -0.304           | [-0.386, -0.222]          |

Hold CPU fell in both trace workloads. Corrected unloaded wait wall p99/max and
loaded hold wall p99/max are higher in these three-pair summaries. Wait and
wall-hold tails remain variable and require review; short-run distributions do
not prove a universal latency improvement or resolve an ambiguous tail.
Copied-POI/frame work is unchanged. Gate-lookup counts, full
tick/collection/frame/final-check/publication distributions, and per-run counts
are retained in the artifact.

Public `producer_prepare` and `source_binding_validation` hooks have no coverage
of corrected private main calls: their durations are **unavailable, never
zero**. The unmodified `frame_prepare`, `source_validation`, publication, gate
class and whole-tick wrappers retain common coverage. Counter
`backend_metrics_prepare` is exporter preparation, not the missing producer
hook. Structural operation counts/order are established by regression tests, not
fabricated trace spans.

## Prometheus and browser resources

Comparisons below use uncorrected/corrected pairs. CPU is mean cores; memory is
the mean per-run peak MiB (not mean resident memory). The artifact includes each
run, slopes, endpoints, PSS and all original/dev comparisons.

| Cohort   | Resource             | Before   | Corrected | Paired delta | Descriptive 95% delta |
| -------- | -------------------- | -------- | --------- | ------------ | --------------------- |
| off      | Prometheus CPU cores | 0.020242 | 0.019938  | -0.000304    | [-0.001677, 0.001069] |
| off      | Browser CPU cores    | 9.626240 | 9.628673  | 0.002433     | [-0.016576, 0.021441] |
| off      | Backend peak MiB     | 331.61   | 331.45    | -0.16        | [-4.25, 3.93]         |
| off      | Prometheus peak MiB  | 44.09    | 46.17     | 2.09         | [-1.12, 5.30]         |
| off      | Browser peak RSS MiB | 2741.66  | 2743.95   | 2.29         | [-23.80, 28.38]       |
| off      | Browser peak PSS MiB | 2216.90  | 2220.46   | 3.57         | [-17.04, 24.18]       |
| counters | Prometheus CPU cores | 0.020571 | 0.020408  | -0.000164    | [-0.003740, 0.003413] |
| counters | Browser CPU cores    | 9.611079 | 9.610576  | -0.000503    | [-0.017731, 0.016725] |
| counters | Backend peak MiB     | 331.75   | 331.45    | -0.31        | [-1.11, 0.49]         |
| counters | Prometheus peak MiB  | 45.97    | 47.05     | 1.08         | [-2.56, 4.73]         |
| counters | Browser peak RSS MiB | 2744.96  | 2734.01   | -10.96       | [-34.53, 12.62]       |
| counters | Browser peak PSS MiB | 2220.45  | 2210.09   | -10.36       | [-42.06, 21.35]       |

The frozen sparse-resource rules remained unchanged, including the 10 s span
guard. Every new comparison passed. Rejected r2 is not rehabilitated: its six
TSDB storage samples covered ~155/160/170 s across roles. Raw sampling offsets
and measured-window timestamps for prior/new runs are retained in the results
and manifest. No TSDB sample was removed, span reconstructed, or validator
contract changed; no further validator decision was required by this
continuation.

## Scrape/history latency and source freshness

**Off scrape duration is unavailable.** Frozen `final-scrapes.json` retains the
`up` series, not a scrape-duration distribution. Counter `/metrics` timings
below are instrumented backend ASGI wall time, not an off-cohort Prometheus
scrape RTT. This clarifies the earlier recovery report’s reference to raw scrape
latency; no missing duration is presented as zero and no frozen collector was
extended.

| Cohort   | Latency boundary      | Before p50 / p95 / p99, ms  | Corrected p50 / p95 / p99, ms | Descriptive 95% p95 delta, ms |
| -------- | --------------------- | --------------------------- | ----------------------------- | ----------------------------- |
| off      | Browser history       | 207.853 / 330.427 / 384.283 | 207.129 / 326.846 / 384.745   | [-34.082, 26.920]             |
| counters | Browser history       | 208.165 / 330.668 / 395.399 | 210.432 / 336.328 / 386.613   | [-31.119, 42.438]             |
| counters | Backend /metrics ASGI | 3.405 / 72.120 / 144.121    | 4.158 / 58.461 / 148.928      | [-64.118, 36.800]             |

History p95 and counter `/metrics` p95 paired intervals cross zero; neither a
repeatable improvement nor a repeatable regression is established by these small
cohorts. Per-run sample counts and tails remain visible.

| Cohort   | Source boundary      | Before p50 / p95 / p99 / max, ms          | Corrected p50 / p95 / p99 / max, ms       |
| -------- | -------------------- | ----------------------------------------- | ----------------------------------------- |
| off      | Observer capture gap | 1000.021 / 1106.056 / 1188.731 / 1210.922 | 999.899 / 1096.248 / 1159.726 / 1211.773  |
| off      | Acquisition age      | 549.986 / 979.557 / 1142.490 / 1178.620   | 503.666 / 981.874 / 1155.527 / 1217.947   |
| counters | Observer capture gap | 1000.083 / 1089.580 / 1137.488 / 1218.154 | 1000.220 / 1094.616 / 1205.507 / 1236.234 |
| counters | Acquisition age      | 566.336 / 994.037 / 1110.303 / 1121.331   | 512.014 / 984.095 / 1125.591 / 1179.536   |

Across all 24 new production runs, the largest measured observer capture gap was
**1.306422 s** and maximum acquisition age was **1.304102 s**. All short
availability checks passed the unchanged 1.5 s observer-cadence rule. Diagnostic
capture gaps also had zero >1.5 s intervals. Acquisition age and observation
intervals are distinct; a 1 Hz observer cannot establish every intermediate
producer acquisition or a universal completion-delivery bound. Historical >1.5 s
behavior remains unresolved.

## Completion delivery, instrumentation and scheduling

Backend HTTP worker completion delivery is the process-local interval from
worker execution end to dispatch completion. It is separate from observer
wake/send/receipt and from acquisition-to-acquisition collection gaps. There is
no dedicated producer tick return-to-loop completion event; that boundary is
unavailable.

| Trace workload | Boundary                   | Before p50 / p95 / p99 / max, ms   | Corrected p50 / p95 / p99 / max, ms | Descriptive 95% p99 delta, ms |
| -------------- | -------------------------- | ---------------------------------- | ----------------------------------- | ----------------------------- |
| unloaded       | HTTP worker return to loop | 0.057 / 0.083 / 0.085 / 0.085      | 0.067 / 0.096 / 0.113 / 0.113       | [-0.053, 0.109]               |
| unloaded       | Backend heartbeat lag      | 0.188 / 1.513 / 48.810 / 78.732    | 0.172 / 1.068 / 47.121 / 50.398     | [-4.630, 1.251]               |
| unloaded       | Observer wake delay        | 0.000 / 0.458 / 1.171 / 1.171      | 0.000 / 0.485 / 1.195 / 1.195       | [-0.027, 0.074]               |
| loaded         | HTTP worker return to loop | 0.080 / 2.850 / 65.915 / 65.915    | 0.091 / 4.631 / 11.367 / 11.367     | [-331.121, 222.026]           |
| loaded         | Backend heartbeat lag      | 0.478 / 55.912 / 138.907 / 224.215 | 0.517 / 62.045 / 137.813 / 253.227  | [-60.521, 58.333]             |
| loaded         | Observer wake delay        | 7.784 / 8.916 / 10.795 / 10.795    | 8.128 / 10.003 / 11.687 / 11.687    | [-58.539, 60.323]             |

Completion-delivery and scheduling tails remain uncertain with three short
pairs; no fix for the historical 202.938 ms delivery tail or cadence failure is
claimed. Raw request-ID joins, HTTP receipt, queue/service/return, observer
CPU/wake/loop delays, scheduler wait, cgroup CPU/throttling and all run-local
clocks are preserved. Throttling occurred in this fixed limited-service
environment; it is recorded, not removed or assigned a causal explanation.

| Diagnostic workload | Instrumentation | Before backend CPU ms / 30 s | Corrected backend CPU ms / 30 s | Paired delta ms |
| ------------------- | --------------- | ---------------------------- | ------------------------------- | --------------- |
| unloaded            | trace           | 31679.968                    | 31312.655                       | -367.313        |
| unloaded            | off             | 31128.867                    | 30776.761                       | -352.106        |
| loaded              | trace           | 40614.877                    | 40425.001                       | -189.876        |
| loaded              | off             | 40397.497                    | 40417.458                       | 19.961          |

Calibration and trace are separate workload groups. They demonstrate
observer/instrumentation context; their CPU is not substituted for production
off results and estimated overhead is not subtracted.

## Verification, evidence and cleanup

Canonical backend passed: **4,616 passed, 20 skipped**. Canonical frontend
passed: **308 files / 2,102 tests**, followed by a successful production build.
Nonfatal test/build warnings remain in the logs. **Canonical static failed and
is not waived:** the byte-identical preserved cloud report has 50 MD060
table-alignment errors and one MD018 heading-spacing error. The subsequent full
internal-link check also failed on the preserved Forge report’s link to absent
`perf-391-rank-1-measurement.md`. Both defects are present in `060b799c`;
earlier reports were deliberately preserved rather than silently reformatted or
relinked. Changed-document lint and links passed. The tooling tests passed
**12/12** after creating a missing private basetemp parent; the original
2-pass/10-setup-error attempt is retained. Supplemental checks do not turn
canonical static green.

- Canonical `./tools/verify backend`: passed. Exact command, limits, source
  identity and exit are retained in the manifest evidence.
- Canonical `./tools/verify frontend`: passed. Exact command, limits, source
  identity and exit are retained in the manifest evidence.
- Canonical `./tools/verify static`: failed (see recorded exit and log). Exact
  command, limits, source identity and exit are retained in the manifest
  evidence.

Regression checks use a separate private environment resolved from the canonical
dev/GFS requirements; it is not a new performance dependency cohort.
Application/backend/frontend/tools bytes remain identical to exact Task 2
`3cd79e2a`; no application code, requirements or production Dockerfile was
edited. Final exact-head GitHub checks are reported on PR #406 separately from
this local evidence snapshot.

Final host verification found no owned processes/groups, browser groups,
listeners, containers, networks, volumes or image tags. Private source exports,
venv, regression cache/data and temporary dependency links were removed. Raw
evidence and open-PR worktrees remain; shared runtime, configuration, caches and
credentials were preserved.

Historical Task 6/v2 and both local preflight/recovery evidence manifests are
rehashed before and after continuation. The earlier cloud report/manifest remain
unchanged; off-host private cloud artifacts are not represented as locally
rehashed. Analysis-only readers corrected missing-series assumptions, joined
admission span starts/ends by ID, and retained structured observer CPU without
treating it as a scalar. These changes did not alter raw runs, frozen analysis,
comparators or accepted pairings.

The approved short matrix is complete. **Retain NO-GO and stop for review:**
system-wide savings and historical cadence qualification remain unproven, with
ambiguous latency tails. No additional optimization, 60-minute soak, merge,
deployment or issue closure. Keep #403/#405/#406 draft and unmerged and #391
open.
