# Operator events plan: Tasks 6–8 and handoff

Part of the [approved plan](2026-10-18-operator-events.md).

## Task 6: Single frontend controller and local delivery

**Files:** Create `src/types/operatorEvents.ts`,
`src/services/operatorEvents.ts`, `src/hooks/api/useOperatorEvents.ts`,
`eventAlerts.ts`, `eventEmitter.ts` in the locations mapped above, with
colocated tests.

**Interfaces:**
`getOperatorEvents(missionId: string, cursor?: string, signal?: AbortSignal):
Promise<EventSnapshot>`
and
`acknowledgeOperatorEvent(request: AckRequest, key: string, epoch: string):
Promise<AckReceipt>`;
`useOperatorEvents(missionId: string, identity: string | null):
OperatorEventsState`;
`selectAlertBatch(input: AlertSelectionInput): AlertBatch | null`;
`createEventEmitter(options: EmitterOptions): { emit(batch: AlertBatch):
Promise<DeliveryResult>; dispose(): void }`.
Define local types beside owners; use backend field names exactly. State exposes
snapshot, freshness/error, refreshing, pending acknowledgment, retry and
refresh.

- [ ] Write failing client/controller tests: contract round-trip, single
      in-flight request, pinned pagination assembled atomically, abort on
      mission/store/run switch, late-response discard, visible/hidden
      15/60-second cadence, mutation/ focus/reconnect invalidation, 30-second
      real snapshot age, pending frozen ack retry and obsolete token
      reconciliation without losing drafts.
- [ ] Run
      `timeout --kill-after=10s 10m npm run test:unit --
      src/services/operatorEvents.test.ts
      src/hooks/api/useOperatorEvents.test.tsx`
      from frontend; confirm missing-implementation failures.
- [ ] Implement API types/controller using existing identity/network/error
      conventions. Keep a single query/controller per Operator page, not per
      editor. Stop timers, aborts and listeners on unmount.
- [ ] Write fake-timer selector tests for one grouped reconnect cue capped at
      three, specified priority/UTC ordering, five-second coalescing, 30-second
      spacing, cancellation of deferred candidates, no premature thresholds, ack
      suppression, reschedule/higher-tier generation, long-offline overdue
      timeline retention, muted then enabled and hidden then visible behavior.
- [ ] Implement pure selection from server eligibility plus monotonic receipt
      age and local emission cache. Persist bounded seven-day cache by
      store/run/mission; mark successful visual emission independently of
      sound/vibration success.
- [ ] Write emitter tests for gesture-gated audio, vibration
      unsupported/rejected, muted settings, no output on load, storage
      exceptions, tab emitter ownership expiry/handoff, disposed controller and
      unsupported coordination fallback. Use Web Locks for safe same-browser
      emitter ownership where available; without safe tab coordination disable
      automatic output and expose manual enable in the single current
      tab/session, without claiming cross-tab dedup.
- [ ] Implement local generated tone, guarded vibration and visual cue
      callbacks; return explicit `DeliveryResult` capabilities/status. No
      external asset/API.
- [ ] Run all new frontend tests with bounded Vitest; verify no network
      destination outside relative application APIs and no timers/audio contexts
      left owned.
- [ ] Commit `feat: add bounded local Operator alert controller`.

## Task 7: Compact timeline, source actions and delivery settings

**Files:** Create strip/feed/settings components and tests; modify
`src/pages/OperatorJournalPage.tsx`, its tests, and `OperatorBrief.tsx` only
where replacing duplicate Upcoming content is necessary.

**Interfaces:**
`OperatorEventStrip({ events }: { events: OperatorEventsState })`,
`OperatorEventFeed({ events, onClose }: { events: OperatorEventsState; onClose:
() => void })`,
`OperatorAlertSettings({ preferences, onChange, delivery }:
AlertSettingsProps)`.
Use existing dialog/popover primitives and existing dirty-draft navigation
guards.

- [ ] Write failing rendering tests: Now/Next/Attention all derive from one
      ordered snapshot; acknowledged/muted events remain;
      provenance/freshness/unknown source labels; protected unknown discrepancy
      remains prominent; no all-clear on missing source and honest
      audio/background capability states.
- [ ] Run bounded Vitest for new components and `OperatorJournalPage.test.tsx`;
      confirm expected missing-component/behavior failures.
- [ ] Mount one controller and modest sticky strip; keep settings in one popover
      and details in a dismissible drawer/sheet. Preserve existing editors and
      Display Tools. No automatic drawer opening or large new control section.
- [ ] Add tests for access from all four work areas, draft/scroll preservation,
      source links with dirty editors, keyboard focus/escape/return, restrained
      grouped live-region output, long/escaped source titles, mobile scroll,
      independent acknowledge action and pending/error/retry states.
- [ ] Implement feed and preferences: in-app defaults on, sound/vibration
      requested for high priority, routine follow-up vibration-only; explicit
      gesture test, local preference storage and accessible cue status without
      permission prompts.
- [ ] Run focused components, page identity/recovery tests and full unit suite;
      run bounded `npm run lint` and `npm run build`. Expect passing without
      Overview/Missions behavior changes.
- [ ] Commit `feat: integrate compact Operator events and alert controls`.

## Task 8: Production simulation, failure controls and evidence

**Files:** Create `tools/acceptance/operator-journal/events_probe.py`,
`tools/tests/test_operator_events_acceptance.py`,
`frontend/mission-planner/tests/e2e/operator-events.spec.ts`; modify existing
operator-journal `seed.py`, `scenario.py`, `backend_fixture.py`, `run.py`,
`compose.yml`, and `playwright.operator-journal.config.ts`. Create
`docs/operations/operator-events.md` and
`docs/reports/2026-10-18-operator-events/README.md` plus sanitized evidence.

**Interfaces:** Extend the existing owned runner with `--events` selection and
`events_probe.run(owner, origin, evidence_root) -> dict` for deterministic
backend/race/restart results; reuse its recorded ownership and production
candidate identity. Add a test-only injected source-publication barrier and
deterministic clock control to the acceptance fixture, never a production
mutation endpoint.

- [ ] Write failing harness tests pinning scenario selection, owned
      ports/projects, exact-SHA image checks, signal/timeout cleanup,
      internal-only product network, source barrier release on failure and
      evidence sanitization.
- [ ] Run
      `timeout --kill-after=10s 10m python -m pytest
      tools/tests/test_operator_events_acceptance.py -q`
      from repository root; confirm expected failures before harness changes.
- [ ] Extend the owned runner/fixtures with synthetic overlapping calls,
      conference-only/call-only participants, closed conference + connected
      customer, overdue follow-up, real PoP route crossing and changing injected
      positions. Include wholly local unreachable provider and real #349 leg
      completion/archive. Build actual production Dockerfiles and use Nginx; do
      not replace prediction integration with canned responses. Honor actor
      Docker context/socket and cloud proxy/CA guidance for builds; runtime
      application stays offline.
- [ ] Add production Playwright journeys for 1920×1080, 390×844 and 844×390:
      schedule shifts/cancel, two-client acknowledgments, actual
      crossing/advisory, protected discrepancy, revision changes,
      muted/unsupported delivery, offline failure/reconnect, restart,
      unavailable sources and dirty-editor access. Assert request destinations,
      one durable ack, bounded cue counts, no false outage, no overflow and
      preserved Overview/export controls.
- [ ] Add backend probes for real migration/backout,
      disk-full/commit-crash/restore, external publication change during
      acknowledgment, provisional rapid-crossing policy and unchanged #349
      archive/mission export hashes. Preserve machine- readable normal event/ack
      examples, all synthetic.
- [ ] Run harness tests, full backend/frontend suites, existing #348/#349
      integration selections and required lint/build gates with explicit limits.
      Backend full suite:
      `timeout --kill-after=10s 20m uv run --with-requirements requirements.txt
      pytest -q`.
      Frontend full suite/build: bound `npm run test:unit`, `npm run lint` and
      `npm run build` separately at 10 minutes. Investigate each failure before
      retry.
- [ ] Commit the product/harness/docs candidate, then execute from repository
      root:
      `timeout --kill-after=10s 90m python
      tools/acceptance/operator-journal/run.py --candidate "$(git rev-parse
      HEAD)" --project starlink-operator-events-368 --evidence
      test-results/issue-368-events --events`.
      Extend the existing parser/run selection to support the new `--events`
      flag. Internal build/browser probes retain tighter ownership-aware limits.
      Any product fix requires a new candidate SHA and rerun of affected
      production acceptance; never describe dirty-tree evidence as exact.
- [ ] Inspect sanitized captures and results, record candidate SHA/image
      digests, tool versions, scenario assertions, exported hash comparisons and
      known limits. Verify owned
      processes/listeners/containers/networks/disposable volumes gone; use
      approved host inspection if sandbox namespaces hide resources. Keep only
      evidence and the open-PR worktree; no service remains running for review.
- [ ] Commit evidence/docs, push to PR #379, update its title/body around the
      final implementation and validation, obtain product review and required
      final-head CI. Do not mark #368 complete or merge based solely on unit
      tests or this plan.

## Plan self-review and handoff

The specification's feed/identity/protection contracts map to Tasks 2–4;
persistence, receipts and acknowledgment to Tasks 1/5; catch-up/device
limitations to Task 6; compact accessible UX to Task 7; all real integrations,
restart/failure and resource cleanup to Task 8. Every Review Focus item has a
corresponding test step. Shared interfaces use one event/generation vocabulary;
no task introduces a second prediction, transport action or export format.

Review this plan and select Native or Subagent-driven execution before product
implementation. Native is recommended: the eight tasks share source-capture,
generation and receipt interfaces and benefit from continuous integration
context. Keep an independent whole-branch review and production acceptance
before completion.
