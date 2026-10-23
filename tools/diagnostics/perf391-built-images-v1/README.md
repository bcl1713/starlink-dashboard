# #391 diagnostic image build receipts

Build-only qualification on local Forge, starting at
`f9cf80bd4fe7915863cf7e0ed5a6bc52616c377b`, under the
[orchestrator authorization](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6354971626).
**Build/receipt checks pass. Stop for review; runtime remains unauthorized.**
This directory adds evidence and task-local inspection helpers only. The
preparation package, Stage 5 instrumentation, original A/corrected C, #407
collector and frozen acceptance tooling are unchanged.

## Images and immutable receipts

| Diagnostic derivative | Actual Docker image ID / OCI index digest                                 | Inspected image size, bytes |
| --------------------- | ------------------------------------------------------------------------- | --------------------------: |
| A backend             | `sha256:8b8518fe1007170ce423b76f98958d85a4153927a0d8e59930d3790f38318abd` |               2,230,848,264 |
| A frontend            | `sha256:aee6d4fdf4a1c7746c8e4ba65458aa3160ffb8d1792982ba56a3e1cb1745dd88` |                 141,425,713 |
| C backend             | `sha256:91ba1d82f80d6d27afd7ed5cda4876be3a0e5ad9c7f5f5f156d32c8b0bbb3db9` |               2,231,188,809 |
| C frontend            | `sha256:05afd27ad94e61bad76ddde918be17b9b1702cdc724d51f98a584bc4b3c714ec` |                 141,425,713 |

Docker 29.8.1 with the actor containerd store returns the OCI index digest as
`image inspect .Id`. Each actual RepoDigest has the same digest, under the
`perf391-diag-408-<role>-<kind>` repository; these images were **not pushed to a
registry**. Config digests are distinct and retained separately in
[build-log-config-digests.json](evidence/build-log-config-digests.json). Image
inspection JSON includes config, RootFS layers, platform, tags and labels; build
metadata includes base materials and build references.

[Built A receipt](evidence/built-A.json) and
[built C receipt](evidence/built-C.json) validate against the unchanged closed
`perf391-runtime-receipt-v1` schema and its original semantic validator.
[Qualification results](evidence/qualification.json) bind their SHA-256 hashes,
assets, dependencies and actual image identities. All required immutable labels
match the plan, including `diagnostic=true`, role, base application, tested
instrumentation, patches, effective source, collector, harness and overlay. The
diagnostic tags and labels distinguish these derivatives from production.

- Original A: `25e34168f0e2cecb149b0323f1f5a795cb28cae0`.
- Corrected C: `ee9ce1010e72e83cb6d4b8c79ecc15091b9d8832`.
- Tested instrumentation: `051870c738d9ab72338852ea848918a35a663094`.
- Effective A application SHA-256:
  `015c5f515438b7114f903e90c5c43014a2b29fb6c316fdbca0232681585c5baa`.
- Effective C application SHA-256:
  `4f1913894101595ab96bdd289bd80f88a6dcb95c058d0851cb3e4e025ae13f4a`.

## Source and compiled closure

The Stage 5 release manifest hash is unchanged:
`1ff9bf12f578538b6a2fb8946395f88993f569b1ec9aeb3939d4f27284601200`. All **621
entries / 97 source entries**, the preparation checkpoint files, reviewed
patches, fresh context hashes, Dockerfiles and Compose configs verify. The
regenerated plan is byte-identical to the approved preparation plan.
[Before audit](evidence/source-verification-before.json) and
[after audit](evidence/source-environment-verification-after.json) retain
hashes.

Stopped-container extraction verified every copied application source/test file
(**826 per role**), all **11 diagnostic overlay files** (including all four
backend Python modules), and **49 frozen fixture/alias files per role** against
the generated contexts. The required factory command, PYTHONPATH and original
entrypoint are retained in actual image configs. No module was imported as an
application and no application process or healthcheck ran.

Each frontend has **29 assets**, including the Vite manifest and emitted module
graph. The validator confirms live runtime/probe, history hook, history service
and chart component modules, plus all referenced chunks/assets. A/C complete
frontend asset maps are byte-identical, SHA-256
`80ba558abe1930f4154c3fc1cc190a73596545db499be5b29e9c614d6b699d92`. Their
compiled module-closure hash is
`65d3242be697b31509335368702179041ea6a3a9c6e476e641425174c77011cf`. The four
mission-export renderer assets also match across A/C; their map hash is
`180c1bfe5541d57912086695ed42312f0f97a9bbe6b8f0ba4a74addbcfe8114b`. Actual
assets, per-file hashes, module inventories and Nginx config hashes are
retained, rather than inferred from the build recipe.

## Actual dependency identities

Both images expose Python **3.11.17** in the extracted image version header;
actual Python binary SHA-256 is
`92d7e40ec50be176cb1b790c7568b7e08cd862137b5aa69f1413ba1967886b79`. The
89-package appuser-visible inventory, reconstructed offline from installed
local/global dist-info metadata with pip canonical ordering, reproduces the
retained production JSON **byte for byte**, SHA-256
`03cf956e500c08952d7b1a1747f24e391f6d0c5cf32a675a93c55847c92e9a40`. No pip
process was executed in an application image. The receipt's
`python_freeze_sha256` hashes the separately named metadata-derived
`name==version` inventory; it is not represented as captured output of
`pip freeze`.

The approved base supplies exact **Node 22.22.2 / npm 10.9.7**. Its extracted
Node SHA-256 is
`81925c0995b5c1427b5d538e6a90ca2fdc4daffb786b09af749beaf7369d4e90`; host ELF
dependencies resolve. Each actual cached frontend/renderer build stage contains
**453 installed npm packages**, with package metadata versions and integrity
entries checked against the unchanged lockfile. Package inventory hash:
`c69bd8da14f9ecf09620bc3ef9f77133f2750a3fb1343d642e59099849648b16`. Application
lockfile SHA-256:
`ffff2faabc44900887409a91af375f098bcc9580d788df991d3c492848177482`. The
engine-strict frontend install passed; C reused the identical build stages.
Backend production dependency layers were cached and then independently
inspected. No lockfile edits or historical Python dependency drift occurred. TLS
verification stayed enabled; Forge had no injected proxy CA selector, and direct
trusted registry/package access succeeded without changing host trust or
credentials.

Actual Debian dpkg and frontend Alpine apk inventories are retained per role.
`os_packages_sha256` hashes the canonical JSON mapping of their two file hashes.
The browser tree hash uses the unchanged preparation helper. Playwright 1.63.0,
Chromium revision 1243 and its binary/tree hashes were inspected without launch.
The receipt's Node hash/version identifies the private 22.22.2 lane; it does not
claim historical browser benchmark equivalence. Shared Node 22.12.0, shared
frontend manifests and browser installation were unchanged.

## Checks, resources and cleanup

All four final builds exited 0; build logs, metadata, argv, wall deadlines,
PID/start/group ownership and client child resource usage are retained. The
original **10/10 offline preparation tests pass**. Both actual receipts,
compiled closures, required labels and config-only Compose renders pass.
[Retained-artifact verifier](verify-retained.py) can rerun these checks offline.
No broad repository lint or runtime/production acceptance pass is claimed.

Build wall durations were A backend **13.673 s**, A frontend **31.913 s**, C
backend **2.349 s**, C frontend **0.648 s**, with substantial shared cache
reuse. These are build accounting, not application performance measurements.
Each build had a **45-minute limit / 10-second forced grace**. The two cached
stage exports used 20.187/20.586 s and were removed after inventory extraction.
The configured Forge rootless actor daemon/context were preserved. The shared
ancestor quota is **10 CPUs**, not the 20 host-visible threads. The proposed 4
CPU / 8 GiB per-build planning budget was not enforced; no per-build daemon
CPU/RSS peak is claimed. Client accounting excludes daemon/BuildKit execution.
The scoped private root reached **5,003,687,922 bytes** at inspection; no
continuous peak sampler was used. Final retained image sizes are shown above,
share layers, and must not be summed as exclusive disk consumption. Shared
BuildKit cache accounting is retained as shared/global evidence, not attributed
wholly to this task.

The first helper qualification failed on an incorrect assumption that Docker's
metadata always includes `containerimage.config.digest`; inspection showed this
store exposes index IDs, and only the new task helper was corrected. Failure
output is retained. An attempted completed-build history lookup was unavailable;
its metadata reference is retained but no missing resource statistics invented.
Two bounded Black CLI runs timed out during process shutdown after formatting;
no formatter workers survived. Serial Black API checks and scoped Ruff checks
cover only the new helper files. A completed sandbox qualification wrapper also
remained in `ep_poll` after persisting success; the first cleanup audit
correctly failed. Its verified PID/start identity exited after SIGTERM, its
handle was reaped, and the final host audit passes. These are task-tooling
incidents, not application measurements; no application, frozen tooling or build
recipe changed.

[Cleanup evidence](evidence/cleanup.json) verifies **20 PID/start/namespace
identities**, no matching live processes, no scoped containers/networks/volumes,
and no task listeners. All extraction containers stayed in `created` state with
PID 0 and zero start time, then were removed. Temporary stage tags and the
private source/dependency/Node root `/tmp/perf391-build-408` were removed.
**Four final diagnostic images are retained on the actor daemon for receipt
review**, as pre-recorded in the ownership plan. Shared base images/cache,
services, credentials and runtime configuration were preserved. The open-PR
worktree and immutable evidence remain; the primary checkout is clean on `dev`.

## Remaining runtime prerequisites and stop

Separate review and explicit runtime authorization are still required. Before
any smoke, regenerate identical guarded contexts into a newly owned root, bind
the reviewed plan/receipt to those paths, recheck retained image/asset/browser
identities and verify actual browser launch/disposal,
sandbox/SwiftShader/pixels, container-to-host PID/cgroup mapping, real adapter
wiring, loss/final-drain gates, headroom and runtime cleanup. The absolute
`asset_root` paths in these receipts identify this retained Forge worktree. A
different checkout requires a separately reviewed path rebinding; do not
silently edit an immutable receipt.

No application containers/services, Playwright/browser launches, application
HTTP, packets, timing benchmarks, short A/C smoke, calibration or soak were run.
Raw-wire capture remains unavailable; Stage 3B is deferred. No Nginx changes,
elevated capture privileges or unbounded response-body fallback. Keep
#403/#405/#406/#407/#408 draft and unmerged, #390/#391 open, and the
**1.5-second observer-cadence requirement unchanged**. Stop after publishing
these receipts.
