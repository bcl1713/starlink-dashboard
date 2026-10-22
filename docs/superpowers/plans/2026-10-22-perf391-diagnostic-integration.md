# Perf391 diagnostic integration plan

> Review candidate only. No implementation or runtime collection is authorized
> by this document. A later executor must obtain the integration checkpoint
> decision before implementing, and a separate runtime decision before
> calibration. Use the executing-plans workflow if execution is subsequently
> authorized.

**Goal:** Collect supplemental, bounded evidence explaining #391 timing and
history presentation in separately built original A and corrected C
applications.

**Architecture:** Apply small, explicit source patches to disposable diagnostic
derivatives of each application. Use one matching event contract, the immutable
PR #407 collector as a dependency, a separate integration sidecar schema for
missing boundaries, and passive observation of existing browser requests. Keep
production images and frozen comparison runs independent.

**Stack:** Python 3.11, existing asyncio/AnyIO/FastAPI pools, React/TanStack
Query/Axios/uPlot, Node/Playwright, a bounded libpcap-based HTTP capture
companion, the existing Nginx and Prometheus path, task-owned Compose projects.

**Design authority:**
[User-requested scope and #407 orchestration review](https://github.com/bcl1713/starlink-dashboard/pull/407#issuecomment-6350190288).
This document supplies both integration design and its proposed implementation
sequence. Current work is investigation/documentation only; tests below are
specified, not implemented or executed.

## Frozen inputs and isolation

| Role                                 | Pinned input                               |
| ------------------------------------ | ------------------------------------------ |
| Original A                           | `25e34168f0e2cecb149b0323f1f5a795cb28cae0` |
| Corrected C final-head build/archive | `ee9ce1010e72e83cb6d4b8c79ecc15091b9d8832` |
| Corrected implementation reference   | `3cd79e2ac77557b7ef0ba7bc8bf60069bd260bbc` |
| Supplemental collector source        | `a48837b99d87366c6e3fc24ba2915f0b739cddad` |
| #407 release metadata/manifest       | `c47d21e3c5bbf92189afbf291b73b9da7a035a4b` |
| Earlier diagnostic protocol, #405    | `f7253c687041342ee080b0197f0b98f20eaefdfe` |
| Frozen availability-v2 runner        | `f3029024b5950a267645195476da5cbca326f16a` |
| Planning base, origin/dev            | `33b60fa85c0d0b80d9b82ea5eac7d612a54f4c96` |

Source inspection confirms that backend/frontend/tools/monitoring/scripts and
the inspected Compose inputs are unchanged between the corrected implementation
reference and the listed #406 delivery. Build C from its actual final-head
archive and revision label, as required by the
[accepted readiness protocol](https://github.com/bcl1713/starlink-dashboard/pull/406#issuecomment-6348735966),
rather than relabeling a reference image. The inspected frontend source is
identical in A and C. A has no FrameStore, immutable frame identity,
final-authority predicate, or CAS; these must stay unavailable. The #407
delivery changes release metadata and RESULTS relative to its source commit; use
the source commit for executable collector bytes and the delivery commit to
verify the release manifest.

The integration implementation, if approved, belongs in a new
`tools/diagnostics/perf391-diagnostic-integration-v1/` directory on a new branch
from then-current `origin/dev`. Do not add it to #403/#406 or change the pinned
PR #407 package. Keep primary checkout on `dev`. Build two child source trees
from exact A/C archives; apply only the reviewed role-specific patch files, with
no fuzz, reject files, extra dependencies in application manifests, or unrelated
refactoring. Record the complete resulting tree hash and per-file hashes.

Every diagnostic image has labels `diagnostic=true`, `base_application_sha`,
`integration_source_sha`, `collector_source_sha`, `patch_sha256`, and
`effective_source_sha256`. Retain the original revision label as base identity,
never as proof of unchanged runtime bytes. Use unique image tags and distinct
build contexts. Use the unchanged production Dockerfiles, lockfiles, Nginx
configuration and service limits; inject backend adapters read-only at
`/diagnostic-integration`, outside `/app`, and change only the diagnostic
command and PYTHONPATH in an owned Compose override. Build the patched frontend
with a compile-time diagnostic entry enabled. Record compiled module and asset
hashes.

Create source worktrees/branches under `.worktrees/`, with separate diagnostic
derivatives and reviewable patch commits; retain them while their PRs are open.
Branches begin at origin/dev, then populate the diagnostic export from A or C;
do not merge production branches to manufacture a diagnostic identity. The
manifest must identify both ancestry and effective application base. No existing
worktree, source commit, acceptance script, historical artifact, or manifest is
rewritten.

Primary off measurements use exact **unpatched** A/C images, no integration
mounts, wrapper entrypoint, diagnostic query endpoint, request-ID headers,
packet tap, bindings, source observer, plot probes, or diagnostic collector. A
disabled probe in a patched image is a calibration control, not a primary off
result. Diagnostic, counter, replay, calibration and primary results have
separate directories and reports. Never subtract estimated overhead from primary
results.

## Decisions and rejected alternatives

1. Explicit diagnostic patches are preferred over global monkey patches. They
   expose private C validation/CAS outcomes and actual React/uPlot state without
   wrapping every application threadpool or changing a production entrypoint.
2. For compressed/chunked history, prefer a passive bounded HTTP capture
   companion on the task's existing dedicated loopback connection. It requires
   host capture permission and a verified cleartext HTTP/1.1 path. These are
   preflight gates. Direct `response.body()`/CDP whole-body retrieval cannot
   guarantee a decoded-size bound; Content-Length can describe compressed bytes
   and can be false. Request interception, replacing Axios with streaming fetch,
   disabling gzip, and injecting a proxy change the measured request behavior
   and are excluded. Lack of capture permission means unavailable evidence and
   no runtime qualification, not an automatic fallback.
3. Keep the pinned v1 schema/analyzer unchanged. Add a closed integration
   sidecar contract and a separate integration analyzer for new phases,
   successful-CAS filtering, joins and paint evidence. Project only compatible
   events into v1. Schema fixtures passing alone cannot qualify real application
   integration.

## Matching instrumentation contract

New files below are relative to
`tools/diagnostics/perf391-diagnostic-integration-v1/` unless an application
path is explicit. None are created by the present planning task.

| Proposed file                                    | Responsibility and public interface                                                                                                                                                                                    |
| ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `contract.json`, `integration-event-schema.json` | Closed version `perf391-diagnostic-integration-v1`, version 1; capability matrix and phase/outcome enums                                                                                                               |
| `backend_probe.py`                               | `mark(phase: str, *, op_id: str, span_id: str \| None = None, outcome: str \| None = None, identity: dict \| None = None) -> None`; bounded nonthrowing emission; ContextVar parent operation; capability declarations |
| `workers.py`                                     | `invoke_sync(role, op_id, fn, *args, **kwargs)` and `await_pool(role, op_id, pool, fn, *args, **kwargs)`; pool-preserving dispatch/start/end/returned probes                                                           |
| `diagnostic_app.py`                              | Synthetic-only fixture import, diagnostic source-state endpoint, outer ASGI wrapper and lifespan/drain owner                                                                                                           |
| `observer.mjs`                                   | Absolute scheduled source-observer loop, bounded HTTP parser/body and record completion                                                                                                                                |
| `browser-probe.ts`                               | Bounded page-local events, WeakMap object/request associations, commit/actual uPlot snapshot hooks, no UI                                                                                                              |
| `browser.mjs`                                    | Passive Page lifecycle listeners, bounded binding transport, artifact/screenshot owner and joins                                                                                                                       |
| `capture.py`, `http_stream.py`                   | Bounded passive pcap owner; TCP/HTTP framing and gzip decoding; no request injection                                                                                                                                   |
| `analyze.py`                                     | Sidecar validation, joins, capability/outcome-aware durations, paint/image and v1 report references                                                                                                                    |
| `build.py`, `run.py`, `compose.json`             | Exact-source exports/patch guards, diagnostic builds and isolated resource lifecycle                                                                                                                                   |
| `patches/A.patch`, `patches/C.patch`             | Only the application call sites specified below; hash every patch                                                                                                                                                      |
| `tests/`, `fixtures/`, `README.md`               | Deterministic call-site/protocol tests, fixed inputs, ownership and bounded future invocation                                                                                                                          |

All sidecar records carry run, stream and strictly increasing sequence IDs,
process UUID, PID, native TID when known, process/thread start identity, clock
ID, decimal-string monotonic ns, optional same-thread CPU ns, operation, parent
operation and span IDs, phase, outcome, and bounded allowlisted identity fields.
The run manifest supplies process/container/namespace mappings. Browser TID/CPU
are unavailable, not copied from Node. A browser document/navigation creates a
new clock/stream ID. A backend restart creates a new process/stream ID even if
the PID is reused. Sequence gaps, missing summaries and restarts remain visible.

Outcomes: `ok`, `error`, `cancelled`, `rejected`, `cas_lost`, `unchanged`,
`unavailable`. Capability entries contain `available` and `reason`; missing
capabilities default to unavailable. No null identity is filled from timestamp
or numeric equality. Distinguish a source-owned acquisition timestamp from
collection return, retained observation, registry mutation and publication.

Identity fields are bounded scalar IDs/hashes already exposed by the caller:
source mode/lifecycle, observation identity/timestamp, route/config/input
revision, replay runtime/run/revision/mission time, expected head and resulting
publication token. Do not perform new manager/file reads, source checks, model
serialization or telemetry advancement to fill metadata. C can reuse existing
FrameIdentity fields; A can expose existing source/timestamp scalars but cannot
claim frame coherence. Tokens for objects are process-local diagnostic IDs, not
externally meaningful source identities. Nonfinite metric values retain their
existing application semantics; evidence uses null plus availability.

Use operation IDs of at most 96 ASCII characters. Request IDs include run token,
viewer/page ID and sequence. Only the diagnostic service call adds the ID to the
existing same-origin history request config; no additional request, retry, cache
option, body or polling change. ASGI accepts that allowlisted header for
joining; other requests get a backend-local ID. A/C use identical header logic.
Record child worker operations because one request may dispatch multiple jobs.
Each depth-zero admission gets a distinct span ID, not just a thread ID.

Emit the v1 names already supported by the pinned schema for
producer/worker/repo/observer/browser lifecycle, coverage, bodies, histories and
charts. Additional sidecar phases are explicitly enumerated: `collection.enter`,
`collection.return`, `source.final.begin`, `source.final.end`,
`publication.attempt`, `publication.result`, `publication.swap`,
`replay.commit`, `repo.local_grant`, `repo.acquire_failed`, `asgi.headers`,
`asgi.send.begin`, `asgi.send.end`, `asgi.disconnect`,
`observer.record_complete`, `observer.skipped_deadline`, `app.request`,
`app.response`, `app.parse_available`, `query.success`, `query.error`,
`react.render_candidate`, `react.commit`, `history.retained`, `plot.upload`,
`plot.commit`, `paint.request`, `paint.artifact`, `probe.failure`.
`app.parse_available` is after Axios parsing, not an invented parse-start time.

Only a successful ready-frame CAS projects to `producer.published`. Failed
validation, schema error, stale CAS, invalidation, failure-head swaps and
derived refreshes retain their actual outcomes and do not become new
observations. Operation types distinguish `tick`, `replay`, `derived_refresh`,
`scrape` and `source_observer`. A's in-place metric update completion is
recorded as such, with `producer.published` and frame/final-authority
capabilities unavailable. The integration analyzer filters outcomes; the pinned
v1 generic duration table must not be presented as a successful-publication
census.

For every claimed duration require exactly one start/end pair on the same clock.
Thread CPU additionally needs the same process/TID/start identity. Never
subtract browser, Node, packet, backend or host clock origins. Use bounded
UTC/monotonic anchors at start, 1 Hz and shutdown, with read
brackets/uncertainty. An offset step invalidates approximate time alignment, not
ID joins. HTTP RTT minus ASGI elapsed time is only an unattributed combined
residual. Overlapping spans are not additive CPU savings.

## Detailed companion plans

- [Exact backend/browser hooks, response capture and bounds](2026-10-22-perf391-diagnostic-integration-boundaries.md).
- [Tests, runtime preflight, calibration, unavailable boundaries and cleanup](2026-10-22-perf391-diagnostic-integration-verification.md).

## Proposed implementation sequence after review

- [ ] **1. Contract and exact-source exporter.** Add contract/schema/build
      guards and `tests/test_build_identity.py`. First demonstrate failures for
      wrong SHA, patch drift and frozen-tree changes; implement the minimal
      guard and pass the same cases. Commit the contract and identity evidence
      before probes.
- [ ] **2. Backend call-site patches.** Add backend/worker modules and A/C
      patches. Run producer/publication/admission/worker tests red against the
      uninstrumented exports, then implement the stated hooks and preserve
      per-role equivalence. Review emitted joins/outcomes before committing this
      independently reviewable backend step.
- [ ] **3. Browser hooks and passive bounded capture.** Add page/binding and
      HTTP capture modules with protocol/browser/frontend/plot tests. Prove
      failures for missing actual retained input, compression bomb and stale
      commit; then pass these cases with the specified caps. Commit separately
      with fixture hashes.
- [ ] **4. Observer/host integration and owner.** Add observer, lifecycle and
      integration analyzer, owner/clock/failure tests. Exercise deterministic
      timeout/signal/saturation failures, then confirm clean teardown and null
      unavailable reporting. Commit evidence; review all source/patch/module
      hashes.
- [ ] **5. Integration checkpoint.** Publish exact derived source/image build
      manifest, deterministic results, unavailable matrix and cleanup evidence
      to #407. Stop. A separate runtime authorization is required before the
      browser replay, preflight launch probe, or calibration schedule below.

Future bounded test commands run from the package root, with private dependency
environments and exact app roots supplied by `tests/test_build_identity.py`:
`timeout --kill-after=10s 10m python3 -m unittest discover -s tests -p 'test_*.py'`,
`timeout --kill-after=10s 10m node --test tests/*.test.mjs`, and targeted Vitest
for the patched service/panel tests. Frontend component tests use the existing
locked frontend runner; `presentation.spec.mjs` is intentionally excluded from
offline Node tests. Every process-owning test uses the same owner registry.
Timeouts fail the step; verify the old process tree is dead before any
subsequent run.
