# #391 proposed runtime runbook

**Preparation only: no build or runtime authorization.** Read the
[design, identities and feasibility gates](README.md) first.

## Offline validation and future commands

Run from repository root. The offline output must be new and task-owned. The
retained validation report gives exact tool versions, counts and hashes. No
proposed runtime script is evaluated by these checks.

```sh
PREP=tools/diagnostics/perf391-runtime-preparation-v1
timeout --kill-after=5s 120s python3 -B "$PREP/prepare.py" \
  --output /tmp/perf391-runtime-prep-408-validation
PERF391_OFFLINE_ROOT=/tmp/perf391-runtime-prep-408-validation \
  timeout --kill-after=5s 30s python3 -B "$PREP/test_preparation.py"
timeout --kill-after=5s 10s python3 -B "$PREP/launcher.py" --role A \
  --plan /tmp/perf391-runtime-prep-408-validation/runtime-build-plan.json \
  --root /tmp/perf391-smoke-408-a
node --check "$PREP/browser-owner.proposed.mjs"
node --check "$PREP/vite.perf391.mjs"
```

Repeat preparation into a second fresh output and compare
`runtime-build-plan.json` bytes, generated Dockerfiles and both Compose
configurations. Config-only `docker compose config --format json` uses explicit
synthetic sentinel image IDs; it neither contacts an application nor certifies
an image. Do not run `up`, `build`, `pull`, browser launch, source HTTP or
proposed execution in this task.

**Future build authorization only:** for role A, then C, from a regenerated and
verified private context; substitute C and its base SHA for the second build.
Record intended tags/output before invoking either command. Preserve the actor
daemon/context and inherited proxy/CA. Each build has a 45-minute wall limit and
10-second forced grace; build serially, with a proposed 8 GiB/4 CPU planning
budget and 12 GiB disk allowance. These are estimates, not measured
requirements. If enforcement is required, separately verify BuildKit cgroup
support first.

```sh
CONTEXT=/tmp/perf391-runtime-prep-408-validation/A
timeout --kill-after=10s 45m docker build --platform linux/amd64 \
  --secret id=proxy_ca,src="$CODEX_PROXY_CERT" \
  --build-arg ACCEPTANCE_CANDIDATE_SHA=25e34168f0e2cecb149b0323f1f5a795cb28cae0 \
  -f "$CONTEXT/.perf391/backend.Dockerfile" \
  -t perf391-diag-408-a-backend:reviewed "$CONTEXT"
timeout --kill-after=10s 45m docker build --platform linux/amd64 \
  --secret id=proxy_ca,src="$CODEX_PROXY_CERT" \
  -f "$CONTEXT/.perf391/frontend.Dockerfile" \
  -t perf391-diag-408-a-frontend:reviewed "$CONTEXT"
```

If a CA selector is absent, resolve trusted build setup before these commands;
never disable TLS verification or copy credentials into a context/image. Record
actual immutable IDs using `docker image inspect`, then use stopped, recorded
task-owned containers and `docker cp` to extract frontend assets, backend
installed metadata and `/usr/local/bin/node`. Remove those containers without
starting them. A Node copied from the pinned backend renderer may supply 22.22.2
if its host ELF dependencies resolve; rehash/version-check it. Construct the
closed receipt with actual image IDs/labels, all asset hashes, exact npm lock,
installed Python/OS inventories and `prepare.browser_tree(...)` SHA-256. Review
the receipts, A/C dependency equality and missing capabilities **before** any
smoke authorization. Invented/sentinel values are not launchable receipts.

**Future short-smoke authorization only:** compile the receipt-bound plan first.
The launcher output contains every exact Compose argv and browser option. Review
the generated plan and executor proposal together; the checkpoint URL records
authorization and is not itself proof of permission.

```sh
timeout --kill-after=5s 10s python3 -B "$PREP/launcher.py" --role A \
  --plan /tmp/perf391-runtime-prep-408-validation/runtime-build-plan.json \
  --receipt /reviewed/built-A.json --root /tmp/perf391-smoke-408-a \
  > /reviewed/launch-A.json
timeout --kill-after=10s 90s /reviewed/python3.11 -B "$PREP/execute.proposed.py" \
  --launch-plan /reviewed/launch-A.json \
  --build-plan /tmp/perf391-runtime-prep-408-validation/runtime-build-plan.json \
  --receipt /reviewed/built-A.json --node /reviewed/node-22.22.2 \
  --authorization 'https://github.com/bcl1713/starlink-dashboard/pull/408#FUTURE_APPROVED_CHECKPOINT' \
  --execute
timeout --kill-after=5s 30s /reviewed/python3.11 -B "$PREP/audit.py" \
  --runtime /tmp/perf391-smoke-408-a
timeout --kill-after=5s 60s /reviewed/python3.11 -B "$PREP/analyze-runtime.py" \
  --build-plan /tmp/perf391-runtime-prep-408-validation/runtime-build-plan.json \
  --receipt /reviewed/built-A.json --runtime /tmp/perf391-smoke-408-a \
  --output /reviewed/analysis-A
```

Those `/reviewed` inputs are deliberate unmet prerequisites, not existing paths.
After **all A gates and cleanup pass**, compile and run the corresponding C
commands with C's receipt/root and role. No automatic retry, calibration or
soak.

## Concrete schedule, budgets and hard stops

Order is **A once → host cleanup audit → offline analysis → C once → audit →
analysis → checkpoint**. A failure stops before C. Each role has a 90-second
outer deadline and 10-second forced grace. Work shares a 78-second deadline;
phase caps never extend it. Offline build/identity checks and post-run analysis
are separately bounded; they are not performance intervals.

| Role-relative interval | Operation / latest gate                                                                                                                                                                                                                                                                                                     |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0–12 s target          | Verify receipt/binaries/overlay/context; inspect exact images and extract/check frontend bytes from an unstarted owned container; record ownership. Stop on any drift.                                                                                                                                                      |
| By 22 s target         | Seed fictional OpenMetrics (3 s cap) and private TSDB with promtool (7 s cap).                                                                                                                                                                                                                                              |
| By 40 s target         | Start Prometheus/backend; 18 s startup cap, backend health required. Start Nginx (2 s cap). No browser yet if readiness/mapping fails.                                                                                                                                                                                      |
| 40–65 s target         | Map containers; launch private browser/Node, host sampler and source observer. Five source/host samples at 1 Hz, each source request capped at 2 s. Capture first latency chart slice and one screenshot attempt; close Page evidence admission promptly. Browser phase total cap 35 s, subject to remaining work deadline. |
| By 78 s hard work stop | Stop backend, await final drain, copy bounded backend files and retain final summaries. No new work after this deadline.                                                                                                                                                                                                    |
| By 90 s cleanup target | Reap owners/descendants; remove only the recorded Compose project/disposable volumes and stopped extraction container. External timeout grace ends at 100 s; audit/recovery follows if forced.                                                                                                                              |

Backend: 2 CPUs/2 GiB/256 PIDs. Prometheus: 1 CPU/1 GiB/256 PIDs. Nginx: 0.5
CPU/256 MiB/64 PIDs. One host Node/browser plus Python owner: plan for 2 CPUs/2
GiB and at most 256 descendants; **host budgets are estimates, not
kernel-enforced caps**. The actor's 10-CPU ancestor quota is shared. Stop if
headroom or process visibility is inadequate; do not infer an idle host from
Docker's empty rootless container listing. Future tighter host cgroups require
separate reviewed setup, not a claim of existing isolation.

Evidence budgets: Node sink 128 MiB, backend export 32 MiB, host export 64 MiB,
each command log 1 MiB; target total retained live evidence ≤256 MiB per role.
Compose logs independently cap at 10 MiB per service. Source/browser bodies and
persisted PNGs ≤2 MiB each; ≤64 artifacts, browser jobs ≤8, bounded queues and
five panels maximum remain unchanged. Backend capacity/real overhead are not
qualified; overflow, dropped/invalid events, token loss, missing finals, changed
streams, skipped deadlines, bad request joins or incomplete artifacts fail the
run. No uncertainty acknowledgement is imposed on mission planning.

## Ownership and cleanup

Before first resource creation, record command/session, owner PID/PGID/start,
task root, project, expected containers/network/volumes, four listeners,
temporary profile root and cleanup commands. Capture actual IDs immediately
after creation. Do not record proxy credentials. Keep the actor socket and
context untouched.

On normal exit, INT, TERM or failure: stop admissions; cancel/await observer and
bindings; retain final browser/loss summaries; close context/browser/server;
drain backend workers/lifecycle; reap owned process groups and adopted escaped
descendants; stop/remove the private project. Graceful TERM precedes KILL of
verified survivors. No broad pkill/killall/prune. After forced timeout, inspect
old ownership and stop its process tree **before** another command/run.

The future host cleanup sequence uses the original recorded Compose files/env:

```sh
timeout --kill-after=5s 15s docker compose -p perf391-smoke-408-a \
  -f /tmp/perf391-smoke-408-a/compose.base.json \
  -f /tmp/perf391-smoke-408-a/compose.override.json \
  down --volumes --remove-orphans --timeout 2
docker ps -aq --filter label=com.docker.compose.project=perf391-smoke-408-a
docker network ls -q --filter label=com.docker.compose.project=perf391-smoke-408-a
docker volume ls -q --filter label=com.docker.compose.project=perf391-smoke-408-a
```

All three listings, owned PID/start/group checks, temporary profile contents and
four listeners must be empty through approved **host** inspection. Remove only
the recorded task `tmp/` after its processes are gone, then run `audit.py`; keep
the empty lock file while serial A/C work may still use its inode. Its final
removal is task-scoped cleanup after both runs/audits. Preserve receipts,
evidence and open-PR worktrees. Report exact survivors/unavailable checks if
cleanup fails. The audit never signals an unknown process or removes shared
data.

This preparation task created no runtime project, container, listener, browser,
capture or service. Its exported sources and test temporary paths are removed
after validation. Retain only review artifacts and the isolated open-PR
worktree.

## Node identity correction — review checkpoint only

The [latest orchestrator decision](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6355528452)
separates these contracts:

| Role | Required identity |
| --- | --- |
| Diagnostic image build / app-side scripts | Node minimum 22.22.2; accepted images unchanged |
| Diagnostic smoke/browser owner | Exactly Node 22.22.2, SHA-256 `81925c0995b5c1427b5d538e6a90ca2fdc4daffb786b09af749beaf7369d4e90`, as bound by both receipts |
| Historical frozen benchmark browser | Node 22.12.0, SHA-256 `177208bfc4a9403121a40c72d038c670f4fd937fa16ca7df0a720e90be0fe2d9`; frozen comparator requirements unchanged |

The diagnostic tuple is a new functionality lane. It is not a matched historical
benchmark; its timings must not be compared to historical controls. Playwright
1.63.0 and Chromium revision 1243/binary hash are verified independently.
`verify_runtime_identity` hashes Node before executing it, checks `--version`,
reads package engines/revision metadata and imports Playwright to resolve its
configured executable without calling launch. Package compatibility and import
do not qualify actual browser startup.

Use a private executable extracted from the retained pinned Node image; do not
fall back to PATH Node. Container-free preparation can use `docker image save`
and read only `usr/local/bin/node` from its layers. Record ownership and bound the
export/extraction; hash-check before executing. This task's private copy is
removed after verification; a future authorized smoke must recreate and verify
it, then supply that exact path to `--node`.

The accepted build plan, receipts, assets and image IDs remain immutable.
`node-contract-overlay.json` records the original overlay inventory and the
corrected launcher/executor/schema/helper inventory. The executor checks both;
it does not rewrite the original plan to make the old receipt accept new bytes.
The launcher binds the correction manifest hash into every new dry-run plan.
Regenerate the proposed A plan using the **retained**
`perf391-built-images-v1/evidence/runtime-build-plan.json` and `built-A.json`;
old launch-plan JSON intentionally fails equality validation. Do not regenerate
build contexts or receipts for this contract correction.

STOP for review. A future A-only proposal retains the private Compose project,
5 samples at 1 Hz, 78 s work / 90 s outer / 10 s force grace, one chart join and
at most one screenshot attempt. Fresh image, identity, source/context, port,
headroom and cleanup gates remain mandatory. The 1.5-second cadence requirement
is unchanged. No A smoke is authorized here; no C, calibration or sustained run.
Raw-wire provenance remains unavailable. Keep #403–#408 draft/unmerged and
#390/#391 open.
