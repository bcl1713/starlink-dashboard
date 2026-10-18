# Operator transport decisions — acceptance specification

Companion to [the proposed design](2026-10-18-operator-transport-design.md).

Implementation must supply the following evidence before merge. These are future
acceptance requirements, not tests claimed by this document. Use wholly
synthetic identities, coordinates, missions and UTC clocks; no terminal or
external service.

| Scenario                    | Required assertion                                                                                                                                                     |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Independent reports         | Intent/request/application can differ; applied-only, checked-only and unknown-time entries save; actual routing stays unknown                                          |
| Multiple services and moves | One atomic decision covers voice/VTC/IPTV with distinct reports; later service move preserves earlier record and reason                                                |
| Corrections                 | All entered timestamps, transport reports and reasons can be corrected/cleared; history and acceptance times remain immutable                                          |
| Check association           | Replacing application clears stale check unless explicitly replaced; older pairing stays in history                                                                    |
| Prediction integration      | Real #348 predictor on synthetic trajectory produces its actual advisory window overlapping modeled X restriction and scheduled call/preparation                       |
| Delayed departure           | A 45-minute delay moves operative airborne restriction UTC using #379; obsolete planned UTC cannot trigger overlap assessment                                          |
| Groundspeed                 | Real live ETA interface moves review timing and existing notification threshold together; no duplicate durable event                                                   |
| Deviation/rejoin            | Real route projection produces updated ETA or explicit unknown, then recovers; no fallback to airborne plan UTC                                                        |
| Route/leg revision          | Future review reflects accepted route/leg publication; historical decisions and their reported times/reasons are byte-for-byte unchanged                               |
| Protected communications    | Changes ahead of and during active calls/connected participation warn but save; conference remains independent of call completion                                      |
| Overlapping restrictions    | X/Ka restriction and PoP advisory all remain visible with distinct semantics and correct fallback classification                                                       |
| Unknown/stale feeds         | Missing route, stale position/speed, missing Ka/catalog and unreachable optional provider produce partial/unknown context; decision entry works                        |
| Concurrent clients          | Desktop/mobile conflicting edits return existing explicit conflict; no silent overwrite or duplicate event/receipt                                                     |
| Network loss                | Before-send failure and lost committed response preserve draft/frozen retry; reconnect recovers exactly one accepted mutation                                          |
| Restart/recovery            | Records, corrections, links, receipts and existing acknowledgments survive restart and backup/restore; crash/commit failure cannot leave half a multi-service decision |
| Compatibility               | Existing call/conference/feed contracts, mission exports and Overview behavior remain unchanged with gate on/off                                                       |
| Migration/backout           | Existing schema-002 fixture upgrades transactionally without data/sequence/trigger loss; failed migration rolls back; old binary rejects upgraded store                |

Backend unit/contract tests cover strict DTOs, UTC/precision validation, overlap
boundaries, provenance, history, references and API errors. Integration tests
drive real mission timeline preparation, #348 live predictor, #379 route-aware
ETA and the production source/feed admission path. Mocked review rows alone are
insufficient. Source-change races and mismatched journal/snapshot identities
must produce retryable snapshot errors or explicit unknown context, never a
mixed apparently authoritative assessment.

Production acceptance builds a committed exact candidate through Docker and
Nginx, using an isolated Compose project and synthetic deterministic clock.
Exercise actual browser workflows at 1920×1080, 390×844 and 844×390, with two
clients, ordinary LAN HTTP, reconnect and restart. Capture sanitized screenshots
of independent reports, active-call warning, moved live restriction, unknown
model state and corrected history. Preserve machine-readable assertions, command
versions, candidate SHA, migration/restart/failure logs and export compatibility
results. Existing #349 lifecycle/archive interfaces supply leg transitions;
introduce no parallel flight lifecycle or export mechanism.

Record resource ownership before each run, apply explicit wall-clock timeouts
with termination grace, use cleanup handlers, and verify task-owned processes,
listeners, containers, networks and disposable volumes are gone after checks.
Preserve evidence and the open-PR worktree; preserve shared runtime
configuration and credentials. Report simulation findings only, with no
aircraft-readiness claim.
