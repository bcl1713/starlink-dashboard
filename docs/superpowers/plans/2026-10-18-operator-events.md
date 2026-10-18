# Operator Event Feed and Local Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> for native execution, or superpowers:subagent-driven-development if the user
> selects delegation. Steps use checkbox syntax for tracking. Implementation
> awaits plan review and execution-method selection.

**Goal:** Deliver #368's authoritative UTC event feed and separate local alerts,
with durable shared acknowledgment and bounded reconnect behavior.

**Architecture:** Project current Operator records and existing #348 published
predictions into a versioned feed. Reconcile only material notification changes
in Operator SQLite. A single page-level controller renders the compact timeline
and emits best-effort local cues from fresh server eligibility.

**Tech Stack:** Existing Python 3.11/FastAPI/Pydantic/SQLite backend and
React/TypeScript/TanStack Query frontend; pytest, Vitest, Playwright and
production Docker/Nginx. No new runtime dependency.

**Spec:**
[Operator events design](../specs/2026-10-18-operator-events-design.md),
including PR #379 comment 6244453274 and the versioned capture clarification.

## Global Constraints

- Keep the existing Operator gate disabled by default.
- No routing actions, transport approval, mission-save acknowledgments, export
  changes, Overview changes, broad layout redesign (#376), external notification
  infrastructure, PWA, certificates, Web Push or native application.
- Reuse the actual #348 predictor/advisory/continuity logic and #349 leg/archive
  lifecycle. Unknown PoP or handover timing never means service unavailable.
- Every nonremoved connected participation remains protection-relevant despite a
  closed, interrupted, missing or removed conference. Label discrepancies
  unknown.
- Events remain visible independently of cue delivery and acknowledgment.
- UTC backend injected Clock controls eligibility. Browser wall time is not
  authority.
- Default model policy: shift 300 seconds, two stable captures spaced 15
  seconds, two escalation captures. Provisional deployment-configurable software
  constants.
- Visible/hidden poll cadence 15/60 seconds; emission requires snapshot age at
  most 30 real seconds. Token TTL 120 real seconds. Default horizon 24 hours,
  page cap 200, recent history 24 hours; retained local emission cache seven
  days.
- Prep/follow-up cue at due; customer start cue two minutes early; significant
  restriction cue five minutes early. Catch-up follow-up age 15 minutes; unknown
  call end fallback start plus 15 minutes. One grouped catch-up cue, at most
  three candidates, five-second crossing coalescing and at least 30 seconds
  between cues.
- Guard acquisition order: source publication, Operator admission, SQLite write;
  release in reverse. No distributed transaction claim.
- All test commands use timeout with a forced-termination grace. Runtime owners
  record resources before starting and verify scoped cleanup on every exit.
- Work in `.worktrees/issue-368-events` on `feat/issue-368-events`; primary
  checkout remains `dev`. PR #379 targets `dev`; merge requires separate
  authorization.

## Review Focus

1. Connected participation outlives its conference: preserve protection with
   unknown relevance, including call-only and conference-only associations (Task
   3).
2. A forecast changes during acknowledgment: reject changed generation or
   serialize against guarded publication; never acknowledge a replacement
   implicitly (Task 5).
3. A long disconnection crosses many thresholds: timeline retains overdue
   events, cues remain bounded and do not replay on refresh (Task 6).
4. Route re-entry and rapid crossings change prediction identities: preserve
   distinct occurrences without duplicating revision refreshes or dropping
   windows (Task 3).
5. Shared receipt parsing assumes operational records: acknowledgment-only
   receipts must survive recovery without altering existing journal/export
   contracts (Tasks 1 and 5).

## File and interface map

Backend paths below are relative to `backend/starlink-location/`.

| Files                                                                                                                      | Responsibility                                                         |
| -------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `app/operator/event_models.py`, `event_policy.py`                                                                          | feed/token/ack contracts and validated tuning                          |
| `app/operator/event_projection.py`, `event_identity.py`                                                                    | pure event derivation and source-aware occurrence matching             |
| `app/operator/event_sources.py`, `event_publication.py`                                                                    | capture existing sources, generation guards and bounded token registry |
| `app/operator/event_ledger.py`, `event_ack.py`                                                                             | material generation reconciliation and transactional acknowledgment    |
| `app/operator/migrations/002_event_notifications.sql`                                                                      | occurrence history and unique immutable acknowledgment tables          |
| `app/operator/schema.py`, `recovery.py`, `backup.py`, `__main__.py`, `store.py`, `commands.py`, `service.py`, `runtime.py` | migration, receipts, resource lifecycle and existing-store integration |
| `app/api/operator_events.py`, `main.py`, `app/mission/pop_status.py`                                                       | gated routes, binding and read-only published PoP snapshot integration |
| `tests/operator/test_event_*.py`, `tests/integration/test_operator_event_sources.py`                                       | focused contracts, deterministic behavior and real source integration  |

Frontend paths below are relative to `frontend/mission-planner/`.

| Files                                                                                                  | Responsibility                                                     |
| ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `src/types/operatorEvents.ts`, `src/services/operatorEvents.ts`                                        | versioned API contract and error-safe client                       |
| `src/hooks/api/useOperatorEvents.ts`                                                                   | one request lifecycle, identity isolation and acknowledgment retry |
| `src/components/operator/eventAlerts.ts`, `eventEmitter.ts`                                            | pure selection/rate rules and local device/tab lifecycle           |
| `src/components/operator/OperatorEventStrip.tsx`, `OperatorEventFeed.tsx`, `OperatorAlertSettings.tsx` | modest strip, accessible drawer and small preferences popover      |
| `src/pages/OperatorJournalPage.tsx`                                                                    | mount one controller, replace snapshot Upcoming integration        |
| colocated `.test.ts`/`.test.tsx`, `tests/e2e/operator-events.spec.ts`                                  | fake-clock, component and production browser verification          |

## Task 1: Upgrade and durable notification storage

**Files:** Create migration 002 and `event_models.py`, `event_policy.py`,
`event_ledger.py`; modify schema/store/recovery/backup/CLI and receipt parsing;
create `tests/operator/test_event_schema.py`, `test_event_ledger.py`,
`test_event_policy.py`; extend existing backup/recovery/projection tests.

**Interfaces:** Define `EventPolicy` with the four model constants in Global
Constraints; `OperationalEvent`, `SourceCapture`, `EventSnapshot`, `AckRequest`,
`AckReceipt` as strict version-1 models.
`reconcile(connection, events: list[OperationalEvent], *, as_of: datetime, policy: EventPolicy) -> list[OperationalEvent]`
returns persisted generation/disposition metadata. `OperationalEvent` includes
`protected_participation_ids: list[str]`, `transport_relevance` (`configured`,
`intended`, `unknown`, `call`) and `continuity_status` (`modeled`, `unknown`),
independent from source evidence confidence. Define immutable transition rows,
current occurrence pointers, and unique acknowledgment identity. `AckReceipt`
has command/ack identity, occurrence/severity, acknowledged UTC and `replayed`;
it contains no fake operational `saved_records`.

- [ ] Write failing migration tests: unchanged 001 checksum, upgrade from v1,
      checksum mismatch/unknown version rejection, failed migration rollback,
      normal startup requiring explicit upgrade, same-store backup/restore.
- [ ] Run
      `timeout --kill-after=10s 10m uv run --with-requirements requirements.txt pytest tests/operator/test_event_schema.py -q`
      from the backend; confirm expected missing-implementation failures.
- [ ] Add ordered checksum migration support and explicit `upgrade` CLI command
      with exclusive admission and a validated pre-upgrade backup. Keep startup
      nonmigrating for existing stores. Add policy environment overrides named
      `OPERATOR_EVENT_MODEL_SHIFT_SECONDS`,
      `OPERATOR_EVENT_MODEL_STABLE_CAPTURES`,
      `OPERATOR_EVENT_MODEL_CAPTURE_SPACING_SECONDS`, and
      `OPERATOR_EVENT_MODEL_ESCALATION_CAPTURES`; inject the resulting policy.
- [ ] Write failing ledger/policy tests: one accepted generation per material
      change, immutable prior generations, duplicate acknowledgment constraint,
      no writes for steady polls, invalid/nonfinite policy rejection, minimum
      two stable/escalation captures, valid rapid-crossing overrides.
- [ ] Implement occurrence/current-pointer/transition/ack tables and triggers;
      integrate capacity checks and schema integrity/recovery. Generalize
      receipt validation by discriminating operational versus acknowledgment
      receipt, preserving every existing operational receipt byte and projection
      input.
- [ ] Run the three new test modules plus `test_backup.py`, `test_recovery.py`,
      `test_commit_outcome.py` and `test_projection_compatibility.py` with the
      same bounded pytest invocation; expect all passing and unchanged export
      hashes.
- [ ] Commit `feat: add versioned Operator notification ledger`.

## Task 2: Capture existing sources with explicit authority

**Files:** Create `event_sources.py`, `event_publication.py`; modify
`runtime.py`, `main.py`, `app/mission/pop_status.py`; create
`test_event_sources.py`, `test_event_publication.py`,
`tests/integration/test_operator_event_sources.py`.

**Interfaces:**
`EventSourceAdapter.capture(mission_id: str, *, as_of: datetime) -> CapturedEventInputs`
returns immutable record snapshot/H and per-source `SourceCapture` values with
input/publication generation, freshness/alignment and lifecycle.
`EventPublication.guard(expected: tuple[SourceCapture, ...])` is a context
manager yielding only while those relevant publications remain current. Registry
is bounded to 256 snapshots per runtime with least-recently-issued eviction;
expired/evicted pagination or acknowledgment tokens require refresh.
`SnapshotRegistry.issue(snapshot: EventSnapshot) -> str` and
`resolve(token: str) -> EventSnapshot` enforce identity, monotonic TTL and
bounds.

- [ ] Write failing source tests using real synthetic route/catalog/projector
      and `PopStatusService` snapshot logic: active matching leg, inactive saved
      leg, live mismatched mission/run, unknown observation, stale
      position/speed, disabled feed, unavailable local provider and unchanged
      source revision.
- [ ] Run the two source test modules with bounded pytest; expect missing
      adapter.
- [ ] Implement capture around existing locally published inputs. Add read-only
      publication to the existing PoP coordinator so Operator reads never call
      `evaluate_live` again, publish POIs, alter planning, or contact providers.
      Cache by input identity; distinguish observation and mission clock inputs.
- [ ] Write failing gate tests: change before acquisition rejects, publication
      waits during lease, invalid input generation rejects, unrelated source
      does not invalidate, registry TTL exactly 120 seconds, pagination uses
      pinned capture, registry eviction and restart invalidate old tokens.
- [ ] Implement a generation-aware read guard around adapter publication and
      input invalidation. No existing source is presumed guardable merely
      because it exposes a revision. Prove publication and every relevant input
      invalidation participate before enabling modeled acknowledgment.
      Single-process sources must synchronously invalidate whenever the captured
      authoritative input identity no longer matches; guardable adapters alone
      permit modeled acknowledgment. Detect unsupported multiprocess publication
      and report unguardable/503 for acknowledgment rather than rely on a
      process-local lock. Keep their event display available.
- [ ] Run new source/publication tests and existing
      `tests/integration/test_pop_status.py`, `test_simulation_pop_status.py`,
      `test_pop_continuity_status.py`; expect original outputs and no extra
      coordinator advancement or external calls.
- [ ] Commit
      `feat: capture existing Operator event sources with revision guards`.

## Task 3: Pure unified event derivation and stable occurrences

**Files:** Create `event_projection.py`, `event_identity.py`; extend
`event_ledger.py`; create `test_event_projection.py`, `test_event_identity.py`.

**Interfaces:**
`derive_events(inputs: CapturedEventInputs, *, as_of: datetime, policy: EventPolicy) -> list[OperationalEvent]`;
`reconcile` from Task 1 accepts these events. Protected participation IDs and
relevance/discrepancy fields live on `OperationalEvent`; do not change
conference/participation source records.

- [ ] Write failing derivation tests with deterministic UTC: scheduled/delayed
      prep/start, persisted prep lead, tentative visibility, null timing,
      unknown prep, overdue issue, resolved/deleted suppression, UTC midnight,
      cancel, complete, remove/restore and reopen. Assert ten-minute creation
      default through the existing call API rather than inventing a new read
      default.
- [ ] Run bounded pytest on projection/identity modules; confirm failures.
- [ ] Implement chronological event derivation from existing record/continuity/
      segment/PoP values. Normal PoP transitions remain visual advisories;
      significant restrictions use existing classifications and transport
      states.
- [ ] Write protection tests: closed/interrupted/missing/removed conference with
      connected participation stays protected and unknown; call-only and
      conference-only participation; left/unknown state; old connected
      observation past planned end; multiple customers share one restriction/cue
      candidate. Pin the protection assertions with named parameterized cases:

  ```python
  def test_connected_customer_survives_conference_discrepancy(protected_case):
      event = protected_case.derive_restriction()
      assert event.protected_participation_ids == [protected_case.participation_id]
      assert event.transport_relevance == "unknown"
      assert event.continuity_status == "unknown"
  ```

  `protected_case` enumerates closed/interrupted/missing/removed conference and
  call-only participation; conference-only with a valid established transport
  instead asserts configured relevance. Define these event fields in Task 1.

- [ ] Implement relevance without changing #366 sources or treating association
      gaps as a reason to drop the customer observation.
- [ ] Write identity tests: repeated regional re-entry, timing-only refresh,
      cumulative 299/300-second drift, two captures 14/15 seconds apart, route
      or catalog replacement, split/merge ambiguity, severity tiers and
      acknowledged re-escalation. Exercise injected rapid-crossing policy;
      windows must remain intact and distinct even when closer than the default
      stability spacing.
- [ ] Implement stable source-family keys and unique overlap reconciliation;
      persist only material accepted-generation transitions. Do not place raw
      forecast revision in the stable operational key.
- [ ] Run focused tests plus real source integration; assert sole-Starshield
      full-window restriction, usable Ka/coordinated concurrency-only X
      protection, no false outage on unknown PoP and no durable writes on
      identical polls.
- [ ] Commit `feat: derive unified Operator timeline and stable occurrences`.

## Task 4: Versioned feed and deterministic eligibility API

**Files:** Create `app/api/operator_events.py`; modify `main.py`, `runtime.py`;
create `test_event_api.py`, `test_event_eligibility.py`.

**Interfaces:** `GET /api/v2/operator/events` accepts `mission_id`, optional
pinned `cursor`, returns `EventSnapshot`. Each event carries
`notification.eligible`, `notification.priority`, `notification.threshold_at`,
`notification.generation`, `notification.acknowledged`, and availability/reason.
Add
`select_eligible(events: list[OperationalEvent], *, as_of: datetime) -> list[OperationalEvent]`
for server timing/actionability only; frontend handles emission history/rate.

- [ ] Write failing API tests for disabled gate, missing mission, source partial
      failure, 24-hour horizon/history, >200 events with pinned pagination,
      expired cursor, unknown times, no-store headers and sanitized errors.
- [ ] Run bounded pytest for the two new modules; confirm failures.
- [ ] Implement feed capture/derive/reconcile, registry token and pagination.
      Revalidate relevant Operator versions before publishing; modeled results
      identify their own publication generation, never a global atomic snapshot.
- [ ] Write exact threshold tests: prep/follow-up due, customer start minus 120
      seconds, restriction start minus 300 seconds, 15-minute catch-up limits,
      planned call end/unknown-end fallback, active window, no future follow-up
      early cue, regression and stale/unaligned/unguardable evidence.
- [ ] Implement server eligibility with injected UTC. Preserve last-known
      unknown rows on missing evidence; never retire them just because a source
      failed.
- [ ] Run new tests plus existing Operator API, mode-isolation and runtime
      tests; expect passing and disabled-feature startup unchanged.
- [ ] Commit `feat: expose versioned Operator event feed and eligibility`.

## Task 5: Shared acknowledgment and cross-source races

**Files:** Create `event_ack.py`, `test_event_ack.py`,
`test_event_ack_races.py`; modify `operator_events.py`, receipt integration and
`event_ledger.py`.

**Interfaces:**
`acknowledge(request: AckRequest, *, key: str, epoch: str, runtime: OperatorRuntime) -> AckReceipt`
serves `POST /api/v2/operator/events/acknowledge`. Request contains occurrence
ID, severity generation and opaque snapshot token. Reuse existing header names
and idempotency-key scope; distinguish ack request hashes from operational
commands.

- [ ] Write failing tests for same-key retry, incompatible key reuse, two
      clients with distinct keys, old epoch, expired/restarted token, changed
      dependent record, unaffected unrelated write, canceled/completed/resolved
      sources. Assert one immutable acknowledgment and no operational revision.
- [ ] Run bounded pytest for acknowledgment and race modules; confirm failures.
- [ ] Implement receipt replay first for an already committed identical request,
      preserving original historical generation. New writes follow Task 2 guard,
      admission and immediate SQLite transaction order; validate relevant
      current records/publications, reconcile and insert acknowledgment/receipt
      once.
- [ ] Add deterministic barrier tests: external forecast changes between refresh
      and guard acquisition -> 409 with zero ack writes; stale/unavailable or
      unguardable required evidence -> 503; publication attempts during guarded
      commit -> waits, then supersedes old generation without acknowledging new.
      Add cancellation between snapshot and commit, two separate SQLite
      connections, rollback after ack insertion, lost response and
      restart/replay cases. Pin the change-before-guard case with this test
      contract:

  ```python
  def test_forecast_change_during_acknowledgment(ack_race):
      before = ack_race.acknowledgment_count()
      response = ack_race.change_publication_before_guard_then_ack()
      assert response.status_code == 409
      assert ack_race.acknowledgment_count() == before
      assert ack_race.replacement_is_acknowledged() is False
  ```

  Implement `ack_race` using two controlled threads and barriers in the source
  adapter, with bounded joins and guaranteed release/cleanup, never timing
  sleeps.

- [ ] Implement conservative 409/503 responses and lock cleanup on all
      exceptions. Do not fail scheduled-call acknowledgment on unrelated PoP
      unavailability. No network/source computation occurs while SQLite is
      locked.
- [ ] Run new tests plus existing concurrency, commit-outcome, backup/recovery,
      command API and projection compatibility suites. Assert
      acknowledgment-only receipts round-trip without requiring `saved_records`
      and source/export bytes stay unchanged.
- [ ] Commit `feat: acknowledge event generations with guarded concurrency`.

## Task 6: Single frontend controller and local delivery

**Files:** Create `src/types/operatorEvents.ts`,
`src/services/operatorEvents.ts`, `src/hooks/api/useOperatorEvents.ts`,
`eventAlerts.ts`, `eventEmitter.ts` in the locations mapped above, with
colocated tests.

**Interfaces:**
`getOperatorEvents(missionId: string, cursor?: string, signal?: AbortSignal): Promise<EventSnapshot>`
and
`acknowledgeOperatorEvent(request: AckRequest, key: string, epoch: string): Promise<AckReceipt>`;
`useOperatorEvents(missionId: string, identity: string | null): OperatorEventsState`;
`selectAlertBatch(input: AlertSelectionInput): AlertBatch | null`;
`createEventEmitter(options: EmitterOptions): { emit(batch: AlertBatch): Promise<DeliveryResult>; dispose(): void }`.
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
      `timeout --kill-after=10s 10m npm run test:unit -- src/services/operatorEvents.test.ts src/hooks/api/useOperatorEvents.test.tsx`
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
`OperatorEventFeed({ events, onClose }: { events: OperatorEventsState; onClose: () => void })`,
`OperatorAlertSettings({ preferences, onChange, delivery }: AlertSettingsProps)`.
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
      `timeout --kill-after=10s 10m python -m pytest tools/tests/test_operator_events_acceptance.py -q`
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
      `timeout --kill-after=10s 20m uv run --with-requirements requirements.txt pytest -q`.
      Frontend full suite/build: bound `npm run test:unit`, `npm run lint` and
      `npm run build` separately at 10 minutes. Investigate each failure before
      retry.
- [ ] Commit the product/harness/docs candidate, then execute from repository
      root:
      `timeout --kill-after=10s 90m python tools/acceptance/operator-journal/run.py --candidate "$(git rev-parse HEAD)" --project starlink-issue-368-events --evidence test-results/issue-368-events --events`.
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
