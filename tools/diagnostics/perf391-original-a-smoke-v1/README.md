# Original-A runtime smoke: preflight STOP

Starting commit: `68f3f644beef98cd8412e8a354c8621540660739`.
Authorization: [latest orchestrator checkpoint](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6355361655).

**No smoke was attempted.** Fresh preflight found incompatible browser identity
requirements. The checkpoint specifies browser Node 22.12.0; Forge's historical
Node is exactly 22.12.0, SHA-256
`177208bfc4a9403121a40c72d038c670f4fd937fa16ca7df0a720e90be0fe2d9`.
Both accepted closed receipts instead bind Node 22.22.2, SHA-256
`81925c0995b5c1427b5d538e6a90ca2fdc4daffb786b09af749beaf7369d4e90`.
The immutable proposed executor requires the supplied executable to match that
receipt hash and version. The launcher also applies the app Node engine floor
to the browser identity: substituting the historical browser identity in either
receipt deterministically fails with `Node engine floor`.

This is a launch-blocking contract inconsistency. Review must reconcile the
separate browser and app/build lanes, then qualify any revised owner/receipt
contract. No receipt, launcher, executor, image or reviewed overlay was changed;
the build Node was not substituted for the authorized historical browser Node.

## Confirmed checks

- Read AGENTS.md and the latest #408 orchestrator checkpoint. Work is isolated
  on `diag/perf391-original-a-smoke` at the requested starting commit; primary
  checkout remains on dev. Existing #408 head is the publication destination.
- Fresh offline verification: 621-file Stage 5 release, unchanged runtime
  overlay, 187-file built-image manifest, both closed receipts, all retained
  frontend asset bytes and live compiled module closure.
- Read-only Forge host inspection: existing default actor Docker daemon,
  all four exact retained image IDs and labels match receipts. No image started.
- Both historical-browser receipt substitutions fail deterministically.
- Host evidence retains Docker capacity, memory, disk, cgroup and listener
  inventory. These observations do not certify full runtime headroom or mapping.

## Unavailable and unexecuted

Executor missing-image, bad-receipt, startup-error, SIGTERM and scoped-cleanup
qualification was not performed: the required identity gate failed first.
No context regeneration, stopped-container extraction, browser launch, app HTTP,
producer/worker/admission runtime join, five-sample observation, history-to-plot
join, screenshot, loss/final-summary runtime validation or timing qualification
is claimed. Receipt validation and manifest verification use retained files;
fresh daemon extraction remains unqualified. Raw-wire provenance remains
unavailable (Stage 3B deferred); original A final-authority/frame/CAS remain
unavailable by design. Runtime collection completeness is unavailable because
there was no runtime collection.

The 78-second work / 90-second outer / 10-second grace and 1.5-second observer
rules remain unchanged. There were zero A attempts, zero C attempts and zero
screenshot attempts. No benchmark, calibration, soak, merge or deployment.

## Evidence and cleanup

`evidence/offline-preflight.json` records receipt/image/Node identities and
deterministic rejection. `evidence/host-preflight.json` records actual host
commands/results and empty A/C smoke container/network/volume listings and A
ports 38080–38083. No task runtime root, lock, process owner, worker, service,
browser, listener, container, network or disposable volume was created. All
read-only inventory subprocesses returned synchronously. Retained diagnostic
images and existing services/configuration/credentials are preserved.

Checks used `timeout --kill-after=10s 60s`; both final evidence scripts exited 0.
An initial offline evidence invocation used the wrong retained plan path and
exited before writing evidence; corrected to the built-image evidence path and
ran once successfully. Initial sandbox Docker/SSH access failures were resolved
using approved host execution; no daemon or SSH configuration changed.

`artifact-manifest.json` hashes every report/helper/evidence file except itself;
the delivery commit anchors that manifest. Stop for orchestrator review.
