# Operator events: persistence and acceptance

Part of the [approved design](2026-10-18-operator-events-design.md).

## Persistence, compatibility and backout

Generalize the current single-file migration validator to ordered
checksum-checked migrations without changing migration 001. Provide an explicit
maintenance upgrade command under exclusive admission: backup first, apply 002
transactionally, run integrity checks, then reopen. Normal service startup does
not silently migrate an existing store. An unupgraded store reports actionable
schema/upgrade status behind the Operator gate while baseline application
startup remains available.

Migration 002 adds tables/indexes/triggers only; preserve source records,
immutable journal sequences, command receipts and existing projections. New
acknowledgment receipts use the commands table but do not create operational
revisions. Include new tables and their constraints in validation, capacity
accounting, backup/restore, commit-crash recovery and namespace tests.
Notification metadata is local Operator state and is not added to mission
packages, JSONL projections or existing exports.

Keep minimal notification history for the store's lifetime under existing
private storage and capacity controls; no new automatic deletion policy. The UI
bounds its history window independently. If capacity is exceeded,
acknowledge/reconciliation writes fail explicitly without destroying source
history. Do not persist repeated poll timestamps or every source refresh.
Polling a steady feed must cause no writes.

Rollback: stop the task stack, preserve an upgraded-store backup, and restore
the pre-upgrade backup before running old code; old code intentionally rejects
schema 002. This rollback loses acknowledgments and other writes after that
backup, which must be stated in the maintenance instructions. Turning off
Operator stops its feed and alerts without rolling back the database or changing
other application behavior.

## Failure and race semantics

| Situation                                     | Required behavior                                                                                                                  |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Call moved while prep alert pending           | reconcile against the current Operator transaction before returning a fresh snapshot; obsolete generation cannot newly acknowledge |
| Cancel/complete/remove/resolve                | suppress automatic cues after authoritative reconciliation; preserve source history                                                |
| Two acknowledgments, different keys           | one durable acknowledgment; both receive its identity                                                                              |
| Lost acknowledgment response                  | retry same body/key; read back confirmed result                                                                                    |
| Source changes during acknowledgment          | validate pinned generations using the capture protocol; reject with 409/503, without a new acknowledgment                          |
| Feed result arrives after mission/run switch  | discard by request identity; never show or cue in new context                                                                      |
| Forecast refresh or aircraft movement         | update timing/revision in place; apply drift/stability rules without refresh noise                                                 |
| Prediction disappears due to unavailable data | last-known/unknown; no all-clear and no automatic cue                                                                              |
| Backend restart                               | retain occurrences/acknowledgments; bounded catch-up after fresh data                                                              |
| Browser storage unavailable                   | timeline/acknowledgment work; disclose session-only delivery dedup; no replay within the current session                           |
| Audio/vibration fails                         | retain visual cue and event; report output limitation, never mark acknowledged                                                     |
| Mid-transaction crash/disk failure            | atomic rollback or committed result; existing recovery and idempotency paths apply                                                 |

A cue already emitted before another client's cancellation/acknowledgment
reaches this client cannot be recalled. Every cue is checked against the latest
received eligible snapshot; the 15-second polling boundary is visible and
tested. There is no claim of instantaneous synchronization or exactly-once
physical delivery.

## Aircraft-free acceptance

Use wholly synthetic mission identities, routes, positions and operational
records in an isolated production Docker/Nginx project. Inject deterministic UTC
through the backend clock and the actual simulation/replay context, including
the observation freshness clock where existing #348 contracts distinguish it
from mission time. Do not substitute mocked prediction JSON for integration
acceptance. Unit tests may use contract fixtures; integration and browser
acceptance exercise the real local PoP catalog/geometry/timing/continuity and
issue #349 leg/archive lifecycle.

| Area                  | Required controls and evidence                                                                                                                                                                                                                                 |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Contracts and clock   | versioned feed/ack schemas, stable ordering/pagination, unknown times, exact thresholds, UTC midnight, large forward jump, regression and new run                                                                                                              |
| Calls/issues          | ten-minute creation default, overlap, prep/start milestones, pending move, prep-lead edit, cancel/complete/remove/restore, issue resolve/reopen, overdue follow-up, text-only correction                                                                       |
| Identity              | same forecast revision refresh, timing drift and cumulative drift, accepted-anchor shift, repeated PoP re-entry, route/catalog change, split/merge ambiguity, severity downgrade/re-escalation                                                                 |
| Real #348 integration | actual synthetic route crossings and injected aircraft positions; full window bounds, normal PoP advisory, fallback-protected interval and sole-usable-Starshield restriction; unknown PoP is not outage                                                       |
| Protected calls       | overlapping connected participations, shared conference, configured/intended/unknown transport, closed/interrupted/missing conference with still-connected participation, call-only/conference-only participation, stale observations; one cue per restriction |
| Acknowledgment        | leaves event/source unchanged, same/different-key concurrent clients, lost response, schedule/severity replacement, obsolete generation rejection                                                                                                              |
| Catch-up              | first open, long disconnection, muted then enabled, hidden then visible, overdue history, at most one grouped cue, three-item cap, rate limit and local reload dedup                                                                                           |
| Sources               | stale/missing/mismatched snapshots, unreachable optional provider, explicit disabled source, incomplete pagination, late response after mission/leg switch; no false all-clear                                                                                 |
| Recovery              | real backend restart, two clients reconnect, backup/restore, migration rollback, storage-full/failure, commit crash; no duplicate durable acknowledgments                                                                                                      |
| UI                    | production browser desktop 1920×1080, mobile 390×844 and 844×390; access feed from all four work sections, preserve dirty drafts, keyboard/focus, long titles, no horizontal overflow                                                                          |
| Local delivery        | gesture requirement, enabled/muted/unsupported/rejected sound and vibration, hidden page throttling, close/unmount cleanup; no external requests                                                                                                               |
| Existing behavior     | real #349 synthetic leg switch/completion/archive, unchanged mission-package/export hashes, Overview layout/history/POIs and Missions workflows                                                                                                                |

Use two real browser contexts for concurrency. Capture request destinations and
run the synthetic product network without external access; the unavailable
provider must fail locally and cannot block the feed. Capture sanitized
desktop/mobile screenshots, event/ack examples, deterministic scenario results,
browser traces, backend/frontend tests, build/lint results, image SHA and exact
candidate commit. No real aircraft itinerary, terminal, phone number, IP address
or sensitive mission content belongs in fixtures, logs or captures.

Before any runtime check, record process/session ownership, Compose project,
networks, private volumes and temporary paths. Bound all test/build commands
with wall-clock timeout and termination grace. Resource-owning runners install
signal cleanup, close browser contexts, stop/reap workers and remove their
isolated stack. Verify owned processes, listeners, containers, networks and
disposable volumes are gone after checks, including failures. Preserve evidence
and the open-PR worktree. Synthetic acceptance establishes software behavior
only, not aircraft readiness.

## Delivery and review boundary

The written specification and plan were approved in PR #379 comment 6244505182,
and the user selected native execution. Implementation stays in the issue
worktree and draft PR #379 targets `dev`. Product review, applicable exact-head
CI and fresh production acceptance precede merge. Keep #369 allocation, #370
export and #376 layout consolidation separate.
