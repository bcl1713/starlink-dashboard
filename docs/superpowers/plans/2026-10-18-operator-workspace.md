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
uses one separate app/data root on a nonproduction computer and existing
fixture, simulation, predictor, record and archive contracts. A clean import
target is temporary for that lesson; no general training orchestration backend
is planned. Cut over the operational workspace once parity is complete.

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
  or claim a skipped stage passed; Tasks 7–9 test persisted fixture restart,
  explicit segment-restart limits and identity-scoped browser progress.
- Import practice and display presets can mutate global services; Tasks 7, 10
  and 12 test distinct origins/volumes, destination Operator sentinels and
  operational baseline hashes.

## Review gate and sequencing

Concept A is approved in the
[user approval record](https://github.com/bcl1713/starlink-dashboard/pull/382#issuecomment-6253399573).
The
[whole-system training clarification](https://github.com/bcl1713/starlink-dashboard/pull/382#issuecomment-6253414196)
is included here. The
[spec/plan approval](https://github.com/bcl1713/starlink-dashboard/pull/382#issuecomment-6253561956)
authorizes cohesive staged execution. The subsequent
[user clarification](https://github.com/bcl1713/starlink-dashboard/pull/382#issuecomment-6253613063)
simplifies deployment and prioritizes reuse; this amendment applies it directly.
See the [lean reuse map](../../design/issue-376/lean-training-reuse.md) for the
launcher/reset tradeoff and exact T01–T11 capabilities. No new generalized
training subsystem is authorized or required. PR #382 remains a design/planning
artifact, not implementation/merge/release evidence.

Tasks are sequential reviewable commits, not separate partly shipped UIs. Tasks
2–6 prioritize a complete usable workspace by adapting existing components; 7–10
supply required training; 11–12 supply documentation/acceptance and atomic
cutover. Rebase the implementation branch on reviewed `origin/dev` in a new
`.worktrees/` worktree under the recorded plan approval; preserve this design
worktree while its PR is open. Reconcile newer API/features before executing
Task 1. Use one cohesive inline implementation context with staged reviewable
commits, as recommended in the recorded execution review. No renewed choice of
execution method is needed for this clarification.

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
| Training fixture | `tools/training/operator-mission/{backend.py,scenario.py,control.py}` and existing `tools/acceptance/operator-journal` helpers: prerequisite seed, raw inputs and thin binding/clock seam; no `app/training` package                             |
| Training browser | `F/components/operator/training/{GuidedMission,TrainingStep}.tsx`, `trainingSteps.ts`, `trainingProgress.ts`: real-control guidance and actual-evidence evaluation using existing query/services                                                 |
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

**Interfaces:** Preserve the existing hook save/retry/reconcile implementation;
hoist its owners and expose thin registry adapters rather than implement another
write-state engine. `useOperatorWorkspace()` exposes `openDraft(draftId)`,
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

## Task 7: Single-instance training fixture and early namespace/time proof

**Files:** Create
`tools/training/operator-mission/{backend.py,scenario.py,control.py}`,
`tools/tests/test_operator_training_fixture.py`,
`docker-compose.operator-training.yml`, `scripts/operator-training.sh`,
`docs/development/operator-training.md`. Selectively adapt
`tools/acceptance/operator-journal/{seed.py,scenario.py,model_inputs_fixture.py}`
with defaults preserving current acceptance. Do not modify normal `main.py` or
create `app/training` APIs/services.

**Interfaces:** Launcher commands `start`, `stop`, `reset`, `import-start`,
`import-stop` take an explicit marked nonproduction data root/project. Tooling
`scenario.seed_prerequisites(root)` creates fictional mission/routes/planned
requirements, not completed learner actions.
`control.apply_checkpoint(root, checkpoint_id)` applies predefined raw
position/speed/freshness/clock values through existing fixture helpers. The thin
fixture entrypoint uses the existing binding/context seam with a stable
root-scoped simulation ID; existing ScenarioClock/EventsClock and persisted
input files remain the clock authority.

- [ ] Write tests rejecting live mode/unmarked roots and operational volume
      mounts; assert actual preflight/leg 1/leg 2 records, acknowledgments and
      receipts share the fixture journal namespace while normal runtime behavior
      is unchanged.
- [ ] Test raw inputs feed production ETA/PoP and normal flight/replay services,
      not the fixture's direct phase restore; clock/sample freshness align;
      restart retains records/raw checkpoint inputs without replaying learner
      writes. Test actual preview/activation, leg changes and documented
      segment-restart limits.
- [ ] From backend run
      `timeout --kill-after=10s 10m uv run --with-requirements requirements-dev.txt python -m pytest ../../tools/tests/test_operator_training_fixture.py`
      red.
- [ ] Adapt existing seed/raw helpers only as needed; inject stable fixture
      context locally, not through a new production policy. Start one private
      learner stack with normal production images and the explicit fixture
      module. Bind loopback, disable aircraft discovery, preserve Docker
      daemon/context and document setup.
- [ ] Implement CLI reset as owned stop + retained old root + fresh sibling
      seed; refuse ambiguous/unowned roots and never delete operational data.
      Import target is a separate temporary project using existing
      archive-destination patterns.
- [ ] Run tests green and one exact-SHA fixture integration proof before
      investing in guidance. If the seam fails, report the smallest evidenced
      change required; do not expand into the former session/clock/orchestration
      subsystem. Teardown task resources and commit tooling/setup evidence.

## Task 8: Whole-mission steps, progress and recovery using existing contracts

**Files:** Create
`F/components/operator/training/{trainingSteps.ts,trainingProgress.ts,trainingProgress.test.ts}`;
reuse existing record/event/export/simulation services and tooling control/relay
patterns. No training status/progress/command API or extra polling owner.

**Interfaces:** `TrainingProgress` schema 1 contains fixture version, origin,
store identity, mission ID, current stage, visited/skipped IDs and explicitly
manual evidence. `evaluateStep(stepId, evidence): StepEvaluation` returns
passed/skipped/incomplete/unavailable and missing outcomes. Evidence is existing
backend records/events/receipts/export state, not progress flags.
`loadProgress(storage, identity)` and `saveProgress(storage, progress)` validate
identity/version and return explicit storage errors. `trainingSteps` maps every
T01–T11 and parity branch to a real route/target, evidence and guide section.

- [ ] Test Next cannot pass from clicks alone, Back does not undo writes, Skip
      is not success, stale/unavailable evidence is not all-clear, and
      mismatched origin/ store/fixture version cannot resume. No stale draft
      retargeting on reset.
- [ ] Map the concrete APIs in the reuse appendix for every T01–T11 branch.
      Evaluate actual joined/left intervals, applied-only receipt, issue
      correction, archive/download outcome; identify PDF extraction as
      human-observed and check its actual files independently in acceptance.
- [ ] Define lost-receipt/offline exercises using existing relay/browser
      controls, counterpart browser for real 409, and private maintenance
      backup/restore CLI. Tests require one real committed write and same-key
      replay, never a canned success response or a new production fault
      injection API.
- [ ] Run
      `timeout --kill-after=10s 10m npm run test:unit -- src/components/operator/training/trainingProgress.test.ts`
      red; implement the small evaluator and browser progress adapter using
      shared reads.
- [ ] Run green, checking all matrix IDs have instruction/real control/evidence/
      guide coverage. Commit curriculum/progress and narrow fixture exercises.

## Task 9: Hands-on guidance over the completed workspace

**Files:** Create
`F/components/operator/training/{GuidedMission.tsx,TrainingStep.tsx}` and tests;
modify `O/workspace/WorkspaceHelp.tsx`, existing real control targets with
stable accessible `data-training-target` anchors, and `F/App.tsx`.

**Interfaces:** GuidedMission consumes Task 8's progress/evaluator and ordinary
product query/receipt state. It displays dismissible in-context instructions,
next/back/skip/resume, Reset guide and Reset mission. Reset mission provides the
exact local launcher command and restart instructions; it does not fake a hot
reset. Help opens the configured nonproduction instance or clearly explains
setup.

- [ ] Test obvious Help → Guided mission walkthrough discovery, source/training
      label, absent setup, and actual first-use Create call/Create conference
      paths. Preserve ordinary real forms and lifecycle command handlers, not
      duplicate toys.
- [ ] Test T01–T11 route targets and parity branches, dismissal/resume with
      draft/ pending preservation, long labels, unknown times, unsupported
      cues/recenter, keyboard/mobile accessibility, and explicit local-command
      prerequisites.
- [ ] Test reset wording versus actual CLI reset, restart progress revalidation,
      and optional replay segment restart without claiming an exact restored
      frame. No second predictor, PWA, background notification or production
      mode switch.
- [ ] Run focused Vitest and actual-browser guidance cases red; implement the
      guide with existing service reads, no independent training status polling.
- [ ] Run green at all three viewports through the real UI; retain clear passed/
      skipped/manual-observed distinctions. Commit guidance and checked
      journeys.

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

Revised planning estimate: **12–20 engineer-days**, excluding review turnaround
and first-time-user/device availability. This replaces 30–45 days by removing
unnecessary generalized training infrastructure, not by cutting deliverables.
Milestones: M1 baseline/state adapters 2–3; M2 reused workspace/components 3–5;
M3 one-instance fixture/curriculum 2–3; M4 complete guide/Help 2–3; M5
production, first-use, timing and backout evidence 3–6. M2 provides a fast
usable full-parity candidate in **5–8 cumulative engineer-days**; final release
still requires M3–M5. See the
[explicit keep/reuse/remove and T01–T11 API map](../../design/issue-376/lean-training-reuse.md).
This is a planning range, not a fixed delivery promise.

The largest risks are replay/Operator namespace and clock alignment, legacy
draft migration and cross-route receipts, offline predictor inputs and full ZIP
isolation. Tasks 2–3 and 7 gate dependent work early. If the thin fixture seam
fails, report the exact failing case and propose the smallest change before
adding infrastructure. Explicit segment restart is allowed; do not promise exact
replay restoration or create a new reconstruction engine. Record/draft
correctness cannot be traded away.

No product code has been written for this plan. Completion requires
implementation review, all parity/training/guide checks, actual timing and
uncoached first-use evidence, exact candidate checks and resource teardown.
Merely passing the HTML preview checks cannot satisfy any of those.
