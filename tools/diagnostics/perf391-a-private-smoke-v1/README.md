# Original-A private-environment smoke — readiness failed; STOP

Starting commit: `96d48ad7405d2b7b799b4dd62461364f5af1a3a6`.
Authority: [orchestrator checkpoint](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6363470295).
Session: NEW — LOCAL FORGE, 2026-10-23. Isolated worktree on
`diag/perf391-a-private-smoke`, descended from origin/dev through the explicit
starting commit. Publication destination is existing draft #408.

**FAIL_FRONTEND_READINESS. Exactly one A executor invocation; C executions zero.
No retry or repair. Stop for checkpoint review. No functional-smoke pass.**

The unchanged approved executor returned 1 after the bounded frontend HTTP gate
failed. Ten actual GET attempts failed with `ConnectionRefusedError: [Errno 111]`
at 127.0.0.1:38080. The eleventh readiness iteration lacked enough remaining
command/termination budget. The gate retained status `timeout`; executor failure
is `TimeoutError: insufficient command/termination budget`. Readiness observations
span 4.951 seconds within the five-second cap. Browser settings operations and
browser-owner startup did not begin. The runtime exited before the outer timeout.

## Verified environment and identities

The clean task-owned CPython 3.11.16 venv was recreated offline from six wheels
downloaded from the exact approved URLs and checked against their approved hashes.
PYTHONPATH was unset, PYTHONNOUSERSITE=1, and all installed distributions were
private. Functional Draft202012Validator/$ref/Registry and persistent HashTrieMap
operations passed; the CPython 3.11 ELF64 x86-64 rpds extension and linked libraries
matched the checkpoint. Installed payloads matched wheel contents; uv pip check
reported all six compatible. See [environment](evidence/environment.json),
[wheels](evidence/wheels.json), [setup log](evidence/setup.log) and
[dependency check](evidence/dependency-check.log). No host Python was changed.

[Fresh preflight](evidence/preflight.json) passed once before runtime. It verifies
both closed receipts, four immutable image IDs/labels, retained build inventory,
621-file Stage 5 release/97 source files, source/patch/effective contexts,
compiled assets/module closure, dependencies, pinned collector/frozen harness,
approved correction overlays, and both effective Compose configurations. C was
regenerated and inspected offline only. The historical compiler first reproduced
the original build plan byte-for-byte; the active compiler's only differences
were the two approved logging override hashes. No receipt, image or original plan
was rewritten. Active readiness overlay SHA-256:
`ea21f78ca9f71d8b6b67222839727558cd586ebc3e2e438a4b935bd0482fcdec`.

| Identity | Verified value |
| --- | --- |
| A application | `25e34168f0e2cecb149b0323f1f5a795cb28cae0` |
| A backend image | `sha256:8b8518fe1007170ce423b76f98958d85a4153927a0d8e59930d3790f38318abd` |
| A frontend image | `sha256:aee6d4fdf4a1c7746c8e4ba65458aa3160ffb8d1792982ba56a3e1cb1745dd88` |
| A receipt SHA-256 | `7d337809082015880bb51e69bcf8973fd5036518286b876dda77145543c9c24f` |
| Original plan SHA-256 | `8537bddee63b76d65f08548d447fbc93f42dfbe919b09f4fc9826d4e128954d5` |
| Diagnostic Node | 22.22.2; SHA-256 `81925c0995b5c1427b5d538e6a90ca2fdc4daffb786b09af749beaf7369d4e90` |
| Playwright / playwright-core | 1.63.0 / 1.63.0 |
| Chromium | revision 1243; SHA-256 `8c599d43aec53f2460a31ae2f4af6bd863f8258b34ff519564bc5d4726bfaa1e` |
| Collector source / release | `a48837b99d87366c6e3fc24ba2915f0b739cddad` / `c47d21e3c5bbf92189afbf291b73b9da7a035a4b` |
| Frozen harness | `f3029024b5950a267645195476da5cbca326f16a` |

Node was extracted from the retained pinned image without starting a container;
the exact executable, package engines/imports, Chromium and browser distribution
were verified freshly. Historical Node 22.12.0 remained unchanged. Browser import
compatibility does not qualify real Chromium startup; that boundary was not reached.

Forge UID 1002 used inherited `DOCKER_HOST=unix:///run/user/1002/docker.sock`,
context `default`, verified rootless security and cgroup v2/host PID visibility.
Task ports were free before launch. Available disk was 24,505,659,392 bytes;
host memory available was 55,273,537,536 bytes. Ancestor CPU quota was 10 shared
CPUs. The approved backend 2 CPU/2 GiB/256 PID, Prometheus 1 CPU/1 GiB/256 PID,
frontend 0.5 CPU/256 MiB/64 PID limits are retained in the validated Compose
configuration; host browser budgets remain estimates, not private enforced limits.
The managed status tool and network-policy snapshot were unavailable; inherited
configured access successfully acquired only the pinned dependencies and published
GitHub evidence. No networking or daemon configuration was changed.

## Runtime qualifications, failure evidence and limits

Successful runtime qualifications are limited to exact frontend image asset
extraction/receipt validation from a stopped owned container, synthetic seed/TSDB
creation, backend/Prometheus startup health checks, frontend Compose startup,
bounded readiness refusal detection before browser operations, pre-teardown
diagnostic retention and scoped teardown. These do not qualify end-to-end
instrumentation or host frontend HTTP access.

[Readiness attempts](evidence/runtime/frontend-readiness.json) retain host wall
UTC nanoseconds and monotonic seconds, state and command errors. Raw command logs
retain full connection-refused tracebacks. The
[pre-teardown snapshots](evidence/runtime/frontend-failure-diagnostics.json) retain
all seven requested observations: Compose inventory, container identity,
state/NetworkSettings.Ports, docker port, frontend logs, host listener and scoped
forwarder arguments. They show frontend running, `80/tcp: null`, empty docker port
output, no host listener on 38080, and Nginx workers started. This establishes
missing published-port/listener evidence at the snapshot, not why the mapping was
absent. It does not retroactively resolve the historical refusal. No extra live
probe, port repair, application/Nginx/daemon edit or retry followed.

No source/host scheduled observations began: 0 of 5 each. There is no browser
launch, visible latency chart, history response → retained/projection → actual
uPlot commit association, browser/backend event join, or screenshot attempt.
Backend event buffers/final summaries were not exported after this early failure;
their existence, completeness and dropped counts are unavailable. Source, host,
Node and frontend final summaries are also unavailable. Missing evidence is never
classified as zero loss. See [stream status](evidence/stream-status.json).

The 1.5-second source observer cadence requirement is unchanged and unexercised.
Retained readiness clocks identify the same host process clock domain; there are
no actual source/browser/backend clock joins and no cross-clock duration claims.
Raw-wire bytes, native parse-start, physical scanout and original-A frame/final
authority/CAS remain unavailable by design. Diagnostic Node timing cannot support
historical comparative CPU or sustained performance conclusions. The success-only
integration analyzer was not run against absent streams.

## Evidence, cleanup and checkpoint

[Execution intent](evidence/execution-intent.json) records the exact approved
executor/launcher hashes, unchanged launcher output, timeout process group and
78-second work / 90-second outer / 10-second forced grace. Preflight ran once
under its separate five-minute timeout/ten-second grace. Tool sessions were
preflight 30783 and A supervisor 31019, both completed. Administrative preflight
adaptation changes task paths, starting commit and authority, and explicitly checks
the approved readiness hash and actor rootless endpoint. No reviewed executor,
application, harness or collector source was modified.

The runtime's authoritative launch/owner manifests recorded the exact containers,
network and private volumes (`data`, `routes`, `metrics`) before creation. The
setup ownership file's preliminary volume names were inaccurate; they were never
used to create or clean resources. The exact executor resource intent and
label-scoped teardown/audits govern the actual resources. All 42 retained owner
manifests are clean. The unchanged [cleanup audit](evidence/runtime/cleanup-audit.json)
passes. [Independent Forge host cleanup](evidence/final-host-cleanup.json) confirms
52 recorded PID/start identities and owned process groups absent, no task path
processes, no task listeners, empty A/C container/network/volume listings, and all
four original images/labels/RepoDigests unchanged. Private venv, wheels/cache,
Node, generated contexts, runtime scratch/profile directory and empty lock were
removed. The open-review worktree/evidence remain; primary checkout stays on dev.

Raw non-reproducible runtime files are retained byte-for-byte. The
[runtime inventory](evidence/runtime-inventory.json) hashes all original files,
including reproducible image assets, pinned collector export and seed omitted
from duplication. Canonical assets/collector remain in immutable packages; seed
inputs and its successful command are recorded. The artifact manifest closes this
new package and pins external receipt/source/correction identities; verify.py
checks hashes, closure, stop status, no-browser evidence and cleanup. No expanded
regression suite was run for this evidence-only delivery.
Git whitespace checks pass for authored files; raw Docker/Nginx logs retain
their emitted trailing spaces so their evidence hashes remain intact.

PRs #403/#405–#408 remain open/draft/unmerged; #404 is an open issue, not a PR.
#390/#391 remain open. No image rebuild, packet capture, application/Nginx change,
calibration, benchmark, sustained test, merge, deployment or issue closure.
**Stop for checkpoint review on draft #408.**
