# Operator Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the approved mission workspace, complete hands-on synthetic
mission training, offline user guide and quick reference with every existing
capability preserved and verified.

**Architecture:** An application-level provider owns parked drafts, frozen
commands and the active editor while task views consume shared reads. Training
uses two isolated local deployments of the same app and existing simulation,
predictor, record and archive contracts, with guarded session orchestration. Cut
over the operational workspace once parity is complete.

**Tech Stack:** Existing React/TypeScript, TanStack Query, Radix,
FastAPI/Pydantic, SQLite Operator services, Python 3.11 backend selection, Node
22.22.2-compatible toolchain, Vitest, pytest, production Docker/Nginx and
Playwright. No new runtime library is planned.

**Spec:**
[Operator implementation specification](../specs/2026-10-18-operator-workspace-implementation.md).
Read it with the
[approved design contracts](../../design/issue-376/revision-2.md),
[first-use findings](../../design/issue-376/revision-3.md) and
[parity matrix](../../design/issue-376/audit.md).

## Global Constraints

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

## Review Focus

- A new replay run on leg activation must not hide preflight/training journal
  records; Task 7 tests the stable training namespace and normal-mode
  noninterference.
- Two new unsent calls plus a late receipt on another mission must not collide
  or discard newer input; Tasks 2–3 test unique draft IDs and submitted revision
  retirement.
- A first-time user must find create/schedule call and
  create/establish/verify/reuse/close conference without interpreting database
  entities; Tasks 5 and 11 test empty states and uncoached journeys.
- Reset/back/resume must not replay learner commands, rewind immutable history
  or claim a skipped stage passed; Tasks 7–9 test restart reconstruction and
  revisioned progress.
- Import practice and display presets can mutate global services; Tasks 7, 10
  and 12 test distinct origins/volumes, destination Operator sentinels and
  operational baseline hashes.

## Review gate and sequencing

Concept A is approved in the
[user approval record](https://github.com/bcl1713/starlink-dashboard/pull/382#issuecomment-6253399573).
The
[whole-system training clarification](https://github.com/bcl1713/starlink-dashboard/pull/382#issuecomment-6253414196)
is included here. This specification/plan, especially the two-instance training
architecture and stable session identity, requires separate review before any
product code. PR #382 remains the design/planning artifact; it is not a merge or
implementation approval.

Tasks are sequential reviewable commits, not separate partly shipped UIs. Tasks
2–6 build a hidden workspace; 7–10 supply required training; 11–12 supply
documentation/acceptance and atomic cutover. Rebase the implementation branch on
reviewed `origin/dev` in a new `.worktrees/` worktree after plan approval;
preserve this design worktree while its PR is open. Reconcile newer API/features
before executing Task 1. Native inline execution is recommended because
state/training interfaces are tightly coupled; confirm execution approach at the
plan handoff.

## File and interface map

All paths below are repository-relative. `F` is `frontend/mission-planner/src`;
`O` is `F/components/operator`; `B` is `backend/starlink-location`; `A` is
`B/app`. These aliases expand to exact paths; they are not new directories.
Existing paths are modified only where a task names them. Proposed names are
fixed interfaces for the implementer.

| Boundary         | Planned files and responsibility                                                                                                                                                                                                                 |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| App owner        | `F/components/operator/workspace/OperatorWorkspaceProvider.tsx`, `types.ts`, `draftRegistry.ts`, `commandRegistry.ts`, `legacyRecovery.ts`: persistent state outside replaceable routes                                                          |
| Shared reads     | `F/hooks/api/useOperatorJournal.ts`, `operatorReadSession.ts`, `useOperatorEvents.ts`: preserve request/identity semantics, move mutation ownership, avoid duplicated polling                                                                    |
| Shell/editor     | `O/workspace/OperatorWorkspace.tsx`, `WorkspaceAwareness.tsx`, `WorkspaceEditor.tsx`, `MissionContextChooser.tsx`, `WorkspaceHelp.tsx`, `workspace.css`: responsive context and explicit navigation                                              |
| Work views       | `O/workspace/{OperationsView,CommunicationsView,TransportView,IssuesView,HistoryView,ToolsView}.tsx`: contextual actions; existing typed editors/commands adapted rather than dropped                                                            |
| Training server  | `A/training/{models,settings,clock,session,context,fixtures,simulation,exercises,progress,api}.py`: isolated orchestration using existing app services                                                                                           |
| Training browser | `F/components/operator/training/{GuidedMission,TrainingStep}.tsx`, `trainingSteps.ts`, `useTrainingSession.ts`, `F/services/operator-training.ts`: real-control guidance and backend-validated progress                                          |
| Deployment       | `docker-compose.operator-training.yml`, `scripts/operator-training.sh`, `docs/development/operator-training.md`: private learner/import app instances; no operational volume reuse                                                               |
| Acceptance       | `tools/acceptance/operator-workspace/{run.py,compose.yml,fixtures.py,parity.json}` and `frontend/mission-planner/tests/e2e/operator-workspace.spec.ts`, `operator-training.spec.ts`, `operator-guide.spec.ts`: production narrative and evidence |
| Help             | `docs/operations/operator-user-guide.md`, `operator-quick-reference.md`, `frontend/mission-planner/public/operator-help/images/`; `F/pages/OperatorHelpPage.tsx`: packaged offline docs and checked screenshots                                  |

## Task 1: Record the complete baseline and executable parity inventory

**Files:** Create `tools/acceptance/operator-workspace/parity.json`,
`fixtures.py`, `frontend/mission-planner/tests/e2e/operator-workspace.spec.ts`;
reuse `tools/acceptance/operator-journal/{run.py,ownership.py}` and existing
Operator e2e files without replacing their assertions.

**Interfaces:** `parity.json` entries have stable `id`, source/component/API,
action/field, baseline journey, target journey, guide section, training stage,
expected evidence and status. `fixtures.py::build_workspace_fixture(seed: str)`
produces only synthetic raw inputs and planned prerequisites; no expected
predictor output. Later tasks refer to those IDs.

- [ ] Expand EVERY audit row into explicit create/edit/remove/restore/history,
      field and failure checks. Add Help/guide/training controls. No unchecked
      row is excluded as cosmetic, legacy or optional-provider behavior.
- [ ] Run existing production baseline against normal and five-customer busy
      fixtures at all three viewports; capture task activations, typing/selector
      operations, elapsed time, mis-selection and recovery separately. Preserve
      exact source SHA, inputs, PDF/ZIP digests and Overview/Configuration
      baselines.
- [ ] Write the new narrative tests against expected approved destinations;
      confirm they fail on current UI for destination/flow, not setup/network
      errors.
- [ ] Commit baseline fixture, parity IDs and evidence index. No product
      changes.

## Task 2: Persistent unsent draft registry and legacy recovery

**Files:** Create `O/workspace/{types.ts,draftRegistry.ts,legacyRecovery.ts}`
and `draftRegistry.test.ts`; adapt existing `useOperatorIssueDraft.ts` and
`useOperatorTransportDraft.ts` through explicit migration adapters.

**Interfaces:** Export `DraftTarget`, `DraftEnvelope` as specified;
`createDraft(target: DraftTarget, input: OperatorInput): DraftEnvelope`,
`parkDraft(envelope: DraftEnvelope): void`,
`resumeDraft(draftId: string): DraftEnvelope | null`,
`discardDraft(draftId: string): void`,
`recoverLegacyDrafts(storage: Storage, identity: string): RecoveryResult`.
`RecoveryResult` contains `migratedDraftIds: string[]`,
`quarantinedKeys: string[]`, and `errors: {key: string; message: string}[]`.
Typed input uses existing `OperatorInput`; persistence failures are results,
never hidden exceptions.

- [ ] Write `two_new_calls_have_distinct_ids`,
      `mission_scope_switch_keeps_target`,
      `legacy_pending_is_not_an_unsent_draft`,
      `corrupt_or_full_storage_retains_memory` and
      `edited_after_submit_keeps_new_revision`; assert full
      identity/leg/correction targets and explicit migration/quarantine,
      including duplicate legacy keys.
- [ ] From frontend run
      `timeout --kill-after=10s 10m npm run test:unit -- src/components/operator/workspace/draftRegistry.test.ts`;
      confirm meaningful failures.
- [ ] Implement envelopes/registry and one-time legacy migration with schema 1;
      remove a legacy key only after the replacement is durably retained. Do not
      make session storage cross-tab sync or retain secrets in logs.
- [ ] Run the focused tests to green, including storage failure on write/retire.
      Commit the registry/adapters/tests.

## Task 3: Hoist frozen commands and editor ownership above routes

**Files:** Create
`O/workspace/{commandRegistry.ts,OperatorWorkspaceProvider.tsx}` and
`commandRegistry.test.tsx`; modify `F/App.tsx`,
`F/hooks/api/{useOperatorJournal.ts,operatorReadSession.ts}`; preserve existing
identity/recovery tests and add route-change cases.

**Interfaces:** `useOperatorWorkspace()` exposes `openDraft(draftId)`,
`submitDraft(draftId): Promise<void>`, `retryExact(commandId): Promise<void>`,
`rereadAndReconcile(commandId): Promise<void>`, selected editor and named tray
states. `PendingEnvelope` contains the spec's exact frozen command and revision.
Record writes still call `services/operator.ts` with existing headers/types.

- [ ] Write tests for route unmount to Missions during save, lost receipt retry
      byte/key/time identity, late receipt on another mission,
      accepted/current-read failure, 409 latest-read failure, store rotation,
      storage rejection before send, and receipt retirement that preserves newer
      draft input.
- [ ] Run focused registry plus existing `useOperatorJournal.test.tsx` and page
      identity/recovery tests under a 10-minute wall limit; verify red cases.
- [ ] Mount one provider outside replaceable application routes; serialize per
      identity/mission/type; reuse existing health/query keys and recovery
      authority. Keep pending envelopes during navigation; no optimistic Saved
      or auto retry.
- [ ] Run tests to green and inspect request counts for duplicate mutation
      owners. Commit the provider and hook adaptation without enabling the new
      page.

## Task 4: Mission shell, awareness and mobile editor

**Files:** Create
`O/workspace/{OperatorWorkspace,WorkspaceAwareness,WorkspaceEditor,MissionContextChooser}.tsx`,
`workspace.css`, `WorkspaceAwareness.test.tsx`, `WorkspaceEditor.test.tsx`;
modify `F/pages/OperatorJournalPage.tsx` only to select the hidden candidate
shell.

**Interfaces:** Components consume `useOperatorWorkspace()` and existing event/
mission reads. `WorkspaceAwareness` accepts a validated snapshot/coverage and
named future requirement, not raw counters guessed from loaded partial pages.
`WorkspaceEditor` renders the registry-owned typed editor with Save/Keep draft/
discard and receipt status. Mission chooser never activates a leg implicitly.

- [ ] Test five customers/three risks/overdue versus future requirement, unknown
      times/coverage, missing mission, disabled/unavailable store, long labels,
      explicit scope selectors, and live-unavailable without planned fallback.
- [ ] Add browser cases for landscape keyboard/visual-viewport resize, inline
      validation, focus preservation during customer/event changes, 44×44
      targets, no horizontal overflow, one scroll body and visible Next/actions.
- [ ] Run focused Vitest/browser cases red, then implement the approved bounded
      rail/strip and editor layout with actual source-basis details and correct
      focus return. Keep the existing Overview theme/display passive.
- [ ] Run focused checks green; capture all requested normal/busy/error
      viewports from real app data. Commit the hidden shell.

## Task 5: Communications and operational quick actions

**Files:** Create `O/workspace/{OperationsView,CommunicationsView}.tsx` and
tests; adapt
`O/{OperatorCommunications,CallEditor,CallList,OperatorConferences,ConferenceEditor,ConferenceCard,ParticipationEditor,ParticipationRow}.tsx`
and existing `conferenceCommands.ts`, `callTiming.ts` integrations.

**Interfaces:** Views call provider draft/submit methods; direct lifecycle
intents build the EXISTING `conferenceCommand`, `joinCommand`, `leaveCommand`,
`resumeCommand` commands from the selected latest record. Creation buttons open
new typed drafts; no conference provisioning/call-control API is introduced.

- [ ] Test empty-state Create call/Create conference discovery; planned versus
      actual call, prep default 10/zero/unknown, signed shift preserving
      duration, cancel/reinstate/remove/restore, and readable relationship
      lookup.
- [ ] Test establish/verify, unknown customer join, overlap/reuse, leave without
      bridge teardown, interrupt/restore NEW interval versus tombstone
      restoration, and closed bridge/connected customer discrepancy. Assert
      immutable history.
- [ ] Run relevant existing/new Communications/Conferences unit and browser
      tests red; implement the concise first-use orientation and nearby actions
      using registry ownership. Operations combines next prep and real modeled
      risk.
- [ ] Run all Communications/Conferences checks green; demonstrate the user's
      specific create/schedule/use/reuse/close paths on desktop and mobile.
      Commit.

## Task 6: Transport, issues, notes, history, tools and mission navigation

**Files:** Create
`O/workspace/{TransportView,IssuesView,HistoryView,ToolsView}.tsx` and tests;
adapt existing Transport/Issue/Capability/Journal editors/lists/history,
`OperatorDisplayTools.tsx`, `OperatorEventFeed.tsx`,
`OperatorAlertSettings.tsx`. Keep
`components/missions/{ExportDialog,ImportDialog}.tsx` authoritative.

**Interfaces:** Same provider commands and existing
record/event/Overview/mission services. History filters loaded records with
coverage and loads full paged revisions; it does not invent a backend full-text
search endpoint.

- [ ] Test applied-only Save with protected activity/advisory and no gate;
      independent intended/requested/check, 32 service limit, precision, another
      move versus correction, and prior check invalidation/reference restore
      rules.
- [ ] Test issue monitor/resolve/reopen/mitigation/follow-up, separate
      functional/ redundancy observation ages, historical message correction
      without lifecycle replay; note scope/times/label, edit/remove/restore and
      immutable provenance.
- [ ] Test eligible acknowledgment, cue dedup/capability failure, shared
      settings/ presets and version conflict, same-browser recenter target
      loss/multiple peers/ receipt timeout, and navigation to the existing ZIP
      workflow with drafts parked.
- [ ] Run the corresponding existing suites/new view tests red; implement the
      unified views and full disclosed fields. Run to green; update parity IDs
      with evidence. Commit. Do not expose incomplete candidate views to
      ordinary users.

## Task 7: Isolated training deployment, session identity and deterministic replay

**Files:** Create
`A/training/{models,settings,clock,session,context,fixtures,simulation,api}.py`,
`B/tests/training/test_training_runtime.py`,
`docker-compose.operator-training.yml`, `scripts/operator-training.sh`,
`docs/development/operator-training.md`; modify `B/main.py` to register guarded
training dependencies, not normal-mode behavior.

**Interfaces:** `TrainingClock.now()/monotonic()/advance(seconds)` implements
existing injected clock contracts. `TrainingSession` is the spec manifest;
`TrainingSessionService.start(key): TrainingSession`,
`status(): TrainingSession`,
`advance(session_id, expected_revision, checkpoint, key): TrainingSession`,
`reset(session_id, expected_revision, key): TrainingSession`. GET session and
start/advance/reset routes use typed models, explicit instance/session authority
and existing service admission. Stable namespace is session UUID; paced run ID
remains a separate field. No global environment-mode switch from a browser.

- [ ] Write tests rejecting normal/live mode, foreign IDs, operational paths,
      missing marker, invalid stores and reset during uncertain writes. Assert
      preflight + leg 1 + leg 2 + postflight records share the training
      namespace, reset creates a new namespace and normal replay binding remains
      unchanged.
- [ ] Test clock/telemetry freshness alignment, deterministic route progression
      through existing replay/flight/predictor code, restart reconstruction with
      new replay ID but same journal receipts, plan fingerprint mismatch
      recovery, and idempotent concurrent starts/resets. No canned event
      payloads or SQL edits.
- [ ] From backend run
      `timeout --kill-after=10s 10m uv run --with-requirements requirements-dev.txt python -m pytest tests/training/test_training_runtime.py`
      red.
- [ ] Implement the guarded adapter and explicit fresh simulation-store
      initialization, preserving existing-store failure semantics. Compose
      learner and clean import destination use the production images,
      independent origins/ private volumes and offline synthetic inputs; no
      operational mounts/discovery.
- [ ] Run tests green and an isolated exact-SHA deployment check. Compare all
      mutable volume mounts and instance identities with the live installation;
      prove display/config changes and reset cannot cross them. Stop the task
      stack and verify resources gone. Commit runtime/profile/setup docs.

## Task 8: Training exercises and authoritative progress

**Files:** Create `A/training/{exercises,progress}.py`,
`B/tests/training/{test_training_exercises,test_training_progress}.py`; extend
training API/models from Task 7 only.

**Interfaces:** `exercise(session_id, expected_revision, kind, target, key)`
supports allowlisted `lost_receipt`, `counterpart_conflict`, `stale_inputs`,
`missing_provider` effects.
`progress(session_id, expected_revision, stage_id, action, key)` accepts
next/back/skip; evidence evaluation returns passed/skipped/
incomplete/unavailable and named unmet outcomes. Ordinary learner writes still
use existing record services/API, never the progress endpoint.

- [ ] Test real persisted command with one suppressed acknowledgment and exact
      replay receipt, actual counterpart version conflict, foreign target
      rejection, effect expiry and no fault middleware in normal deployment.
- [ ] Test progress evaluates real versions/events/export artifacts, skip never
      becomes pass, back never rewinds data/time, reset rejects foreign/pending
      work, restart never replays learner writes, and concurrent progress
      receives 409.
- [ ] Run those named pytest files red under the backend command from Task 7;
      implement narrow training-only effects and atomic progress manifests.
- [ ] Run tests green; verify old session history remains immutable and the
      clean import instance's Operator sentinel is unchanged. Commit.

## Task 9: Whole-system hands-on guide in the real UI

**Files:** Create `F/services/operator-training.ts`,
`F/components/operator/training/{GuidedMission.tsx,TrainingStep.tsx,trainingSteps.ts,useTrainingSession.ts}`
and tests; modify `O/workspace/WorkspaceHelp.tsx`, existing same-app route
targets with stable accessible `data-training-target` anchors, and `F/App.tsx`.

**Interfaces:** `operatorTrainingApi` mirrors Task 7–8 typed routes without
changing the operational API base. `useTrainingSession()` supplies one validated
session/progress read owner. `trainingSteps` maps stage/branch ID to
instruction, real route/target, required evidence and related guide section.
GuidedMission renders dismissible current stage, next/back/skip/resume/reset,
never duplicate record forms. The live Help entry navigates to configured
training origin.

- [ ] Test Help discovery, absent training setup instructions, unmistakable
      Training context, real-controller targets, first-use calls/conferences,
      navigation while drafts/pending work are retained, and stage mismatch
      recovery.
- [ ] Test every T01–T11 stage/branch from the spec and every parity ID has a
      real target/evidence/guide mapping. Include Overview window + foreground
      cues, all record lifecycle branches, typed UTC/unknown fields and actual
      ZIP import.
- [ ] Test next/back/skip/resume/reset revision handling, hidden/stale session
      reads, mobile keyboard/assistive focus and training-client offline
      exercise without service worker/network reconfiguration. No
      fake-completion flags.
- [ ] Run new focused Vitest and real-browser training tests red; implement
      guide controls and raw transport failure simulation gated to training
      instance. Apply the specified five-second visible/60-second hidden read
      budget.
- [ ] Run to green across three viewports; verify full navigation/context and
      saved input survive dismiss/resume/restart. Commit required training UI.

## Task 10: Full production narrative and archive transfer acceptance

**Files:** Create `tools/acceptance/operator-workspace/{run.py,compose.yml}` and
`frontend/mission-planner/tests/e2e/operator-training.spec.ts`; extend existing
`playwright.operator-journal.config.ts` with explicit owned-origin selectors for
the new tests. Reuse production archive/export/import assertions, not a new ZIP.

**Interfaces:** Runner takes exact candidate SHA, owned origins/project/volumes
and evidence root, emits parity IDs, images, timings, source hashes and cleanup
status. It must reject a dirty/inexact candidate or shared runtime identity.

- [ ] Add the complete spec curriculum plus failure branches to
      production-browser acceptance. Include normal and high-workload versions
      of find next, add/log/ reschedule call, participation/reuse, applied-only
      report, issues/correction, observation, recenter, prior decision and
      prepare/export/import journeys.
- [ ] Use real predictors and lifecycle/telemetry archival. Extract original PDF
      path/content and validate complete
      journal/history/telemetry/checksums/timing. Import through actual Missions
      UI in the separate synthetic destination; compare destination Operator
      sentinels before/after, including nonempty store.
- [ ] Exercise two clients, actual network loss, lost receipt, 409, store
      identity, invalid/unavailable storage, restart/backup/restore, training
      reset, global settings isolation and unsaved mission/leg switch. Preserve
      traces, not only screenshots.
- [ ] Record resource ownership before launch; preserve actor Docker context and
      `DOCKER_HOST`. Use `timeout --kill-after=10s 60m` around the full runner;
      signal/ exit handlers close contexts and gracefully terminate/reap owned
      workers, Compose containers/networks/private volumes. Verify host
      processes/listeners and resource absence after success/failure/timeout
      before retrying.
- [ ] Run this gate against a committed candidate; fix failures through focused
      red/green cycles, then rerun only affected journeys plus final narrative
      where changed behavior warrants it. Commit runner and sanitized evidence
      manifest.

## Task 11: Finished guide, quick reference, Help and uncoached first use

**Files:** Create `docs/operations/operator-user-guide.md`,
`operator-quick-reference.md`, canonical accessible HTML
`frontend/mission-planner/public/operator-help/{guide,quick-reference}.html`,
annotated images under `frontend/mission-planner/public/operator-help/images/`,
`F/pages/OperatorHelpPage.tsx`,
`frontend/mission-planner/tests/e2e/operator-guide.spec.ts`; modify `F/App.tsx`
and `O/workspace/WorkspaceHelp.tsx`. Package guide content/images into the
existing Vite build for offline access; do not link to a required web service.

The HTML is the canonical full guide/quick reference; Markdown files are
repository entry points, not duplicate prose. Help displays the packaged public
HTML with a titled frame and accessible navigation. No runtime Markdown
compiler, new dependency or production Docker build-context change is needed.

**Interfaces:** Canonical HTML guide sections use stable IDs linked from
`trainingSteps`; each parity entry names guide task and tested journey. Help
supports User guide, Quick reference, Guided mission walkthrough and reopenable
orientation. It must preserve current/next context or a clear return to the
retained operational editor.

- [ ] Write guide procedures while running the actual shipped controls, covering
      every section of the spec. Annotate real desktop/mobile screenshots;
      include setup, all UTC/status/field semantics, lifecycle, display/alerts,
      one ZIP and recovery. Explain what reports/bridge establishment/import do
      not do.
- [ ] Add browser checks that Help/section/training links work offline,
      referenced labels/targets/outcomes match, quick reference prints legibly,
      examples are synthetic, and each procedure has evidence at the same
      candidate SHA.
- [ ] Conduct first-time full-mission desktop/mobile sessions without verbal
      coaching. Record completion/time/interactions/confusion/recovery and guide
      use. Specifically test understanding and discovery of call scheduling and
      bridge creation/establish/test/reuse/close. Automated tests do not stand
      in for people.
- [ ] Fix confusing UI/labels first, then guide wording; rerun affected
      first-use tasks and browser assertions. Keep this gate open if no
      first-time user is available; do not mark the feature finished. Commit
      guide/Help/evidence.

## Task 12: Final parity, performance, accessibility, cutover and backout

**Files:** Modify `F/pages/OperatorJournalPage.tsx` and `F/App.tsx` to enable
the whole approved workspace; update `docs/development/operator-training.md`,
`tools/acceptance/operator-workspace/parity.json` and release/backout evidence.

- [ ] Require all parity IDs passed with source/API/browser/guide/training
      evidence; optional-provider branches must be explicitly tested, not
      deleted or silently skipped.
- [ ] Run the canonical `./tools/verify static`, `backend`, `frontend` tiers
      with exact `ACCEPTANCE_POLICY_BASE_SHA` and suitable explicit wall limits
      (10/30/20 minutes); use `./tools/verify all` for the final candidate where
      CI requires it.
- [ ] Run exact-SHA production acceptance, real-device keyboards, keyboard-only
      / screen-reader focus and reading order, touch dimensions/overflow,
      foreground cue capabilities, training restart/reset/import isolation and
      full guide checks.
- [ ] Compare actual baseline/new timings and errors; explain any increase.
      Check specified polling/render limits and 60-second CPU traces; verify no
      regression to Overview, Missions, Configuration, original PDF or archival
      contracts.
- [ ] Rehearse backout with pending/parked drafts, not just clean state: stop
      new submissions, reconcile or quarantine uncertain commands, retain access
      to new envelopes, revert the whole shell without rewriting the store.
      Training stops independently; operational data/settings remain untouched.
- [ ] Enable candidate shell atomically, rerun affected cutover journeys,
      preserve acceptance SHA/checks/evidence, tear down all task resources,
      push implementation PR to dev for its own review. Do not merge based on
      design approval alone.

## Coverage crosswalk

| Parity area                                                                 | Main tasks | Training     | Guide / acceptance |
| --------------------------------------------------------------------------- | ---------- | ------------ | ------------------ |
| Mission/leg/scope, brief, overdue/future, freshness                         | 2–4        | T01, T09     | 10–12              |
| Calls planned/actual, prep/shift/duration/status/relationships              | 3, 5       | T02          | 10–12              |
| Call correction/remove/restore/history                                      | 3, 5–6     | T02, T11     | 10–12              |
| Conference lifecycle/configuration/verification                             | 3, 5       | T03          | 10–12              |
| Participation intervals/interruption/restore/discrepancy                    | 3, 5       | T03          | 10–12              |
| Protection, overlapping activity and fallback context                       | 4–6        | T03, T05–T06 | 10–12              |
| Issues lifecycle/mitigation/follow-up/capability/old-message correction     | 3, 6       | T07          | 10–12              |
| Timeline/cues/acknowledgment/source history                                 | 4, 6       | T04–T05      | 10–12              |
| Live ETA/PoP, stale/unavailable, flight archival                            | 4, 7–10    | T05, T09     | 10–12              |
| Multi-service independent reports/check invalidation/new move/correction    | 3, 6       | T06          | 10–12              |
| Observation, all timing/scope/label fields, tombstones and immutable audit  | 2–3, 6     | T08, T11     | 10–12              |
| Display groups/presets/history/boundaries/recenter, global conflicts        | 6–7        | T04          | 10–12              |
| One ZIP/PDF/telemetry/journal, preparation/failure/cancel/import boundaries | 6, 7, 10   | T10          | 10–12              |
| Drafts/pending/409/epoch/receipt/reread/invalid storage/two clients         | 2–3, 7–10  | T08, T11     | 10–12              |
| Help/orientation/full manual/quick reference and every visible control      | 5, 9, 11   | T01–T11      | 10–12              |

## Effort, risks and completion gate

Planning estimate: **30–45 engineer-days**, excluding reviewer turnaround and
availability of first-time users/devices. Indicative allocation: baseline/owners
6–9; shell/views/lifecycle 7–10; isolated training runtime/exercises/curriculum
9–14; guide/first-use/production acceptance/backout 8–12. This is a range, not a
delivery date or authorization to reduce scope. Training is a required part of
the estimate; it is not deferred to another issue.

The largest risks are replay/Operator namespace and clock alignment, legacy
draft migration and cross-route receipts, offline predictor inputs and full ZIP
isolation. Tasks 2–3 and 7 gate dependent work early. If existing replay
services cannot reconstruct a checkpoint through their injected dependencies,
stop for plan revision with evidence; do not add a second engine or fake
successful resume.

No product code has been written for this plan. Completion requires separate
plan approval, implementation review, all parity/training/guide checks, actual
timing and uncoached first-use evidence, exact candidate checks and resource
teardown. Merely passing the HTML preview checks cannot satisfy any of those.
