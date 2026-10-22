# Rank 1 Task 3: dependencies reproduced; measurement coverage stop

**Task 3 remains incomplete and NO-GO.** The dependency blocker from `0f91c36b`
is resolved on Forge. Three matched component pairs show lower producer CPU on
the fixed fixture. The unchanged production comparability validator rejected
repetition 2, so the matrix stopped without relaxing guards or retrying. One
production pair per comparison qualified; three are required. No whole-backend
savings or regression is established, and admission delays remain unmeasured.

This updates
[draft PR #406](https://github.com/bcl1713/starlink-dashboard/pull/406) under
the approved protocol at `f7253c68` and the
[latest review](https://github.com/bcl1713/starlink-dashboard/pull/406#issuecomment-6338733039).
The [earlier Forge preflight](perf-391-rank-1-forge-results.md), cloud
preflight, and frozen historical evidence remain unchanged. No application,
requirements, production Dockerfile, harness, threshold or shared environment
was changed.

## Dependency reproduction

The
[complete inventories and comparisons](probes/perf391-rank1-dependency-recovery.json)
record both lanes independently.

- Component: a new task-owned Python **3.11.16** venv reproduced all **93**
  recorded packages, including FastAPI **0.158.1**. Constraints were
  reconstructed from the retained `perf391-independent/install.log` (87
  packages) plus `format-install.log` (six tooling additions before
  `component-final`). Actual distribution inventory equality, executable imports
  and `uv pip check` passed. Installation used `--no-cache`; repository
  manifests and shared installations were preserved.
- Production: all four exact-source backend images were built with their
  approved Dockerfiles and normal frozen-runner build arguments. Builds reused
  retained dependency layers. Every **appuser** inventory contained **89**
  packages and matched the retained availability-v2 original reference
  byte-for-byte:
  `03cf956e500c08952d7b1a1747f24e391f6d0c5cf32a675a93c55847c92e9a40`. This
  reference uses FastAPI **0.156.8** and Python **3.11.17**, independently
  verified in the production lane. The older October 20 inventory is a different
  dependency cohort and was not substituted for the v2 reference.

Exact installed equality is demonstrated for these cached builds; unpinned
requirements do not guarantee that a future fresh resolution will reproduce
them. No private production lock or version substitution was introduced.

**Superseded attempts are retained:** initial component setup mistakenly used
only the 87-package install log. Two completed component runs and a third
cancelled run are rejected and excluded from every result. The third was
explicitly terminated after discovering the later tooling log; its GNU timeout
wrapper returned 124 after about 4.7 seconds, not after a five-minute
expiration. The old process tree was verified gone, all six additional exact
packages were installed, and complete equality/compatibility/import checks
passed before six fresh runs in `matched-runs/`. This correction is not an
accepted retry of a failed measurement. The later production coverage rejection
was not retried.

## Source and runtime identity

| Role                    | Exact commit                               |
| ----------------------- | ------------------------------------------ |
| Original                | `25e34168f0e2cecb149b0323f1f5a795cb28cae0` |
| Dev                     | `33b60fa85c0d0b80d9b82ea5eac7d612a54f4c96` |
| Uncorrected             | `e1f657986f7b988a967ddd2bef8ca4626e30b5de` |
| Corrected               | `3cd79e2ac77557b7ef0ba7bc8bf60069bd260bbc` |
| Approved tools/protocol | `f7253c687041342ee080b0197f0b98f20eaefdfe` |
| Frozen availability-v2  | `f3029024b5950a267645195476da5cbca326f16a` |

Remote dev still matched the approved baseline. Exact source archives were used;
application and harness worktrees remained clean. Forge hardware/runtime matched
retained controls: i9-10900K, 20 logical CPUs, kernel `7.0.0-34-generic`, Docker
29.8.1/overlayfs and 65,915,523,072 daemon-visible memory bytes. Current actor
ancestor CPU quota was recorded as `1000000 100000`; session quota was
unlimited. The configured `unix:///run/user/1002/docker.sock` and context were
preserved.

Node v22.12.0, Playwright 1.63.0, Chromium 153.0.8010.12 and the SwiftShader
renderer matched the frozen controls. The actual launched headless-shell SHA-256
was `ded93a9c9a53a1ae040f08124badcca95c938e9d5015ff340c3b5538c41bf39e`. The full
Chromium executable has a different hash and was not confused with the launched
shell. A task-local `NODE_PATH` resolved the existing browser packages; no
dependency link or installation changed the frozen checkout. Completed
production runs independently recorded matching browser/runtime identities, 1 Hz
scrape/evaluation, 30-minute history, two Overview viewers plus Operator,
1920×1080/DPR 1, and 2 CPU/2 GB limits per service.

## Component producer CPU

Three sequential alternating uncorrected/corrected pairs used the unchanged
approved component tool, separate unprofiled timings and profiles. Each role has
300 tick samples at 0/2/10 POIs and 90 at 100/1,100 POIs. The
[results artifact](probes/perf391-rank1-recovery-results.json) includes every
per-run mean, median, p95, p99 and maximum.

At the primary two-POI fixture, mean full-tick CPU averaged **2.455 → 2.161
ms**. Mean paired change was **−0.295 ms**, averaging **−11.99%** across the
three pairs. Paired changes ranged from −0.326 to −0.233 ms; a descriptive
Student-t 95% interval over the three run means was **[−0.427, −0.163] ms**.
Median CPU was 2.495→2.166, 2.371→2.117 and 2.406→2.100 ms; corresponding p95
values were 2.739→2.396, 2.507→2.337 and 2.581→2.217 ms. This is a fixed-fixture
local producer result, not a system-wide saving or cadence diagnosis.

| POIs  | Mean paired CPU change, ms | Mean paired change | Descriptive 95% interval, ms |
| ----- | -------------------------- | ------------------ | ---------------------------- |
| 0     | −0.650                     | −20.84%            | [−2.117, +0.818]             |
| 2     | −0.295                     | −11.99%            | [−0.427, −0.163]             |
| 10    | −0.313                     | −10.18%            | [−0.449, −0.177]             |
| 100   | −0.276                     | −2.82%             | [−1.250, +0.698]             |
| 1,100 | −0.229                     | −0.24%             | [−2.980, +2.522]             |

The intervals are descriptive, with only three paired runs; zero-POI startup
outliers and large-fixture variability remain visible. No large-POI copying
saving is claimed. In repetition 1's separate 20-tick profile at two POIs,
source-check calls fell 60→40, repository-gate lookups 200→160 and active-route
reads 120→80. These are fixture-wide counts, not universal production constants;
overlapping profile cumulative times were not summed as CPU savings.

## Production stop and CPU accounting

Each production control used 120-second warmup and 180-second measurement.
Instrumentation was off. Repetition 1 ran original/dev/uncorrected/corrected;
repetition 2 rotated to dev/uncorrected/corrected/original. Seven runs completed
and passed their individual availability checks. The eighth, repetition 2
original, was cancelled after comparability rejection and remains preserved.

| Run            | Backend CPU cores | Prometheus CPU cores | Browser CPU cores | Comparison disposition           |
| -------------- | ----------------- | -------------------- | ----------------- | -------------------------------- |
| r1 original    | 0.229420          | 0.019538             | 9.629499          | Comparable to r1 corrected       |
| r1 dev         | 0.233074          | 0.020338             | 9.621187          | Comparable to r1 corrected       |
| r1 uncorrected | 0.233789          | 0.020800             | 9.619360          | Comparable to r1 corrected       |
| r1 corrected   | 0.231284          | 0.020720             | 9.622848          | One accepted pair per comparison |
| r2 dev         | 0.233529          | 0.020446             | 9.620251          | Rejected against r2 corrected    |
| r2 uncorrected | 0.227920          | 0.020070             | 9.637291          | Rejected against r2 corrected    |
| r2 corrected   | 0.230912          | 0.020852             | 9.620993          | Rejected resource coverage       |

The only accepted corrected/uncorrected pair had −0.002506 backend cores
(−1.07%); corrected/original was +0.001864 cores (+0.81%), and corrected/dev was
−0.001790 cores (−0.77%). These single-pair observations establish neither net
savings nor regression. No paired confidence interval or production claim was
manufactured from fewer than three accepted pairs. Rejected repetition 2 raw
values are shown for accounting only and are not pooled into a claim.

The unchanged v2 validator rejected
`prometheus.prometheus_tsdb_head_chunks_storage_size_bytes` resource coverage.
All three r2 roles had six samples, but resource spans were:

| Role        | Resource span, seconds |
| ----------- | ---------------------- |
| Uncorrected | 155.000372             |
| Corrected   | 169.999787             |
| Dev         | 159.999076             |

Corrected/uncorrected span difference was 14.999416 seconds, above the unchanged
10-second guard; corrected/dev also exceeded it. Full measured CPU windows were
approximately 180 seconds, which does not waive per-resource coverage. The
metric was not dropped, spans were not normalized to force acceptance, and no
retry was made. Exact rejection details and validator output are retained.

**Counters and timing diagnostics were not started after this stop.** There are
zero accepted counters, unloaded/loaded trace or diagnostic-off pairs.
Production producer CPU distributions, admission wait/hold wall/thread CPU,
completion-delivery delay and their regressions are unavailable. Public
`producer_prepare` and `source_binding_validation` spans bypassed by the private
main path remain unavailable, never zero cost. Complete tick CPU is the valid
component boundary; no depth-zero hold result is invented without a trace. Raw
scrape latency distributions from completed off runs remain in the results
artifact, without a qualified three-pair comparison. Across the seven completed
runs, per-run maximum source-observer capture gaps ranged from 1.157 to 1.235
seconds; maximum acquisition ages ranged from 1.083 to 1.261 seconds. Per-run
p50/p95/p99/max distributions remain in the results artifact. These short
observations do not qualify historical cadence or a timing regression claim.

## Evidence, verification and cleanup

The [manifest](probes/perf391-rank1-recovery-manifest.json) hashes private raw
runs, profiles, commands, inventories, rejection details and cleanup evidence at
`.worktrees/perf391-rank1-task3-forge/.superpowers/forge-task3-recovery/`.
Historical evidence was rehashed before measurement and after cleanup: all 5,385
Task 6 manifest entries and 317 overlapping v2 entries matched, with zero
missing or changed files. Both earlier preflight reports remain unchanged.

Every production run, including the cancelled eighth, verified browser groups
empty, children reaped, task listeners removed, and private containers,
networks, volumes, images and source archives removed. Host-level final
inspection verified no owned process groups or Docker resources remained. The
private venv, exported preflight sources and all disposable component storage
were removed. Shared configuration-preview volumes, caches, credentials and
runtime configuration were preserved. Raw evidence and open-PR worktrees remain.

No new canonical backend/static/frontend or exact-head CI qualification was
completed after the measurement stop; this report does not waive those gates or
represent previous checks as new passes. Documentation/artifact integrity checks
are recorded separately. No application edits were made.

The **1.5-second source-observer limit is unchanged**. Seven individual short
availability checks passed, but short runs do not fix or qualify historical
cadence. Retain NO-GO. No 60-minute soak, optimization, merge, deployment or
closure of #391 was performed. PRs #403, #405 and #406 remain draft and
unmerged. Task 3 returns for review of the preserved coverage failure, with no
guard change or additional measurements proposed as already authorized by this
report.
