# #391 diagnostic correction — offline checkpoint

Source commit: `31b1fbbfded503344e9df653ba148850a2e69f95`. Baseline:
`09095e263d3d1c237309b9f2359fa879b91353d2`. Authority:
[orchestrator comment 6368326352](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6368326352),
following
[forensics 6368261902](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6368261902).

**STOP for checkpoint review.** This stage implements and qualifies diagnostic
source offline. Original A acceptance remains failed; C remains NO-GO. No image
or compiled asset was rebuilt; no A/C application, browser, calibration,
benchmark, sustained test, merge or deployment ran.

## Correction

Snapshot copying now charges actual UTF-8 JSON bytes, including escaping,
separators and keys, instead of worst-case charges for every primitive. The
2,097,152-byte artifact cap, 50,000-node traversal cap, depth 32, 256-character
strings, 1,820-point trace cap, eight concurrent jobs, 256 queued events and 8
MiB queue remain unchanged. The authenticated retained shape fits without
changing production charts, patch specifications or sample provenance IDs.

The Node observer retains at most 16 reason-coded failures, timestamps and
counter snapshots; further failures increment an explicit overflow count.
Reasons cover write, listener/event, request/event/binding capacity, binding
assembly/artifact, setup, close-incomplete and handle-disposal failures. Final
summary preserves the state before active requests, partial assemblies and
queues are cleared. Loss stays sticky; cleared counters never imply successful
collection.

The owner saves the exact metadata returned by its passing readiness predicate,
the selected panel, last frontend/Node readiness state, Finish admission, actual
Finish return and guard failure. Absent Finish, invalid Finish, incomplete
commits, frontend/Node loss, nonquiescence and metadata/Finish deadlines remain
distinct. The authentic chain executes the existing `browser-runtime.ts` Finish
source in memory and verifies its stable final sequence.

Screenshot evidence records before-metadata, native-screenshot, after-metadata
or artifact failure. All stages share the existing two-second maximum; no retry
or deadline increase was introduced. Optional PNG storage has a separate failure
counter and a finite partition inside the existing disk budget. It cannot
consume the mandatory chart/source partition or set mandatory loss. Both
mandatory and optional stored artifacts retain the frozen importer's 2 MiB cap;
larger PNGs become unavailable with no import reference. Mandatory chart loss,
missing commits, missing Finish and backend accounting remain gates.

Backend stop/drain, export-copy and statistics preservation run in bounded
cleanup before volume teardown on success and failure. Stop/copy commands each
have an owner that terminates/reaps a timed-out child before the next command.
The preservation attempt shares a maximum eleven seconds and the existing
80-second evidence cutoff within the 90-second cleanup envelope. Copy is still
attempted after stop failure. Missing/invalid/negative counters cannot mean zero
loss. Evidence/report faults cannot bypass teardown or replace the original
browser failure. Late deadlines can make evidence unavailable; that remains a
failed result, never inferred success.

## Focused verification

| Selection                                                   | Result    | Retained evidence                              |
| ----------------------------------------------------------- | --------- | ---------------------------------------------- |
| Executor + Node/source identity                             | 21 passed | `evidence/correction/python-focused.log`       |
| Observer, owner facts, collection and PNG import boundary   | 29 passed | `evidence/correction/node-reviewed.log`        |
| Probe through binding, collector, snapshots and real Finish | 10 passed | `evidence/correction/authentic-reviewed.log`   |
| Exact A exported panel/request fixtures                     | 11 passed | `evidence/correction/frontend-A-qualified.log` |
| Exact C exported panel/request fixtures                     | 11 passed | `evidence/correction/frontend-C-qualified.log` |

The source artifact is the immutable r1 latency record
`b0c67faf174567e9523d98a9f2a7a8dac6f86b1d88acb1efe41a4832301b3d45`: four finite
1,801-sample traces with provenance ID `synthetic-408a/p/b34655ed4a2b4e82/r1`
(36 characters). Two correct commit chains, `p/c2` create and `p/c3` setData,
remain associated with **r1**. No second response association is invented. Their
actual-chart artifacts are 628,798 and 628,800 bytes. Every retained,
projection, plot number and provenance ID is compared exactly; artifact hashes
are independently recomputed. The separate real-panel fixtures use the unchanged
exported application hooks and compare captured plot input against the uPlot
test fixture's actual data. This is offline boundary qualification, not native
rendering or physical-paint evidence.

[Authentic verified output](evidence/correction/authentic/verified.json), its
Node records/artifacts/hash inventory and real Finish/selection facts are
retained. [Executor fixtures](evidence/correction/executor) preserve fake
backend exports, original browser failures, missing-stats/copy/stop/report
faults, command ordering and real process-owner cleanup. No fake payload is
represented as actual backend runtime evidence.

Negative cases include escaped JSON byte overflow, depth/node exhaustion,
malformed/oversized chunks, duplicate/stale/interrupted assemblies, bounded
reason history, write/listener/disposal failures, absent/invalid Finish,
incomplete commits, metadata/native/artifact timeouts, missing backend counters,
forced browser failure, copy failure and an owned hung copy worker. Existing
focused fixture files were extended; no general suite or sustained test was
added.

Scoped TypeScript no-emit, Node/Python syntax, Black, Prettier and Git
whitespace checks pass. Ruff introduces zero findings; twelve findings in the
existing executor/analyzer remain equal to the baseline. See `ruff-final.json`.
The post-test lint-comment adjustment has identical Python ASTs, recorded in
`comment-only-formatting.json`; the final identity tests pass separately.

## Exact identities and preserved evidence

[Correction overlay](../perf391-runtime-preparation-v1/diagnostic-correction-overlay.json)
SHA-256: `43a28519858ed545e5fe2ed8720a1437985b40e4dd49f8d3675b5ea5f954a970`. It
pins all 15 changed/new source files, their predecessor hashes and 16 immutable
pins. The complete hashes and unchanged four image IDs are also recorded in
[qualification-summary.json](evidence/correction/qualification-summary.json).
Corrected compiled-asset identity is **unavailable/unbuilt**, not an old receipt
relabelled as corrected. The executor explicitly rejects this layer before
runtime preflight or ownership; historical guards/manifests remain unchanged and
intentionally reject changed source. Future asset qualification needs separate
authorization; this delivery requests no build or runtime execution.

All 117 original smoke evidence files and all 13 original Node hash entries
still match. All 24 external predecessor pins are verified: 22 still match
current files, and the owner/executor predecessors are preserved at the baseline
and explicitly replaced by this new source layer. No historical manifest was
rewritten. Original smoke manifest SHA-256 remains
`c7ed335f173fdea0d3f9534eb2b9fb3e4d5196fc4a6083c9c7c4ccc68513e258`; raw JSONL
remains `6960bf04e51c115f17de5b535a89a42d3f12b653d2049c5095840a6baa398b13`.
Production application files, A/C patch bytes, frozen #407/comparator tools and
the 1.5-second cadence requirement remain unchanged.

## Review, failures and limitations

A read-only reviewer identified preservation-report exceptions bypassing
teardown, optional PNG errors contaminating mandatory loss, and the downstream 2
MiB PNG import boundary. Each was reproduced in the focused fixture and fixed;
red/green evidence is retained. No Critical finding was reported. Final code and
fixtures resolve all reported Important findings; the reviewer did not rerun
tests.

The initial snapshot regression failed under the original budget. An immutable
baseline executor also fails the new forced-browser regression because backend
preservation evidence is absent. Initial reason/finalization fixtures failed
before implementation. These expected failures remain in the evidence directory.

Exploratory failures are excluded from passing results: initial Python test
setup lacked cached dependencies; one sandbox process-owner run did not complete
within its wall-clock limit; Node's default child isolation failed in that
sandbox; Vite's jsdom URL rewriting required a filesystem path in the authentic
panel fixture; one fixture's stop-failure expectation was corrected. Ruff
initially reported misplaced lint comments, subsequently fixed. A formatter
invocation without an outer timeout stalled in sandbox multiprocessing and was
explicitly terminated by verified PID/start identity; the subsequent bounded
multi-file attempt also stalled. Bounded single-file formatting passed. No
incomplete or aborted check is counted as a pass.

Runtime remains unqualified: original exceptions and Node lost=1 are historical
inferences, not retrospectively attributed by these new reason codes. Actual
browser scheduling, native screenshots, real backend drain timing and corrected
compiled assets still need separately authorized qualification. Source equality
and these offline fixtures make no performance or physical-paint claim.

## Cleanup and disposition

[Host cleanup audit](evidence/correction/cleanup.json) checked 255 recorded
PID/start identities: no survivors, unexpected task processes, or task
listeners. Scoped Docker container/network/volume inventories are empty; no
Docker runtime resources were started. The actor's configured Docker socket was
preserved. Task dependencies, export trees, caches, abandoned fixture paths and
temporary runners were removed. Evidence and the isolated open-PR worktree
remain; primary checkout stays clean on `dev`.

PRs #403/#405/#406/#407/#408 remain draft/open/unmerged; #404 is an open issue,
not a PR. Issues #390/#391 remain open. Stop here for checkpoint review.
