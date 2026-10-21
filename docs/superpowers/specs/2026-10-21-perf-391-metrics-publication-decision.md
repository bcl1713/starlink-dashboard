# Metrics publication architecture decision

Status: proposed revision for
[PR #403 review](https://github.com/bcl1713/starlink-dashboard/pull/403#issuecomment-6304866293),
not approval to implement. The
[specification](2026-10-21-perf-391-metrics-publication-design.md) and
[plan](../plans/2026-10-21-perf-391-metrics-publication.md) adopt the decision
below and remain subject to review.

## Decision

Use one bounded immutable snapshot for the 29 coupled dynamic Gauge families and
custom position alias, exposed by a collector in the existing registry. Leave 18
independent Gauges, seven Counters and four Histograms as standard client
objects. Keep the standard serializer. Reject the earlier global epoch,
client-private undo, quarantine restoration and replay-checkpoint architecture.

This changes the consistency requirement from a whole-registry transaction to
one generation for the values that describe a coupled aircraft/route/ETA frame.
Independent cumulative and planning measurements retain their own provenance and
clocks. That explicit boundary is sufficient to prevent the demonstrated
live-position/synthetic-ETA mixture without making counters, GEP and mission
planning metrics participants in a new transaction system.

## Alternative comparison

Let N be coupled samples, I independent samples, W concurrent readers, and J
values touched by a write. Costs below are structural analysis unless a probe
measurement is explicitly cited. No journal implementation was built.

| Approach                                                               | Compatibility and authority                                                                                                                                  | CPU, allocations and memory                                                                                                                                    | Concurrency and recovery                                                                                                                                          | Decision                                                                                                 |
| ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Global optimistic epoch plus undo journal                              | Retains raw Gauge objects but depends on private value, parent-child, histogram and exemplar layouts; supports whole-registry transactions nobody needs here | Every scrape collects O(N+I), potentially repeatedly; writes journal O(J), including child membership; failed restoration requires retained journal/quarantine | Global writers contend; bounded retries may create 503s; exceptions require private restoration and replay state coordination                                     | Reject: broadest scope and maintenance risk, without a demonstrated need for global atomicity            |
| One mutex around writes and complete registry collection               | Preserves client objects, uses public APIs, no second numeric state                                                                                          | O(N+I) allocation/collection occurs under lock; callback collector cost becomes part of lock hold time                                                         | Simple consistency for cooperating writers, but serializes scrapers/producers through full traversal; mid-write exception still needs recovery policy             | Reject: violates short publication-lock boundary and scales lock work with POIs/independent callbacks    |
| Producer-captured complete registry or exposition cache                | Raw gauges remain mutable; captured result is a second retained numeric representation; cache invalidation must cover every independent mutation             | O(N+I) captured per publication, retained complete copy; byte cache additionally makes serialization/metadata freshness a producer concern                     | Straightforward reads, but freezes independent counters/created/exemplars until refresh; failed partial raw writes can poison later capture                       | Reject for this issue: unnecessary dual state and invalidation scope, no evidence byte caching is needed |
| Immutable coupled gauge snapshot with ordinary independent instruments | One numeric authority per family; uses public collector APIs; coupled raw Gauge class identity changes to small staging/read handles                         | Prepare O(N) outside lock; lock copies/swaps one reference; render O(N+I) once; one current frame plus bounded reader/build references, no generation history  | Readers retain a complete old/new frame, no retries; failed preparation is discarded; pending/failed state masks affected values, next existing producer recovers | Select: smallest demonstrated mechanism that meets the scoped consistency requirement                    |

Simply deleting `_prepare_metrics` is also insufficient: it removes the scrape
bug but loses scrape-owned route timing and preflight/lifecycle behavior and
leaves cross-family position/ETA collection interleaving unaddressed.

## Registry and import tradeoff

The standard registry remains the canonical public collection endpoint. The
registered frame collector owns the numeric state for its families, rather than
mirroring separate registered or unregistered mutable Gauges. This is a normal
collector model, similar to existing PositionCollector, not a second exporter.
Dynamic labels are immutable frame entries; public GaugeMetricFamily creates
normal samples and `generate_latest` remains responsible for encoding them.

Preserve existing import symbols, legacy re-export identities, named updater/
clear APIs, metric names/help/types/labels/units, custom position dimensions,
content type and EOF. Existing independent instruments remain actual Gauge,
Counter or Histogram instances, including histogram/counter labels, buckets,
count/sum, exemplars and created series. Their update cost/recovery semantics
are unchanged; no inverse client operations are required.

Coupled exports become frame-backed staging/read handles. They are not actual
Gauge instances and do not promise private `_value` or `_metrics` access.
`labels` returns a view without publishing a child; `set` is accepted only
inside a producer preparation context. A standalone setter cannot partially
patch a live frame. Existing application coupled write sites are concentrated in
the metric updater, scrape exporter, coordinator progress and last-update
accounting. Those sites must migrate; private test resets must migrate too.

The view is intentionally limited to audited call operations, not a general
Gauge proxy. A new compatibility dependency discovered at the stop/go review
returns to design review; do not add hidden mutable shadows or arbitrary
callback-gauge emulation. The scope of this cost is more explicit and testable
than a rollback adapter for every client-private layout and future version.

## Isolated feasibility probe

Executable: [perf391_snapshot.py](../../performance/probes/perf391_snapshot.py).
Compact results:
[snapshot probe results](../../performance/probes/perf391-snapshot-results.json).
This disposable probe imports no application modules and changes no application
or deployment file. It registers three fictional coupled families plus standard
independent Counter/Histogram/Gauge objects and uses only public client APIs. It
demonstrates staging handles, frozen nested values, public collector/encoder
integration, dynamic labels, failed preparation, a barrier-controlled overlap,
superseded-head rejection, standard exemplar/created behavior and an explicitly
independent read-only callback collector, plus a weak-reference check that 100
swaps retain only the current frame.

Reproduce in a disposable test environment, choosing a new output/cache path and
recording ownership before launch:

```bash
timeout --kill-after=10s 3m uv run --no-project \
  --cache-dir /tmp/perf391-probe-026-cache --python 3.11 \
  --with 'prometheus-client==0.26.0' python \
  docs/performance/probes/perf391_snapshot.py \
  --output /tmp/perf391-probe-026-new.json --seconds 30 --iterations 100
```

Repeat with 0.19.0 and separate paths (10 seconds for the recorded minimum-
version case). The output refuses reuse. Verify process/thread exit before
removing the owned cache; preserve result/hash evidence. These commands do not
change production dependencies or invoke Docker.

Test matrix executed on Python 3.11.16 with client 0.19.0 and 0.26.0. Both
passed all ten recorded checks. The minimum-version sandbox attempt first failed
DNS; the isolated host retry succeeded in a disposable uv environment, without a
production manifest change. The 0.26.0 contention run had one 1-Hz writer and
three 1-Hz readers for 30 seconds at 1,100 POIs: 30 operations per participant,
zero mixed frames, zero retries, zero remaining threads. The 0.19.0 run used 10
seconds. These are short component checks, not a 60-minute soak.

Representative 0.26.0 results, 100 serial scrapes per row, nearest-rank
quantiles; CPU and wall timing use separate clocks. Tracemalloc is a separate
one-scrape diagnostic, outside primary timing. The unsafe control uses ordinary
mutable gauges and has the same fictional sample set but no atomicity guarantee.
It is a cost reference, not an acceptable architecture or frozen app baseline.

| POIs  | Model                           | Scrape CPU p50 / p95 ms | Separate scrape allocation peak bytes |
| ----- | ------------------------------- | ----------------------: | ------------------------------------: |
| 0     | Standard mutable unsafe control |           0.109 / 0.114 |                                14,772 |
| 0     | Immutable snapshot              |           0.105 / 0.112 |                                14,475 |
| 10    | Standard mutable unsafe control |           0.156 / 0.166 |                                17,140 |
| 10    | Immutable snapshot              |           0.141 / 0.151 |                                15,611 |
| 100   | Standard mutable unsafe control |           0.555 / 0.576 |                                50,401 |
| 100   | Immutable snapshot              |           0.441 / 0.446 |                                46,033 |
| 1,100 | Standard mutable unsafe control |           5.121 / 5.680 |                               452,631 |
| 1,100 | Immutable snapshot              |           3.823 / 4.229 |                               448,983 |

At 1,100 probe POIs one prepared frame retained 226,350 traced bytes; the
prebuilt pointer publication loop averaged 0.659 microseconds of thread CPU.
That pointer number excludes frame building, validation and source admission; it
is not the producer update cost or mutex hold-time distribution. Traced
frame-building CPU/peak values are included separately in the results and must
not be mixed into uninstrumented distributions. The probe uses one ETA family
and a few position samples, not the complete application dataset or two POI
families. Do not extrapolate the numbers into an application speedup.

A single current frame is retained by the store. Old frames survive only while
bounded in-flight collectors/builders reference them; memory is O((1+W)N) plus
builder and exposition allocations. At a fixed input size, repeated swaps do not
retain generations. There is no second mutable client-value set or internal
history queue. Standard independent client label retention remains unchanged and
is still the subject of #393. Whole-application retention/CPU remains an
acceptance question, not proven by these small results.

No optimistic-journal benchmark or private mutation-restoration spike was
needed: the simpler alternative passed the requested feasibility checks. Its
structural cost comparison is reported honestly as unmeasured rather than
implementing a rejected subsystem or inventing its timing/allocation figures.
The old #390 preparation measurements remain the applicable application
reference.

## Failure and operational consequences

Preparation and label binding are private temporary work, so failure cannot
partially mutate the registered frame or require counter/histogram rollback.
Publish pending/failed status with the existing frame reference; render affected
values as NaN and keep the old successful-observation timestamp. Reject stale
publication/failure attempts after a newer source/config/mission state wins. A
complete next refresh restores values without special repair machinery. Optional
unknown inputs can produce a valid complete frame with per-field NaN.

No normal scrape needs retries or returns 503 because a producer is preparing or
swapping. Genuine registration/collector/serializer errors still fail
explicitly; health must distinguish a recent scrape attempt from successful
publication/exposition. The revised spec adds a small publication-state health
diagnostic and degraded status on publisher/exposition faults, while ordinary
source disconnect remains an available publisher with unavailable observations.

The change does not make replay and registry updates a distributed transaction.
Stage aircraft gauges in the existing callback, publish them only after the
existing runtime commit succeeds, and use existing failed-run handling on an
error. Independent mission gauges preserve their existing clock/producer
semantics. No new replay runtime checkpoint is necessary to keep a prepared
frame out of a successful scrape.

## Remaining gates

The probe does not verify actual 29-family/import migration, full application
concurrency, preflight/source/lifecycle handling, every histogram label case,
restart/export, or long retention. Those remain explicit tests and the stop/go
checkpoint before production replay/lifecycle changes. Do not treat the raw
Gauge identity tradeoff as approved until the revised documents are reviewed.

Preserve all frozen #390 and before-change #391 evidence, comparison integrity,
three matched original/current-dev/candidate controls, separate allocation
profiles, and the minimum 60-minute original/candidate acceptance. No app
savings, GPU/dish qualification, or integrated eight-hour acceptance is claimed.
Return for review if synchronization/view cost erases the gain or compatibility
needs expand. Keep PR #403 draft; do not implement, deploy, merge or close #391.
