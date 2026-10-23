# Stage 5 offline release qualification

**Offline qualification complete; runtime qualification remains unauthorized.**
Starting delivery: `9f50189ed4ad067e49135b2325bae754f3539d23`. Final tested
source: `051870c738d9ab72338852ea848918a35a663094`. The delivery adds reporting,
immutable inventories and runbook formatting only. Authorization is the
[latest orchestrator checkpoint](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6353772496).

## Exact identities and preservation

| Input                                   | Identity                                                           |
| --------------------------------------- | ------------------------------------------------------------------ |
| Original A                              | `25e34168f0e2cecb149b0323f1f5a795cb28cae0`                         |
| Corrected C application                 | `ee9ce1010e72e83cb6d4b8c79ecc15091b9d8832`                         |
| C implementation reference              | `3cd79e2ac77557b7ef0ba7bc8bf60069bd260bbc`                         |
| #407 executable collector source        | `a48837b99d87366c6e3fc24ba2915f0b739cddad`                         |
| #407 release                            | `c47d21e3c5bbf92189afbf291b73b9da7a035a4b`                         |
| Frozen acceptance harness               | `f3029024b5950a267645195476da5cbca326f16a`                         |
| Effective guarded A application SHA-256 | `015c5f515438b7114f903e90c5c43014a2b29fb6c316fdbca0232681585c5baa` |
| Effective guarded C application SHA-256 | `4f1913894101595ab96bdd289bd80f88a6dcb95c058d0851cb3e4e025ae13f4a` |
| Backend A patch SHA-256                 | `c45588f73582531dda971e359ff368d5843cc924cd24e3a5a233be3baaf9f43c` |
| Backend C patch SHA-256                 | `b0886cc70df5811670f43e455cd8917b641d42a09c320bb378cb5df85be26c3c` |
| Identical frontend A/C patch SHA-256    | `e744be0f260e77799d55c6c4f9f23e8a65d9fd793e9eb164c13a21f156e44551` |

Fresh owned Git exports passed exact archive/file/mode verification, reviewed
preimage/postimage and whole-tree patch guards, identical A/C frontend checks, C
implementation/final runtime equivalence and pinned collector-release/harness
verification. Complete source and effective inventories are retained under
[evidence/stage5](evidence/stage5/source-identity.json) and
[derivative identity](evidence/stage5/derivative-identity.json). All production
application, Docker/Nginx/network configuration, patch specs, #407 and frozen
acceptance-tool bytes remain unchanged. Only separately versioned integration
verifier/importer and qualification tooling changed. No images or compiled
assets were produced; their runtime identities remain unavailable.

## Qualification results

- **120/120 Python tests**, 62.874 seconds, at the final tested source;
  exclusive owner clean, no adopted survivors.
  [Tests](evidence/stage5/release-tests-tests.log),
  [owner](evidence/stage5/release-tests-owner.json).
- **34/34 Node tests**, using fake Pages and fixed streams. No browser launch.
  [Node coverage and results](evidence/stage5/node.log).
- **18/18 active diagnostic frontend tests per role**, plus **2,102/2,102
  existing frontend regressions** with instrumentation off, 308 files, 99.79
  seconds. [A](evidence/stage5/frontend-A.log),
  [C](evidence/stage5/frontend-C.log),
  [regressions](evidence/stage5/frontend-regression-off.log).
- Immutable #407 dependency: **28/28 Python** and **7/7 fake-Page Node** tests.
  [Python](evidence/stage5/collector-python.log),
  [Node](evidence/stage5/collector-node.log).
- Scoped Ruff, synchronous Black, Prettier, Bash syntax, Node syntax and opt-in
  diagnostic TypeScript no-emit checks pass. A broad Ruff scan has **173
  existing findings in 17 unchanged files**; byte identity to Stage 4 is
  recorded in
  [the existing-debt inventory](evidence/stage5/ruff-existing-debt.json).

The complete fixed backend producer/admission/worker stream passes through the
real owner, bounded sink, pinned #407 Recorder, integration analyzer, #407
supplemental analyzer and independent schema/artifact/duration verification.
Separate tests pass actual guarded A/C tick/gate functions and actual AnyIO
worker events through this pipeline. Fixed request/response records pass through
the real Stage 3A Page adapter and collection owner, persisted parsed history,
retained/projection/actual chart snapshots, owner import and analyzer.

Both roles also pass the actual `run.py integrate` and `run.py analyze` process
entrypoints, followed by independent artifact and report verification.
[Full retained pipeline](evidence/stage5/pipeline/results.json) includes owners,
event streams, v1 records, reports, body artifacts and exact #407 source
exports. API chart projection uses the independently reproduced, reviewed
projection module inventory. The CLI has no such module inventory and
deliberately leaves v1 chart projection unavailable. A complete sidecar commit
bracket alone cannot certify chart contents.

Missing/interior records, duplicate identities, backwards clocks, source/process
restarts, partial bodies/snapshots, dropped events, queue/disk limits, absent
summaries, cleanup callback failures and signal interruption are tested.
Invalid/lost evidence never yields a verified complete duration. New streams
prevent cross-restart pairing; UTC steps preserve explicit ID joins while
invalidating approximate time alignment. Independent process clocks are never
subtracted. Resource cleanup status and evidence qualification status remain
separate: a cleanly closed failed collection is still failed evidence.

Synthetic paint and raw-wire omissions cannot produce an artificial PASS: the
positive fixtures have no presentation capture or raw body provenance, v1 chart
paint/visible-gap fields remain null, and the pinned supplemental analyzer emits
`acceptance: not_evaluated`, chart `classification: unknown`, with paint
explicitly unavailable. Hashed artificial PNG adapter tests establish only byte
retention and a same-clock capture bracket, never real painted pixels.

## Independent review and resolutions

An independent read-only reviewer rechecked all ten Stage 4 Important findings.
Eight fixes were confirmed; two residual defects were reproduced and fixed:
snapshot integrity/retention could be skipped when chart capabilities were
unavailable, and the duration verifier could join two distinct plot tokens.
Three focused regressions failed before the fixes and passed afterward.

The same independent reviewer inspected Stage 5 source and found one Important
termination defect in the new replay runner. Its SIGTERM regression reproduced
an escaped separate-session child; TERM/INT cancellation now enters the owner
cleanup path, reaps that child and returns nonzero. The regression and full
120-test suite pass. Preflight verification was also strengthened to reject an
unexpected source file after a failing regression.

[Review disposition](evidence/stage5/review.json),
[original failing regressions](evidence/stage5/red-review.log),
[signal failure](evidence/stage5/signal-red-tests.log),
[signal fix](evidence/stage5/signal-green-tests.log). No unresolved Critical or
Important source finding is deferred. The review is read-only; tests were
executed by the implementer. Runtime topics explicitly declined by review remain
unqualified.

## Coverage, boundaries and remaining risk

Python coverage is **82.62% combined statement/branch**, **84.97% statements**
and **74.90% branches**, including the parent CLI module at 33%. Owned
subprocess CLI entrypoints execute separately and are not included in that
parent coverage. No coverage claim is made for the entire pinned application.
[Full coverage and uncovered lines](evidence/stage5/coverage.txt).

Node production-module line/branch coverage remains browser **96.99/89.25%**,
observer **93.92/79.78%**, collection **85.54/66.07%**. The 96.21/87.71% Node
aggregate includes tests. Uncovered paths include collector finalization and
write failures, stream/body/path limits, host visibility failures, owner
identity/signal races, malformed input branches and CLI orchestration. Selected
deterministic failures are covered, not every OS failure ordering.

| Boundary              | Offline evidence                                                                          | Unavailable claims                                                    |
| --------------------- | ----------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Producer/publication  | A in-place; C final-authority/CAS and fixed success count; guarded real tick pipeline     | A coherent frame/final authority/CAS; runtime equivalence/overhead    |
| Admission/workers     | Real gate, selected AnyIO queue/execution/delivery, explicit parents and cancellation     | Arbitrary server worker coverage                                      |
| Browser history/chart | Fake request/response, parsed history, retained/projection/actual input hashes and commit | Native Axios parse start, live browser behavior, physical acquisition |
| Observer/host         | Fixed 1 Hz deadline/body-timeout, identity/cgroup/counter/UTC-step fixtures               | Actual Forge PID/container/cgroup topology and inaccessible counters  |
| Paint                 | Hash/retention/capture-bracket adapter fixtures                                           | Actual pixels, continuous presentation, physical scanout              |
| Raw transport         | Explicit omission                                                                         | Raw browser wire-body provenance; Stage 3B deferred                   |
| Timing                | Unique successful same-clock pairs and explicit ID joins                                  | One-way cross-process latency, additive CPU savings                   |

[Machine-readable available/unavailable matrix](evidence/stage5/instrumentation-matrix.json)
distinguishes the positive replay fixture from separately exercised
observer/host adapters. Instrumented source is not an uninstrumented A/C
performance equivalent. Build/image/asset integration, actual Playwright API
compatibility, live request provenance, host mapping, real pixels, probe
overhead, calibration, representative performance and sustained resource
boundedness remain uncovered. Offline GO does not satisfy #390/#391 production
acceptance or change its cadence gate.

## Release, cleanup and checkpoint

[The immutable release manifest](evidence/stage5/release-manifest.json) pins
full source references, source/module/schema/patch and fixture hashes, external
dependency inventories, all retained package evidence and the offline signoff.
Its SHA-256 and the final delivery commit are published on PR #408. Verify that
published digest first, then run `./forge-preflight.sh --offline`; the script
checks source closure and declared hashes. This is an agent offline signoff, not
a cryptographic signature or a runtime release approval.

[Detailed Forge preflight and short qualification runbook](FORGE-RUNBOOK.md)
includes executable offline reproduction and a future read-only runtime
inventory. No runtime launcher is authorized or supplied; diagnostic build and
owner wiring still require separate review. The proposed short-run samples
remain a proposal, not calibration/benchmark/soak permission.

[Resource ownership](evidence/stage5/resource-ownership.json) and
[verified cleanup](evidence/stage5/cleanup.json) retain process/session
identities, scoped teardown and host checks. Private environment, dependency
links, source exports and timeout leftovers are removed after evidence capture.
Open-PR worktrees and committed evidence remain. Earlier failures and test setup
errors are explicitly retained in the
[execution ledger](evidence/stage5/execution-ledger.md).

**STOP after Stage 5 publication.** No Docker image build, application service,
browser launch, real application HTTP traffic, packet capture, calibration,
benchmark, sustained test, host privilege or Nginx/network change occurred.
Stage 3B stays deferred. Keep #403/#405/#406/#407/#408 draft and unmerged,
#390/#391 open and the **1.5-second observer-cadence requirement unchanged**.
