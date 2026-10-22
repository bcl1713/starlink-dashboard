# Stage 4: offline collection and analysis

Authorized by
[the Stage 3A orchestrator checkpoint](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6353042788).
Starting commit: `8faeac62601720cec711d0a6ddc97f18a497cb09`. This package
remains independently versioned. Production revisions, Stage 2 and 3A
application patches, frozen acceptance tools and PR #407 are unchanged.

## Collection interfaces

`observer.mjs` implements a supplemental source observer with absolute monotonic
1 Hz deadlines, one request, a total 2 second deadline, 64 KiB headers and 2 MiB
encoded/decoded response limits. It accepts only a loopback HTTP diagnostic
state endpoint. Gzip decoding is incremental; unsupported encodings, status
errors, invalid UTF-8/JSON, transport failure and deadline/cancellation retain
failure outcomes. Requests, response streams, decoders and timers are closed.
Late callback entry and skipped deadlines are distinct; no catch-up requests are
sent. HTTP invocation is not a wire-send timestamp. Record-complete follows a
completed drain and is persisted without recursively timing its own write.

`collect.mjs` owns bounded, AbortSignal-aware disk sinks for that observer and
the existing `browser.mjs` adapter. It records actual Node process/clock
identity separately from browser document clocks, admits two Pages with shared
screenshot budget, tracks pending attachment and source jobs, and closes
bindings/jobs before its file. It never launches or navigates a browser. Disk
budget is at most 256 MiB, artifacts at most 2 MiB each/64 total, streams at
most 32, and metadata has a separate reserve. Large compositor PNGs are
unavailable rather than copied outside this cap. Final summaries and SHA-256
inventories remain separate from the raw adapter records.

`diagnostic_app.py::Boundary` wraps an explicitly supplied diagnostic ASGI app.
It accepts only a run-scoped request header, retains actual send/receive/error
boundaries, and offers the dedicated state endpoint through the original
Starlette/AnyIO pool and supplied repository gate/capture callback. It does not
import production `main`, mount routes into a production app, or replace pools.
The future runtime owner must supply the pinned frozen synthetic state capture
and the real repository gate. State workers survive waiter cancellation under an
explicit owned task; `drain()` reports a deadline failure if they remain. The
process owner must terminate/reap that diagnostic service before closing its
sink when drain fails. Application HTTP workers remain independently visible
through the Stage 2 hooks and owned service process.

`host.py` uses the pinned #407 global/cgroup sampler, plus bounded
process/thread directory iteration. It captures raw CPU/load/PSI, cgroup
quota/throttle/cpuset/ I/O/memory and process/thread stat, scheduling, I/O,
cgroup/status counters. File reads are capped at 64 KiB, eight explicit PIDs,
sixteen explicit cgroups, 256 threads/PID and an 8 MiB retained sample. Missing
files/namespaces/ancestor visibility carry null plus a reason. Boot, namespace,
process/thread start and host clock-kind metadata are retained. Counter deltas
require matching clock, start identity and counter epoch, and reject
decreases/missing counters. Bracketed UTC/monotonic anchors occur at start,
sampling and shutdown; UTC offset steps invalidate approximate alignment without
invalidating explicit ID joins. No Docker PID mapping or real Forge topology is
claimed by offline fixtures.

## Ownership and integrity

`owner.py` records spawn intent before fork and PID/PGID/start identity before
proceeding. Only handles created by that owner enter its shutdown registry.
Signals check group membership and start identity; unrelated owners survive
shutdown. Callback failure does not bypass remaining cleanup. Repeated caller
cancellation waits for the shared shutdown task. Each owned child is waited and
descendant survivors are reported. No Compose, Docker or shared service cleanup
command is generated. Future runtime owners must register external resources
before starting them; this stage owns only short offline test children.

`run.py tests` installs Linux child-subreaper behavior in the runner; the test
entrypoint also adopts nested test descendants. This is process-local adoption,
not an added host capability. It has a 120 second inner deadline. Always retain
an outer GNU timeout with a forced termination grace. The manifest records
source/module/patch identities, processes, budgets, streams, output paths,
guarded cleanup commands and final cleanup status.

`collector.py` exports and verifies the entire exact #407 source dependency at
`a48837b99d87366c6e3fc24ba2915f0b739cddad` before import. It never edits #407.
`evidence.py` uses that Recorder's bounded queue/drain/artifact/final-summary
machinery and its schema validator. A source-preserving queue adapter avoids
replacing backend PID/TID/CPU/clock with collector metadata. The v1 schema
requires integer native TID: browser and Node boundary events with unknown TID
stay in the sidecar, rather than acquiring a fabricated collector TID.
Compatible backend boundaries and collector-owned history/chart/resource/body
records pass through #407. Missing summaries, loss, disk errors and oversize
artifacts prevent a complete-evidence result. ENOSPC can prevent final summary
persistence; returned failure and missing summary/hash files both fail review.

## Joins and analyzer

`integration.py` consumes real Stage 2 drains/stats and Stage 3A sink records.
It verifies full browser artifacts and separate retained/projection/plot hashes,
then projects actual parsed histories and committed arrays into v1. A chart
requires explicit accepted request/object provenance, retained input, actual
plot data and module hashes. Array equality or equal time endpoints never create
a request association. v1 visible-gap and paint claims stay null. The in-memory
API accepts reviewed module hashes; offline CLI input without those hashes
deliberately reports chart input unavailable.

`analyze.py` reports producer collection/publication/final-authority, repository
admission, worker queue/execution/delivery, ASGI, observer, polling, chart-input
and compositor-capture brackets. Every duration requires a unique successful
same-clock pair and intact stream/final-summary evidence. CPU also requires same
process/TID/start identity. Missing, duplicate, failed, restarted or
inconsistent events yield null with a reason. Source/process/document restarts
require new streams; non-browser streams can share an explicitly identical
process clock. Thread identity must remain stable within each stream.

Explicit request IDs join browser requests to ASGI; explicit parent IDs join
worker operations. No browser/backend/host clock origins are subtracted. C
publication counts require observed CAS results; A and missing instrumentation
remain unavailable. Overlapping spans are not additive CPU savings.
`verify_evidence.py` validates closed analysis/summary schemas, checks every
claimed duration against its original event references and verifies the exact
artifact set and hashes. The generic #407 analyzer is supplemental and cannot
replace these outcome/capability checks.

## Offline reproduction

Use a private Python 3.11 environment with `requirements-test.txt`. From this
package, on the host (the managed sandbox's worker/event-loop teardown can
stall):

```sh
timeout --kill-after=10s 140s python -B run.py tests --output artifacts/stage4-new
timeout --kill-after=10s 30s node --test tests/*.test.mjs
```

No test launches services, browsers or real HTTP requests. Fake Pages and HTTP
streams exercise real adapters at external boundaries. Source-slice tests retain
real RepositoryGate/AnyIO/FrameStore behavior. Preserve failed logs as failed
evidence. Read the owner manifest and check host PIDs before retrying a timeout.

For already collected bounded files only:

```sh
timeout --kill-after=10s 60s python -B run.py integrate --role C \
  --backend backend.jsonl --stats backend-stats.json \
  --node-root node-collection --output artifacts/offline-import

timeout --kill-after=10s 60s python -B run.py analyze \
  --events artifacts/offline-import/evidence/integration.jsonl \
  --summary artifacts/offline-import/evidence/summary.json \
  --output artifacts/analysis-new.json
```

The input files are capped at 1 MiB/line and 32 MiB/100,000 events per file.
These commands contain no runtime collection path.

## Available and unavailable boundaries

| Boundary                                                           | Offline status                                                                                         |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| Producer, final authority/CAS in C, A in-place update              | Real Stage 2 hooks and explicit outcomes                                                               |
| Repository admission, selected worker queue/execution/delivery     | Real gate/pool source-slice evidence; arbitrary server workers unavailable                             |
| Source observer and ASGI joins                                     | Deterministic transport/ASGI fixtures; actual network runtime unavailable                              |
| Host/resource counters                                             | Bounded adapter and fixture tests; actual host/container mapping and inaccessible counters unavailable |
| Parsed history, retained input, actual committed chart arrays      | Real Stage 3A adapter projection; module/provenance/hash gates                                         |
| Layout versus compositor capture                                   | Separate clocks/brackets/artifacts; real pixels and continuous presentation unavailable                |
| Raw browser wire bodies / capture                                  | Unavailable: Stage 3B deferred                                                                         |
| Native Axios parse start, one-way cross-process latency            | Unavailable                                                                                            |
| A coherent frame/final authority/CAS, physical acquisition/scanout | Unavailable by design                                                                                  |

## Stage 5 and real-browser qualification

Stop for Stage 4 review. Stage 5 needs a separate checkpoint: reviewed exact
source/patch/module inventories, independently built diagnostic A/C image and
compiled-asset hashes (none exist here), actual actor Docker/host PID/cgroup and
namespace mapping, and reviewed lifecycle wiring for application/browser owners.
A separate runtime decision must precede browser replay, traffic, preflight
launch probes, calibration or sustained testing. Actual browser bundle/request/
retention/uPlot/compositor behavior and instrumentation overhead remain
unqualified. Stage 3B remains deferred without effective permission and verified
cleartext topology or a separately reviewed bounded alternative. No gzip/Nginx/
fetch-path/privilege changes or whole-browser-body fallback are permitted.
Primary unpatched A/C runs and the historical 1.5 second rule remain
independent. Keep #403/#405/#406/#407/#408 draft and unmerged; #390/#391 open.
