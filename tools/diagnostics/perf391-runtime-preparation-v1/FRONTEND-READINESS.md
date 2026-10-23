# Frontend HTTP readiness correction — offline checkpoint

Starting commit: `360cd1afe3b3ef3803ad9753872310fdf14523f7`.
Authority: [orchestrator review](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6362840530).
Stop for review after push. A retry and C execution remain unauthorized.
The historical ECONNREFUSED cause remains unresolved.

## Design and implementation plan

The review specifies an HTTP-success gate rather than a sleep or container-running
assumption. The executor inserts it immediately after frontend Compose startup,
before host mapping and browser-owner operations. No Nginx, application settings,
polling, network, image, collector or observer-cadence change is involved.

- [x] Exercise immediate/delayed success, bad status/content, exited/unhealthy
  containers, refusal, request timeout and cancellation through offline fixtures.
- [x] Add owner-controlled GET `/` with status 200 and SHA-256 equality to the
  receipt-bound `index.html`. Request identity encoding, close the connection,
  and reject bodies over 256 KiB.
- [x] Preserve snapshots in `finally`, before Compose down, even if frontend
  startup raises or receives TERM. Reap owned commands before collection.
- [x] Check diagnostic failures and TERM-resistant probe cleanup; retain evidence,
  verify unchanged manifests and push only this correction to draft #408.

The original node correction manifest and build/source manifests remain intact.
The additive `frontend-readiness-overlay.json` binds its predecessor hash,
the two replaced source hashes, and all three new executor/helper/checker hashes.
The identity checker still validates the original plan, original correction
inventory and every unaffected source. Existing launch JSON is not rewritten.
Future authorization must review both the unchanged receipt-bound launch plan and
this new source overlay; an old launch plan alone does not authorize execution.

## Limits and failure evidence

Readiness has a five-second cap, clipped to the original 78-second work deadline,
with 200 ms between failed attempts. Each owned inspection/HTTP command has a
750 ms cap. HTTP socket operations have a 500 ms timeout; an owned GNU timeout
bounds the whole command, including slow bodies, to the command allowance.
Its execution budget reserves 50 ms TERM-to-KILL grace and 50 ms for exit
observation. Near deadline, commands without those reserves fail closed.
No browser-owner launch follows a readiness failure. Observed exited/dead/removing
or unhealthy state stops immediately. Running alone never establishes readiness.

Attempts retain wall and monotonic clock stamps, observed state, status/body hash,
error and completion time. Failed command messages point to their retained
bounded stdout/stderr log and retain its final error text. The gate establishes
static HTTP readiness, not backend settings success or future container survival.

Failure snapshots have a 1.5-second total collection allowance and 250 ms per
command, including the same termination reserves. They run before teardown while
the task containers remain owned. They may use the first two seconds of the
existing cleanup window, stopping by elapsed 80 seconds to reserve the existing
ten-second Compose teardown. Work remains 78 seconds, outer timeout 90 seconds,
and forced outer grace ten seconds; none are extended.

Snapshots retain Compose inventory, frontend State/Health/exit information,
observed NetworkSettings.Ports and docker port output, 80 frontend log lines,
the target host listener, and bounded argv for actor-owned known forwarding
processes only (32 processes, 4096 bytes each). Each retained observation is
capped at 32 KiB; underlying command logs retain the existing 1 MiB limit.
Errors, absent identities and exhausted budgets remain explicit unavailable
evidence. Observations do not automatically attribute refusal to a startup race,
Nginx, or missing host forwarding. No unrelated process arguments are collected.

Each probe and diagnostic command has its own owner, intent-before-spawn and
descendant reaping. Diagnostic collection catches failures, including cancellation,
and cannot bypass the existing scoped Compose teardown. Cancellation of the
executor and startup signals also reach this path. SIGKILL cannot run finally;
the existing external post-timeout host audit remains mandatory.

## Verification and evidence

The complete offline preparation suite passes **35 tests** using the retained
build plan, including 12 executor cases, focused readiness/HTTP/snapshot cases,
a TERM-resistant Python child with real process cleanup, receipt/overlay guards
and the existing 621-file frozen release check. Docker and HTTP boundaries are
faked; no real container, browser, application HTTP, packet capture, calibration
or sustained test runs. Immediate/delayed executor fixtures stop at a deliberate
post-gate sentinel before browser launch.

```sh
PERF391_OFFLINE_ROOT=tools/diagnostics/perf391-built-images-v1/evidence \
  timeout --kill-after=10s 90s python -B -m unittest discover \
  -s tools/diagnostics/perf391-runtime-preparation-v1 -v
```

[Full test log](evidence/frontend-readiness/offline-tests.log),
[integrity evidence](evidence/frontend-readiness/integrity.json),
[cleanup evidence](evidence/frontend-readiness/cleanup.json), and
[SHA-256 inventory](evidence/frontend-readiness/hashes.json) are retained.

Integrity checks establish 40 unchanged original manifests/receipts, 59 unchanged
historical artifact hashes and 17 historical external pins at the starting
commit. The historical verifier is unchanged: its old executor/checker pins
describe the historical run and intentionally differ from these corrected
sources. The new overlay records those replacements instead of rewriting the
historical evidence. Exact A/C image receipts, build plan, source manifests,
comparison contract, application sources and frozen 1.5-second rule are unchanged.
No Docker commands contacted a daemon, so images were neither rebuilt nor changed.

Two initial sandbox executor checks hit their explicit 60/180-second limits
because PID/proc visibility was unsuitable for this process-owner test.
Host execution with consistent PID visibility passed. Those aborted fixture
identities (20 recorded processes) were verified absent; six task-owned temporary
paths were removed. Successful executor fixtures assert clean owners and reaped
children. Final host inspection found no fixture processes, task-port listeners,
or fixture paths. No real containers, networks or volumes were created.
The open-PR worktree and evidence are preserved.

Review identified termination work outside probe allowances and insufficient
forwarder arguments. Both are addressed by the nested TERM/KILL budget plus
the real resistant-child case, and scoped forwarder argv collection.
PRs #403/#405–#408 remain draft/open/unmerged; #404 is an open issue.
#390/#391 remain open. No A retry or C run is authorized by this checkpoint.

