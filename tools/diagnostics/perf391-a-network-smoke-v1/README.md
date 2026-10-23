# Original-A network-corrected smoke — failed browser finalization; STOP

Exactly **one original-A invocation**, executor exit 1; **zero C executions**.
No retry, functional-smoke pass, calibration or performance claim. Stop for
checkpoint review on draft #408.

Starting commit: `9d474bc2ac86989ac56f13299599266b5e5b3739`.
Authority: [latest orchestrator checkpoint](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6365234957).
Session: NEW — LOCAL FORGE, 2026-10-23. Evidence-only isolated worktree
`diag/perf391-a-network-smoke`, descended from origin/dev through the explicitly
requested starting commit. The primary checkout remains on dev.

The runtime failed with `RuntimeError: browser smoke failure`; retained browser
reason is `frontend final summary absent or changed`. The outer timeout did not
fire. Approved executor, launcher, application, collector and frozen tools were
unchanged. No image was built or pulled and no daemon configuration changed.

The approved network correction crossed the previously failing boundary:
bounded frontend GET readiness returned HTTP 200 with the exact receipt-bound
index hash on its first attempt, before browser-owner startup. Actual Chromium
startup, connection, context creation and Playwright disposable API checks ran.
The browser owner found a mounted, nonhidden committed panel `o6`, configured as
the only enabled network latency chart. Pixel visibility remains unqualified.

Both source and host collection completed five scheduled observations with none
skipped. Source wake gaps were 1.000572122, 0.999339971, 1.000705729 and
1.000427672 seconds. The unchanged **1.5-second observer-cadence gate passes**
for these observations. This does not make the smoke pass.

Exactly one screenshot bracket ran; it returned `unavailable: deadline` after
approximately two seconds. No screenshot image exists. The browser collection
closed with `complete: false`, browser `failed: true`, browser `lost: 1`, and
collection `dropped: 0`. These separate counters do not establish zero loss.
Source final summary is closed, completed 5, failed/cancelled false, skipped 0;
host final summary is complete, completed 5, skipped 0. Frontend final summary
and backend drain/export/final dropped counts are unavailable. Backend events
were not exported after the browser failure, so no backend/browser join or
complete producer/admission chain is claimed.

Two actual browser request IDs, HTTP 200 response events, parsed history payloads,
two `history.retained` events and two `plot.upload` events survive. For request
`synthetic-408a/p/b34655ed4a2b4e82/r1`, panel `o6`, the retained object `o8`
is associated with commit tokens `p/c24` (`create`) and `p/c25` (`setData`).
These are partial associations only: **zero actual `plot.commit` records and
zero retained/projection/plot snapshot sets were retained**. The requested
history response → retained/projection → actual uPlot commit evidence chain is
incomplete. The success-only integration analyzer was not run on failed streams.

[Outcome and counters](evidence/outcome.json),
[actual event joins with raw line references](evidence/actual-event-joins.json),
[observations and clocks](evidence/observations-and-clocks.json), and
[raw runtime evidence](evidence/runtime/runtime-result.json) retain the exact
limits of these findings. Source gaps use the Node monotonic domain only.
Host UTC/monotonic anchors, read brackets, source late times and browser clock IDs
are retained; no cross-clock duration is asserted. Raw wire bytes, physical
scanout and native parse-start remain unavailable.

Fresh preflight passed under its five-minute timeout/ten-second grace. The
approved three-layer comparator first regenerated the immutable original plan
byte for byte, then permitted only the four approved A/C base-network and
logging-override hash differences. All other fields remained equal. Both
rendered effective configurations matched the strict approved contract, including
non-internal default bridge, only default-network attachments, loopback-only host
publications, immutable images, resource limits and bounded logging. C was
regenerated and inspected offline only.

The private CPython 3.11.16 environment was recreated using six exact approved
wheel URLs and SHA-256 values, verified against installed wheel payloads and
functional validator/Registry/HashTrieMap operations. PYTHONPATH was unset and
user site packages disabled. Both closed receipts, all four original image IDs,
labels and RepoDigests, Stage 5 621-file release/97-file source closure, collector
source/release, frozen harness, application source/context, module/asset closure
and exact browser distribution verified. Node 22.22.2, Playwright/core 1.63.0 and
Chromium revision 1243 matched their approved executable hashes. Historical Node
22.12.0 remained unchanged. Exact identities are in
[preflight](evidence/preflight.json), [environment](evidence/environment.json),
[wheel inventory](evidence/wheels.json) and [host audit](evidence/preflight-host-audit.json).

Forge host PID visibility was verified with PID 1 `systemd`, actor UID 1002,
configured `unix:///run/user/1002/docker.sock`, context `default`, Docker 29.8.1
and rootless security options. Disk headroom was 24,505,659,392 bytes and memory
available 55,206,064,128 bytes. Ports were free before launch and the unchanged
executor repeated its bind checks. Approved CPU/memory/PID limits remain in the
launch and rendered Compose evidence. The managed environment-status tool and
network-policy snapshot were unavailable; no readiness is inferred from them.
Sandbox Docker denial was resolved through the approved host executor, preserving
actor socket/context configuration.

The two historical broader process tests remain **timed out at 120 seconds,
not passing**. They were not rerun. A fresh 15-second bounded host prerequisite
used the exact Owner implementation to register a task child, terminate it with
TERM, reap it and verify its process group absent. Exclusive subreaper capability
was verified. An independent host audit confirmed both prerequisite PID/start
identities absent, no prior scoped runtime resources/listeners, and no matching
old task processes or known scratch roots before A. Historical sandbox PID
identities were not misinterpreted as host PID identities.

The [execution intent](evidence/execution-intent.json) records the unchanged
executor/launcher hashes, exact launch plan, owner identity and timeout PID/group:
78-second work deadline, 90-second outer timeout, ten-second forced grace.
Setup recorded preliminary volume names incorrectly; the corrected
[runtime ownership](evidence/runtime-ownership.json) and authoritative unchanged
launcher intent identify the actual private `data`, `routes`, `metrics` volumes.
No preliminary names were used to create or delete resources.

After failure, Compose teardown and all 13 owner manifests were clean. The
approved read-only audit and independent host cleanup checked 40 PID/start
identities, task process groups, listener ports and A/C project labels. All scoped
containers, networks, disposable volumes, processes and listeners were absent.
Private environment, wheels/cache, Node executable, contexts, runtime scratch,
browser profile and empty lock were removed. A further independent host audit
confirmed absence after removal and all four image identities unchanged. See
[final host cleanup](evidence/final-host-cleanup.json),
[approved cleanup audit](evidence/runtime/cleanup-audit.json) and
[post-removal audit](evidence/final-host-audit.json). No runtime resources remain.
Only the open-review worktree and evidence remain.

Administrative failures are preserved: the first retention helper expected the
separately generated `cleanup-audit.json` too early and stopped before copying or
removing evidence. The approved audit was then run, followed by successful
retention/removal. The first offline summary serialization failed on a null
phase key; its label was corrected to source-body and summary generation passed.
Neither administrative correction launched services, browser traffic or A again.
Tool sessions: preflight 37995, A supervisor 65392, both completed. No expanded
regression suite or broader timeout-test rerun was performed.

Raw non-reproducible files were retained byte for byte. The
[runtime inventory](evidence/runtime-inventory.json) hashes every original runtime
file, including reproducible image-assets, collector export and seed omitted
from duplicate retention. Canonical source packages, exact seed command and
closed receipts preserve their identities. [Artifact manifest](artifact-manifest.json)
closes the new package and pins the source and predecessor evidence. `verify.py`
checks that closure, raw retention hashes, failure status, stream counters,
unchanged cadence policy and independent cleanup.

PRs #403/#405–#408 remain open/draft/unmerged; #404 is an open issue rather than
a PR. #390/#391 remain open. No production change, packet capture, image rebuild,
calibration, benchmark, sustained run, merge or deployment occurred. Remaining
blockers are browser finalization/loss and missing complete commit/backend evidence;
no cause or fix is asserted. **STOP for checkpoint review on #408.**
