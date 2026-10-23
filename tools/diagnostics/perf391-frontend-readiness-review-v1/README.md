# Frontend refusal investigation

**STOP for checkpoint review. Cause unresolved; no readiness retry added.**
The retained original-A failure confirms that the executor never establishes
frontend HTTP readiness before handing control to the browser owner. It does
not establish why `127.0.0.1:38080` refused the first connection. Startup delay,
a later Nginx exit, and defective rootless forwarding remain distinguishable
hypotheses that the available evidence cannot resolve. Adding polling now would
assume the explanation that this task explicitly requires us to establish.

Starting commit: `8e9d69d1cb82925a0bf0742097a9389d0a533465`.
Authority: [latest orchestrator review](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6362658933).
The isolated task branch starts at that explicit checkpoint, which already
contains `origin/dev`; the primary checkout remains on `dev`.

## Retained evidence

Paths below are relative to
[`perf391-a-approved-smoke-v1/evidence`](../perf391-a-approved-smoke-v1/evidence).
All 16 `runtime/command-*.log` files and all three owner manifests were inspected.

| Boundary | Supported finding | Evidence |
| --- | --- | --- |
| Backend dependencies | Compose returned 0 after backend and Prometheus reported Healthy. | `runtime/command-09.log`, `runtime/manifest.json` |
| Frontend startup | Compose returned 0 for `up -d --no-build --pull never --no-deps mission-planner`. No frontend healthcheck or HTTP wait was configured. | `runtime/command-10.log`, `runtime/manifest.json`, `A.compose.json` |
| Frontend state before browser owner | Running, PID 2804122, ExitCode 0, not restarting, OOMKilled false, empty Error, FinishedAt zero, StartedAt `2026-10-23T10:11:47.677086909Z`. No Health field. | `runtime/command-16.log` |
| Host process mapping | The mapped process is `docker-init`, in the task container cgroup. This proves a living container init at that observation, not a listening Nginx worker. | `runtime/host-mapping.json`, `runtime/host.jsonl` |
| First settings operation | Browser owner failed with `connect ECONNREFUSED 127.0.0.1:38080`, return code 1, before Chromium launch. No HTTP response was received. | `runtime/browser/failure.json`, `runtime/manifest.json`, unchanged browser-owner source |
| Teardown | Compose stopped and removed the frontend and private volumes/network. No post-failure State or final exit code was retained. | `runtime/compose-down.log`, cleanup owner manifest |

**Actual Nginx stdout/stderr was not retained.** Command 10 is Compose progress,
not Nginx output. Command 03 is image metadata, not container output. None of the
recorded commands requests `docker logs` or Compose logs. Logging used the
bounded `local` driver, and the original container was removed. A fresh read-only
`docker inspect ef4c009feb79f4ad257f6b4ac33e70d1f2091298582bca1a18c1bc225963c95f`
returned “no such object”. The pre-browser ExitCode 0 is not a final process exit
result and cannot exclude a subsequent startup error. Teardown's “Stopped”
progress does not prove Nginx had remained alive.

## Published endpoint and proxy path

The rendered effective configuration requests TCP
`127.0.0.1:38080` → frontend container port 80. It has `restart: no`, `init: true`
and an internal default network. The launch environment agrees on port 38080;
the browser owner explicitly uses `node:http` with `agent: false` against that
origin. It sends the first PUT to `/api/overview-history/settings`.

Original A at `25e34168f0e2cecb149b0323f1f5a795cb28cae0` configures Nginx
`listen 80`, serves `/` as static content, and proxies `/api/` to
`http://starlink-location:8000`. The diagnostic Dockerfile copies that config
unchanged and runs `nginx -g 'daemon off;'`. No static port mismatch was found.
The refusal precedes an HTTP status, so the evidence does not implicate the
settings handler or prove that Nginx reached its backend proxy.

Neither the runtime command logs nor host samples retain live
`NetworkSettings.Ports`, `docker port`, rootless forwarding state, or a frontend
listener snapshot. A requested Compose mapping is not an observed working
mapping. The actor's configured default daemon uses
`unix:///run/user/1002/docker.sock`; the fresh audit confirms rootless mode and
preserves the inherited Docker configuration. Its current health cannot prove
forwarding worked during the failed run. Namespace binding and forwarding
failure remain unresolved.

## Timing and missing readiness contract

The original host anchor joins monotonic `2151887243931143` ns to UTC
`1792750308094615991` ns. The fresh host audit confirms 100 clock ticks per second.
Owner start IDs are process start ticks, with roughly 10 ms quantization; these
are not command completion or HTTP request timestamps.

| Event | Retained time |
| --- | --- |
| Frontend Compose command process starts | start ID `215188673` |
| Frontend container starts | UTC `10:11:47.677086909` |
| First subsequent service lookup process starts | start ID `215188699` |
| Frontend State inspect process starts | start ID `215188722` |
| Browser owner process starts | start ID `215188724` |
| Host collection anchor just after browser-owner spawn | UTC `10:11:48.094615991` |
| First cleanup-owner command process starts | start ID `215188761` |

From the process order, Compose completed before start ID `215188699` and the
browser owner started about 0.25 seconds later. Its launch was roughly 0.42
seconds after container start, using the host anchor. Exact Compose completion,
settings request, and refusal times are absent. The request occurred after
browser-owner launch and before cleanup; these bounds support temporal
proximity, **not a confirmed listener race or eventual successful readiness**.

`launcher.py` waits for backend/Prometheus Docker health, then starts the
frontend without `--wait`. `execute.proposed.py` runs service PID/cgroup mapping
and spawns the browser owner without an HTTP gate. The browser owner's first
network operation is the settings PUT. There is no evidence of frontend HTTP
success anywhere in this attempt.

## Decision and remaining gates

No executor, launcher, owner, application, Nginx, image, receipt, frozen tool or
historical evidence was changed. The existing 78-second work deadline,
90-second outer limit and 10-second forced grace are unchanged. There is no
new launch proposal to authorize.

1. Review this unresolved-cause checkpoint. Establish whether the missing
   Nginx/exit/listener/forwarding evidence can be supplied from a separately
   retained source. A future evidence-gathering runtime requires new explicit
   authorization; this task authorizes no retry.
2. If later evidence supports a startup readiness delay, correct the executor
   with an owner-controlled bounded HTTP success gate on the task endpoint,
   before browser-owner execution. Polling and request timeouts must consume the
   existing 78-second deadline and preserve cleanup within 90 seconds. It must
   stop on established crash/forwarding failure. Behavioral fixtures must cover
   immediate/delayed success, permanent refusal, timeout and cleanup before any
   runtime authorization. Those readiness tests are not applicable to this
   investigation-only change and were not run.
3. A instrumentation remains unqualified: no visible chart, history to retained
   data/projection to actual uPlot commit join, complete backend/source/browser
   summaries or zero-loss proof. Host collection has one sample and is
   incomplete. The 1.5-second observer threshold remains unchanged and unexercised.
   Raw wire, native Axios parse-start, physical scanout, and A final-authority,
   CAS and frame boundaries remain unavailable. C remains NO-GO.

Keep #403/#405/#406/#407/#408 draft and unmerged, #404 open as an issue, and
#390/#391 open. No A retry or C execution, containers started, browser launched,
application HTTP, benchmark, calibration or sustained soak occurred in this task.

## Verification and cleanup

The unchanged historical verifier passed under a 15-second wall-clock limit:
**59 artifact hashes and 17 external pins**, one failed A and no C, incomplete
streams explicit, and 23 historical process identities covered. No new readiness
behavior is claimed or tested. `git diff --check` passes.

[`host-audit.json`](host-audit.json) records a fresh read-only Forge audit:
23 historical PID/start identities absent; no matching actor task commands or
readable task working directories; ports 38080–38083 and 38180–38183 clear;
empty scoped A/C container/network/volume listings; private historical scratch
and lock absent. Four retained image IDs, labels and RepoDigests match receipts.
Two shared actor processes, systemd PID 2575907 and sd-pam PID 2575912, deny cwd
inspection; their command lines were inspected. This is the explicit cwd
visibility limit, not a task resource left running. No task runtime resources
were created. The audit command completed and was reaped; no temporary paths
were created. The open-PR worktree and review evidence remain.

The first two audit invocations failed on procfs cwd permissions (kernel PID 2,
then shared actor systemd); neither started resources. The successful audit
checks historical identities across host procfs, scans actor commands, and
records shared cwd visibility limits instead of claiming full cwd access.

Unchanged SHA-256 source identities (also recorded in the host audit):

| Source | SHA-256 |
| --- | --- |
| Executor `execute.proposed.py` | `92736fd1805d9f140853dcc070e33106362ebd7f321c454f22c68850f6ec0fe8` |
| Launcher `launcher.py` | `f202e79fc31add067c5c76b43bce6834f87685afc4a5444dffaaf5ddf04ec7c4` |
| Browser owner `browser-owner.proposed.mjs` | `885a11a55bb76de21d75d885928ec2b60037f0b4e7525234968c44c181d41bb0` |
| Process owner `owner.py` | `b1c2f65c4179b9a60751c6e3eb7709ab81a4379a33d102282e986d506ccd2511` |
| Historical executor launch JSON | `26bcc96656550768d74498ea3dd795d6ef0d17a43ad9ef6505e31d838272b6d6` |
