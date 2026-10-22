# Offline delivery and checkpoint record

Delivery is tooling implementation and offline validation only. No performance
acceptance, overhead measurement or runtime qualification is claimed.

Exact collector source commit: `a48837b99d87366c6e3fc24ba2915f0b739cddad`.
Immutable source/schema/fixture/evidence hashes are in `release-manifest.json`.
The PR description records the final metadata delivery SHA separately.
`RESULTS.md` and the manifest are excluded release metadata to avoid circular
hashes. No implementation files changed after that source commit.

## Verification

- **28 Python tests passed**, including all 16 deterministic fixture cases,
  schema/clock/ID joins, deliberate unavailable boundaries, worker completion,
  cancellation, SIGTERM cleanup with a fictional resource sampler, and queue,
  byte, body and disk limits. See `evidence/regression-python.log`.
- **7 Node fake-Page tests passed**, including shared schema compatibility,
  dropped bodies, listener detach, failed-request bounds, terminal request-ID
  retention and late body rejection after shutdown. No Chromium was launched.
  See `evidence/regression-browser.log`.
- `evidence/offline-results.json` and `evidence/offline-results.log` contain the
  machine-readable and compact human-readable fixture results. Each case was
  replayed into the independent analyzer with literal expected classifications
  or durations. These are analyzer fixtures, not actual A/C frontend playback.
- Source was formatted and checked with the available Black 26.5.1, Ruff 0.16.8,
  Prettier and markdownlint. Internal links passed; the advisory external-link
  checker could not reach the private GitHub links (certificate/network error).
  These are focused tooling checks, not a claim to have rerun canonical
  application/CI gates. See `evidence/static-checks.log`.

Offline runtime: Python 3.14.4, jsonschema 4.19.2, Node 22.12.0. This tooling
runtime is separate from the pinned production Python/browser lane. Python 3.11
is the package minimum, but was not installed here and was not independently
executed in this delivery. Actual Playwright/browser qualification is
unavailable.

The sandbox hung during asyncio executor shutdown, including a minimal
`asyncio.run(asyncio.to_thread(lambda: 42))` probe. The 30 s and diagnostic
12/10/5 s attempts ended under explicit wall-clock limits; their logs are
preserved. After each timeout the session exited. Offline worker tests passed on
the host. No blocked run was counted as a pass or used as a performance
measurement.

## Preserved evidence compatibility

One retained corrected unloaded diagnostic trace was read, imported and analyzed
without modifying it: 1,055,423 bytes, 7,882 legacy events, 483 imported events,
134 operation IDs, zero reported legacy drops. Its SHA-256 was checked before
and after import; the path/hash and phase distributions are recorded in
`evidence/preserved-trace-result.json`. There are 41 joinable producer ticks and
31 worker operations. Missing producer return, successful-CAS/final-validation
and reliable repository joins remain unavailable. This is a compatibility check
of one existing trace, not a reanalysis of historical failures or a benchmark.

## Review and limitations

A fresh read-only reviewer found six Important evidence-integrity/lifecycle
issues. Each was reproduced by a failing offline test and fixed: incomplete
stored coverage/stale sample provenance, retained plot-input comparison,
per-stream missing-summary loss accounting, late browser-body cleanup, missing
segment/query/source joins, and browser schema/nonfinite validation. The related
minor terminal-request-ID retention issue was also fixed. The full suite passed
after the fixes; the reviewer did not rerun a second review pass.

The reviewer declined live browser ordering, actual instrumentation integration,
ancestor cgroup access, measured overhead, calibration/soak behavior and frozen
acceptance. Ruling: these remain explicit runtime qualification blockers or
out-of-scope acceptance work; an offline pass does not resolve them. The cost of
assuming coverage would be false attribution or unqualified performance claims,
so required unavailable boundaries stop the proposed preflight.

No production hook/build was added. Actual producer call-site coherence, final
CAS, callback/commit, retained input and painted-canvas evidence need a
separately reviewed diagnostic integration using this package's explicit APIs.
The current release cannot qualify those runtime boundaries alone.
Compressed/chunked body capture also needs a separate bounded streaming adapter.
The historical 1.5 s violations, CPU uncertainty and all issue/PR decisions
remain unchanged.

## Ownership and cleanup

The isolated worktree and branch are retained for this open draft tooling PR.
All other worktrees and the primary `dev` were preserved. Test children were
terminated and reaped by their owners; no application/server/browser/Compose
stack, listener, image, container, network or volume was started by this task.
Host process checks and task-specific Docker/listener checks are retained in
`evidence/cleanup.log`. The task-owned schema-generation file under `/tmp` was
removed. The environment policy snapshot and environment-status tool were not
available in this session; no network-policy or credential changes were made.
Git transport and connected GitHub tools were used through existing
configuration.

Stop at this checkpoint. [Qualification](QUALIFICATION.md) proposes a short
coverage/overhead schedule only after a separate authorization and required
integration review. No sustained runs, merge, deployment or issue closure.

Keep PRs #403/#405/#406 draft and unmerged, and #391/#390 open.
