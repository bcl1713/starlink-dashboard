# Operator workspace implementation specification

Status: the original plan was approved; this lean revision applies the
subsequent user clarification for a smaller execution scope without a
generalized training backend.
[Concept A approval](https://github.com/bcl1713/starlink-dashboard/pull/382#issuecomment-6253399573)
permits planning. The
[training scope clarification](https://github.com/bcl1713/starlink-dashboard/pull/382#issuecomment-6253414196)
requires the entire Operator system, not just calls/conferences. The
[execution approval](https://github.com/bcl1713/starlink-dashboard/pull/382#issuecomment-6253561956)
and later lean clarification also apply to
[issue 376](https://github.com/bcl1713/starlink-dashboard/issues/376).

Read the approved [revision 2 contracts](../../design/issue-376/revision-2.md),
[first-use findings](../../design/issue-376/revision-3.md), and
[feature/action matrix](../../design/issue-376/audit.md) with this
specification. The initial code baseline is `1a3e77d3`; re-audit upstream
changes before execution. The existing HTML is design evidence only, never the
shipped training runtime.

## Outcome and immutable boundaries

One cohesive workspace lets the communicator conduct the whole mission with
reported customer activity, the named next future requirement/preparation,
useful modeled context and exception actions in view. A guided synthetic mission
teaches every actual Operator function through those same real controls. The
final guide and quick reference describe the shipped UI and mirror the training
narrative.

- Desktop 1920×1080; portrait 390×844; landscape 844×390.
- All interactive touch targets at least 44×44 CSS pixels.
- Overview remains passive and readable at a distance.
- Missions owns itinerary and the existing single mission ZIP.
- Configuration owns global/provider settings.
- No routing commands, new predictor, PWA or external service.
- No uncertainty acknowledgment or reason gate for ordinary report/plan use.
- No success before backend receipt; accepted receipt and failed reread remain
  distinct.
- No silent draft discard, mission retargeting or old-store command replay.
- No feature in the parity matrix may be omitted for visual simplicity.
- No ordinary ZIP import may restore destination Operator records.

## Workspace and first-use contract

Operations is home; Communications, Transport, Issues and History are named
working views. Tools explicitly lists Display controls, foreground Alerts and
Mission records. Help contains User guide, Quick reference and Guided mission
walkthrough. Onboarding is short, dismissible and reopenable. Empty states offer
Create call and Create conference rather than unexplained blank lists.

Communications exposes Create conference → Establish → Verify/test report →
Customer joined → Customer left/Interrupt/Restore connection, and Close
conference. These use existing commands, not physical bridge provisioning.
Scheduling and logging a call are obvious separate modes, with contextual
reschedule. A call ending does not close its bridge; closing a bridge does not
invent departures. Independent mitigation/status/follow-up and historic message
correction remain explicit. Real software never retains prototype “Illustrated
only” controls.

Pin named future requirement/prep separately from overdue. Show connected total
and first three intervals on desktop, with complete-list affordance; show count
and expansion on portrait. Show next three timed events and two attention rows,
with totals/expansion and honest pagination coverage. Earliest relevant modeled
advisory retains kind/time/basis plus remaining count. Long labels cannot crowd
out the next time. The editor has one scrolling body and a non-scrolling action
footer; new events update reserved awareness without moving input focus.

Selectors resolve mission, leg, call and conference names from existing paged
reads; unresolved historical references retain their identity in details. Active
flight/source context and chosen record scope are distinct. Preflight Planned
UTC changes to backend Live route ETA only with aligned airborne inputs;
unavailable live timing never uses scheduled UTC as a live fallback. Unknown PoP
or transition timing is not an outage. Transport routing remains unknown.

## Persistent state owners

Mount one workspace provider above application route switching in `App.tsx`. It
owns the foreground editor, parked draft registry and frozen-command registry;
working views consume selectors and dispatch intents. Do not mount one mutation
hook per card or lose commands when opening Missions. The existing Operator
health query remains shared; leaving Operator stops its event/record reads
except reads needed to finish a named pending transaction. No new background
alert service.

`DraftTarget` contains store ID/epoch/source mode/simulation namespace, mission,
record type, record ID or unique new-draft ID, scope, leg, previous/next leg and
optional correction target version. `DraftEnvelope` adds schema version 1, base
record/version, typed input, local revision and persistence result. Persist
unsent drafts in tab-scoped session storage; support multiple parked drafts and
one foreground editor. Session storage does not promise survival after tab
close. Store and validate targets separately from the currently browsed mission.

`PendingEnvelope` stores the exact `OperatorCommand`, idempotency key, epoch,
identity, submitted draft revision and target BEFORE dispatch. Serialize writes
per `(identity, mission, record type)`. Do not auto-send parked/offline drafts.
Uncertain receipt permits exact retry; 409 retains input for explicit review;
identity change quarantines the old envelope. Receipt completion updates the
named tray even on another view; it retires only the submitted revision, not
subsequent edits. Receipt accepted/current unreadable is not a new unsent write.

Lift/adapt existing `useOperatorJournal.ts` owners and durable hooks rather than
writing another save/retry/reconciliation engine. Keep its existing API headers
and expected-version semantics; the registries are thin ownership/persistence
adapters. Existing pending storage is opt-in for issue, capability and transport
callers; unsent call/conference/note recovery is new frontend work. Read legacy
draft/pending keys once, preserve ambiguous data in recovery, and never replay
an envelope twice. Corrupt/unavailable session storage keeps recoverable
in-memory input and exposes the failure. Backout must not silently strand new
drafts in an older editor.

## Performance budgets

One health query at the existing 15-second interval; one event feed at 15
seconds visible / 60 seconds hidden, using the existing source identity checks.
Preset polling remains lazy at its existing five seconds only while controls are
open. Normal record views read on mount/focus/reconnect/accepted save and
explicit page load; do not add per-row polling. Training evaluation consumes
existing query snapshots and accepted-action notifications; it adds no
independent status polling endpoint. Abort obsolete reads. Render initially at
most 50 list rows per working view; offer explicit continuation without claiming
complete coverage. Foreground cue deduplication and capability failures remain
supported.

Compare the same normal/busy fixture before/after: request counts must not
exceed these ownership budgets; record render commits and browser CPU traces
over a 60-second idle period. Investigate any >10% sustained CPU increase
against the same machine/run conditions, preserving raw evidence rather than
asserting a generic performance win. Bounded resource owners must tear down
their checks.

## Lean guided training architecture

The user runs three computers, one being the aircraft production machine. Run
training as one separate local app instance/data root on a nonproduction
computer. The second clean import destination is temporary for T10 and
acceptance only. Do not build a permanent second stack, `app/training` service,
production training APIs, server progress/session registry or general
clock/replay persistence engine. The
[reuse map](../../design/issue-376/lean-training-reuse.md) identifies existing
APIs/helpers for every T01–T11 stage and the small fixture adaptations needed.

Use production frontend/backend images with a tooling-only training entrypoint,
following the existing `tools/acceptance/operator-journal/backend_fixture.py`
startup injection pattern. The launcher requires an explicit nonproduction root
marker and simulation configuration, binds loopback by default, uses private
volumes/data and disables real aircraft/provider discovery. It must not mount
operational data or switch a running live coordinator into simulation. Preserve
the actor Docker context/daemon; document setup and stop/reset commands. The
normal app does not gain plausible-but-unprovisioned training start actions:
Help explains how to start/open the local training instance if absent.

Reuse existing scenario/seed/raw-input/clock/ownership/archive tools. Add only a
prerequisite-only seed variant and a raw-input helper excluding the existing
fixture's seeded learner records and direct flight-phase restoration. Normal
flight-status/replay services and flight-event capture must create lifecycle and
archival outcomes. Production ETA/PoP adapters still compute predictions; the
guide never substitutes canned outcomes or frontend physics.

### Minimal identity and time seam

Existing normal replay changes Operator namespaces. The nonproduction fixture
entrypoint supplies a stable simulation ID for its private data root through the
existing binding/context injection seam, consistently for journal, model/PoP
context and source validation. No production `main.py` namespace policy changes.
A small test proves preflight, both replay legs, acknowledgments and receipts
remain visible; expose the actual replay ID separately. Reuse ScenarioClock /
EventsClock and persisted raw checkpoint files; no new TrainingClock class.

Test clock/observation/speed freshness with the real prediction/flight services.
Use either controlled raw telemetry + normal manual phase APIs or paced replay;
manual flight endpoints cannot edit an active replay that disallows it. Label
manual synthetic progression accurately. Raw phase overwrite in the acceptance
fixture is NOT evidence of lifecycle correctness. Reuse existing clock injection
for deterministic fixture tests rather than rewriting the flight/replay engine.

### Reset, progress and recovery

The launcher supports `start`, `stop`, `reset`, `import-start`, `import-stop`
for its exact owned project/root. Reset stops the training project, retains its
old root and creates a fresh sibling seed. It never deletes immutable history or
rewrites a live store. The guide's Reset mission displays the exact local
launcher command and explains the restart; Reset guide only resets guidance
progress and is separately labeled. This is an intentional tradeoff of
documented local commands for automatic hot reset, permitted by the deployment
clarification.

Next/back/skip/resume are in-product, dismissible guidance over real controls.
Keep browser progress keyed by fixture version, origin, store identity and
mission; revalidate outcomes from existing records/events/receipts/export state
on resume. Completion flags/Next clicks are not proof. Back does not rewind
time/records; Skip remains skipped. Keep cross-view drafts and frozen pending
commands under the same correct product owner used outside training.

Restart resumes guide and persisted records/raw fixture inputs, without
replaying learner writes. If a paced run cannot resume an exact frame,
explicitly offer restart of that flight segment using existing
preview/activation; do not claim an exact replay snapshot was restored. The
stable fixture journal ID remains the same. A mismatched root/store/fixture
version cannot silently resume old work.

Lost receipt/offline exercises reuse fixture transport interception/relay tools
or documented browser controls. Counterpart browser edits produce real
conflicts; retry goes to the real backend receipt. No production fault API is
needed. Guide controls that require a local command show that command instead of
pretending an automated effect occurred. File extraction is human-observed;
production acceptance independently checks actual ZIP/PDF contents and import
sentinels.

## Whole-mission curriculum

| Stage                            | Real learner work and evidence                                                                                                                                                                                                                  |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T01 Context and navigation       | Choose synthetic mission/scope; find Now/Next/Attention, UTC/unknown time, history and Help; distinguish active leg from draft target.                                                                                                          |
| T02 Preflight requirements       | Create planned call and VTC, edit/shift/cancel/reinstate, log ad-hoc/actual with unknown end, configure prep; inspect next separately from overdue.                                                                                             |
| T03 Conference and participation | Create bridge, establish, verify report, join/leave overlapping customers, reuse bridge, interrupt/restore new linked interval, close independently; inspect corrections/history and discrepancy.                                               |
| T04 Display and alerts           | Select a connected training Overview window, recenter with receipt, visibility/presets/history/boundaries; enable/mute foreground cues, inspect unsupported delivery and acknowledge eligible occurrence.                                       |
| T05 Airborne predictions         | Activate synthetic replay; normal flight lifecycle and position/speed feed production PoP/X/Ka ETA; inspect changing boundaries, fallback, staleness and unavailable timing without planned fallback.                                           |
| T06 Transport decisions          | Applied-only report during protected customer activity with nonblocking risk; intentions/requested/checked, multi-service rows, links/precision; another move versus correcting/check invalidation; history.                                    |
| T07 Issues and readiness         | Create/monitor/resolve/reopen, independent mitigation and functional/redundancy observations, follow-up set/change/clear, correct historic issue message without replaying lifecycle.                                                           |
| T08 Notes and recovery           | Observation, edit/remove/restore, paged immutable history/provenance; parked drafts across mission/scope, accepted/current-unreadable, uncertain exact retry, offline/reconnect, real 409 reconciliation and changed-store quarantine.          |
| T09 Between legs                 | Land/on-blocks through actual lifecycle; record ground gap with previous/next legs; activate leg 2 while prior records and drafts stay associated, then inspect completed/removed record branches.                                              |
| T10 Postflight and package       | Retrospective correction, unresolved handover, prepare/cancel/retry/download one ZIP, extract original customer PDF plus telemetry/journal/checksums; ordinary import in the second synthetic instance leaves its Operator sentinels untouched. |
| T11 Coverage branches            | Every remaining action/field/recovery in the parity matrix is linked to a short repeatable optional branch; completion distinguishes passed/skipped/unavailable. No undocumented Operator-visible control.                                      |

Actual training screens and guide screenshots are implementation acceptance
artifacts; existing prototype screenshots are not evidence of this subsystem.

## Full user guide and first-use acceptance

Ship accessible, maintained
`frontend/mission-planner/public/operator-help/guide.html` and
`quick-reference.html` with annotated images under its `images/` directory.
Repository entry pages `docs/operations/operator-user-guide.md` and
`docs/operations/operator-quick-reference.md` link to those canonical guides.
Vite packages these public assets unchanged; the offline Help route displays
them without a new Markdown renderer, CDN or duplicated guide text. Every guide
task links to a training stage/branch and a checked production-browser journey
at the shipped SHA. Cover setup, every record lifecycle/field,
status/time/source semantics, display tools, single ZIP, failure and recovery.
Explain reports versus physical control, bridge versus participation, and plan
import versus restoring Operator history.

First-use feedback specifically concerned knowing what the screen represents and
how to create/schedule calls and create/establish/verify/reuse/close bridges.
These need visible actions, useful empty states and a short guided orientation,
not only help prose. Run a first-time operator through the ENTIRE mission
without verbal coaching on desktop and mobile; record completion, help
retrieval, errors, recovery and elapsed/interactions. Fix preventable UI
confusion before expanding instructions. Automated replay is necessary but does
not certify that human run.

## Rollout, backout and acceptance

Develop reviewable tasks behind a private workspace switch; expose the complete
new shell atomically after parity gates, not a long-lived mixed workflow.
Preserve the prior page until cutover acceptance. No Operator SQL schema change
is planned; guide progress is versioned browser data and existing fixture
manifests/raw inputs remain under the private training root. Legacy clients
remain subject to existing expected-version/store authority.

Backout stops new submissions, reconciles accepted/uncertain commands, preserves
new draft/transaction envelopes and returns to the old page only with explicit
recovery access for retained work. Do not rewrite history or downgrade/delete
the Operator store. Training can be stopped independently; its private volumes
are never mounted into operational backout. Fixture endpoints/injection remain
confined to the explicit tooling entrypoint; normal application imports do not
register them. Keep exact candidate evidence and open-PR worktrees, but
terminate all task runtime resources after checks.

Release requires 100% parity matrix coverage; actual normal/busy timing against
the recorded baseline; exact-SHA Docker/Nginx browser journeys at all three
viewports; real-device keyboard/accessibility; two clients, restart, reset,
storage failure/invalid, conflict/lost receipt and backup/restore; real
predictors/ flight archival; learner and temporary import instances' isolation
and ZIP import; every guide procedure and an uncoached first-use full mission.
No aircraft certification.
