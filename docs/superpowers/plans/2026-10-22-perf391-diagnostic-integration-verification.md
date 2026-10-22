# Perf391 diagnostic integration verification and runtime plan

This is part of the
[integration plan](2026-10-22-perf391-diagnostic-integration.md). It is a
proposal only.

## Deterministic integration tests and expected evidence

Create these tests under the new package, using exact A/C exports, injected
virtual clocks, barriers and fixed synthetic models. No arbitrary sleep is a
timing assertion. An unpatched control call and patched call receive equivalent
input schedules; compare return value, exception type, side-effect call order,
source/metric outputs, counters and cancellation ownership. Differences already
between A and C are expected; instrumentation must preserve each role
separately.

| Proposed test                        | Required cases and assertions                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/test_build_identity.py`       | Wrong role/SHA, dirty export, patch drift/fuzz, collector hash change, modified frozen file, absent labels and diagnostic import in primary image all fail before build/run. A/C frontend patch/hash agreement; C delivery/runtime equivalence.                                                                                                                                                                                                                                                      |
| `tests/test_producer_integration.py` | Success, collection exception, retained telemetry, disconnect/recovery, no coordinator, paused/advancing replay, replay callback/commit failure and caught metric-preparation failure. Exactly one main-tick dispatch/start/collected/end/returned when that phase occurs; absent collected on failed collection; no accounting repeats; A frame/final/CAS explicitly unavailable.                                                                                                                   |
| `tests/test_final_publication.py`    | Barrier replaces coordinator/config/route/POIs/mission/replay between collection and final validation. Entry success cannot imply final success. C final check runs exactly as often as control; failed predicate never emits published. Force a newer head before CAS: original expected token remains, false result is cas_lost, newer head survives. Schema error, fail/invalidate swap and derived unchanged produce no successful ready publication. Replay publish occurs after actual commit. |
| `tests/test_admission.py`            | Real RepositoryGate with nested decorated/model paths, competing thread and separate-process file holder, acquire timeout/cancel_check, exception under hold, failed FileLock acquire, normal/force release and repeated release. Exactly one span per real outer grant; exact wait/hold pairing and no span for nesting; FIFO/ticket cleanup and return context manager unchanged. Inject sink failure at all hooks and prove lock is released/next waiter proceeds.                                |
| `tests/test_worker_delivery.py`      | Bound pool with a deliberately occupied limiter, worker barrier and blocked event-loop delivery. Queue, execution and post-worker delivery vary independently. Exceptions and cancellation before admission/during work/after completion preserve original pool semantics. Double cancellation drains the background producer; cancelled HTTP waiter cannot close the sink while its worker writes. No async-history worker is fabricated.                                                           |
| `tests/observer.test.mjs`            | Virtual scheduled late wake, late send, slow header/body, non-2xx, malformed/oversize JSON, trickle past total deadline, socket reset, cancellation and record-write failure. Exact ID joins, skipped deadlines without catch-up bursts, destroyed/reaped requests and explicit unavailable markers; event timestamps remain in emitter domain.                                                                                                                                                      |
| `tests/browser.test.mjs`             | Fake Page lifecycle order permutations, response/requestfinished inversion, failed request after headers, body capture success but browser failure, duplicate callback, ID collision, navigation, close with eight pending jobs, binding failure and queue saturation. No Page.body/CDP whole-body call in any path. All pending work is accounted and closed; no stale bundle is synthesized.                                                                                                       |
| `tests/test_http_stream.py`          | Fixed pcaps for identity/gzip × Content-Length/chunked/close framing; missing length, chunk extensions/trailers, split headers/TCP segments, retransmission and reorder, conflict/truncation, false small length, bad chunk terminator, CRC, malformed UTF-8/JSON, zip bomb, nesting bomb, unsupported encoding/TLS/H2, deadline and pcap drops. At limit succeeds, limit+1 fails; counters and max allocated working buffers stay within declared bounds; no partial artifact is marked complete.   |
| `tests/frontend.test.tsx`            | Use actual patched service/hook/panel with existing frontend test setup. AbortSignal passthrough; unchanged polling/error/retry/focus options. A late older bundle, equal-end distinct body, wrong window, Query structural sharing, React abandoned render/StrictMode, unmount and resize cannot create a false commit/request join. Actual retained older left margin appears in evidence.                                                                                                         |
| `tests/plot.test.tsx`                | Raw present/rollup absent, explicit nulls, >1.5×step midpoint break, missing metrics, log zeros/floor 1, rollup masks, timestamp shifts, reordered bundles, hidden/error freeze, reduced motion and 7.5 s reserve. Capture actual plot.data after new/setData and reuse; retained input/arrays match the real component. Deliberately change plot input only: classify frontend input defect, not upstream gap.                                                                                      |
| `tests/presentation.spec.mjs`        | Future short browser replay only: fixed response/delivery schedule against both exact diagnostic frontend bundles, same viewport/DPR/renderer. Distinct fixtures change only plot arrays or only CSS/canvas presentation. Require correct input-defect versus presentation-gap classification, screenshot hash/commit bracket, and unknown for changed-generation or missing screenshot. No pixel evidence from mocked uPlot tests.                                                                  |
| `tests/test_clock_resources.py`      | UTC step, clock mismatch, monotonic reset, process/TID reuse, cgroup reset, inaccessible ancestor, thread/file cap and missing summary. All invalid deltas/durations are null with reasons; ID joins can survive wall-clock steps.                                                                                                                                                                                                                                                                   |
| `tests/test_lifecycle.py`            | Owner failure before/after Compose/browser/tap startup, SIGINT/TERM, repeated cancellation, body timeout, disk ENOSPC and stuck worker with forced termination. Verify owned PID/PGID/start-time registry, joined children, closed contexts, no listeners/containers/networks/disposable volumes and retained partial evidence/summary status. Never broad-kill shared resources.                                                                                                                    |

Use the existing application regression cases as read-only references, including
C's final-validation/CAS/retained/replay cases and frontend retention/panel
tests; add focused diagnostic assertions in the package rather than modifying
production tests or frozen comparator assertions. Fixed clock fixtures must
produce byte-identical hashes. Saturation/overflow tests are intentionally
failed-evidence cases, not green runtime qualifications.

Required outputs per fixture: expected capability/outcome matrix, sidecar/v1
streams, loss/final-summary accounting, operation/span two-sided join tables,
raw request/response and plot/retention hashes where applicable, expected
classification, buffer high-water counts, and cleanup record. Required coverage
is 100% of claimed applicable joins with zero unplanned loss; A's designed
unavailable boundaries are displayed explicitly and excluded from comparisons,
never filled with zero. Offline tests do not establish browser/pcap runtime
compatibility or negligible overhead.

## Runtime preflight: requirements, not actions performed here

1. Require reviewed, committed integration patches/tests and a separate runtime
   authorization. Recheck #407 review and all application/tool/harness SHAs,
   clean trees, hashes and manifests. Preserve frozen v2 files byte-for-byte; do
   not execute its comparator on diagnostic streams as a replacement gate.
2. Verify actual **local Forge** host and actor daemon/context, preserving
   DOCKER_HOST. Discover socket through XDG_RUNTIME_DIR or `/run/user/<uid>`;
   failure at `/var/run/docker.sock` is not service failure. Record actual
   Docker info, rootless forwarding, cgroups/ancestors/cpusets and other
   workloads. No shared service shutdown or cloud-host substitution.
3. Compare against #406's recorded i9-10900K/20 logical CPUs, kernel
   7.0.0-34-generic, Docker 29.8.1/overlayfs, 2 CPU/2 GB service limits and
   actor ancestor quota `1000000 100000`. Differences are a review gate, not
   silent normalization. Preserve proxy/CA configuration and credentials.
4. Verify build input/base-image and resulting image digests, exact application
   source archives/patches/assets, Python 3.11 runtime and backend package
   inventory. #406 records production Python 3.11.17 and 89-package hash
   `03cf956e500c08952d7b1a1747f24e391f6d0c5cf32a675a93c55847c92e9a40`; keep
   component/collector inventories separate. No dependency update to obtain a
   preferred result.
5. Locate the actual browser dependency root and executable, hash the binary and
   verify shared-library availability and effective sandbox configuration.
   Reference identities are Node v22.12.0, Playwright 1.63.0, Chromium
   153.0.8010.12, revision 1243, SwiftShader and launched shell SHA-256
   `ded93a9c9a53a1ae040f08124badcca95c938e9d5015ff340c3b5538c41bf39e`. Package
   presence or fake-Page tests do not prove browser usability. Under later
   runtime permission, perform a ≤10 s owned launch/close test of that exact
   binary and record actual version/renderer, 1920×1080/DPR 1, context exit and
   child reaping. A mismatch blocks calibration.
6. Verify the dedicated HTTP listener/capture interface and host libpcap/helper
   binary/hash/permissions without broad capture. A short later preflight must
   demonstrate both gzip and chunked bodies through the same Nginx path, bounded
   decoding, Page/app/backend/tap joins and zero capture drops. Synthetic
   protocol cases remain separately labeled from natural runtime data. Missing
   capture permissions or protocol coverage is a hard gate, not permission to
   change Nginx, browser headers or frozen tools.
7. Verify real 1 Hz Prometheus scrape/evaluation and both existing Overview
   clients plus Operator, 1,800 s history, same fictional mission/workload,
   active source mode and warmup policy. Record fixtures, real package/runtime,
   module hashes, visible roots and existing poll traffic; never increase poll
   frequency. The extra source observer is declared diagnostic traffic.
8. Preserve actual stored Prometheus sample provenance: selected job/instance,
   raw instant-query range vector, `up`, all 11 v2 correctness families, scrape
   duration/sample counts, request/query/export hashes. Store evaluated
   range-query results/grid and source sample timestamps separately. Cache
   hits/shared evaluations may lack per-request source-frame identity; mark that
   unavailable rather than matching equal values or query timestamps to producer
   observations. No producer-to-Prometheus-to-API exact causal claim without
   actual two-sided provenance.
9. Record resource ownership before creation, enforce all caps, verify free disk
   exceeds the 512 MiB evidence budget plus normal workload allocation and
   teardown reserve, and verify host process visibility for cleanup. Do not
   launch if ownership, stop command or host verification is unavailable.

The cloud-environment status tool and policy snapshot are unavailable in the
present tool/environment surface; this planning task does not infer runtime
credential/network readiness from their absence. No runtime preflight item above
is claimed passed by reading source.

## Short calibration proposal, subject to separate approval

Use #407 QUALIFICATION's fixed overall schedule, with clearer control labeling:
one C functionality run of 15 s, then two blocks of four runs, each 30 s warmup
plus 60 s measured. Block 1: A disabled, A enabled, C enabled, C disabled. Block
2: C disabled, C enabled, A enabled, A disabled. Total nominal runtime is 735 s;
whole owner timeout 20 minutes with 10 s forced-termination grace, each run 120
s with 5 s grace. Cleanup is immediate after each run. No retries, replacement
pairs, additional repetitions, fault injection or soak are included.

Here disabled/enabled use the same diagnostic-derived image. Disabled turns off
all supplemental adapters/observer/tap/bindings; it is an overhead control, not
the primary production off cohort. The source endpoint is installed but idle.
Both controls use the same underlying production workload, scrape/evaluation,
normal browser polling and service limits. Differences against exact unpatched
source are checked deterministically; if a measured build-only versus production
cost is required, bring back a revised schedule for approval rather than
silently adding runs. This proposal does not itself authorize primary runs.

Within each enabled run attribute direct process/thread CPU, write bytes/time,
queue high-water, encoded/decoded body rates, host/cgroup counters, RSS/PSS/JS
heap, request/poll tails, event-loop delay, frame/long-task observations and
cleanup time by owner. Keep source-observer traffic, backend hooks/exporter,
passive capture, binding/artifact transport and screenshot costs visible. These
direct costs do not fully isolate interaction overhead; additional ablation runs
require a separate reviewed schedule. Report paired differences between enabled
and disabled complete runs and both repetitions, with no event-level
pseudo-replication or claimed rare-tail confidence from two pairs.

After runtime approval, the separate browser replay uses one immutable
response/delivery fixture in both exact diagnostic frontend bundles, three fixed
repetitions, reversed bundle order in repetition 2, and fixed screenshot
checkpoints. Cap the replay owner at 2 minutes plus 10 s grace per repetition;
do not issue live backend polls from this fixture cohort. This proves selected
render/projection behavior, not real Prometheus ingestion or natural
performance.

Require complete applicable joins, zero dropped events/bodies/packets and a
summary for every stream. Report all outliers, failures and ambiguous phases.
There is no invented CPU/latency overhead tolerance: any material or unexplained
shift returns to review, and even apparently small shifts need a checkpoint
decision before sustained work. Historical 1.754899/1.583978 s failures remain
failures under the unchanged 1.5 s gate. Short diagnostic success does not prove
savings, acceptance cadence or #390's eight-hour integrated boundedness.

## Known unavailable boundaries and hard stops

| Boundary                                                                                                    | Required representation                                                                                                 |
| ----------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| A immutable frame/final source authority/CAS/coherent publication                                           | Unavailable by design; no behavioral backport; A/C common tick/worker/gate comparisons remain possible                  |
| Exact physical acquisition/device timing, physical display scanout                                          | Unavailable; retained telemetry and compositor captures do not establish these                                          |
| Axios native parse start, arbitrary FastAPI/Operator pool dispatches                                        | Unavailable unless the exact future contract is separately expanded; never use zero                                     |
| Cross-process one-way latency or per-request host scheduler cause                                           | Unavailable from local clocks/1 Hz resources; report ID joins and local durations only                                  |
| Exact producer frame → stored scrape → evaluated/cache bundle provenance                                    | Unavailable where current sources do not expose IDs; no value/timestamp reconstruction                                  |
| Direct browser-internal raw response bytes and unsampled paint intervals                                    | Unavailable; bounded passive wire content/app semantic content and sampled compositor screenshots are distinct evidence |
| Unsupported encoding/protocol/capture permission, missing retained input, missing required plot/commit join | Full qualification blocked; preserve partial evidence and stop                                                          |

Hard stops also include identity/build/hash drift, dirty diagnostic export,
production/frozen-tool modification, workload or browser mismatch, unplanned
HTTP/schema errors, unknown/lost records, overflow, quota or timeout, clock
ambiguity in a claimed duration, anomalous overhead, and incomplete teardown. Do
not reinterpret unavailable as a zero-duration phase, success or physical
network outage. Keep estimates/advisories, Starshield assumptions and all
customer-facing Overview behavior unchanged. No acceptance-rule change or
uncertainty acknowledgement is introduced.

## Ownership, deterministic teardown and handoff

Before creating anything, atomically write owner manifest with run token,
command/session handle, root PID/PGID/start time, child handles, Compose
project, image tags/digests, dedicated ports, named private volumes, network
IDs, paths, wall-clock deadline and exact stop commands. Use one sequential
project/run, for example `starlink-diag391-integration-<run-token>`. Preserve
credentials, shared runtime configuration and other tasks' resources.

Install normal-exit/INT/TERM handlers before startup. On exit/failure: stop new
observer requests and page transport scheduling; detach listeners; cancel/drain
pending capture/body/export jobs within their deadlines; close Page contexts and
browser; drain/reap workers and backend before final sink close; flush summaries
and loss/coverage; stop capture helper and collect its final drop statistics;
TERM verified process groups, then KILL only owned surviving PID/start-time
matches after grace. Reap all children. Run scoped Compose down with disposable
volumes, then verify filtered containers, networks and volumes are empty. Remove
only task-owned image tags/exports/private dependency environments and temporary
partial files. Retain immutable evidence and open-PR worktrees.

Verify host processes, owned listeners and process groups using an approved host
command when sandbox PID visibility is incomplete. SIGKILL cannot run handlers;
the parent owner performs the same verification after forced timeout. Never
`pkill`, `killall` or Docker prune. Do not begin another run while a prior owned
worker/tap/browser/project remains. A failed cleanup records exact resource
IDs/stop commands and blocks the next run and handoff qualification.

Publish the integration manifest, capability matrix, all results including
rejections, boundedness/high-water data, joins, immutable artifact hashes,
unavailable reasons and host-verified cleanup to #407. Stop for review at each
checkpoint. Keep #403/#405/#406/#407 draft and unmerged and #391/#390 open. No
implementation, browser launch, benchmark, calibration, sustained test, merge,
deployment or issue closure was performed to prepare this plan.
