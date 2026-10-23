# Original-A approved smoke: browser setup failed; STOP

Starting commit: `2dcad461f6dd74958ec2f2e88f85c8c71c6d4b92`.
Authority: [orchestrator approval](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6362494281).
Local Forge, 2026-10-23. **One A attempt, zero C executions. Stop for checkpoint review.**

The unchanged reviewed executor exited 1 with `RuntimeError: browser smoke failure`.
The browser adapter's first settings PUT through the frontend failed with
`connect ECONNREFUSED 127.0.0.1:38080`. This occurred before Chromium launch,
collection creation, navigation or any screenshot. No retry or repair followed.
The immediate connection failure is established; its underlying cause is not.

## Preflight and capabilities actually demonstrated

[Fresh preflight](evidence/preflight.json) passed once. The historical compiler
first reproduced the immutable original plan byte for byte. The second layer
accepted only the two approved override hashes, independently bound to the
logging correction manifest and full effective Compose configurations. All six
A/C service logging configurations match the approved `local`, `compress: false`,
`max-file: 1`, `max-size: 10m` configuration. C was regenerated offline only.
The original plan, closed receipts and all historical evidence are unchanged.

| Identity | Verified value |
| --- | --- |
| A source | `25e34168f0e2cecb149b0323f1f5a795cb28cae0` |
| A backend image | `sha256:8b8518fe1007170ce423b76f98958d85a4153927a0d8e59930d3790f38318abd` |
| A frontend image | `sha256:aee6d4fdf4a1c7746c8e4ba65458aa3160ffb8d1792982ba56a3e1cb1745dd88` |
| A closed receipt SHA-256 | `7d337809082015880bb51e69bcf8973fd5036518286b876dda77145543c9c24f` |
| Immutable original plan SHA-256 | `8537bddee63b76d65f08548d447fbc93f42dfbe919b09f4fc9826d4e128954d5` |
| A full regenerated context SHA-256 | `9563d8f4396323fc2ba726605704fb41a14c56c89010d55a2b48cfa1d412f7ab` |
| Collector source / release | `a48837b99d87366c6e3fc24ba2915f0b739cddad` / `c47d21e3c5bbf92189afbf291b73b9da7a035a4b` |
| Frozen harness | `f3029024b5950a267645195476da5cbca326f16a` |
| Diagnostic Node | 22.22.2; `81925c0995b5c1427b5d538e6a90ca2fdc4daffb786b09af749beaf7369d4e90` |
| Playwright / playwright-core | 1.63.0; configured Chromium revision 1243 |
| Chromium executable SHA-256 | `8c599d43aec53f2460a31ae2f4af6bd863f8258b34ff519564bc5d4726bfaa1e` |

The full source, patches, module/dependency/compiled-asset closures, 187-file
retained build inventory and 621-file Stage 5 release with 97 source files were
verified. The executor independently rechecked context, image, receipt, runtime
identity and image-extracted assets. Private Node was extracted from the retained
pinned image without creating a container. Historical Node 22.12.0 was preserved.

Forge UID 1002 used the configured `default` rootless daemon at
`unix:///run/user/1002/docker.sock`, host PID namespace and cgroup v2. Ports
38080–38083 were free. Disk headroom was 24,506,380,288 bytes; available memory
55,444,066,304 bytes. Shared ancestor limits are retained in preflight and do not
establish a private browser cgroup budget.

The bounded local logging configuration allowed TSDB seeding and service startup.
Prometheus and backend reached Docker health checks; frontend Compose startup
returned successfully. All three container PID/start/cgroup mappings were retained.
One actual host resource observation, bracketed clock anchors and permission-related
counter omissions are preserved. These facts do not establish frontend HTTP readiness
or end-to-end diagnostic instrumentation.

## Failed gates and unavailable evidence

The [stream status](evidence/stream-status.json) records each boundary explicitly:

- Host sampling ended with `completed: 1`, `skipped: 0`, `complete: false`, after
  cancellation on browser setup failure. The five-sample gate failed. This partial
  summary does not establish zero loss for the run.
- Source observation never started: zero captures, no final summary, cadence and
  dropped-event counts unavailable. The **1.5-second requirement is unchanged**.
- Backend producer, worker and repository admission events/final summaries are
  unavailable. Failure bypassed the normal stop/drain/copy phases; Compose teardown
  removed the private data volume. In-memory events may have existed, but were not
  retained and are not represented as zero work or zero drops.
- No Chromium launch, real Page, visible chart, history-response → retained data →
  projection → actual uPlot commit chain, browser/observer final summaries or
  successful event joins were demonstrated. `browser-intent.json` records intent only.
- Screenshot attempts: zero. Raw-wire bytes, native Axios parse-start, physical
  scanout and original-A frame/final-authority/CAS remain unavailable by design.

The executor ran once under `timeout --kill-after=10s 90s`, preserving its
78-second working deadline. The failure exited before the outer timeout.
No success-only analyzer was run against incomplete streams. The applicable joins,
loss and final-summary gates remain failed/unqualified, not silently waived.
No benchmark, calibration, sustained acceptance or production conclusion follows.

## Evidence, ownership and cleanup

[Execution intent](evidence/execution-intent.json), three unchanged owner manifests,
all raw command logs, browser failure, host mappings/counters and partial summaries
are retained. Tool sessions: preflight 39960; executor 94767; both completed.
Preflight had its separate 180-second outer limit. The preflight adaptation changes
only administrative task/output paths, starting commit and authorization.
The executor receives exact unchanged launcher output; supplementary two-layer
provenance remains in the separately retained preflight launch and checks.

The stopped extraction container was removed before service startup. Its exact
asset hashes match the closed A receipt. Duplicate extracted assets, collector
export and generated synthetic seed bytes were inventoried before scratch removal;
canonical assets and collector remain in their immutable packages. Raw runtime
observations and logs are preserved without modification.

The executor reports a clean owner and no cleanup error. A separate unchanged
[audit](evidence/runtime/cleanup-audit.json) passed, followed by the
[independent final Forge audit](evidence/final-host-cleanup.json): 23 recorded
process/start identities and owned groups absent, no task path processes, ports
38080–38083 and 38180–38183 clear, both A/C project container/network/volume
listings empty. Private Node/Python environment, exports, runtime scratch and empty
lock were removed after evidence retention. Four retained image IDs, labels and
RepoDigests remain unchanged. Shared configuration, credentials and other tasks'
resources are preserved. The isolated open-PR worktree remains; primary stays on dev.

[Manifest](artifact-manifest.json) closes retained artifacts and pins unchanged
external source/receipt identities. `verify.py` checks hashes, exact closure,
preflight, precise failure, failed-gate accounting, extracted-asset identity and
cleanup. This verifies the failure evidence, not successful smoke qualification.
No images rebuilt, production/frozen tooling changed, packets captured, retries,
C execution, merge, deployment or issue closure occurred. Existing PRs
#403/#405/#406/#407/#408 remain draft/open/unmerged; #404 is an open issue.
#390/#391 remain open. **STOP for checkpoint review on draft #408.**
