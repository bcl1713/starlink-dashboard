# Operator Event Feed and Local Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> for native execution, or superpowers:subagent-driven-development if the user
> selects delegation. Steps use checkbox syntax for tracking. Native execution
> authorized by the user after approval in PR #379 comment 6244505182. Tasks 1–8
> implemented, production acceptance passed, four final-review findings fixed.
> Final-head CI and handoff checks remain required.

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
`reconcile(connection, events: list[OperationalEvent], *, as_of: datetime,
policy: EventPolicy) -> list[OperationalEvent]`
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
      `timeout --kill-after=10s 10m uv run --with-requirements requirements.txt
      pytest tests/operator/test_event_schema.py -q`
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
`EventSourceAdapter.capture(mission_id: str, *, as_of: datetime) ->
CapturedEventInputs`
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

Continue with [Tasks 3–5](2026-10-18-operator-events-backend.md) and
[Tasks 6–8 and handoff](2026-10-18-operator-events-frontend.md).
