# Forge qualification handoff

Stage 5 authorizes deterministic offline qualification only. This file prepares
a future short-run review; it does not authorize images, services, browsers,
HTTP, capture, calibration or sustained tests. Stage 3B remains deferred.

## Repeat offline qualification

Use a private Python 3.11 environment with `requirements-test.txt`; record the
environment and output path before starting. Run from this package, using new
output directories. The Python owner installs a process-local subreaper and
records child PID, PGID, start identity and final cleanup. Retain an outer
timeout.

```sh
timeout --kill-after=10s 30s ./forge-preflight.sh --offline
timeout --kill-after=10s 140s python -B run.py tests --output artifacts/stage5-repeat-tests
timeout --kill-after=10s 45s node --experimental-test-coverage --test tests/*.test.mjs
timeout --kill-after=10s 90s python -B tests/stage5_qualify.py --output artifacts/stage5-repeat-pipeline
timeout --kill-after=10s 2m python -B verify.py --output artifacts/stage5-repeat-identity
timeout --kill-after=10s 2m python -B verify_frontend.py --output artifacts/stage5-repeat-derivatives
```

`tests/stage5-node-fixture.mjs OUTPUT` reproduces persisted synthetic request,
response, parsed history, retained and committed chart records through the real
Page adapter and collection owner using an EventEmitter fake Page. It normalizes
host UUID/PID/start/receipt fields explicitly after collection; these fixture
values never describe a real browser or performance. Backend fixtures use real
probe entrypoints with fixed stamps and explicitly normalized process
identities. Separate tests feed guarded production tick/gate functions and
actual AnyIO worker events through the owner, collector and verified analyzer.

For frontend checks, first finish guarded derivation. Add temporary dependency
links only after source identity succeeds. Run the 18 focused tests for each
role using `PERF391_FRONTEND_ROOT` and `tests/frontend/vitest.config.mjs`. For
the 2,102 existing tests, change working directory to the effective frontend
root, set `PERF391_FRONTEND_ROOT="$PWD"` and `PERF391_DIAGNOSTIC_TEST_MODE=off`,
and invoke Vitest with the absolute `tests/frontend/regression.config.mjs` path.
The existing regression tests assert the primary request API; active diagnostic
request headers are covered by the separate focused tests. For TypeScript, use a
private configuration extending `tsconfig.app.json` with the diagnostic alias
`@perf391/browser-probe` pointing to this package's `browser-probe.ts`, preserve
the application's `@/*` path, and disable incremental output. Run
`tsc --noEmit -p PRIVATE_CONFIG`; the root solution has no source files and the
raw application config deliberately has no diagnostic alias.
Remove dependency links before rechecking complete source-tree identities.

The replay script calls the actual `run.py integrate` and `run.py analyze`
entrypoints for A and C and independently verifies resulting artifacts and
duration references. The CLI deliberately has no reviewed module inventory, so
its v1 chart projection remains unavailable; the API path supplies the pinned,
independently reproduced projection-module inventory. A valid sidecar commit
bracket alone does not establish valid chart contents or painted pixels.

## Future read-only Forge preflight

First obtain a separate runtime checkpoint. Review diagnostic Docker/build and
owner lifecycle wiring before running any image, server, browser or traffic. No
runnable application launcher is supplied by Stage 5; `run.py` remains an
offline importer/test runner. A launch recipe must be separately reviewed.

After authorization, record actor UID, executor, UTC, source/delivery manifest
hash, command owner and intended task project. Read the current cloud runtime
network policy and readiness through supported runtime tools if available; this
session had no `environment_status` tool or executor policy snapshot. Do not
infer credential/VPN readiness from their absence. Preserve proxy/CA,
credentials, `DOCKER_HOST` and the active context.

The executable inventory command below performs read-only Docker and local
filesystem/process inventory. It does not launch or download a browser, build
images, open an HTTP endpoint, alter ports or grant capture privileges. Do not
run it in the Stage 5 session. Set image variables to reviewed existing
immutable diagnostic image IDs; missing images correctly stop the inventory.

```sh
# Future separately authorized session only; supply existing reviewed values.
PERF391_NODE_ROOT=/reviewed/playwright-install \
PERF391_A_IMAGE=sha256:REVIEWED_A_IMAGE_ID \
PERF391_C_IMAGE=sha256:REVIEWED_C_IMAGE_ID \
timeout --kill-after=10s 90s ./forge-preflight.sh --inspect-runtime
```

If Docker configuration is absent, discover the actor socket at
`${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/docker.sock`; inspect explicitly with
`docker -H unix://PATH info`. Failure at `/var/run/docker.sock` does not
establish actor-daemon failure. Do not clear configuration, switch to root,
restart shared services or request host capabilities.

Before a short-run GO, require the following recorded evidence:

| Gate              | Required evidence and failure action                                                                                                                                                                                                                                                   |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Sources           | Exact A/C source, reviewed patch specs, effective whole-tree inventories, external diagnostic module closure, #407 source/release and frozen harness identities match the Stage 5 manifest. Drift stops preparation.                                                                   |
| Diagnostic builds | Separately reviewed opt-in build specs; exact image IDs/digests, seven required build-manifest labels, external modules and compiled JS/CSS maps. Stage 5 has no image/assets and its unbuilt schema cannot certify a built image. Extend/review the runtime manifest before building. |
| Isolation         | Task Compose project, private volumes and loopback ports, image/container IDs and all commands recorded before creation. Preserve shared services/configuration. Empty `ss` results are advisory until a task owner actually reserves ports.                                           |
| Host mapping      | Host and container PID namespaces, PID/TID start IDs, boot ID, cgroup v2 mount/path, CPU quota/cpuset/throttling and accessible counters mapped to each process. Inaccessible counters are null with a reason. No guessed cross-namespace PIDs.                                        |
| Browser           | Existing Playwright/package lock and Chromium binary hashes, package/API compatibility, owned Page/context/browser close contract, viewport/DPR/visibility and document-generation identities. Fake-Page disposal does not establish real Playwright support.                          |
| Observer          | Dedicated 1 Hz absolute deadlines, 2 s total request/body cap and bounded queues. The historical 1.5-second observer-cadence requirement is unchanged. Skips, failures and dropped events must remain visible.                                                                         |
| Transport         | Actual task-owned browser → production Nginx → backend topology and compression documented. No Nginx/compression/fetch changes or unbounded `response.body()` fallback. No raw-wire claims: Stage 3B remains deferred.                                                                 |
| Clock/source      | Process/thread/document/source restarts use new streams and start IDs; bracketed UTC anchors expose steps. Explicit request/parent joins only. Never subtract independent clock origins or treat unknown PoP/handover as an outage.                                                    |
| Shutdown          | Register handles and callbacks before startup; stop admissions, cancel/await observer and browser bindings, flush/finalize loss summaries and artifacts, close contexts, terminate/reap owned workers. Verify scoped cleanup on normal completion, timeout and interruption.           |

## Future short qualification sequence

The separate runtime review must approve concrete launcher commands, resource
budgets and exact diagnostic images/assets. Stop if any preflight gate fails; do
not substitute another transport or unreviewed image. Proposed bounded scope:
one A run and one C run, each at most 30 observer samples with a 90-second outer
deadline and 10-second forced-termination grace. Fixed samples exercise source
observation, one history request/response, retention and one actual plot commit;
they do not establish long-run boundedness or performance savings. Calibration,
benchmarks and soak need their own scope and are not part of this proposal.

For each role, record identities and clock anchors, validate source/stream/final
summary continuity, perform offline `integrate`/`analyze`, verify artifact
hashes and unique successful same-clock duration references, and report each
boundary independently. Real compositor snapshots, if separately approved and
supported, must retain hashed PNG bytes plus unchanged
document/generation/viewport brackets; they establish a sampled compositor
result only. Missing paint/raw-wire evidence must leave those claims
unavailable, even when the collection is complete.

Use exit/INT/TERM cleanup handlers. After a timeout, verify the previous owned
process tree is gone before retrying. Remove only the recorded project's
containers/networks/disposable volumes, then inspect project-label listings and
host PID/start/PGID/listener state through an approved host command. Preserve
acceptance artifacts and open-PR worktrees; remove private environments/exports
and dependency links. Report exact survivors if cleanup cannot finish.

Keep #403/#405/#406/#407/#408 draft and unmerged, #390/#391 open. An offline GO
does not change primary uninstrumented acceptance, the 1.5-second rule or the
need for a separate runtime authorization.
