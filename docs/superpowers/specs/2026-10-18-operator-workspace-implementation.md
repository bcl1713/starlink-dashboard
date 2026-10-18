# Operator workspace implementation specification

Status: specification and plan review requested; no product changes authorized
by this document.
[Concept A approval](https://github.com/bcl1713/starlink-dashboard/pull/382#issuecomment-6253399573)
permits planning. The
[training scope clarification](https://github.com/bcl1713/starlink-dashboard/pull/382#issuecomment-6253414196)
requires the entire Operator system, not just calls/conferences. Both apply to
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

Adapt `useOperatorJournal.ts` into shared owners without changing API headers or
expected-version semantics. Existing pending storage is opt-in for issue,
capability and transport callers; unsent call/conference/note recovery is new
frontend work. Read legacy draft/pending keys once, preserve ambiguous data in
recovery, and never replay an envelope twice. Corrupt/unavailable session
storage keeps recoverable in-memory input and exposes the failure. Backout must
not silently strand new drafts in an older editor.

## Performance budgets

One health query at the existing 15-second interval; one event feed at 15
seconds visible / 60 seconds hidden, using the existing source identity checks.
Preset polling remains lazy at its existing five seconds only while controls are
open. Normal record views read on mount/focus/reconnect/accepted save and
explicit page load; do not add per-row polling. Training status polls once per
five seconds only while its guide is visible (60 seconds hidden), with immediate
invalidation after stage actions. Abort obsolete reads. Render initially at most
50 list rows per working view; offer explicit continuation without claiming
complete coverage. Foreground cue deduplication and capability failures remain
supported.

Compare the same normal/busy fixture before/after: request counts must not
exceed these ownership budgets; record render commits and browser CPU traces
over a 60-second idle period. Investigate any >10% sustained CPU increase
against the same machine/run conditions, preserving raw evidence rather than
asserting a generic performance win. Bounded resource owners must tear down
their checks.

## Guided training architecture and tradeoff

Training is a required shipped subsystem, not an HTML tour or optional
follow-up. Use two isolated local instances of the same production
frontend/backend images: the learner instance and a clean synthetic import
destination. They have separate origins, private
mission/Operator/settings/route/telemetry volumes and simulation configuration;
neither mounts operational data or connects to real hardware. They are an
explicitly provisioned local Compose profile, not a server launched from an
ordinary user request. Production Help links to the configured training origin
via full-page/new-tab navigation; it never silently switches the live client's
API base. Unprovisioned training has clear setup instructions and no
working-looking Start button; release acceptance requires provisioning it.

This costs two additional local app stacks while training is in use, additional
isolated storage and a deployment/setup procedure. It avoids contaminating
global Overview settings, mission/telemetry or exports on the operational
installation. A shared-process training mode would require namespacing every
mutable global service and is rejected for this release. This architecture
addition needs plan review, even though Concept A itself is approved.

New training orchestration APIs are registered only with explicit training
deployment configuration AND coordinator simulation mode. They reject a live
mode, unknown instance, foreign session/mission/store or unsupported scenario;
ordinary record APIs remain unchanged. Seed raw synthetic mission/routes,
satellite/coverage/PoP inputs and training prerequisites; never seed completed
learner actions or canned predictor outputs. Reuse the existing mission APIs,
`SimulationRunRuntime` / `SimulationRunService`, flight state, production live
timing/PoP adapters and export code. Acceptance-only monkey patches are
references, not shipped runtime imports.

### Identity, clock, reset and restart

Current `main.py::_operator_context` binds the Operator namespace to the active
paced replay run, and `OperatorRuntimeBinding` opens existing stores without
initialization. A training mission spanning preflight and two legs cannot ignore
this: activating a replay must not hide prior training records.

In the guarded training deployment only, the current training session UUID is
the stable Operator simulation namespace. Pass it consistently to Operator and
PoP/model source context; expose the actual paced replay run ID separately in
training status. Normal simulation/live binding behavior is unchanged. Each
session explicitly initializes ONLY its own new simulation store using existing
maintenance/store admission primitives; invalid existing stores fail rather than
being reinitialized. Preflight, both legs and postflight share that namespace.

Use a persisted `TrainingClock` implementing Operator `Clock` and the existing
replay runtime's injected monotonic/UTC callables, at pacing multiplier 1.
Freeze between explicit synthetic progression actions so trainees have time to
operate. Advance only nonnegative deterministic offsets; then collect normal
replay/coordinator telemetry and existing flight lifecycle. Align observation/
speed timestamps to the same clock. Planned times, freshness, actual validation,
notifications, snapshot expiry and recorded UTC use that common timeline. Do not
add frontend ETA physics or replace phases/events with prescribed answers.

Persist session/fixture version, clock offset, mission IDs, namespace/store
identity, stage/checkpoint, replay-plan identity, actual replay ID and resolved
evidence references. On restart rebuild replay through its supported plan/start
and injected clock progression; a new ephemeral replay ID is explicit, but the
training journal namespace and receipts remain unchanged. Revalidate stages
against current records; never replay learner writes from completion flags. If
deterministic reconstruction cannot match stored plan/input identity, stop with
recovery/reset guidance rather than claim resumed flight state.

Reset creates a new session, namespace, mission IDs and progress; it does not
rewrite/delete immutable history, flush live settings or restore a live backup.
Retain old sessions in private training storage subject to its explicit storage
capacity; capacity failure is visible. Reset is an explicit training action and
cannot proceed while an old outcome is uncertain; reconcile it or deliberately
leave it quarantined in the old session. Back changes guidance only, not time or
records. Skip marks the stage skipped (incomplete), never successful.

### Training APIs and progress

Proposed `/api/v2/operator/training` routes: GET `/session`; POST `/sessions`;
POST `/sessions/{id}/progress`; POST `/sessions/{id}/advance`; POST
`/sessions/{id}/exercise`; POST `/sessions/{id}/reset`. Mutations require
training-instance ID, expected session revision and idempotency key; admission
rechecks coordinator mode and owned paths/IDs. Progress is stored separately
from the immutable Operator journal and supports conflict/reload recovery. A
requested stage completion is validated from real current/revision/event/export
evidence, not a frontend click flag. Reset itself is idempotent and
transactional.

The dismissible guide uses real route links/stable accessible target IDs, next,
back, skip, resume and reset; it does not duplicate forms. It pins concise
progress outside Now/Next, keeps mobile focus/keyboard space, and names any
inaccessible target instead of guessing coordinates. Documentation can be read
when training is unavailable. An observation/decision is recorded through the
same application controllers as operational use, with unmistakable Training
context.

Exercises are explicitly labeled simulation effects. Lost receipt performs a
real training command and once suppresses its acknowledgment; retry returns the
same receipt/record. Conflict uses a real counterpart edit and actual 409.
Offline exercise rejects requests at the training client's transport boundary
without inventing success or changing the host network. Stale/missing provider
exercises alter raw owned inputs/freshness only. Allowlisted effects cannot
target live or foreign records, and expire after the named session exercise.
None run in normal deployments. Browser acceptance also tests genuine network
interception/loss.

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
is planned; training progress is a separate versioned file under private
training data. Legacy clients remain subject to existing expected-version/store
authority.

Backout stops new submissions, reconciles accepted/uncertain commands, preserves
new draft/transaction envelopes and returns to the old page only with explicit
recovery access for retained work. Do not rewrite history or downgrade/delete
the Operator store. Training can be stopped independently; its private volumes
are never mounted into operational backout. Scope-only training endpoints stay
absent from a normal deployment. Keep exact candidate evidence and open-PR
worktrees, but terminate all task runtime resources after checks.

Release requires 100% parity matrix coverage; actual normal/busy timing against
the recorded baseline; exact-SHA Docker/Nginx browser journeys at all three
viewports; real-device keyboard/accessibility; two clients, restart, reset,
storage failure/invalid, conflict/lost receipt and backup/restore; real
predictors/ flight archival; both training instances' isolation and ZIP import;
every guide procedure and an uncoached first-use full mission. No aircraft
certification.
