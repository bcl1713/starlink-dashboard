# Original-A functional runtime smoke — failed startup; STOP for review

The one authorized A attempt stopped at TSDB seed-container startup. Docker
rejected the approved local logging configuration with:
`compression cannot be enabled when max file count is 1`.
The backend, frontend and browser never started. Instrumentation did **not** work
end-to-end in this attempt; C is **not ready** for a separately approved test.
There was no retry, C execution or configuration repair.

Authority: [orchestrator checkpoint](https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6355796338).
Starting commit: `6ce682bf69c4b48ee5751c20093b15b4afb0b189`.
Execution occurred on local Forge, not a cloud instance, on 2026-10-23 from
02:50:07 to 02:50:12 UTC (supervisor wall-clock records, not measured application
latency). The exact existing executor ran once under GNU
`timeout --kill-after=10s 90s`, with its unchanged 78-second work deadline.
It exited 1 without reaching the timeout. No production, frozen, collector,
executor, receipt or image bytes were changed.

## Preflight and immutable identities

[Preflight evidence](evidence/preflight.json) records fresh verification of both
closed receipts, all four retained image IDs and exact labels, the 187-file
build inventory, 621-file Stage 5 release, corrected runtime overlay,
compiled-asset/module closures, collector and frozen-harness identities.
The actor context was `default`, endpoint `unix:///run/user/1002/docker.sock`,
daemon `forge`, with host PID and cgroup v2 visibility. Ports 38080–38083 were
free. Available disk was 24,506,380,288 bytes and available host memory was
54,520,045,568 bytes. Ancestor CPU quota remained the shared 10-CPU quota;
host browser budgets were not represented as enforced cgroup limits.

The original historical overlay was exported into a private compiler directory
and every file checked against the immutable plan. Fresh source/patch/context
regeneration reproduced the complete retained build plan byte-for-byte. The
corrected overlay was verified separately for execution. Regeneration also
exported C offline; no C runtime operation occurred. Neither immutable plan nor
receipt was rewritten to accommodate regeneration.

| Identity | Verified value |
| --- | --- |
| Original A source | `25e34168f0e2cecb149b0323f1f5a795cb28cae0` |
| A backend image | `sha256:8b8518fe1007170ce423b76f98958d85a4153927a0d8e59930d3790f38318abd` |
| A frontend image | `sha256:aee6d4fdf4a1c7746c8e4ba65458aa3160ffb8d1792982ba56a3e1cb1745dd88` |
| A receipt SHA-256 | `7d337809082015880bb51e69bcf8973fd5036518286b876dda77145543c9c24f` |
| Retained build-plan SHA-256 | `8537bddee63b76d65f08548d447fbc93f42dfbe919b09f4fc9826d4e128954d5` |
| Regenerated A context SHA-256 | `9563d8f4396323fc2ba726605704fb41a14c56c89010d55a2b48cfa1d412f7ab` |
| Collector source | `a48837b99d87366c6e3fc24ba2915f0b739cddad` |
| Frozen harness | `f3029024b5950a267645195476da5cbca326f16a` |
| Diagnostic Node | 22.22.2; SHA-256 `81925c0995b5c1427b5d538e6a90ca2fdc4daffb786b09af749beaf7369d4e90` |
| Historical Node, untouched | 22.12.0; SHA-256 `177208bfc4a9403121a40c72d038c670f4fd937fa16ca7df0a720e90be0fe2d9` |
| Playwright / playwright-core | 1.63.0; Node engine `>=20` |
| Configured Chromium | revision 1243; SHA-256 `8c599d43aec53f2460a31ae2f4af6bd863f8258b34ff519564bc5d4726bfaa1e` |

Private Node was read from the retained pinned Node image archive without
creating a container; its SHA was verified before execution. API import and
configured executable resolution passed; browser distribution hash and dynamic
libraries matched. The executor independently ran private Node `--version`.
Actual browser version, renderer, pixels and runtime compatibility remain
unavailable because no browser launch occurred. This diagnostic lane supplies
no historical timing comparison or performance result.

## Operations and partial evidence

The [launch plan](evidence/launch-A.json) retains explicit phase argv, identities,
resource intent and deadlines. The three owner manifests retain PID/PGID/start
identities and reaping results for all owned commands. Asset verification used
one stopped extraction container, removed before seeding. All extracted image
asset hashes match the unchanged A receipt; the hashes are retained in
[extracted-asset-hashes.json](evidence/extracted-asset-hashes.json). Redundant
extracted asset bytes were removed; their canonical retained copies remain in
the built-images evidence package.

The synthetic OpenMetrics file was generated successfully. The next operation,
`seed-tsdb`, failed at Docker task initialization; the seed process could not
start. [command-08.log](evidence/runtime/command-08.log) preserves the daemon
error. The approved Compose override specifies local logging and `max-file: 1`
without an explicit compression override. No daemon, Nginx, logging or polling
configuration was changed, and no alternative configuration was tried. A
separately reviewed launcher/logging compatibility correction is required
before any further runtime request; the immutable images are not implicated by
this failure.

[Stream status](evidence/stream-status.json) explicitly records availability:

- Five source and five host observations at 1 Hz were planned; zero ran.
- No visible chart, request/history/retained/uPlot evidence chain or screenshot
  attempt occurred. Required joins remain unqualified.
- Backend producer, worker, depth-zero admission and observer evidence and their
  final stream summaries are unavailable because startup never reached them.
- Dropped-event counts are unavailable; absent producers do not prove zero loss.
  The owner stream list is empty. Owner errors/survivors are retained separately.
- Raw-wire capture, native Axios parse-start and A's CAS/final-authority/frame
  capabilities remain unavailable by design.
- The 1.5-second observer requirement is unchanged and was not exercised or
  waived. No source cadence or sustained acceptance claim is made.

Clock domains are explicit: supervisor intent/exit use host UTC wall clock;
process start identities use Forge Linux `/proc` ticks since boot (100 Hz);
the executor uses host `time.monotonic()` for deadlines. No cross-domain
operation duration is inferred. No browser/backend operation clock was emitted.

## Independent cleanup and evidence integrity

The executor's three owners report clean, reaped child processes and no cleanup
error. Its scoped Compose teardown removed the created metrics volume and
network. The independent host [runtime audit](evidence/runtime/cleanup-audit.json)
passed, followed by a separate [final host audit](evidence/final-host-cleanup.json)
covering 11 unique recorded process/start identities and their owned groups,
private-path process scans, A/C Docker project resources and ports
38080–38083/38180–38183. All were absent. No temporary browser files existed.
The private Node, Python environment, image archive, regenerated exports/runtime
directory and empty task lock were removed after evidence retention. All four
accepted diagnostic images remain present with their exact labels. The open-PR
worktree and evidence remain; no task runtime resource remains running.

[artifact-manifest.json](artifact-manifest.json) hashes every retained report,
script and evidence file. The partial result is deliberately not passed through
the success-only runtime analyzer: startup, final streams and joins are absent.
The final verifier checks exact artifact closure, hashes, failure identity,
receipt/asset consistency, owner reaping and both independent cleanup reports.

Preliminary sandbox Docker/Git/cache access was restricted; the approved host
executor resolved those access checks before preflight, without starting any
service. The first sandbox-only Python-environment setup failed on the cache
lock; bounded offline host setup succeeded. These were setup operations, not
additional A attempts. No image rebuild, packet capture, calibration,
performance benchmark, soak, merge, deployment or issue closure occurred.

STOP for checkpoint review on draft #408. C remains NO-GO. Existing draft PRs
#403/#405/#406/#407/#408 are open and unmerged; #390/#391 remain open. No PR or
issue state was changed. #404 is an open issue, not an existing PR.

The first offline report verifier invocation caught an incorrect log reference
(`command-07.log`, the successful seed-file step). The report and verifier now
reference `command-08.log`, the failed seed-container step. This documentation
correction involved no runtime operation; the final verification passed.

Git whitespace verification passes for non-log artifacts. Raw Docker log bytes
retain their emitted trailing spaces for evidence integrity. The first commit
command found no configured Git author; the final commit uses the existing
Codex author identity through command-scoped options, without changing shared
Git configuration.
