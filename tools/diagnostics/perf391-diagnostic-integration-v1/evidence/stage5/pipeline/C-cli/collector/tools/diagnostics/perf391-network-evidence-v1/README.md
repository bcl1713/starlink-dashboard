# perf391-network-evidence-v1

Independent supplemental tooling for
[#391](https://github.com/bcl1713/starlink-dashboard/issues/391), linked to
[#406](https://github.com/bcl1713/starlink-dashboard/pull/406). Release
**1.0.0**, event schema **1**, analysis schema **v1**. This package neither
imports production code nor changes acceptance decisions. Only tooling
implementation and offline validation are authorized here.

Application reference: `3cd79e2ac77557b7ef0ba7bc8bf60069bd260bbc`. Frozen
comparator: `f3029024b5950a267645195476da5cbca326f16a`. Existing diagnostic
protocol: `f7253c687041342ee080b0197f0b98f20eaefdfe`. Their files remain
unchanged. The primary worktree stays on `dev`.

## Offline invocation

Run from this directory. Python 3.11+ and `jsonschema==4.19.2` are required;
Node 22.12.0 is used for the fake-Page tests. No Playwright installation or
browser executable is required for offline validation. `pyproject.toml` supports
installation into a task-owned environment; it changes no application manifest.

```sh
PYTHONDONTWRITEBYTECODE=1 timeout --kill-after=5s 30s \
  python3 -m unittest discover -s tests -v
timeout --kill-after=5s 30s node --test tests/browser.test.mjs
PYTHONDONTWRITEBYTECODE=1 timeout --kill-after=5s 30s \
  python3 -m perf391_network_evidence fixtures --output /tmp/perf391-fixtures.json
python3 -m perf391_network_evidence analyze /owned/observer/events.jsonl \
  /owned/backend/events.jsonl /owned/browser/events.jsonl --output /owned/analysis
python3 -m perf391_network_evidence import-legacy /retained/backend.json \
  --run-id retained-diagnostic-1 --output /owned/imported.jsonl
python3 -m perf391_network_evidence import-stored /owned/stored-matrix.json \
  --run-id diagnostic-1 --attest-stored-range-vector --output /owned/stored.jsonl
```

Outputs use exclusive creation. An analysis writes `analysis.json` and
`analysis.txt`; exit 1 indicates observed collection/sequence integrity issues.
Schema errors, artifact tampering and invalid grids raise errors. Missing
instrumentation stays in `unavailable` and duration `reason` fields. Empty
coverage is **not** coverage approval. Every stream needs its own final summary;
missing summaries make total loss and shutdown coverage unknown, while retaining
separately observed drop counts. The analyzer never returns frozen acceptance
PASS. Fixtures have explicit expectations, fixed virtual clocks and fictional
values. Regeneration uses `python3 fixtures/build.py`; it must produce identical
bytes and hashes. Hashes are in `fixtures/SHA256SUMS.json`.

## Events, clocks and joins

The closed [JSON Schema](perf391_network_evidence/event-schema.json) defines
`boundary`, `anchor`, `coverage`, `resource`, `scrape`, `evaluation`, `history`,
`chart`, `body` and `summary` events. Unknown versions/properties are rejected.
Each event carries run/stream/sequence, clock ID, local monotonic nanoseconds,
PID/TID, optional thread CPU, operation and span IDs. Nanoseconds are decimal
strings to preserve JavaScript precision. CPU is null where unavailable.

Operation IDs join requests or producer ticks across processes; repository span
IDs distinguish repeated admissions within an operation. Repeated boundary names
make an operation duration ambiguous, never last-value-wins. Run IDs must match,
while stream/sequence pairs must be unique. Stream and clock IDs must change
after restart. Equal field values never identify an observation.

Durations require two exact boundaries on the **same monotonic clock**. Thread
CPU additionally requires the same PID/TID. Clock anchors contain UTC and the
local read uncertainty; anchor offset changes are reported. UTC anchors support
approximate alignment only: no subtraction of unrelated monotonic origins, no
automatic clock-offset correction and no cross-process one-way latency claim.
Imported stored timestamps remain UTC sample coordinates; the event timestamp is
the importer's local time, not a synthetic acquisition time.

The timing model separates producer dispatch/start/collection/publication/end/
return-to-loop; ASGI entry/end; worker dispatch/start/end/return; depth-zero
repository wait/acquisition/release; observer scheduled/wake/send/headers/
received/parse/write; and browser request/headers/end/body. Missing final
validation or CAS instrumentation is never inferred from a generic source check.
`producer.collected` means collection completion; it does not prove the source's
physical acquisition instant. Use `identity` to retain explicit source/frame/
route/config/replay identifiers only when actually exposed by a diagnostic hook.

## Collection adapters and bounded storage

`Recorder` bounds pending count (4,096), pending bytes (8 MiB), event size (1
MiB), individual body size (2 MiB), and event/body disk bytes (256 MiB). Drain
regularly; overflow drops new events, preserving sequence holes and separate
dropped-event/body counts. A reserved 4 KiB guarantees a normal final summary,
including write wall time and bytes. Exceptions close the file. A write or disk
failure remains an error; SIGKILL/power loss can prevent a summary. There are no
background drain workers. External callers must stop their workers before
closing. Body hashes cover exact bytes and are verified during analysis;
artifacts are content-addressed and paths cannot escape the owned output root.
Owner/cleanup metadata is separate small fixed-size output, outside stream
quota.

The Node sink writes synchronously under the same event/body/disk limits, with
no event queue. Browser tracking is bounded to eight requests/jobs per Page.
Uncompressed Content-Length must be present and bounded before calling
Playwright `response.body()`; otherwise the body is explicitly unavailable.
Compressed/unknown-length responses require a separately reviewed streaming
adapter; they are never silently decoded or captured without a bound.

`attachHistory(page, sink, {viewer})` observes existing `/api/overview-history`
traffic only. It does not route, issue requests, change headers, set app state,
change poll cadence or use `page.evaluate`. It saves exact bodies and decoded
bundles, preserving viewer/request/bundle IDs and failures. It records
Playwright callback delivery times, **not** network-stack wire timestamps or app
JSON parse completion. App callback/commit timing is explicitly unavailable
externally. Call `await adapter.close()`, close/reap the **owned**
context/browser, then close the sink. A pending-body timeout reports incomplete
cleanup; never claim success or start another run until the owner verifies that
context/process has exited.

`recordPlot` reads an explicitly supplied actual uPlot instance into a chart
event: `[times,max,min,avg,observed]`, visible x domain and module hashes. It
installs no hook. Supply `retainedHistory` from the actual retained projection
input; comparing a rendered plot to only the latest response is invalid because
the application retains older left-margin points. Missing retained input makes
plot comparison unavailable. Only a separately versioned diagnostic build may
call it. Log floors must be declared from that exact build; raw values remain in
the body. Paint intervals need independent screenshot/video evidence; null means
unavailable. No pixels are inferred from the existence of a canvas.

`diagnostic_worker` and `admission` are opt-in diagnostic-build helpers; no
monkey patches, global hook installation, application imports or image builds
are included. Worker completion is recorded after delivery to the awaiting loop;
cancellation drains the owned worker. A stuck callable still needs the owner's
wall-clock timeout. Admission is for an explicit depth-zero call site and
preserves lock release on failure. Do not wrap every nested admission with it.
Collection/final-validation/successful-CAS identities need dedicated existing
call-site evidence; emitting a publication attempt is insufficient.

Legacy import composes existing trace boundaries, preserving source PID/TID,
operation IDs and monotonic scope. It does **not** reconstruct dedicated
producer return, final validation, successful publication, or admission spans
where reliable joins/outcomes are absent. Legacy write bytes/timing are null.
This conservative subset deliberately reports less than the original trace
analyzer.

## Data and gap interpretation

Stored ingestion needs an actual Prometheus instant-query range-vector export
for a single selected job/instance, including `up`, all 11 v2 correctness
families, scrape duration and sample counts. `import-stored` defaults to the
five network families; pass repeated `--field` options for all 11 controls. A
successful matrix shape alone cannot establish stored-sample provenance: the
explicit attestation must be backed by the retained request/query/export hash.
Evaluated `query_range` results are a separate `evaluation` event, including
sampled-source timestamps or null. No finite lookback value is treated as a
fresh stored sample.

Each history event preserves exact bounds/step, finite-only API samples, raw and
five-minute min/avg/max traces, and a seeded/measured segment. Compare an exact
matching evaluation grid before claiming an API projection defect. This requires
matching viewer/request/bundle/segment, source and evaluation IDs, plus
stored-sample timestamp/value provenance. Absent IDs remain unavailable. Plot
analysis independently models timestamp alignment, >1.5×step midpoint nulls, raw
masking of rollups, `spanGaps:false` and declared logarithmic floors.

Classifications include missing ingestion/NaN (`network_data_gap`, which says
nothing about a physical link outage), exact API projection/timestamp defects,
frontend input defects, stale/out-of-order committed bundles, and presentation
gaps with complete input plus paint evidence. Missing upstream provenance or
paint stays unknown. Stored interval jitter is reported separately from missing
values. Evaluation spacing is never labeled acquisition cadence. Overlapping
windows deduplicate missing slots by metric/segment/coordinate. Viewer-specific
null and visible gaps stay separate. Visible intervals must be ordered and
nonoverlapping; raw and rollup null breaks are reported separately.

The classifier checks evidence layers in order and reports the earliest proven
defect, preserving other findings. It does not make exclusive causal claims:
queue/hold/completion durations describe where time was observed, not why the
host descheduled a thread. The historical 1.754899/1.583978 s failures remain
failures under the unchanged 1.5 s gate.

## Bounded runtime commands, for a future authorization only

The current task ran **none** of these commands. They are separate supplemental
processes, never additions to a primary off run. Collection is capped at 180 s;
there is no benchmark, Compose, workload or sustained runner in this package.

```sh
timeout --kill-after=5s 195s python3 -m perf391_network_evidence host \
  --run-id diagnostic-1 --output /owned/host --duration 180 --diagnostic-lane \
  --cgroup /visible/service/cgroup --cgroup /visible/actor/ancestor --pid 1234
timeout --kill-after=5s 195s python3 -m perf391_network_evidence observe \
  --run-id diagnostic-1 --output /owned/observer --duration 180 --diagnostic-lane \
  --url http://127.0.0.1:18000/api/_diagnostic/state
```

Host collection reads CPU/load/PSI, explicit container/ancestor `cpu.stat`,
`cpu.max`, cpusets, I/O and memory, plus supplied process/thread stat/schedstat
at 1 Hz. File reads cap at 64 KiB and thread enumeration at 256 retained
threads. Missing namespace permissions/files stay null with a reason; raw
scheduling counters preserve process/thread start identities. Throttle deltas
reject resets and mismatched clocks. The continuous bounded stream retains the
±10 s context around any anomaly within its edges; missing leading/trailing
context stays unavailable. No subsecond trace, scheduler-cause attribution or
per-core trace is implied by 1 Hz counters.

Source observation records absolute scheduled deadlines and actual callback
entry through receive/parse/disk-drain boundaries, with a 2 s HTTP timeout. It
adds traffic only in the declared diagnostic lane; urllib send is user-space
entry and wire-send is unavailable. HTTP/JSON errors remain coverage events.
SIGINT/SIGTERM stop the loop and close/drain in context managers; owner and
cleanup metadata identify PID/PGID/paths and stop command. No child process,
listener, container or volume is created. The launching owner must reap this
process and verify external runtime cleanup.

## Limitations and checkpoint

Full primary acceptance, CPU benefit, data correctness, chart quality and
reliability are separate gates. Offline fixture passes prove these tooling
contracts only. No actual producer completion/plot/paint diagnostic build is
released here; integration would need its own reviewed build manifest and exact
module/call-site hooks. This is an explicit qualification blocker, not silently
available instrumentation. Original A has no immutable frame identity.

No application modifications are proposed to obtain missing boundaries. The
separate alternative is an opt-in synthetic diagnostic wrapper/build composing
these helpers with the reviewed existing diagnostic call sites. Freeze it,
verify results/exception/cancellation equivalence and review before collection.
Browser-only actual callback/plot/paint integration needs the same separate
review. Physical/live-device evidence and #390's eight-hour integration remain
outside this package. See [calibration proposal](QUALIFICATION.md) and
[offline delivery record](RESULTS.md). Stop for checkpoint review.
