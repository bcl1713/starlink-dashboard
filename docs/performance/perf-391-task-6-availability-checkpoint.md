# Task 6 availability harness checkpoint

The separately versioned `perf390-availability-v2` harness passed its short
original/candidate validation pair. The candidate's real setup NaN was accepted
at its original timestamp; deliberately corrupted captures were rejected. This
is a harness-readiness checkpoint. **Task 6 performance and sustained acceptance
remain incomplete; no CPU improvement or soak acceptance is claimed.**

[Contract and commands](perf-391-availability-contract-v2.md) ·
[Verified results](probes/perf391-task6-availability-v2-results.json) ·
[Retained evidence hashes](probes/perf391-task6-availability-v2-manifest.json) ·
[Original investigation](perf-391-availability-review.md)

## Frozen identities and scope

- Original application: `25e34168f0e2cecb149b0323f1f5a795cb28cae0`.
- Current dev/instrumentation base: `33b60fa85c0d0b80d9b82ea5eac7d612a54f4c96`.
- Candidate application: `aa05a00a626faea475046544737fe218435dd6ab`.
- Measured v2 harness: `f3029024b5950a267645195476da5cbca326f16a`.
- Strict original harness: `13cbf1d54b526307747578ecd4fc691562846834`.

Both short roles used identical v2 source/file hashes, workload,
instrumentation, hardware, runtime/package inventory and browser. All 2,525
original and Tasks 1–5 evidence files reverified unchanged. The strict harness
files also remain byte-identical to current dev; the original detached harness
remains unchanged. Retain all strict controls and failures as a separate cohort.
Historical package drift identified earlier remains a limitation; this does not
replace or rewrite the historical baseline.

This revision changes acceptance tooling and documentation. The branch also
contains the previously prepared Task 6 position-table fix at `aa05a00a`:
Starlette rejects nonfinite JSON numbers, so unavailable position dimensions now
become JSON null while Prometheus retains NaN. Seven RED/GREEN cases reproduced
that HTTP 500 defect. The existing numeric-format test retains every assertion
and uses deterministic available inputs. That independently reproduced fix is
separate from the availability-harness decision; no further production change
was made to satisfy v2.

## Short original/candidate pair

Production Docker images, Nginx, real Prometheus at 1 Hz, two Overview clients
and Operator; 30-minute history, ten-second warmup and 30-second requested
measurement. These short timings establish functional validation, not repeatable
performance.

| Observation                          | Original | Candidate |
| ------------------------------------ | -------- | --------- |
| Reconstructed aligned grid per field | 1,801    | 1,801     |
| Setup unavailable slots per field    | 0        | 1         |
| Finite history coverage              | 100%     | 99.944%   |
| Recovery after activation completion | 56.6 ms  | 106.5 ms  |
| Actual successful measured scrapes   | 30       | 31        |
| Maximum actual scrape gap            | 1.006 s  | 1.000 s   |
| Distinct measured acquisitions       | 30       | 29        |
| Unexplained measured NaN samples     | 0        | 0         |
| Unexpected browser HTTP failures     | 0        | 0         |

The candidate retained one actual stored NaN per field for the documented setup
activation. The API omitted each nonfinite point as intended; the analysis grid
kept all 1,801 coordinates and represented the unavailable coordinate as null.
This is the exact case the strict validator rejects. No finite values were
fabricated, shifted or backfilled. Sample/publication states, source identity,
accepted acquisition times and field availability are retained with the event.

The adapter's measured capture-thread CPU median was 0.681 ms on the legacy
original and 0.172 ms on the candidate. This measures only the capture body, not
all request/serialization overhead. Report and account for this instrumentation
cost in future v2 comparisons; do not attribute the difference to application
CPU savings or combine these numbers with strict-harness measurements.

## Validation and review

The validator separates complete evaluation grids from actual stored samples and
from the unchanged finite-only API projection. It distinguishes explicit NaN,
missing scrape, failed scrape, missing series, shifted grid and filtering error.
Setup recovery must meet its two-second deadline, correct source binding and
required field availability. Steady intervals permit no new unexplained NaNs.
Field-specific replay/network or initial live-speed unavailability is truthful.

A fresh review found four Important gaps before the pair: old soak samples could
age out, provenance lacked identity checks, average acquisition counts could
hide local stalls, and concurrent observer responses could reorder captures. All
four received RED/GREEN cases and fixes. V2 now checks every stored measured
sample, retains overlapping 15-minute API/raw checkpoints, validates
authoritative in-memory source bindings and local clock progress, and serializes
observer reads. Recovery requests use their remaining deadline. No application
publication architecture changed.

- **34 Node adversarial/concurrency cases passed.**
- **28 Python v2/strict-harness tests and 20 subtests passed.**
- **Eight adapter/tool tests passed at each client 0.19.0 and 0.26.0.**
- Offline replay accepted both real captures and rejected eight mutations each:
  missing scrape, measured NaN, finite API deletion, shifted raw timestamp,
  missing raw series, persistent startup failure, late recovery and wrong route.
- Full canonical backend: **4,486 passed, 20 skipped**, one existing Cartopy
  warning, 630.26 seconds under a 30-minute hard limit. Application bytes match
  the measured candidate.

The replay command preserves input files:

```bash
node docs/performance/probes/perf391_availability_replay.mjs \
  FROZEN_V2_HARNESS_DIRECTORY CASE_EVIDENCE_DIRECTORY
```

## Rollback verification

The final revert candidate `bbcdde453480d98a4f3c4f3eea310cbbbedba0db` has a
complete Git tree identical to current dev. Its **114 focused tests passed** in
5.71 s. Production images built and passed a ten-second, zero-viewer
Docker/Nginx/real Prometheus smoke using the frozen strict harness. This
diagnostic overlapped regression work and is excluded from performance
comparisons. It was never applied to a deployment. The rollback bundle and proof
remain retained.

A revert restores legacy scrape-time simulation/ETA work and legacy availability
semantics. It is a tested escape path, not authorization to deploy it.

## Rejected attempts and regression limitations

Every unsuccessful attempt remains retained:

- First short original attempt passed source/history setup checks but could not
  launch Playwright. Broad tooling tests had replaced the feature dependency
  symlink with a local installation and emptied the shared target. The shared
  directory was restored from the identical lockfile; its Playwright version is
  1.63.0. Both roles were rerun from scratch under unchanged v2 source.
- Broad tooling initially lacked optional h5py/netCDF4/rasterio packages. They
  were installed only into the private test environment, without changing
  application requirements or Docker runtime packages.
- The four-minute broad-tooling run timed out and is not a passing suite. A
  focused diagnostic identified subprocess import-path failures; after supplying
  an absolute tools path, **14 passed and three unrelated tests still failed**:
  `test_backend_dockerfile_consumes_candidate_in_app_source_stage`,
  `test_candidate_is_not_persisted_in_dockerfile_runtime_metadata`, and
  `test_lossless_assembly_comparison_has_zero_pixel_difference`. The first two
  assert a Dockerfile layout/metadata contract that already differs in unchanged
  dev; the third requires unavailable `pdftoppm`. No assertion was relaxed and
  no unrelated Dockerfile or PDF tooling was changed.
- Initial static dispatch lacked its required `ACCEPTANCE_POLICY_BASE_SHA`. The
  retained rerun supplies the unchanged instrumentation-base commit.

## Remaining acceptance and cleanup

The next performance work requires at least three matched original/current-dev/
candidate repetitions under this identical v2 harness, with instrumentation off
and counters separate. The required minimum 60-minute measured
original/candidate soaks, separate controlled transition/Operator workloads, and
final performance report remain outstanding. No long soak was started in this
checkpoint. A short pair cannot establish sustained memory/series stability or
net backend savings.

All private runtime resources from the pair and rollback smoke were stopped and
cleaned. Keep the open PR worktree and frozen source/evidence for review;
preserve actor Docker configuration and the original baseline. PR #403 remains
draft and unmerged; #391 and #390 remain open, including #390's final eight-hour
gate.
