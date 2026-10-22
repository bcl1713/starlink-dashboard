# Stage 3A frontend/browser checkpoint

Authorized by
[the orchestrator Stage 2 checkpoint](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6352254478),
starting at `e880c4d9e6b2b9c7c46bcf7985ab028efe98e5cd`. This package supplies
source patches and offline adapters only. **Stop for review before Stage 3B or
Stage 4.** No app image, browser, service, application HTTP request, packet
capture, calibration, soak or benchmark is part of this stage.

## Source identity and attachment

`patches/frontend/A.patch` and `C.patch` are byte-identical. Their role-specific
specs apply through the unchanged Stage 1 line-exact guard, after the unchanged
Stage 2 backend patches. `verify_frontend.py` exports complete original A and
corrected C archives, verifies base identities and all non-target files, applies
both layers, and inventories the effective application and external module
closure. Production checkouts, pinned revisions, dependency manifests,
Dockerfiles, Nginx, #407 and frozen benchmark tools remain unchanged.

Only three existing frontend files change in disposable derivatives. The
separate `browser-probe.ts` is resolved with `frontend-config.mjs` in a future
explicitly enabled, synthetic-only diagnostic Vite configuration; no build is
performed here. The module refuses attachment without the diagnostic compile
constant and the matching pre-navigation synthetic host binding. Each document
has a separate random identity, clock/stream and request sequence. The only
read-only page global returns commit/viewport metadata and loss counters, never
history arrays or telemetry. Browser-native parse start/duration are
unavailable.

The existing queryFn allocates a diagnostic ID, then calls the same service with
the same AbortSignal. The service adds only `x-diagnostic-id` in that existing
Axios config and observes resolution/error. It changes no interceptor, body,
query key, retry, focus/background option or 1 s/5 s polling interval. Parsed
response samples are bounded and recorded per network metric, including
responses never accepted by a panel. Response/object/sample WeakMaps preserve
identity; equal timestamp/value comparisons never manufacture a join. Actual
Query structural sharing can leave the old committed object associated with its
old response; an unknown replacement remains unknown.

The panel's original retention, projection, scale, animation and rendering code
is preserved. Render candidates remain distinct from commit events. Its existing
layout effect observes actual retained input, projection, uPlot instance data,
numeric scales, upload/create/reuse, dimensions and assigned CSS motion state.
There are no extra plot calls, redraws, state updates, subscriptions, timers or
layout reads on that measured path. A separate mount effect invalidates commit
IDs on cleanup, including StrictMode. No-data state invalidates an old commit.
Per-sample provenance follows the retained sample objects, including the older
7.5 s left reserve. Raw/rollup/null masks remain independent.

## Bounds and host integration boundary

The page keeps at most five panels, four input traces of 1820 samples per
metric, 50000 traversed nodes/depth 32, 2 MiB serialized artifacts, 256 queued
records/8 MiB and eight in-flight binding calls. Chunks have at most 15000
UTF-16 code units (at most 60000 UTF-8 bytes, below 64 KiB). WeakMaps do not
strongly retain expired bundles/samples. Current snapshots and queued strings
remain bounded; they are not an uptime history store. Overflow, invalid input,
clock or collector errors increment sticky failure/loss counters. UI code never
awaits an acknowledgment. A hung binding occupies one of eight slots until the
later owner closes its Page/context; no replacement bindings or retries are
launched.

`browser.mjs` attaches passive Page listeners before a later owner navigates. It
records Request-object identity, allowlisted response metadata and terminal
callbacks with separate Node receive timestamps. It never calls response body,
text, CDP body, routing, navigation or launch APIs. Eight requests, eight
binding handlers, eight bounded sink jobs, 256 records/8 MiB and eight 2 MiB
chunk assemblies cap its queues. Missing terminal/response callbacks, queue loss
and collector failure remain incomplete evidence. Sink operations have a total 2
s deadline and per-operation AbortSignal; a timeout aborts that signal and stops
new sink admission. Close disposes the pinned Playwright binding and init-script
handles, removes listeners, aborts waits, discards incomplete queues and settles
owned waiters. The later owner must supply nonblocking bounded sinks honoring
cancellation and close the owned Page/context so any underlying Playwright
command cannot survive teardown. The disposable init-script handle also removes
future-navigation attachment.

These are raw Stage 3A adapter records, not fabricated integration/v1 rows. The
Stage 4 owner must preserve document-origin clocks/sequence and project them
into the existing closed sidecar contract, own the pinned Recorder/disk quotas
and final summaries, and share the screenshot budget across both viewer
adapters. No v1 `chart` is claimed merely from a response or DOM. Actual
retained and plot snapshots exist together; missing provenance remains explicit
null. Parsed history, retained input, projection, plot and PNG hashes are
separate artifact identities; raw network bytes remain unavailable until Stage
3B.

## Compositor evidence

The screenshot adapter requests a compositor PNG only with a mounted committed
panel, visible document, bounded 1920×1080 viewport/DPR 1 and valid clip. It
checks commit/bundle/retained generation, panel mount state, viewport rectangle,
visibility and DPR again after collection. A changed bracket is unavailable; the
artifact can be retained as ambiguous evidence and never triggers a favorable
retry. Inline/applied transforms and motion state accompany the two brackets. At
most eight screenshots share one run budget, each at most 8 MiB, one at a time.
The owner supplies actual browser/renderer build identity in its later manifest.

A layout commit is not painted pixels. Fake Page tests prove adapter decisions,
not real raster correctness. A future successful compositor bracket proves only
sampled presentation, never exact scanout or continuous gap absence. Physical
hardware/GPU and live-device qualification are separate.

## Verified offline result

- 68/68 Python Stage 1–3A tests pass with the owned host runner; no surviving
  descendants. The earlier sandbox worker timeout is retained as failed
  evidence.
- 18/18 active frontend tests pass for each exact role export; 15/15 fake Page
  tests pass after review fixes. Real Axios, Query and application
  panel/functions are used; uPlot and compositor boundaries are explicit
  deterministic doubles.
- The full original frontend regression suite passes with attachment disabled:
  2102 tests in 308 files. This proves the covered disabled-adapter behavior;
  active diagnostic request headers have separate real-client assertions.
- TypeScript no-emit checking of the effective application and probe, focused
  Ruff, Prettier, Markdown lint, Python formatting and Git whitespace pass.
- One independent review found three Important issues, reproduced and fixed;
  there was no second independent review. The enabled timestamp-shift/resize
  fixture matrix and duplicate-callback/request-ID-collision cases remain
  unverified offline coverage suggestions, listed in `review.json`.

[Exact identities and external module closure](evidence/stage3a/identity.json)
and [complete inventories](evidence/stage3a/inventories) identify the source
bytes; no image/compiled asset hashes exist because no build was authorized.

## Reproduction and evidence

Use Python 3.11 with `requirements-test.txt` in a task-private environment. From
this package, export into a NEW owned scratch directory:

```sh
timeout --kill-after=10s 2m python -B verify_frontend.py --output /tmp/owned-new
```

Wait for successful completion before adding test-only dependency links to the
exports. Reuse the unchanged locked frontend dependencies; do not change app
manifests. Point `PERF391_FRONTEND_ROOT` to each role's
`*-effective/frontend/mission-planner` and use the package's
`tests/frontend/vitest.config.mjs` for focused offline jsdom tests. Use
`node tests/browser.test.mjs` under the same wall-clock limit for deterministic
fake Page tests. No runtime browser is needed. The regression config loads the
exported application's original Vite unit config; run it FROM the exported
frontend directory, with `PERF391_DIAGNOSTIC_TEST_MODE=off` to test the disabled
adapter. Two existing exact-Axios-config assertions intentionally exclude the
newly authorized header; their active-mode replacement contracts are covered in
`request.test.tsx`, alongside real Axios and TanStack Query.

See [Stage 3A evidence](evidence/stage3a),
[capability/limitation matrix](evidence/stage3a/matrix.json), and
[read-only passive capture assessment](CAPTURE-FEASIBILITY.md). Failed discovery
runs remain recorded, including the sandbox worker timeout and the incorrectly
located initial regression run; these are not passed verification evidence. No
timing-overhead or deployed parity claim follows from offline tests.

Keep #403/#405/#406/#407/#408 draft and unmerged and #390/#391 open. Preserve
the historical 1.5-second rule. Cleanup retains only this open-PR worktree and
committed evidence; no task runtime resource is required for review.
