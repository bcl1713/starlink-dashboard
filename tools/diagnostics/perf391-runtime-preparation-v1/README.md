# #391 runtime integration preparation

**Preparation checkpoint only. Runtime, image builds, calibration and sustained
qualification remain NO-GO.** This sibling package leaves the accepted Stage 5
package, production revisions, frozen v2 harness and #407 collector unchanged.
It supplies executable offline context/manifest validation and **proposed**
runtime adapters. Proposed files have only been parsed and reviewed; they have
not been imported as application entrypoints or executed against a browser.

The controlling
[orchestrator checkpoint](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6354250453)
authorizes this work. Keep #403/#405/#406/#407/#408 draft and unmerged, and
issues #390/#391 open. Preserve the **1.5-second observer-cadence rule**. No
deployment, production acceptance, performance comparison or sustained run
follows from these results.

## Reviewable artifacts

| File                                                            | Purpose                                                                                                                                                                                                          |
| --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `prepare.py`                                                    | Verify frozen delivery; export exact A/C; apply reviewed patches without fuzz; generate diagnostic build contexts, labels, module inventories and task Compose base/override. No Docker calls.                   |
| `frontend.Dockerfile`, `vite.perf391.mjs`, `browser-runtime.ts` | Opt-in compiled frontend design, diagnostic alias and explicit owner admission-close control.                                                                                                                    |
| `runtime_backend.proposed.py`                                   | Synthetic fixture, original lifecycle, Stage 2 probes and guarded state wrapper. Copied as `runtime_backend.py` only inside generated diagnostic contexts.                                                       |
| `browser-owner.proposed.mjs`                                    | Actual Playwright launchServer/connect and Page attachment proposal, bounded settings/activation, first chart evidence slice, sampled compositor capture and disposal.                                           |
| `launcher.py`                                                   | Offline argv/ownership/schedule compiler. `--execute` deliberately rejects before reading a plan.                                                                                                                |
| `execute.proposed.py`                                           | Future executor proposal with exact receipt checks, process owners, host observation, startup and teardown. Requires a separately approved checkpoint reference and explicit `--execute`. **Not executed here.** |
| `runtime-receipt-schema.json`                                   | Closed built-receipt contract, separate from the frozen unbuilt schema.                                                                                                                                          |
| `analyze-runtime.py`                                            | Offline importer using the existing `Integration` API with reviewed projection modules; validates owner/receipt/cleanup and successful history-to-chart joins.                                                   |
| `audit.py`                                                      | Read-only host cleanup audit; no signals/deletions.                                                                                                                                                              |
| `evidence/`                                                     | Actual Forge inventory, registry metadata, generated configurations, offline validation, review and cleanup records.                                                                                             |

## Immutable inputs and identities

| Input                                         | Exact identity                                                                          |
| --------------------------------------------- | --------------------------------------------------------------------------------------- |
| Starting delivery                             | `cd734117cb5580ef2579145c99d1cc30aeae9451`                                              |
| Tested Stage 5 source / instrumentation label | `051870c738d9ab72338852ea848918a35a663094`                                              |
| Original A                                    | `25e34168f0e2cecb149b0323f1f5a795cb28cae0`                                              |
| Corrected C                                   | `ee9ce1010e72e83cb6d4b8c79ecc15091b9d8832`                                              |
| C implementation reference                    | `3cd79e2ac77557b7ef0ba7bc8bf60069bd260bbc`                                              |
| Collector source / release                    | `a48837b99d87366c6e3fc24ba2915f0b739cddad` / `c47d21e3c5bbf92189afbf291b73b9da7a035a4b` |
| Frozen harness                                | `f3029024b5950a267645195476da5cbca326f16a`                                              |
| Stage 5 manifest SHA-256                      | `1ff9bf12f578538b6a2fb8946395f88993f569b1ec9aeb3939d4f27284601200`                      |
| Effective A application SHA-256               | `015c5f515438b7114f903e90c5c43014a2b29fb6c316fdbca0232681585c5baa`                      |
| Effective C application SHA-256               | `4f1913894101595ab96bdd289bd80f88a6dcb95c058d0851cb3e4e025ae13f4a`                      |
| A backend patch SHA-256                       | `c45588f73582531dda971e359ff368d5843cc924cd24e3a5a233be3baaf9f43c`                      |
| C backend patch SHA-256                       | `b0886cc70df5811670f43e455cd8917b641d42a09c320bb378cb5df85be26c3c`                      |
| Shared frontend patch SHA-256                 | `e744be0f260e77799d55c6c4f9f23e8a65d9fd793e9eb164c13a21f156e44551`                      |
| Effective frontend tree SHA-256               | `1127ba9fd2b5febb1626c6889ca69963c07db5863a0e29f68c2550fa456476cb`                      |
| npm lock SHA-256                              | `ffff2faabc44900887409a91af375f098bcc9580d788df991d3c492848177482`                      |
| Python requirements SHA-256                   | `bf0b6ee7901e0af37ad53870c44607ca67a9df1cc7b1157e7c5168bfe1e47e73`                      |

`evidence/runtime-build-plan.json` records every generated overlay file/hash,
whole-context identity, external diagnostic module hash, projection module hash,
TypeScript configuration, required label and Compose hash. Its `overlay_sha256`
also binds the launcher, executor, analysis and audit code. The separate
`runtime_frontend_closure_sha256` binds the frontend tree, original
probe/config, new alias, Vite/TypeScript overlays and builder recipe. The frozen
frontend closure identity remains separately recorded; the new alias is not
silently included in its historical value.

Application hashes exclude external overlays by design. Context hashes include
them. No source or image is taken from a mutable A/C worktree. Stage 5
verification still covers **621 files and 97 source-closure entries**, with
executable modules, configs and patches additionally compared with the tested
Git object.

## Diagnostic build configuration

All builds target **linux/amd64**. Read-only registry index metadata is
retained; platform-specific children select Python and Node exactly. Existing
local RepoDigest identities pin Nginx and Prometheus.

| Base                                                     | Selected digest                                                           |
| -------------------------------------------------------- | ------------------------------------------------------------------------- |
| `python:3.11-slim-trixie` (3.11.17 in registry metadata) | `sha256:b95327ce1439e687237841b0210677aeadd62d55a060a5f6bcb9c15bf6251dd3` |
| `node:22.22.2-trixie-slim`                               | `sha256:961a65354946a04bbf2bfb3a1b25b53638a0e1fdb07ff56689955b9788400903` |
| `nginx:alpine`                                           | `sha256:892bb2152464f0c5d8972593a5f5afaf8054552580b699d95f8ff4af08c2d33d` |
| `prom/prometheus:v3.5.0`                                 | `sha256:63805ebb8d2b3920190daf1cb14a60871b16fd38bed42b857a3182bc621f4996` |

The generated backend Dockerfile preserves the production recipe and entrypoint,
substitutes pinned FROM references, appends diagnostic/frozen fixture copies and
labels, creates `/app/data/perf391`, and selects one Uvicorn factory worker. The
original synthetic fixture supplies fictional missions, route and journal. The
original application startup/tick/shutdown lifecycle still runs. The probe is
configured before fixture/application imports. No worker pool is replaced.

The frontend uses `npm ci --engine-strict`, the original Vite plugins and `@`
alias, and an extending TypeScript no-emit config.
`VITE_PERF391_DIAGNOSTIC=true` is compiled in; history polling remains one
second. The exact diagnostic alias is
**`@perf391/browser-probe -> /diagnostic/browser-runtime.ts`**, which imports
the unchanged `/diagnostic/browser-probe.ts` and reexports its instance. The
alias only adds a private owner control that refuses to close pending/lost work.
It adds no customer display or planning acknowledgement.

Vite emits `.vite/manifest.json` and `perf391-module-closure.json`: each output
chunk's rendered module IDs/lengths/exports, plus the resolved static/dynamic
module graph. At build time the plugin rejects a missing live probe, runtime
alias, history service/hook or chart component. Paths normalize to stable
frontend/diagnostic roots. The complete source frontend inventory and npm lock
identify helpers, CSS, uPlot and dependencies; generated chunk references and
CSS/assets must close over the Vite manifest.

Future extraction hashes **every** file under `/usr/share/nginx/html`, including
HTML, JS, CSS, public assets and both manifests. The built receipt rejects extra
files, symlinks, absent chunks and changed bytes. A stopped, task-owned frontend
container supplies a second direct filesystem comparison before startup. Both
roles should compile identical frontend bytes from the same builder inputs;
image labels/IDs differ by role. Compare the A/C asset maps after the builds.

Required image labels include the original seven: `diagnostic=true`,
`org.opencontainers.image.revision`, `base_application_sha`,
`integration_source_sha`, `collector_source_sha`, `patch_sha256`, and
`effective_source_sha256`. Extra labels pin the frontend patch, collector
release, frozen harness, runtime overlay/closure and role. `patch_sha256`
retains its reviewed **backend patch** meaning. Actual image IDs, RepoDigests
(which may be empty for local images), RootFS/config provenance, dependency
inventories and compiled file hashes belong to a separately verified built
receipt. **None exist yet. `image_ids` and `compiled_assets` are null.**
Synthetic receipt test fixtures do not certify images.

Base digests and locked npm inputs do not make the existing pip/apt recipe
hermetic: transitive Python/OS downloads and the backend renderer's installed
Chromium remain future build results. Retain installed metadata/file inventories
and compare dependency hashes across A/C. Any difference stops the cohort; no
cross-build equivalence is inferred. Python 3.11.17 versus the offline test
interpreter 3.11.16 is a declared runtime feasibility gate.

## Compose, endpoint and adapter wiring

Use only the generated private Compose base plus override. Never include the
operator stack's production Compose file, shared volumes, privileged mode, host
networking, Docker socket mounts, capability grants or restart policies. The
private default network is `internal: true`; only explicit loopback publications
are reachable from the host. No network/compression policy is changed on Forge.

| Role/project              | Frontend          | Backend/state     | Prometheus        | Browser WebSocket |
| ------------------------- | ----------------- | ----------------- | ----------------- | ----------------- |
| A / `perf391-smoke-408-a` | `127.0.0.1:38080` | `127.0.0.1:38081` | `127.0.0.1:38082` | `127.0.0.1:38083` |
| C / `perf391-smoke-408-c` | `127.0.0.1:38180` | `127.0.0.1:38181` | `127.0.0.1:38182` | `127.0.0.1:38183` |

Ports were absent from the read-only host inventory; they are **not reserved**.
The proposed executor obtains a task lock and checks all four binds before
startup. A later bind collision fails the run; it never chooses another port or
stops its current owner. Existing Forge services on 18000/18080/19090 and other
ports remain untouched. The actor's rootless daemon, host namespace and future
container namespace are distinct observations; no capture interface or host PID
mapping is assumed from port publication.

The observer alone calls `http://127.0.0.1:BACKEND_PORT/api/_diagnostic/state`,
with `x-diagnostic-id: synthetic-408a/source/N` (or C). Startup requires
explicit `PERF_SYNTHETIC=1`, the fixed synthetic run, role and simulation mode.
The wrapper rejects missing/duplicate/wrong state IDs and non-GET requests. Its
capture callable is the frozen v2 `performance.state.capture` under the existing
repository gate. Production has no such endpoint. History requests travel from
the browser through unchanged Nginx to the backend, carrying their own explicit
diagnostic IDs. Observer bytes are its own bounded decoded state response, never
raw browser-history bytes.

Stage 2 records stay in an 8192-entry bounded in-memory probe. Final application
shutdown and state-worker drain precede serialization into the private data
volume; `compose cp` retrieves it after the backend stops. Nothing drains or
serializes under the application mutex. A's legacy in-place semantics remain
legacy: frame/final authority/CAS are unavailable. C retains its final source
check, frame swap/CAS, replay ordering and captured-head protection.

The Python `Owner` registers command/PID/PGID/start identities before/after each
spawn and acts as an exclusive child subreaper. Separate verification/runtime/
cleanup owners retain the unchanged 16-child bound. Container IDs are mapped
through selected-daemon inspection to host `/proc` start IDs, NSpid/status,
namespace and cgroup-v2 paths. Missing mappings stop admission; individual
inaccessible counters retain null/reason. Stage 4 `host.observe_resources` and
the pinned #407 adapter retain five 1 Hz resource snapshots and bracketed UTC
anchors. No raw subtraction across host, worker, Node or document clocks.

`analyze-runtime.py` uses the existing `Evidence` and `Integration` APIs and the
pinned collector, supplying the verified projection module hashes. The frozen
CLI intentionally lacks that module inventory and cannot certify the same chart
projection. The new importer verifies summaries/artifact hashes, unchanged
1.5-second wake cadence, mandatory producer/browser phases, owner/receipt/run
continuity, clean cleanup and at least one explicit joined history-to-chart
request. It does not turn an absent boundary into success.

## Real browser and compositor ownership

Use the **receipt's reviewed installation**, not the feature worktree's absent
node_modules. Verify the actual Node and Chromium hashes and the complete
Playwright/Chromium distribution tree. Playwright must be 1.63.0; Node must be
22.x at or above 22.22.2. The proposed owner launches one private Chromium
`BrowserServer`, records its PID/PGID/start/profile before connecting with
`chromium.connect(server.wsEndpoint())`, then creates one context and Page. It
never attaches to a shared browser. Bind the WebSocket listener to loopback.

Before navigation it checks actual disposable binding/init-script handles and
attaches `createCollection(...).browser(page, {pageId:'p', origin})`. Stage 3A
installs a fresh document nonce before app modules execute. Each navigation has
a new document stream and clock; this smoke requires exactly one document. The
request ID carries run/page/document/counter. Playwright Request object identity
links response/finished/failed events; parsed-history and retained object
association comes from the existing WeakMaps and accepted-request tokens. Never
join by equal data, approximate timestamps, request order or URL alone.

Before navigation, three bounded ordinary synthetic operations select the
1800-second history window, one visible latency panel and the frozen fictional
mission/leg activation. Each Node HTTP request has a two-second total cap, 16
KiB headers, 64 KiB response cap and no keepalive; response bytes are discarded
and are not body evidence. No browser routing, mocked responses or transport
interception is used. Existing external map asset requests are outside this
qualification; unavailable map tiles cannot establish network telemetry loss.

Capture the first committed latency chart and attempt **one** compositor PNG.
Then wait at most two seconds for frontend and adapter queues to drain, close
frontend admission through the new alias, retain before/after final sequence
summaries, detach the observer and close the context. The five-sample source
observer finishes independently. Continuous five-panel/30-second evidence would
overflow the immutable 64-artifact owner limit; this explicitly bounded slice is
not continuous browser coverage. Extra commits, resizing, slow capture or
artifact growth still fail closed rather than widening that limit.

The screenshot belongs to the same collection owner and budget as browser
records. Its pre/post document, panel generation/commit, accepted/retained
tokens, viewport, DPR=1, visibility and rectangle must agree. Retain hashed PNG
bytes and both brackets. Effective persisted-artifact limit is **2 MiB** even
though the browser adapter's PNG allocation cap is 8 MiB. An oversized PNG may
fail the collection; no truncation or reduced-quality retry. A stable screenshot
establishes a sampled compositor result only, not physical scanout or exact
paint time. An unstable/missing screenshot stays unavailable. Real disposal,
pixels and screenshot timing remain untested.

## Read-only Forge findings

Actual command outputs, binary hashes and UTC are in
`evidence/forge-preflight.json`; registry reads are in `evidence/base-*.json`.
No application connections were opened. `ldd` inspected an existing ELF; the
Chromium executable itself was never invoked, including with `--version`.

| Check            | Finding                                                                                                                                                                                                                                                                                                                                       |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Actor Docker     | UID 1002, inherited `DOCKER_HOST=unix:///run/user/1002/docker.sock`; default context preserved; Docker 29.8.1, overlayfs, rootless, systemd, cgroup v2; Compose 5.5.1. Sandbox socket denial does not describe host daemon health.                                                                                                            |
| CPU/memory       | 20 visible CPUs, 65,915,523,072 bytes reported by daemon. Session cpu.max is unlimited; ancestor user-1002.slice quota is **10 CPUs** (`1000000 100000`). Effective ancestor cpuset is 0–19. No finite observed memory.max. These are limits/inventory, not capacity or performance measurements.                                             |
| Host visibility  | Host `/proc/1/stat`, host PID/net/mount/time/cgroup namespace links and actor process inventory readable through approved host commands. No future container PID/TID/cgroup mapping exists yet. Missing per-session cpuset files are recorded unavailable.                                                                                    |
| Node             | Installed host Node **22.12.0**, SHA-256 recorded; below declared engine floor. Future supported Node extraction/installation and rehash are mandatory.                                                                                                                                                                                       |
| Python           | Default 3.14.4; existing explicit CPython **3.11.16** usable. Its bare installation lacks jsonschema; offline checks can use the existing cached dependency installation. A future reviewed private environment is required for analysis.                                                                                                     |
| Browser          | Playwright **1.63.0**; registry Chromium revision **1243**, declared 153.0.8010.12; executable exists, SHA-256 `8c599d43aec53f2460a31ae2f4af6bd863f8258b34ff519564bc5d4726bfaa1e`; ldd found no missing libraries. Installed types declare Disposable handles for both APIs. This does not prove launch, sandbox or screenshot compatibility. |
| Topology         | Host loopback plus 10.10.50.30 and 10.10.40.30 networks, existing root-owned Docker bridges and services. Selected rootless daemon had no running containers. Proposed ports clear at inventory time. No tap/interface suitability inferred.                                                                                                  |
| Capture          | Actor has no effective/ambient capabilities. tcpdump is root-owned, non-setuid, with no file capabilities. No capture attempt or permission grant. Rootless containers do not grant access to host-loopback packets.                                                                                                                          |
| Policy/readiness | No environment_status tool or `/etc/codex/network-policy.json` snapshot. Credential/VPN/egress readiness not established; inherited authentication/proxy/CA selectors preserved. Read-only Git and registry metadata operations succeeded.                                                                                                    |

## Evidence availability and limitations

| Claim                                                             | Now                         | Future five-sample smoke gate                                                                                                    |
| ----------------------------------------------------------------- | --------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Guarded A/C sources, patches, module/config identities            | Verified offline            | Rehash before build, execution and analysis                                                                                      |
| Images, installed build dependencies, compiled assets             | Unavailable/unbuilt         | Build separately; extract bytes, retain inventories and closed receipts                                                          |
| Producer/admission/worker and C authority/CAS                     | Offline contracts qualified | Required phases, source continuity, zero loss and final drain; A's unavailable semantics unchanged                               |
| State source observer                                             | Offline only                | Five successful 1 Hz absolute-deadline samples; two-second request/body cap; no skipped deadline; unchanged 1.5-second wake rule |
| Browser request → parsed → retained → actual plot input           | Offline only                | Real Page, one document, successful explicit same-request joins, modules/assets and final summaries verified                     |
| Sampled compositor PNG                                            | Unavailable                 | One stable owned bracket/PNG may qualify; missing/unstable remains unavailable                                                   |
| Physical scanout, parse-start, cross-clock one-way latency        | Unavailable                 | Remain unavailable                                                                                                               |
| Host counters and process/cgroup ownership                        | Host feasibility only       | Map actual task processes, retain accessible counters, null/reason for unavailable categories                                    |
| Raw browser response body / passive wire provenance               | **Unavailable**             | **Remain unavailable. Stage 3B deferred.**                                                                                       |
| Probe overhead, savings, long-run behavior, production acceptance | Unqualified                 | Outside this smoke; no claims or extrapolation                                                                                   |

Missing capture permissions eliminate passive raw-body evidence at the proposed
HTTP tap. Browser response metadata and parsed-history snapshots do not recover
encoded bytes, compression, transfer framing or raw provenance. Do not call
Playwright `response.body()`, `response.text()`, CDP Network.getResponseBody or
another unbounded response API as a substitute. A bounded direct observer body
is a different request and cannot certify the browser's response. No TLS/H2/
unsupported-encoding fallback, broad/root capture, Nginx compression change,
packet tool installation or capability request is proposed. Any alternative
adapter needs its own bounded design and approval.

Use the [runbook](RUNBOOK.md) for offline checks, exact future build/launch
commands, the A/C schedule, budgets, hard stops and cleanup.
