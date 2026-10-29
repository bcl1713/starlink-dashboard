# Current-candidate sustained-soak attempt: failed

The clean sustained-soak gate **remains open**. The October 28–29 attempt on
production candidate `46ed6af6d431cd7fac8633a9f3d829d5fc24d831` collected 725
measured samples spanning **3,619.9999360730003 seconds**, then failed the
existing Overview polling gate: its maximum request-start gap was **9.812250565
seconds**, above the unchanged five-second limit. The native run remains
`failed`; no failed run is relabelled or used for a clean-baseline comparison.
PR #432 remains draft.

The separately versioned harness is
[`ca551a0e94b93bbcd0b45b2a69567354f5094098`](https://github.com/bcl1713/starlink-dashboard/commit/ca551a0e94b93bbcd0b45b2a69567354f5094098).
It changes qualification tooling and tests only. Production images use the exact
candidate archive and unchanged production Dockerfiles. The candidate includes
accepted development base `65a4df92b87a27eb8e2ac88985d8ce02f85e8fd8`. The
[protocol](protocol.md) was committed before these runs. Frozen harness tests
passed **63 tests and 68 subtests**;
[the log](results/observers/harness-v2-tests.log.gz) is retained.

## Sustained observations

| Observation                                                     | Result                                                                     |
| --------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Native overall result                                           | **Failed**: Overview polling coverage                                      |
| Measured resource samples / span                                | 725 / 3,619.9999360730003 s                                                |
| Measured browser API starts / terminals                         | 16,534 / 16,534                                                            |
| Measured HTTP / network / observer errors                       | 0 / 0 / 0; GPS 503 exception used 0 times                                  |
| Measured cancellations                                          | **1**, Operator event read during reactivation                             |
| Three lifecycle controls / journal writes / Operator recoveries | All 3 / 3 / 3 succeeded                                                    |
| Independent measured Prometheus observations                    | 724; zero probe errors; all scrapes healthy and identities valid           |
| Current mission identity sequence                               | **1 → 0 → 1**; mission gauges remained zero while inactive                 |
| Final native capture qualification                              | **False**; final qualification fence was not reached after polling failure |
| Independent runtime cleanup                                     | **Clean**                                                                  |

[Native run](results/sustained-001/run.json),
[polling result](results/sustained-001/polling.json),
[raw capture summary](results/sustained-001/api-capture-summary.json),
[API outcomes](results/sustained-001/api-outcomes.jsonl.gz),
[resource samples](results/sustained-001/samples.jsonl.gz),
[control receipts](results/sustained-001/operations.jsonl),
[source recoveries](results/sustained-001/coordination.jsonl), and
[independent observations](results/observers/cardinality-sustained-001-samples.jsonl.gz)
retain the underlying records. The native final resource summary and final
screenshots were not produced because the polling gate failed first. The
[separate descriptive resource summary](results/observers/sustained-001-derived-resource-summary.json)
retains metadata with native status `failed`; its duration flag establishes time
coverage only.

Control times below are relative to browser readiness, including the 120-second
warmup. Sampling and natural-idle coordination delayed the quarter deadlines;
these are actual execution times, not exact 15/30/45-minute claims.

| Control          | Completed at (s) | Operator source recovery wait (ms) | Journal receipt at (s) |
| ---------------- | ---------------: | ---------------------------------: | ---------------------: |
| Activate leg 2   |     1,027.174841 |                          1,597.629 |           1,028.813970 |
| Deactivate       |     1,933.430578 |                          1,468.274 |           1,934.931989 |
| Reactivate leg 1 |     2,836.693159 |                          1,943.092 |           2,838.673132 |

### Cancellation evidence and its limits

Request `p1-r2838` was a measured GET of
`/api/v2/operator/events?mission_id=synthetic-mission-a&include_history=true` on
the Operator page. It ended with `net::ERR_ABORTED`. Its raw `cancellationCause`
remains **unknown**. The observer separately recorded an actual
`XMLHttpRequest.abort()` invocation for the same page, method and URL. Its
recorded XHR send timestamp was within 0.423 ms of the authoritative CDP request
start; the abort itself occurred 7.377 ms after that start. Health, context,
records and a fresh event read successfully recovered the reactivated source
within the declared ten-second window.

The native browser threw at the polling gate before executing its final
cancellation classifier. Its original summary therefore still reports one
unqualified cancellation and `qualification_clean: false`. A
[separate derived proof](results/diagnosis/derived-cancellation-proof.json)
classifies the measured cancellation as an observed handover abort under the
precommitted v2 rules. This does **not** qualify or repair the failed run.
[Derivation metadata](results/diagnosis/derivation.json) binds the raw and
derived hashes. The derived input excludes only eight teardown rows (five starts
and three terminals); failure cleanup left two teardown requests without
terminals. Every warmup and measured row is preserved byte-for-byte, and the
incomplete teardown rows remain in the original raw evidence. The exact
[derivation script](results/observers/derive-failed-soak.py) and
[classifier source](https://github.com/bcl1713/starlink-dashboard/blob/ca551a0e94b93bbcd0b45b2a69567354f5094098/tools/acceptance/performance/cancellations.mjs)
allow reproduction. No inference about the application's internal cancellation
reason is substituted for observation.

### Polling failure and resource limits

The largest observed gap was between requests `p0-r13031` and `p0-r13051`. Their
CDP network-start times are approximately **9.849633 seconds** apart, so the
failure is not explained by Playwright event-delivery delay alone. The long gaps
cluster late in the run and coincide with browser frame/long-task stalls. Direct
observer status requests remained responsive (whole-run p99 32.71 ms), and
browser history network timing had p99 381.82 ms. These observations localize
the next investigation toward the Overview/browser/software-renderer path, but
do not establish a root cause or distinguish host contention from
renderer/driver scheduling. No polling tolerance, workload layer or production
source was changed to obtain a pass, and no second identical hour was started.
The next qualification needs the same strict gate, with browser tracing and host
pressure telemetry sufficient to explain any recurrence.

| Resource                       |    First |     Last |  Maximum | Fitted slope per minute |
| ------------------------------ | -------: | -------: | -------: | ----------------------: |
| Backend memory (MiB)           |   328.85 |   342.65 |   906.35 |              +0.426 MiB |
| Browser process-tree RSS (MiB) | 2,296.16 | 2,618.72 | 2,626.26 |              +3.608 MiB |
| Browser process-tree PSS (MiB) | 1,480.76 | 1,798.06 | 1,805.45 |              +3.553 MiB |
| Browser JS heap (MiB)          |    64.23 |    68.10 |    98.17 |              +0.062 MiB |

The raw descriptive summary is authoritative for unrounded values. Aggregate CPU
consumption was 0.123 backend cores, 0.00656 Prometheus cores and 6.266
browser-process-tree cores. Memory growth remains visible; this run establishes
neither leak freedom, capacity nor a matched speedup.

## Preflight history

All preflights used candidate `46ed6af6` and the same source-archive hash. Their
native histories remain unchanged.

| Run | Harness    | Result                                                   | Measured evidence                                                                                                                                                             |
| --- | ---------- | -------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 001 | `8be66b69` | Failed: redirect-body observer defect                    | 0 measured resource rows; 4/4 measured API starts/terminals. Nineteen warmup 307 bodies were unavailable to Playwright, plus one closure-related secondary capture error.     |
| 002 | `a5d74157` | Failed: unexplained Overview event cancellation under v1 | 14 measured resource rows / 64.983341 s; 331/331 measured API outcomes, one cancellation, zero HTTP/network/observer errors. Two controls/writes/recoveries; no reactivation. |
| 003 | `ca551a0e` | **Passed short preflight only**                          | 25 measured resource rows / 120.000219 s; 587/587 API outcomes, zero cancellations/errors; all controls/writes/recoveries; independent identities 1 → 0 → 1.                  |

Each short preflight's isolated negative controls retained a real backend
`409 store_context_changed` body and a deliberately cancelled request, and kept
those probe outcomes failing. Preflight 003 additionally proved the actual XHR
abort hook. Its main workload had no cancellations, so it did not exercise a
qualified live handover cancellation. Negative controls were **off** throughout
the sustained run. Setup-only independent probe errors are retained; none
occurred during measured preflight 002, preflight 003 or sustained observations.

[Preflight 001](results/preflight-001/run.json),
[preflight 002](results/preflight-002/run.json),
[preflight 003](results/preflight-003/run.json), and its
[negative controls](results/preflight-003/capture-probe-summary.json) are
included. The previous older-candidate failed soak and accepted final browser
evidence remain unchanged in their own addenda.

## Provenance, reproducibility and cleanup

The native [run metadata](results/sustained-001/run.json),
[browser metadata](results/sustained-001/browser.json),
[backend package inventory](results/sustained-001/backend-packages.json),
[Compose inputs](results/sustained-001/compose.json), and command logs retain
actual versions, image IDs and fixture hashes. Rebuilding the same production
archive yielded distinct image IDs across attempts; no dependency/image equality
with an earlier acceptance run is assumed.

- Candidate archive SHA-256:
  `82135b514770c83e408d39d332b2c65cfbec85367f9d18275c7ab0b8e7b1c725`.
- Sustained backend image:
  `sha256:70daa4ab514264af757ccfe25dd098830a0f3535e58b54106dcfc29905841cdf`.
- Sustained frontend image:
  `sha256:dbab3e9b2184011815966a90e844e79fa039a295e51839c7e732652fbf0ac209`.
- Browser: Chrome 153.0.8010.12, SHA-256
  `8c599d43aec53f2460a31ae2f4af6bd863f8258b34ff519564bc5d4726bfaa1e`.
- Host Node: 22.22.2, from the
  [official archive](https://nodejs.org/dist/v22.22.2/node-v22.22.2-linux-x64.tar.xz),
  SHA-256 `88fd1ce767091fd8d4a99fdb2356e98c819f93f3b1f8663853a2dee9b438068a`.

This is a diagnostic **headless SwiftShader** workload with a 1920×1080
fullscreen layout, not physical headed fullscreen. It includes one Overview, one
Operator, the candidate's default layers, a 1,800-second history window, real
clock, one-second Prometheus scrape/evaluation intervals and five-second
resource sampling. Capture observers add overhead as declared in the protocol.
The successful short-run screenshots are labelled by preflight directory. This
workload does not replace the separately accepted final headed journey, which
covered the allowed 503 history fallback with zero scheduled polls.

Every run used its own owned Compose project and private resources. Native
cleanup and approved-host independent checks found no remaining owned process
groups, Docker containers/networks/volumes, image tags, TCP/UDP listeners,
abstract reservations, browser profiles or temporary runtime source inputs.
Receipts are included for
[001](results/observers/preflight-001-independent-cleanup.json),
[002](results/observers/preflight-002-independent-cleanup.json),
[003](results/observers/preflight-003-independent-cleanup.json) and
[the sustained attempt](results/observers/sustained-001-independent-cleanup.json).

[The manifest](results/manifest.json) records original and published byte counts
and SHA-256 values. All command logs and larger JSONL/OpenMetrics files use
deterministic gzip; decompression restores the exact originals. Raw native files
are unchanged. These repository copies preserve evidence integrity for review;
they do not independently authenticate omitted platform-authority seals from
earlier formal acceptance evidence.
