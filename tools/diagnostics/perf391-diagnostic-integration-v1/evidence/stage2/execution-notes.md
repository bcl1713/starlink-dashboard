# SDD ledger — plan: docs/superpowers/plans/2026-10-22-perf391-diagnostic-integration.md

Stage 1 accepted at a4e707e96226400051bbd05e28d831d8fbae6899; do not repeat
implementation. Task 2: in progress. Only Stage 2 backend integration authorized
by #408 issuecomment-6351106343. Pre-flight: Stage 1 guard feeds Stage 2 exact
patches; guard currently excludes main.py despite approved main.py call sites.
Add only exact backend/starlink-location/main.py eligibility, covered by a
failing guard test. No other eligibility expansion. Ruling: Execute only Stage
2; later observer/ASGI owner/host and browser/capture remain deferred by
explicit checkpoint constraints. Cost if wrong: later integration review must
expand separately. Cloud environment status tool and network-policy snapshot
unavailable on this tool surface; no runtime readiness inferred. GitHub
connector used for review, actor Git transport for fetch/push.

Task 2: initial 43-test run had four diagnostic schema errors (numeric identity
fields); no application equivalence difference. Added scalar normalization and
parent-join regression tests RED→GREEN. Expanded 49-test run passed. Ruling:
backend thread streams share a process monotonic clock ID; extend stream
validation to allow the same clock only within the same backend process
identity. Browser/new-process clock reuse remains rejected. Required for
queue/delivery joins; cost if wrong: invalid duration claims, blocked by
explicit join tests and later analyzer review. Sandbox diagnosis: uninstrumented
AnyIO completion also stalls inside restricted sandbox; host bounded control and
worker tests pass. Async suites run via approved host execution, with no
HTTP/services. One test process was stopped by USR1 without a handler; process
and timeout parent verified exited before retry. Later diagnosis used
faulthandler and an explicit 20s timeout. Task 2: complete implementation and
offline tests; 62/62 tests PASS with child-group cleanup clean. Pending final
whole-branch independent review, final evidence refresh, commit/push and
checkpoint report. No control-versus-patched application
return/side-effect/read-order/metric/cancellation difference observed. Guard
applications passed for both roles; no production/frozen source files changed.

Final review: independent fresh-context reviewer, exact candidate
45deab7fc846c3f75c0a91d59b411bb4be888bda. Critical: none; Important:
cross-thread token joins, release-clock permit leak, unexercised cancel_check;
all reproduced RED then fixed. Final: Ruling: regrade offline-runner
surviving-descendant finding from Minor to Important — workspace lifecycle
requires cleanup even when test leader exits — cost if wrong: extra offline
fixture and cleanup code; failing fixture confirms the gap. Final: fixed
shared-head process token join — real two-thread FrameStore and concurrent token
lookup RED→GREEN. Final: fixed release-clock permit leak — actual gate unlock
with missing stamp and subsequent reacquisition RED→GREEN; all 256 permits
restored. Final: fixed cancellation coverage — callback invocation assertion
RED→GREEN; unlimited wait keeps cancel_check reachable. Final: fixed runner
orphan cleanup — exited leader with TERM-ignoring descendant RED→GREEN, scoped
PID/start-time TERM/KILL and reaping. Task 2: complete; final full suite 66/66
PASS, worker adapter 100%, combined reported coverage 92%; owner cleanup clean.
No second review claimed; Stage 3 remains blocked by checkpoint requirement.
