# Stage 2 backend checkpoint

Stage 2 is authorized by the
[latest orchestrator review on #408](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6351106343)
at starting commit `a4e707e96226400051bbd05e28d831d8fbae6899`. Only diagnostic
backend modules, literal backend patches, offline tests and their evidence are
included. Stop for review before Stage 3.

## Installed boundaries

`patches/A.patch` and `patches/C.patch` have independent
SHA-256/preimage/postimage specifications. The Stage 1 guard applies them to
full exact A/C archives with no fuzz or offset search. Its sole eligibility
extension is the exact approved `backend/starlink-location/main.py` path.
Production checkouts, Dockerfiles, frontend, collector #407 and frozen
comparator bytes are untouched.

- The existing producer task/thread/shield/drain remains the owner. Dispatch,
  complete tick execution, normal/error/cancel delivery and actual tick branches
  are separate events. Repeated cancellation drains the original worker.
- The normal main coordinator call has one collection bracket, including any
  existing decorated admission. The simulation decorator contributes its already
  exposed retained-object relation to that bracket; direct/replay calls get the
  same bracket without duplication. Replay outer return includes commit and
  publication, and is explicitly `replay.return`, never acquisition completion.
- C brackets its actual private final predicate, preserving the complete
  expression, short-circuit order, captured head and number of source reads.
  FrameStore publish attempts/results include stale CAS and schema errors. The
  assignment stamp is captured inside its existing pointer mutex; identity work
  and emission happen after leaving that mutex. Failure/invalidation,
  unavailable/service and derived swaps are distinguished. Only successful ready
  tick/replay CAS emits `producer.published`.
- A brackets its existing in-place updater. Its replay callback updates metrics
  before commit; C prepares before commit and publishes after commit. These
  differences are preserved, including compensation and optional-metric failure.
- Both roles observe the gate's own nested decision, FIFO/local grant, actual
  FileLock acquisition, failed acquisition and actual outer release. Inner
  release does not close the hold. Release entry and unlock-transition stamps
  are distinct. Only fixed timestamp/scalar capture occurs under the condition;
  emission occurs outside it. Force release closes the real hold once.
- Metrics and status use the original imported Starlette pool/AnyIO limiter,
  callable arguments and cancellation defaults. Worker start/end execute there;
  dispatch/returned occur on the original event loop. C refresh uses the same
  existing asyncio worker and owner drain. Async history brackets its reader and
  JSONResponse construction and has no invented worker span.

## Bounded emission and identity

`backend_probe.py` keeps at most 8,192 records, with bounded allowlisted scalar
identity fields and explicit invalid/failure/loss/high-water counters. Atomic
CPython deque reservations prevent concurrent overflow from silently evicting
retained records. The global gate-span permit pool has 256 slots; each thread's
object-token cache has 256 entries. Object tokens are process-local diagnostic
identifiers, never source identity. Evicted objects get fresh tokens on reuse.
Clock/sink faults do not escape hooks; missing captured stamps stay unavailable.

No hook calls a sink, performs schema validation or serializes a model/JSON. No
new application lock or executor is introduced. `drain` and `configure` are
owner-only operations before workers start or after they finish; concurrent
export/stream ownership belongs to the later owner stage. This is an in-memory
backend adapter, not a runtime-qualified collector or analyzer.

Threads have independent sequence streams and native-thread start tokens while
sharing the backend process monotonic clock. The validator permits this shared
clock only for identical backend process identity, retaining rejection of
cross-process and browser-document reuse. CPU joins additionally require the
same TID/start token. No cross-process clock subtraction is supported.

## Offline verification

Use Python 3.11 in a private environment with `requirements-test.txt`. From this
package, with that environment active:

```sh
timeout --kill-after=10s 4m python -B tests/run_backend.py \
  --output artifacts/offline-new
timeout --kill-after=10s 2m python -B verify_backend.py \
  --output artifacts/derived-new
```

Both output directories must be new. The test runner records its owner and child
PID/PGID/start identity before and immediately after child creation, traps
INT/TERM, enforces a 180-second inner deadline, terminates/reaps its owned test
group, and checks for live survivors. No service, listener or container starts.
The restricted sandbox stalled even uninstrumented AnyIO completion; the async
suite therefore uses approved host execution. This establishes no application
runtime/network readiness. The first concurrency-test fixture incorrectly
patched Python's global threading function; its corrected fixture patches only
the probe's view and reproduces the buffer race without altering thread startup.

Tests compile unchanged function/method bodies directly from guarded control and
derivative files. Main startup is not imported. Real RepositoryGate, FileLock,
FrameStore, input-admission decorator, Prometheus registry and Starlette/AnyIO
pool are used; external sensors/managers and detached numeric preparation use
deterministic fixtures. Calls, reads, results, exception objects, metric
families, source state and cancellation ownership are compared per role. These
are offline source-slice equivalence tests, not full deployment acceptance.

The matrix and final logs in [evidence/stage2](evidence/stage2) record covered
cases and coverage. Intentional rejected/failed/overflow fixtures do not qualify
runtime collection. [The fixed event](fixtures/stage2-event.json) has a pinned
canonical byte hash and is reproduced twice with injected clocks/identities.

`verify_backend.py` retains the full effective file inventories and checks all
untargeted files against the original archive.
[identity.json](evidence/stage2/identity.json) records exact archive, patch,
spec, effective tree and adapter module hashes. The effective application tree
excludes the separate `/diagnostic-integration` modules; their hashes are
recorded independently. No image was built or labeled.

## Explicitly unavailable / deferred

| Boundary                            | Status                             |
| ----------------------------------- | ---------------------------------- |
| A frame/final/CAS/refresh owner     | Unavailable by design              |
| State worker, ASGI, header joins    | Deferred owner stage               |
| Other FastAPI/Operator pools        | Unavailable                        |
| Physical timing and provenance      | Unavailable without existing IDs   |
| Browser, frontend, packet capture   | Stage 3 deferred                   |
| Host, scheduler, cross-process time | Deferred or unavailable            |
| Unmatched gate, loss, clock failure | Missing evidence; no guessed times |
| Full deployment and overhead        | Unverified by offline tests        |

No performance run, calibration, image build, service, HTTP request, browser or
capture is authorized here. Keep #403/#405/#406/#407/#408 draft/unmerged. Issues
[#390](https://github.com/bcl1713/starlink-dashboard/issues/390) and
[#391](https://github.com/bcl1713/starlink-dashboard/issues/391) stay open. The
historical 1.5-second gate remains unchanged.
