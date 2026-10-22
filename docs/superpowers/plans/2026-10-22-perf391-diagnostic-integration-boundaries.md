# Perf391 diagnostic integration boundaries

This is part of the
[integration plan](2026-10-22-perf391-diagnostic-integration.md). It is a
proposal only.

## Exact backend integration sites

Paths in this section are under `backend/starlink-location/`. Function names are
anchored to A/C above; line numbers are intentionally not used across revisions.

| File and function                                                                                                                    | Proposed diagnostic-only patch and evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `main.py::_background_update_loop`                                                                                                   | Allocate one tick operation before the existing `create_task(asyncio.to_thread(...))`. Record dispatch there, worker start/end through `invoke_sync`, and returned on the awaiting loop after the existing shield resolves. Preserve the existing repeated-cancellation drain loop, error handling, sleep, replay wakeup and C refresh-owner wait. Record cancelled/error return separately, including worker completion after caller cancellation. Do not replace ownership with the collector's simpler helper. |
| `main.py::_background_update_tick`                                                                                                   | Retain the complete tick bracket including existing error handling and early returns. Do not add a publication check or lock to A. C's entry, retained, disconnected and post-event checks are distinct from final validation. Tag the branch actually taken; no branch is inferred from a later head.                                                                                                                                                                                                            |
| `app/simulation/coordinator.py::SimulationCoordinator.update`                                                                        | Bracket the existing call, and on its normal return capture the returned telemetry's existing timestamp/source and retained-object relation. Project exactly one collected boundary per main tick. Replay `collect()` includes commit/publication, so its outer return must not be mislabeled acquisition completion. Bootstrap generation and scrape-created A simulators are separate operations; they are not background ticks.                                                                                |
| `main.py::_publish_replay_telemetry`, `app/simulation/run_service.py::SimulationRunService.collect`                                  | Retain the existing callback arguments, checkpoint/restore, `prepare_tick`, `commit_tick`, compensation and returned telemetry. Mark replay commit immediately after the existing successful commit; paused/no-advance replay is distinct. Join the inner coordinator return to the same tick. A publishes in-place before runtime commit; preserve that ordering and report the difference.                                                                                                                      |
| `app/core/metrics/metric_updater.py::_update_metrics_from_telemetry_admitted` (C)                                                    | Bracket the actual `final_validation(frame)` invocation once, save its existing result to a local, and branch on that same result. Emit final begin/end plus accepted/rejected outcome. Observe the existing `FRAME_STORE.publish(expected, frame)` boolean without retrying. Keep captured-head callback, independent accounting, exception/fail behavior and final check location unchanged.                                                                                                                    |
| `app/core/metrics/metric_updater.py::update_metrics_from_telemetry` (A)                                                              | Bracket existing mutation completion only. No invented atomic publication, source-final check, or FrameStore. C public entry remains public-entry validation, not a substitute for the private final boundary.                                                                                                                                                                                                                                                                                                    |
| `app/core/metrics/frames.py::FrameStore.publish`, `_swap` (C)                                                                        | Capture publish attempt/result with expected/frame IDs already in scope. The actual pointer assignment in `_swap` gets a lightweight timestamp/token marker while under the existing mutex; serialization/export occurs later. Record success only after assignment, and return the original bool unchanged. Distinguish `publish`, `fail`, `invalidate` swap reasons via diagnostic context. No extra FrameStore read or expanded mutex scope for disk/schema work.                                              |
| `app/simulation/run_service.py::publish_committed_metrics` (C)                                                                       | Place final-authority begin/end around the existing complete post-commit predicate, preserving short-circuit order and every source/runtime comparison. Record rejection before its existing `fail`, acceptance directly before existing publish. No source reread for diagnostics and no pre-commit relabeling.                                                                                                                                                                                                  |
| `app/core/metrics/refresh_inputs.py::refresh_current_metrics`, `app/core/metrics/lifecycle.py::MetricsRefreshOwner._run_refresh` (C) | Separate refresh child operation/start/end/await delivery. Bracket its existing final current-source predicate and same-frame early success. `unchanged` is not a CAS. Refresh publication does not increment acquisition count. A declares refresh-owner/frame capabilities unavailable.                                                                                                                                                                                                                         |
| `app/core/metrics/metric_updater.py::clear_telemetry_metrics`, `set_service_info` (C)                                                | Existing unavailable/service frame publications inherit explicit operation types; central FrameStore probes cover their real swaps. Do not label them telemetry collection. A retains existing gauge clears and no CAS capability.                                                                                                                                                                                                                                                                                |
| `app/mission/repository_gate.py::RepositoryGate.acquire`, `release`                                                                  | Instrument actual depth-zero grant/release as specified next. No wrapping `get_active_leg_lock()` lookup as proof of acquisition; no replacement lock.                                                                                                                                                                                                                                                                                                                                                            |
| `app/api/metrics_export.py::get_metrics`, `app/api/status.py::status`                                                                | Replace only each explicit `await run_in_threadpool(...)` call with `await_pool(..., run_in_threadpool, ...)`. Keep the original imported pool/limiter and callable arguments. Worker dispatch includes limiter wait; worker start/end execute in that same pool; returned is on awaiting loop, on normal/error delivery.                                                                                                                                                                                         |
| `app/api/overview_history.py::get_overview_history`                                                                                  | Bracket reader await/JSONResponse construction for history phase IDs and bounded response hash capture via outer ASGI. This endpoint is async; no synthetic worker span or zero worker duration. Keep 503 mapping, response payload and reader/cache behavior unchanged.                                                                                                                                                                                                                                          |
| New `diagnostic_app.py::state`, `Boundary.__call__`, lifespan                                                                        | Import the exact frozen synthetic fixture/state helper read-only, add only `/api/_diagnostic/state`, and acquire the real repository gate around its existing capture in the original pool. Outer ASGI records entry, response-start, final body send and app return; wrap send and await the original send exactly once. Record pre/post-send and disconnect independently; ASGI send completion is server delivery, not browser receipt.                                                                        |

`workers.py` wraps the callable inside the existing pool call; it does not
create an alternate executor, shield all requests, alter AnyIO's abandon
behavior, or patch FastAPI/Starlette globals. A cancelled caller and a
still-running worker remain two separately owned facts. The runner must drain
before closing the sink, then kill/reap the service if an owned worker cannot
finish by deadline. Other FastAPI dependency/Operator worker dispatches are not
automatically covered; declare them unavailable. Covered queue measurements are
the source state, metrics and status workers, not a claim about all server
workers.

### Genuine depth-zero repository operations

`RepositoryGate` combines local FIFO admission with a cross-process FileLock;
both A and C have this class. Use its real `nested = self._owner == owner`
decision under `_condition`, not a wrapper-maintained stack. Capture initial
entry time before entering the condition, assign a span only when `not nested`,
and save the already-read owner/depth and operation. Record local grant before
the existing `_file_lock.acquire`, acquired only after that call succeeds, and
release only on transition to no underlying lock. Reentrant calls retain the
outer span and produce no additional depth-zero hold. Track the span per gate
and native thread, with process identity and a bounded map (256 entries).

To minimize probe effect inside the lock, capture fixed-size timestamps/scalars
there and emit after the lock's existing critical section. On normal release,
record the transition timestamp in the `finally` block before the existing
notify; emit outside `_condition`. Include a release-entry timestamp so actual
critical work can be distinguished from release bookkeeping. Do not close an
outer span on an inner release. `force=True` closes the real outer hold once
when the underlying lock becomes unlocked; unmatched/cross-thread misuse is
unavailable/error evidence, not a guessed duration. A failed acquire emits wait
failure and no acquired/hold span; timeout, cancellation checks and ticket
removal keep their original behavior. Sink failure cannot prevent release or
notify. No file or allocator-heavy identity work under either lock.

## Source observer and host correlation

Use a new integration `observer.mjs`, not edits to the pinned collector CLI or
the frozen v2 observer. Its 1 Hz schedule has absolute monotonic deadlines and
one outstanding request. Record scheduled deadline, actual callback entry, HTTP
request invocation, headers, final body, parsed JSON and completed event drain.
Use a total 2 s request deadline with explicit request destruction and socket
cleanup, not merely a per-read inactivity timeout. After overrun, emit skipped
deadline count and resume at the next future deadline; do not burst catch-up
traffic. The observer is supplemental traffic only.

Use Node's HTTP response byte stream with incremental limit checks before
copy/concatenate and a maximum 2 MiB decoded body. Accept only the dedicated
synthetic diagnostic endpoint, no redirects. Bound headers to 64 KiB, capture
allowlisted status/encoding only, and retain typed parse/HTTP/deadline failures.
`x-diagnostic-id` joins observer request, ASGI, worker and source capture.
`observer.written` brackets a completed drain of preceding events; a final
sidecar `observer.record_complete` marker is persisted by the next drain and the
final summary. Self-write duration is not recursively measured. Wire-send time
is unavailable unless independently captured; invocation is not wire-send.

Use the pinned `sample_resources` adapter in a separate host process at 1 Hz,
with explicit PIDs and container/ancestor cgroups. Read CPU/load/PSI,
`cpu.stat`, `cpu.max`, effective cpusets, I/O, memory, process stat/io/cgroup/
schedstat, and thread stat/schedstat. Retain its 64 KiB/file and 256-thread
limits. Map container PIDs to host PID/start time through the actor daemon
inspection and host `/proc`, without exposing environment/credentials. Record
host boot ID, kernel, monotonic clock kind and time-namespace identity. Missing
ancestor or per-thread visibility remains unavailable with reason.

Correlate counter deltas only for matching process/thread start identities and
unchanged cgroup counter epochs; resets, negative deltas and PID reuse
invalidate that delta. Compare CPU and runnable-wait/throttle deltas with event
envelopes and anchor uncertainty. Retain ±10 s context where inside run bounds;
mark edge context unavailable. One-second observations cannot identify the cause
or exact subsecond scheduling of a 1.5 s gap. No scheduler trace, physical
device capture, or host root-socket assumption is implied.

## Browser request, retention, commit and presentation

All application paths here are under `frontend/mission-planner/src/` and have
the same A/C source bytes. Build the same patch and diagnostic module for both.
Gate imports with the diagnostic build constant and explicit synthetic run
token; a diagnostic bundle refuses to attach without matching host binding. Do
not add Overview panels, controls, visible text or exposed telemetry globals.

| File/function                                                                                                    | Proposed diagnostic-only hook                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `hooks/api/useOverviewHistory.ts::useOverviewHistory` queryFn                                                    | Allocate the request operation for the existing queryFn call and record success/error/cancel delivery. Keep query key, retry false, 1 s normal/5 s error interval, background and focus behavior exactly as written. No added React state or subscription.                                                                                                                                                                                                                            |
| `services/overview-history.ts::overviewHistoryApi.get`                                                           | Pass only the diagnostic ID in that call's Axios config, retaining the exact AbortSignal. Record before existing get and immediately after it resolves/rejects. Associate returned `response.data` through a WeakMap; never mutate the bundle or use equal end timestamps as identity.                                                                                                                                                                                                |
| `services/api-client.ts::apiClient`                                                                              | No global interceptor change. Axios XHR processing and its existing error transformation remain intact. Parsed-response availability is observable on service resolution; native parse start/duration remains unavailable. If Query structural sharing returns an older/different object, record that fact using the queryFn result and committed object identities rather than attributing an old bundle to a new request.                                                           |
| `pages/OverviewMetricHistoryPanel.tsx::OverviewMetricHistoryPanel` accepted-history branch                       | Record render-candidate decision after the existing acceptance/retention branch, including rejected older/window-mismatched candidate IDs. React render is not commit. At the existing layout effect record the actually accepted bundle and `accepted.current.chart.bundle`; link retained input to its constituent request/bundle IDs per metric/trace.                                                                                                                             |
| `pages/overview-metric-retention.ts::retainMetricHistory`                                                        | Do not change algorithm. Supply its actual output from the panel to the diagnostic module, preserving the 7.5 s left reserve, authoritative incoming range, 1,820 trace cap, rollup availability and original values. Track provenance in bounded diagnostic side tables, not in application objects.                                                                                                                                                                                 |
| `pages/overview-metric-history.ts::projectMetricTraces`, `pages/overview-metric-plot-options.ts::metricPlotData` | Observe the actual returned projection and actual data passed by the panel; do not call them again to reconstruct evidence. Retain `[times,max,min,avg,observed]`, null masks, raw/rollup distinction, step, `spanGaps:false`, and declared log floor 1 from `overview-metric-scale.ts`. Record all these module hashes.                                                                                                                                                              |
| `pages/OverviewMetricHistoryPanel.tsx` existing `useLayoutEffect`                                                | After `new uPlot`/`setData`, record upload reason or reuse; after `setScale` and existing transform/transition assignments record `plot.commit`/React layout commit. Read `plot.current.data` and scales from the actual instance, plus actual retained input, CSS viewport/surface geometry and applied motion transform. No forced redraw, extra `setData`, animation change or additional layout flush in the measured path. Destroy/unmount invalidates pending presentation IDs. |

The page-local diagnostic module snapshots bounded plain arrays only at real
history/layout commits. Its in-memory metadata records render candidates
separately so aborted/StrictMode renders do not masquerade as painted commits.
Record unchanged-data motion rebases separately from actual uploads. Tag resize,
hidden, error, reduced-motion, window change and remount outcomes. Preserve the
existing visibility/error freeze, 250 ms UI timer and CSS animation.

Playwright listeners attach before navigation in each of two independent
contexts. Record request, response headers, requestfinished and requestfailed
using the actual Page Request object; never correlate by callback order alone.
Read the allowlisted diagnostic ID to join app/ASGI/capture events. Cap eight
active requests/jobs per Page and 16 for the two-viewer owner. App-to-host
events cross an explicit binding using at most eight in-flight calls, a bounded
queue and acknowledgement; the application never waits for that acknowledgement.
Overflow marks evidence loss and stops qualification without changing polling.

For a bundle to become a v1 `chart`, both its committed actual plot arrays and
retained projection input must exist. Browser-origin timestamps retain their
browser clock in the host sink; Node receive time is separate. Missing parse,
retention, sharing or commit association is unavailable, not reconstructed from
the latest response or from DOM text. Store raw body, normalized history,
retained input and plot snapshot hashes independently.

### Painted presentation is separate evidence

A layout effect, uPlot canvas, draw hook or two requestAnimationFrame callbacks
does not prove painted pixels. After an actual plot commit, request a bounded
Playwright compositor screenshot of the actual viewport; bracket the request and
receipt on the host and capture page commit IDs before/after. Associate it only
if the panel remains mounted with unchanged bundle/plot generation during the
capture. Retain PNG hash, clip rectangle, DPR, dimensions, renderer, viewport,
transform/motion state, visibility and the commit ID. A changed generation is an
ambiguous paint association, not a favorable-frame retry.

At fixed replay checkpoints evaluate visible trace continuity against that
snapshot's viewport transform, not the whole overscan raster. Preserve separate
raw, average and band gaps. Antialiasing/log-floor/transparent bands are
explicit image-analysis parameters pinned in fixtures. Screenshot evidence
establishes sampled compositor presentation within a bracket; exact physical
display scanout and continuous absence of gaps between screenshots remain
unavailable. Real physical/live-device and GPU qualification remain independent
gates.

## Compressed/chunked response capture with hard bounds

The passive companion observes the dedicated task HTTP frontend listener. It
never binds a proxy, changes request headers for encoding, routes requests, adds
polls or calls Playwright/CDP whole-body APIs. Keep Nginx gzip on, unchanged.
Require verified HTTP/1.1 cleartext at the capture point, exclusive task port,
capture-interface visibility and approved packet-capture permission. TLS, HTTP/2
multiplexing, service-worker/cache-served bodies, unknown framing or an
invisible rootless-forwarding hop make this mechanism unavailable and block full
history qualification. Do not disable those features to force a pass.

`capture.py` owns a libpcap subprocess/helper with an exact BPF filter for the
task loopback address/port, snap length 65,535 bytes, 4 MiB kernel capture
buffer, and a bounded 8 MiB user queue. No raw unfiltered traffic is written.
Capture records are length-checked before allocation; truncated packets fail the
affected flow. A continuously drained 64 MiB maximum pcap artifact reserves
shutdown statistics; hitting the limit stops capture and invalidates coverage.
Require zero capture/kernel drops and a complete handshake/framing for claimed
flows. Do not silently rotate away early evidence.

`http_stream.py` reassembles by connection tuple plus SYN/sequence epoch,
handles identical retransmissions, rejects conflicting overlap, bounds
out-of-order data and expires incomplete flows. Bound to 32 simultaneous
connections, 16 active history bodies overall, 64 KiB headers/trailers per
message, 16,384 chunks per body, 2 MiB encoded and 2 MiB decoded entity, 64 KiB
parser/decode working chunks, 64 MiB total flow/body working storage and 2 s
body deadline. Header limits apply before header string decoding. Reject
invalid/duplicate conflicting Content-Length, transfer-encoding ambiguity, bad
chunk sizes, missing terminal chunk, incomplete close-delimited bodies and
unexpected pipelining rather than guessing message boundaries. Drop other
endpoint bodies after bounded framing; retain only synthetic history bodies and
allowlisted headers.

HTTP dechunking and gzip/identity decoding are incremental. Check encoded count
before adding each segment; call gzip decompression with at most remaining
decoded allowance plus one byte and stop at the first excess byte. Never call
unbounded `decompress`, `flush`, `.body()`, `.text()` or concatenate the
complete encoded stream before checking. Validate gzip EOF, CRC/trailer and no
trailing or concatenated members. Brotli/other encodings are explicitly
unsupported in v1 and stop qualification. Missing Content-Length is supported
through valid chunking or connection-close framing; it is not treated as zero
bytes. Correct chunk extensions/trailers must not affect decoded content.

Hash/store both exact encoded entity and decoded JSON bytes, then create the
pinned collector's bounded body/history artifacts. Decoded JSON has a maximum
nesting depth of 32, 50,000 nodes, 16 KiB/string and 1,820 samples per trace;
enforce limits before constructing unbounded normalized copies. Preserve raw
bytes even when schema/JSON validation fails, within the byte quota. Do not emit
a history event for non-2xx, truncated, invalid UTF-8/JSON or mismatched schema.
Every failure emits status/reason/request ID, observed sizes, loss counts and an
unavailable artifact. Discard partial temporary body files deterministically.

Two-sided joins require matching request ID from Page metadata, the captured
HTTP request and backend ASGI, with the response paired by that HTTP
connection's framing. Require Page response success/requestfinished and an app
response event with matching decoded semantic content before attributing
captured bytes to a committed bundle. Semantic digests use a bounded streaming
canonical encoder, without a new unbounded JSON.stringify of the application
object. The packet body is network-path evidence, not direct access to
browser-internal bytes; Axios normalization/parse timing remains a distinct
boundary. A Page failure after server transmission is a failed browser delivery
even if pcap has a body.

The native capture dependency, host permissions and decoder are new integration
risks requiring their own deterministic fixtures and actual runtime preflight.
This plan does not claim they are already installed, permitted or qualified on
Forge. No privileged service is started by the current task.

## Buffer, storage and failure rules

Retain the pinned Recorder's limits: 4,096 events, 8 MiB queue, 1 MiB event, 2
MiB artifact, 256 MiB stream disk and 4 KiB final-summary reserve. Add a
stricter 4 KiB backend hot-event cap and 16-field/256-character identity caps.
Backend emission uses a nonblocking bounded enqueue; it performs no disk I/O,
full schema validation or large serialization inside repository/FrameStore
critical sections. Use a dedicated, owned exporter thread with a 250 ms maximum
idle interval; its work is separately timed and counted, outside the application
pool. The new `backend_probe.py` spool accepts prebounded scalar records and the
exporter validates/writes origin-preserving v1 rows using the pinned
model/schema. Do not call `Recorder.emit` from the exporter to fabricate worker
timestamps/TIDs/CPU: that API captures its caller. Use the new spool for these
rows, retaining its limits/loss/summary semantics; use the pinned Recorder
directly for collector- origin records and bounded artifact handling. No frozen
package edit is needed.

Page evidence is bounded to 256 events/8 MiB pending, eight transport jobs, 16
MiB retained diagnostic snapshots per Page, 2 MiB per serialized artifact, and
four traces × 1,820 points per metric. Cap five instrumented network panels per
viewer; unexpected panel count is a capability mismatch. Bound JSON traversal
before copying/serializing and use chunked artifact transport of at most 64 KiB
per message. Keep the bounded pinned Node sink off page callbacks; sync sink
disk writes run in the owned collector process and are overhead.

The run owner enforces 512 MiB total evidence across streams/pcap/paint
artifacts, and reserves 64 KiB for owner/failure/cleanup manifests. At most
eight 1920×1080/DPR 1 screenshots per run, each ≤8 MiB PNG, under the shared
disk budget; check geometry before capture and cap artifact writes. At most
eight producer/host/observer/page/capture streams are open; one bounded exporter
per backend and one collector owner, not an unbounded worker per event.

Probe exceptions never replace application return values/exceptions, suppress
cancellation, repeat a call, block for sink availability, or prevent lock
release. Record sticky failure/drop counters in reserved metadata, stop the
diagnostic owner and retain the partial run. If evidence storage itself fails,
report the error through the owner channel and mark missing summaries unknown.
Unknown loss is not zero loss. Quota exhaustion, event overflow, bad schema,
missing required join or cleanup failure terminates the schedule; no automatic
retry, buffer enlargement or favorable replacement run.
