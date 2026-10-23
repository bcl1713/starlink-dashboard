# Original-A functional smoke — stopped at fresh preflight

Starting commit: `ae3c8d28fa1e5263fe6d85b0e1a897d3ae339ee9`.
Authority: [approved orchestrator checkpoint](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6356577550).
Session: local Forge, 2026-10-23. **STOP for checkpoint review.**

Fresh preflight exited 1 at exact regenerated-build-plan equality, before any
runtime executor invocation. **A attempts: 0; C attempts: 0.** No application,
Prometheus, Nginx, browser, extraction container or screenshot was started.
No repair, repeated preflight, A retry or C launch followed the mismatch.
The approved 78-second work / 90-second outer / 10-second forced grace limits,
five scheduled 1 Hz source/host captures, one visible chart chain and maximum
one screenshot remain unexercised. The **1.5-second observer gate is unchanged**.

## Exact mismatch and its limits

[Plan differences](evidence/plan-differences.json) contains exactly two fields:
`roles.A.compose_sha256.override` and `roles.C.compose_sha256.override`.
Every other regenerated plan field matches, including source, patch,
diagnostic module and full context identities for both roles. C was regenerated
offline only; it was never launched.

The historical overlay files were restored in a private directory and individually
hash checked. However, changing `prepare.HERE` to those files does not reload
`prepare.compose()`; the active imported function still emits the approved
`compress: "false"` correction. Thus it produces new Compose override hashes
against the immutable pre-correction plan. This is a preflight regeneration
mismatch, not evidence of an application or telemetry runtime failure.
Neither plan nor receipt was rewritten and the preflight was not repaired.

[Logging comparison](evidence/logging-comparison.json) compares the generated
A/C service logging to the retained approved rendered configs: all six use
`local`, `compress: "false"`, `max-file: "1"`, `max-size: "10m"`.
Their canonical override hashes match the accepted correction. This comparison
was performed on retained/generated files after the stop; **no fresh Docker
Compose rendering or daemon logging validation was completed in this session**.
The prior accepted validation remains historical evidence.

## Confirmed checks and unavailable boundaries

[Fresh preflight](evidence/preflight.json) and [raw log](evidence/preflight.log)
retain the completed checks: both closed receipts, four image IDs and exact
labels, asset/module/dependency closures, 187-file retained build inventory,
621-file Stage 5 release and 97 source files, pinned collector and frozen
harness, original and corrected overlay inventories. Receipt and image bytes
are unchanged. Regeneration reproduced the original A source/context identity;
its plan failed only on the two Compose hashes above.

The same Forge actor (UID 1002) was verified outside the sandbox, with the
configured `default` rootless daemon at `unix:///run/user/1002/docker.sock`,
Docker 29.8.1, host `/proc` and cgroup v2 visibility. No sudo or identity change
was used. Ports 38080–38083 were free. Available disk was 24,508,923,904 bytes;
available host memory was 54,683,119,616 bytes. The shared ancestor quota was
10 CPUs; this is not an enforced private browser budget.

Preflight stopped before private Node extraction and fresh Node 22.22.2,
Playwright 1.63.0 and Chromium revision 1243 executable/distribution verification.
Historical receipt identities do not substitute for those uncompleted checks.
The reviewed launcher/executor and application, frozen harness, collector,
Nginx and diagnostic images were not modified.

**No runtime capability is newly confirmed.** Producer, worker, repository
admission, observer and browser event streams, final stream summaries,
request→history→retained/projection→actual uPlot commit joins, observation cadence
and dropped-event counts are unavailable because the runtime never started.
Missing instrumentation is not a measured runtime failure or a zero-loss result.
There are zero screenshot attempts. Raw-wire bytes, native Axios parse-start
and original-A final-authority/CAS/frame semantics remain unavailable by design.
See [stream status](evidence/stream-status.json). No performance or sustained
acceptance conclusion is drawn.

## Ownership, cleanup and delivery

The preflight adaptation changes only administrative task directory, starting
commit and authorization constants in the historical preflight script. The
read-only/regeneration command ran once under `timeout --kill-after=10s 180s`;
its host tool session was 8607. This was not the 90-second runtime command.
Ownership was recorded before creating `/tmp/perf391-a-functional-20261023`.
The generated plans/configs and failure log were retained before scratch removal.

[Independent host cleanup](evidence/final-host-cleanup.json) verifies the ended
preflight command PIDs, scans task path/worktree processes, checks ports
38080–38083 and 38180–38183, and confirms empty A/C project container, network
and volume listings. Runtime root and lock were never created. Recorded private
scratch was removed only after retaining evidence; all four image IDs, labels
and RepoDigests remain unchanged. No task runtime resources remain. Shared
runtime configuration, credentials and unrelated resources are preserved.

[Artifact manifest](artifact-manifest.json) closes this package and pins relevant
unchanged source/receipt/checkpoint files. `verify.py` independently rehashes the
package and external pins, checks exact closure, stop status, mismatch fields,
zero runtime attempts and cleanup. These are evidence-integrity checks, not
expanded regression tests. The open-PR worktree remains isolated; primary
checkout stays on `dev`. The explicit starting commit and existing PR destination
were honored rather than introducing a separate application branch or PR.

Publish to draft #408, then stop. PRs #403/#405/#406/#407/#408 remain draft,
open and unmerged; #404 is an open issue rather than a PR. #390/#391 remain open.
No packet capture, calibration, regression expansion, soak, merge, deployment,
issue closure, image build or application change occurred.
