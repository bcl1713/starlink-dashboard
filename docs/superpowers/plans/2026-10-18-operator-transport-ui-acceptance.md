# Operator Transport Decisions — UI and Acceptance Plan

> **For agentic workers:** Continue Tasks 1–3 from the
> [main plan](2026-10-18-operator-transport.md). Its global constraints, review
> focus and execution-approval gate apply here. No implementation is authorized.

## Task 4: Compact transport workflow and durable client recovery

**Files:** Create the frontend files in the main file map. Modify
`src/types/operator.ts`, `src/types/operatorEvents.ts`,
`src/hooks/api/useOperatorJournal.ts`, `operatorReadSession.ts` and
`src/pages/OperatorJournalPage.tsx`. Extend existing command/input unions and
record-type filters without widening public provenance. Create colocated tests
for each pure form/helper, editor, list, review and draft hook; extend
`src/pages/OperatorJournalRecovery.test.tsx` and
`OperatorJournalIdentity.test.tsx`.

**Interfaces:** `TransportDecisionInput` follows existing public record shape;
`TransportDecisionUpdate` adds `expected_version` and optional transient
`replacement_check_row_ids`. `OperatorTransport({missionId, eventFeed})`
consumes `ReturnType<typeof useOperatorEvents>` passed by the page, never calls
the hook again. `TransportReview({review, stale, error})` receives the backend's
typed review. `TransportEditor({record, identity, disabled, onSave, review})`
supports create/correct;
`onSave(command: OperatorCommand, draftKey: string) -> Promise<boolean>` clears
draft only after acknowledged success/reconciliation.
`useOperatorTransportDraft(key: string, initial: TransportDraft)` returns
`{draft, setDraft, clear, storageError}`. Keys include store/epoch/source/run,
mission, record/new identity. TransportDraft holds raw form values and stable
row IDs, including explicit replacement-check choice; frozen pending requests
remain owned by the existing journal hook.

- [ ] Write failing `transportForms.test.ts`: applied-only input sets intent,
      request and check null; checked-only works; unknown time survives; known
      UTC converts without local timezone ambiguity; service rows retain UUIDs
      on reorder; generated title fits 200 characters even for 32 long labels.
      Reject blank labels, invalid/partial timestamps and reversed planned end.
      Mirror backend size/precision validation without requiring optional
      fields.
- [ ] Run from frontend:
      `timeout --kill-after=10s 10m npm run test:unit -- src/components/operator/transportForms.test.ts`.
      Confirm missing implementation failures; add
      `toTransportCommand(draft:     TransportDraft, current?: SavedRecord) -> OperatorCommand`
      in `transportForms.ts`. Applied edits clear a prior check visibly;
      explicit rechecking sets the transient marker, including same-valued
      replacements. Reordering without application changes must not clear
      checks.
- [ ] Write failing editor/list tests: independent stages, multi-service rows,
      one service's unknown time beside another's known time, optional notes/
      reason/association, “Record another move” creates instead of correcting,
      correction edits all entered times, immutable history remains inspectable,
      actual routing unknown after check. Test keyboard operation and meaningful
      labels for duplicate service names and nested stage controls.
- [ ] Implement editor, row and list components. Add Transport to existing
      desktop/mobile section navigation. Display linked records and timestamps;
      reuse JournalHistory for versions with typed service details. Keep compact
      applied-only entry and optional details. Separate unlink action from
      target removal; expose existing dependency errors with affected record
      links.
- [ ] Write `TransportReview.test.tsx`: simultaneous restrictions shown, active
      call warning visible but Save enabled, established conference independent
      from connected activity, backend unknown/partial shown explicitly, stale
      previous snapshot cannot appear fresh, unlinked service label never
      implies a call association. Missing additive review from an old response
      is unknown. Never calculate live restriction times or a replacement
      overlap model in JS.
- [ ] Implement review rendering from server snapshot. For unsaved/changed
      drafts, show the shared current communications/restriction context and
      mark saved assessment as referring to the saved version; do not present it
      as a computed assessment of the draft. An unscheduled “if changed now”
      preview is optional and omitted in this slice. A successful save
      invalidates the existing event query; disable no saves while awaiting its
      refreshed review.
- [ ] Write failing draft/recovery tests: storage failure, reload, frozen retry
      after lost response, two-client version conflict, target removed/moved
      before save/restore, changed store/mission/leg during pending save, and
      old response resolving after a switch. Assert no false success, no silent
      reassociation/overwrite, and idempotency key/command body unchanged on
      retry. Supply a new key only after explicit reread/reconciliation.
- [ ] Extend the existing hook's allowed record types and use
      `useOperatorJournal(missionId, 'transport_decision', {durable:true})`.
      Follow existing issue-draft storage handling; do not refactor other draft
      workflows or add timers. In the page test, assert one event query
      controller and no additional polling when Transport is opened. Preserve
      dependent targets in history while removed decisions release current
      links.
- [ ] Run the new component/hook tests, existing journal recovery/identity
      tests, `src/services/operator.test.ts`, `operatorEvents.test.ts` and
      event-alert tests with bounded Vitest; all must pass. Run
      `timeout --kill-after=10s 15m npm run build`. Commit
      `feat: add compact operator transport decision workflow`.

## Task 5: Real production simulation and release evidence

**Files:** Create `tools/acceptance/operator-journal/transport_probe.py`,
`transport_qualification.py`,
`tools/tests/test_operator_transport_acceptance.py`,
`frontend/mission-planner/tests/e2e/operator-transport.spec.ts`; modify existing
runner, acceptance Compose and Playwright config. Extend raw model input fixture
only as needed for synthetic scenarios; retain production source/prediction
code. Create `docs/reports/2026-10-18-operator-transport/README.md` and
sanitized evidence files there; update Operator documentation with
migration/backout instructions.

**Interfaces:** Add runner `--transport` mode and
`qualify_transport(owner: Owner) -> dict` in transport_qualification.py.
`transport_probe.run(owner, origin, evidence_root) -> dict` executes journal,
link/recovery and export controls inside the actual production backend image.
Set `OPERATOR_TRANSPORT_ACCEPTANCE=true` and enable existing raw model-input
fixture in this mode; the flag exists only in acceptance wiring, never normal
product APIs. Reuse existing Owner, admission, browser, failure and export
probes. All result sections include exact candidate SHA and explicit passed
assertions.

- [ ] Write failing harness tests for selecting transport qualification, exact
      clean committed candidate, production image labels, Nginx traversal,
      required browser scenarios, missing evidence failing qualification and
      cleanup after build/test/failure/timeout. Verify legacy runner modes
      retain their original behavior. Run

  ```bash
  timeout --kill-after=10s 10m python3 -m pytest \
    tools/tests/test_operator_transport_acceptance.py -q
  ```

- [ ] Implement acceptance mode and probe. Keep existing Dockerfiles/Nginx.
      Mount only synthetic local fixture inputs; use the real
      ProductionEventSources, timeline preparation, live ETA and
      PopStatusService. Fixture controls change raw
      position/speed/route/UTC/catalog state, never inject precomputed risk rows
      or replacement events as primary proof.
- [ ] Write Playwright journeys at 1920×1080, 390×844 and 844×390: quick
      applied- only entry, multi-service mismatch/check, second move,
      timestamp/reason correction and history. Create change ahead of and during
      active call; inline warning must not prevent save. Complete call without
      closing shared conference or connected customer activity. Capture
      sanitized screenshots.
- [ ] Add model journey: synthetic call/preparation overlaps actual #348 PoP
      window and X/Ka restriction; 45-minute delayed departure makes original
      plan UTC obsolete; speed change and deviation/rejoin move real displayed
      live ETA and existing cue threshold together. Accepted route revision
      updates future context without mutating saved decisions. Assert unknown
      actual routing, missing/stale model inputs and unavailable optional
      provider.
- [ ] Add two-client and link journey: target removal fails while referenced;
      unlink preserves historic reference and permits removal; removed decision
      releases links; restore with removed target fails; restoring valid targets
      permits restore. Cross-mission linked movement fails; explicit valid
      detach/reassociation succeeds. Verify restart rebuilds the same links.
- [ ] Add disconnected/lost-receipt journey using existing failure machinery:
      committed response lost then reload/retry yields one accepted revision;
      conflict retains draft; before-send offline never reports success.
      Exercise real backend restart, backup/restore, commit crash and physical
      storage failures. Multi-service state remains atomic, and old exports and
      baseline Overview visibility/history retain their existing
      assertions/hashes.
- [ ] Run focused harness tests and all existing Operator harness regression
      modules; commit `test: qualify operator transport decisions offline`
      before production acceptance so the product and tests have an exact source
      SHA.
- [ ] Complete canonical checks from repository root, with ownership records and
      explicit timeouts: `timeout --kill-after=10s 45m ./tools/verify backend`,
      `timeout --kill-after=10s 20m ./tools/verify frontend`, and

  ```bash
  ACCEPTANCE_POLICY_BASE_SHA=$(git merge-base origin/dev HEAD) \
    timeout --kill-after=10s 15m ./tools/verify static
  ```

  Each must exit zero. External link warnings follow repository policy; do not
  waive required internal links or static/product failures.

- [ ] Read cloud Docker guidance, discover actor daemon without changing
      DOCKER_HOST/context, and record current runtime/network readiness before
      builds. From root run the planned transport mode:

  ```bash
  timeout --kill-after=20s 90m \
    python3 tools/acceptance/operator-journal/run.py \
    --candidate "$(git rev-parse HEAD)" \
    --project starlink-operator-369-transport \
    --evidence /tmp/starlink-operator-369-evidence --transport
  ```

  Its internal deadline must accommodate this bound; build limits stay explicit.
  Existing admission may queue; report queue status and ownership. Qualification
  must fail on any missing group or browser scenario.

- [ ] Inspect all machine-readable results and screenshots. Preserve candidate
      SHA, dependency/tool versions, synthetic clock/input identity, real
      predictor evidence, actual ordinary LAN HTTP traversal, every viewport,
      mutation/history assertions, restart/failure and export controls. Publish
      only sanitized artifacts to the report directory. Document schema-002
      backup, explicit schema-003 upgrade, old-version rejection and
      backup-based backout; no in-place downgrade or deletion of new records.
- [ ] Verify runner teardown and host visibility: task PIDs/process groups,
      browser children, listeners, Compose containers/networks/private volumes
      and image tags gone. Remove task scratch without deleting evidence or the
      open-PR worktree. If cleanup fails, report exact remaining owned
      resources.
- [ ] Commit evidence/docs; rerun relevant documentation checks and require
      backend/frontend/static CI on final PR head. If product code changes after
      acceptance, repeat exact-SHA acceptance; evidence-only follow-ups record
      both tested product and final PR head without claiming they are identical.
      Push branch and update PR #380 from design-only to implementation scope
      only after plan approval and execution. Do not merge or close #369 here.

## Self-review and handoff

Coverage mapping: durable reports/times/migration (Task 1); dependency rules and
recovery (Task 2); real live timing, stale/unknown inputs and advisory
correlation (Task 3); compact independent entry and client resilience (Task 4);
full synthetic production acceptance and compatibility (Task 5). Review Focus
cases each have explicit owning tests. Shared types/signatures are defined in
the main plan and used unchanged here.

Ask the user to review the full plan and select native or subagent-driven
execution. Recommend native execution because the five tasks share journal and
snapshot interfaces and benefit from one continuous implementation context. Do
not start product code until the user approves this plan and execution method.
