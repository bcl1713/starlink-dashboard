# Operator conferences acceptance and rollout

Part of the approved [#366 design](2026-10-17-operator-conferences-design.md).

## Synthetic verification and acceptance

Implementation acceptance must exercise real application paths, using only
synthetic missions, coordinates, parties and observations. Inject deterministic
UTC through the existing simulation clock. Optional providers may deliberately
fail; terminal hardware, aircraft, real itineraries and external services are
not required. Simulation demonstrates software behavior, not aircraft readiness.

| Scenario                  | Required assertions                                                                                                                                                                                                                                                  |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Shared conference         | Two sequential calls reuse one established conference; idle interval remains established; completing/cancelling/rescheduling either call leaves conference revision unchanged                                                                                        |
| Overlap and joining order | Two overlapping calls retain separate intervals; join before establish and establish before join both work; verification never fabricates customer success                                                                                                           |
| Unknowns                  | Unknown identity, schedule, duration, actual timing and transport save without invented values; call-only and conference-only participation remain usable                                                                                                            |
| Interrupt/restore         | Customer restoration creates a new interval, preserves gap and predecessor; conference interruption/closure does not invent customer leave or continuity                                                                                                             |
| Corrections               | Backdated/approximate edits preserve occurrence/recorded separation, old revisions and current snapshot semantics; remove/restore and dependency conflicts remain explicit                                                                                           |
| Protection                | Supported timeline restrictions and real #348 predictions produce bounded contextual advisories; unsupported operator-planned changes remain explicitly uncovered; boundary touches, raw telemetry jitter and unrelated transport do not produce false impact claims |
| Planning rules            | Synthetic #348 positions/routes cover unknown location, transition timing, default Starshield availability, sole-transport outage and usable Ka/coordinated X fallback                                                                                               |
| Lifecycle                 | Exercise real #349 preflight, flight transitions, leg switch, on-blocks and completion; conferences survive, associations remain valid, archives and mission packages retain existing behavior                                                                       |
| Two clients/failures      | Duplicate writes replay; concurrent edits conflict; held/lost responses do not falsely show Saved; offline drafts, reconnect, failed optional sources and pagination retain honest state                                                                             |
| Restart/recovery          | Restart with an established conference and overlapping connected customers; recover identical current states, revisions, receipts, predecessor links and protection snapshot without duplicate events                                                                |

Backend unit/contract/integration tests cover payload defaults, action
validation, UTC tolerance and interval rules, typed links, projections, legacy
receipts, backup/recovery and deterministic advisory derivation. Frontend tests
cover quick actions, target separation, unknowns, accessible desktop/mobile
controls, optional fields, conflict/retry, stale snapshots and incomplete lists.
Extend the existing operator-journal acceptance harness and synthetic fixtures;
do not substitute mocked PoP or lifecycle outcomes for the required real
integration journeys.

Fresh exact-commit production Docker/Nginx browser runs cover 1920x1080 desktop,
390x844 portrait and 844x390 landscape, two clients, restart and failure
injection. Capture sanitized screenshots, machine-readable assertions, test/tool
versions, source clocks and interval inputs, existing export compatibility and
Overview layout/history behavior. Run applicable backend/frontend/static CI
gates on the final PR head. Design-only review does not claim any implementation
tests passed.

Before starting runtime resources record ownership and install exit/signal
cleanup. Use a task-specific Compose project and private disposable volumes,
wall-clock timeout plus termination grace for every test run. Stop and verify
processes, listeners, containers, networks and volumes after checks, preserving
only evidence and the open-PR worktree. Never prune shared resources.

## Compatibility, rollout and review gate

Keep the feature disabled by default. Extend JSON payloads additively without
rewriting historical records. Verify older fixtures and unchanged call/journal
contracts. Before upgrade preserve a store backup. Roll back by disabling
Operator; a binary downgrade with closed old models requires restoring the
pre-upgrade backup and preserving the newer store separately. Document any
required derived index migration and reversal explicitly.

This document is the review artifact. After specification approval, write the
implementation plan and obtain its required review before product changes. Work
stays on feat/operator-conferences in .worktrees/issue-366, based on origin/dev;
submit against dev. Do not merge as part of specification approval. Keep the
worktree for review, then remove task branches/worktree after authorized merge.

## Architecture and alternatives

Extend existing conference and participation payloads and permit their public
writes through the existing records API. Reuse immutable full revisions, typed
same-mission links, UTC RecordTime, journal projections, receipts, expected
versions, store epochs and recovery. Do not add a second store or mission model.

Separate typed records avoid coupling unrelated customer updates. Free-text
observations cannot provide reliable intervals. A conference is reusable; a call
retains its own schedule/completion; participation is one reported connection
interval targeting a call, conference or both. Neither schedule nor elapsed time
creates connection or completion events.
