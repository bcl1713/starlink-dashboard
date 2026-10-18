# Operator Transport Decisions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> for native execution, or superpowers:subagent-driven-development if the user
> selects delegation. Steps use checkbox syntax for tracking. The user approved
> this plan and selected native execution. Implementation and simulation
> verification are complete; merge approval remains separate.

**Goal:** Record independent service transport intentions and human reports,
with advisory communications risk review driven by the existing live event feed.

**Architecture:** Extend the existing journal with atomic multi-service decision
records and its existing dependency rules. Add a pure, ephemeral correlation
result to the same guarded event snapshot. Reuse the page-level event query and
store-bound durable mutation lifecycle in a compact Transport section.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, SQLite, React, TypeScript,
TanStack Query, pytest, Vitest, Playwright, production Docker/Nginx. No new
runtime dependency.

**Spec:** [Reviewed design](../specs/2026-10-18-operator-transport-design.md)
and [acceptance contract](../specs/2026-10-18-operator-transport-acceptance.md).
PR #380 review comment 6250609309 selects existing dependency-conflict behavior.

## Global Constraints

- Keep the current Operator feature gate, local HTTP deployment and single
  mission manager/counterpart model.
- Actual routing remains unknown. Operator Checked is an independent human
  report, never automatic SDR/OSPF/path verification.
- No scheduled call, conference, reason, verification or earlier workflow stage
  is required. Unknown times/transports are supported.
- Allow 1–32 rows per decision, service labels up to 200 characters, reason up
  to 1000 and notes up to the existing 8000-character limit.
- Every operator-entered time is editable or clearable in a correction; server
  acceptance timestamps, journal sequences and previous revisions are immutable.
- Use half-open intervals `[start, end)` and instant membership
  `start <= t < end`; touching endpoints alone do not overlap.
- Airborne review uses existing live route ETA and actual #348 PoP windows;
  planned UTC is reference only. No offsets, buffers or parallel prediction.
- Existing notification policy/identities, Overview, mission planning,
  conference lifecycle and mission-package contracts remain unchanged.
- Active links block target removal/type change/cross-mission moves. Unlink or
  remove dependents first. Restore revalidates links. Never cascade.
- Use `.worktrees/issue-369-transport`, branch `feat/issue-369-transport`, PR
  #380 against `dev`; primary checkout remains on `dev`. No merge authorization.
- Use synthetic data and injected UTC clocks. Record resources before starting;
  explicit timeout/grace and scoped cleanup apply to every run.

## Review Focus

1. Old browser tab carries a stale check while editing application: require an
   explicit replacement-check action, never silently reattach it (Task 1/4).
2. One service has unknown time while another has known time: preserve both
   independently and never fill unknown time with save time (Task 1/3/4).
3. A target is removed or moved between opening an editor and saving/restoring:
   fail atomically with dependency conflict, retaining the draft (Task 2/4/5).
4. Feed pagination or in-flight mutation mixes record versions: pinned context
   or retry/unknown; never a partial all-clear (Task 3/4).
5. Similar service labels in different legs/missions: no inferred customer
   association or inherited current routing (Task 3/4).

## File and interface map

Backend paths below are relative to `backend/starlink-location/`; frontend paths
are relative to `frontend/mission-planner/`. New names below are planned files,
not existing interfaces. Acceptance paths are repository-relative.

| Files                                                                                                                                                                      | Responsibility                                                  |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| `app/operator/payload_base.py`, `transport_models.py`, `transport_actions.py`                                                                                              | strict report/row/payload and check replacement rules           |
| `app/operator/payloads.py`, `models.py`, `api_models.py`, `commands.py`                                                                                                    | additive record/public command integration                      |
| `app/operator/migrations/003_transport_decisions.sql`, `schema.py`, `upgrade.py`                                                                                           | backed-up transactional schema upgrade                          |
| `app/operator/references.py`, `recovery.py`                                                                                                                                | current-link validation shared by writes and recovery           |
| `app/operator/transport_review_models.py`, `transport_windows.py`, `transport_review.py`                                                                                   | typed review, communications windows, pure correlation          |
| `app/operator/event_models.py`, `event_feed.py`                                                                                                                            | attach review to the single guarded/pinned capture              |
| `src/types/operatorTransport.ts`, `src/types/operator.ts`, `src/types/operatorEvents.ts`                                                                                   | matching payload and review contracts                           |
| `src/hooks/api/useOperatorTransportDraft.ts`, `useOperatorJournal.ts`, `operatorReadSession.ts`                                                                            | durable drafts and typed existing mutation/query lifecycle      |
| `src/components/operator/OperatorTransport.tsx`, `TransportEditor.tsx`, `TransportServiceRow.tsx`, `TransportDecisionList.tsx`, `TransportReview.tsx`, `transportForms.ts` | compact entry, history access, context and pure form conversion |
| `src/pages/OperatorJournalPage.tsx`                                                                                                                                        | section navigation and shared event query wiring                |
| `tools/acceptance/operator-journal/transport_probe.py`, `transport_qualification.py`, `run.py`, `compose.yml`, `model_inputs_fixture.py`                                   | existing runner's synthetic transport qualification             |
| `tests/e2e/operator-transport.spec.ts`, `playwright.operator-journal.config.ts`                                                                                            | production desktop/mobile and two-client journeys               |

## Task 1: Durable decision contracts and schema upgrade

**Files:** Create the two backend transport model/action files and migration
003; modify payload/model/public-command unions, `app/api/operator.py` writable
types, command dispatch, schema and upgrade. Extract PayloadBase into
`payload_base.py` and re-export it from `payloads.py` to avoid a model import
cycle. Create `tests/operator/test_transport_contract.py`,
`test_transport_schema.py`.

**Interfaces:**

```text
ReportTime(at: UtcTimestamp | None, precision: exact|approximate|unknown)
TransportValue = Starshield|Ka|X|unknown
TransportIntent(transport: TransportValue)
TransportChangeReport(transport: TransportValue, time: ReportTime)
TransportCheck(time: ReportTime, result: satisfactory|issue_reported|unknown,
               note: str)
TransportServiceRow(row_id: UUID, service: str,
    intended: TransportIntent | None,
    requested: TransportChangeReport | None,
    applied: TransportChangeReport | None, checked: TransportCheck | None)
```

Enum spellings above are literal string values in strict models. Null report
means absent; object with unknown values means reported unknown.
`TransportDecisionPayload(PayloadBase)` has `entry_type='transport_decision'`,
`services: list[TransportServiceRow]`, `reason: str`, `call_id`,
`conference_id`. Use `RecordTime.planned_start_at/planned_end_at` for planned
changes; nested report times are the reported action times. Do not populate
generic actual time from a nested row. Reuse the existing optional generic
actual time contract.

- [ ] Write failing contract tests:
      `test_independent_applied_only_and_checked_only`,
      `test_three_different_transports`, `test_rows_atomic_and_limits`,
      `test_times_unknown_editable_and_utc`, `test_future_report_tolerance`.
      Assert 1 and 32 rows accepted, 0/33 rejected; duplicate UUIDs rejected;
      200/201 label, 1000/1001 reason and 8000/8001 note boundaries; trim blank
      labels; unknown report time stays null; actual times over clock+60s fail;
      planned future times pass; existing 64-KiB command limit remains enforced;
      no imposed request/application/check ordering.
- [ ] From the backend run

  ```bash
  timeout --kill-after=10s 10m uv run \
    --with-requirements requirements-dev.txt \
    pytest tests/operator/test_transport_contract.py -q
  ```

  Confirm missing model failures before implementation.

- [ ] Implement the strict models and additive public create/update unions. An
      untouched absent report stays null. In public transport update and
      internal UpdateRecord, add `replacement_check_row_ids: list[UUID]`
      (default empty), excluded from saved payload. Non-transport commands
      reject nonempty markers; include markers in idempotency request hashing.
      `validate_transport_update(current, replacement) -> None` rejects an
      inherited nonnull check after applied changes unless its row ID is
      explicitly listed. Editor clears check by default and emits this transient
      marker only for an explicit replacement. Reject nonexistent, duplicate or
      nonchecked marker IDs. Do not reset checks on intent edits.
- [ ] Write `test_replacement_check_requires_explicit_marker` using identical
      check values on a changed application: no marker must fail; null check or
      marked replacement must pass. Assert prior revision unchanged and
      transient marker absent from receipt payload/history. Add automatic audit
      text using `transport_audit_reason(current, replacement) -> str | None`;
      no reason field becomes mandatory.
- [ ] Write failing migration tests from populated schema 002: preserve all
      revision/receipt bytes, current links, event acknowledgments, indexes,
      triggers and sequence high-water marks; reject normal startup before
      explicit upgrade; checksum/unknown-schema failure; rollback after injected
      DDL failure; backup restore and old-version rejection.
- [ ] Implement migration 003 and register it without modifying 001/002. Use the
      existing exclusive backup upgrade boundary. For the revisions table
      rebuild, disable foreign-key enforcement only on the maintenance
      connection before BEGIN, restore it in finally after commit/rollback;
      ordinary writer connections always enforce it. Recreate identical
      triggers/indexes/view, retain explicit journal sequences and
      sqlite_sequence maximum, and run `foreign_key_check` plus semantic
      validation before commit. Adapt fresh initialization to the same safe
      migration path. Do not use writable_schema or discard records; failed
      validation must roll back, not commit then fail.
- [ ] Run both new modules and existing `test_schema.py`,
      `test_event_schema.py`, `test_backup.py`, `test_recovery.py`,
      `test_commit_outcome.py` with the bounded backend invocation; all must
      pass. Commit `feat: persist independent operator transport decisions`.

## Task 2: Typed links, removal, restore and recovery

**Files:** Modify `app/operator/references.py`; extend recovery only where
needed for shared link derivation. Create `tests/operator/test_transport_api.py`
and `test_transport_references.py`; extend `test_recovery.py`.

**Interfaces:** Extend `derive_links(record)` with `transport-to-call` and
`transport-to-conference`, mapping explicitly to target types. Existing
`validate_dependencies(connection, changed)` remains the single rule for both
write acceptance and recovery. No new delete endpoint or cascade behavior.

- [ ] Write failing API tests: create applied-only decision through public API,
      correct times/reason, paged history, remove/restore, retry identical key,
      conflicting expected version and mismatch of store/run/epoch.
- [ ] Write `test_transport_target_remove_move_and_type_conflict`: active
      decision blocks target removal, type change and movement to another
      mission; decision cross-mission move with unchanged links fails. Assert
      dependency_conflict lists affected IDs and adds zero revisions/receipts.
- [ ] Write `test_transport_unlink_remove_restore_sequence`: unlink creates a
      correction with historic link retained; target removal succeeds only when
      all dependents are detached/removed. Removed decision releases links;
      restoring while target removed/wrong-mission fails. Restore target then
      decision succeeds. A single replacement moving mission and replacing links
      with valid same-mission targets succeeds; invalid replacement is atomic.
- [ ] Run new API/reference tests to confirm failures; extend public record
      filters and shared link derivation/type mapping. Preserve existing lock
      ordering and affected inbound dependency validation for target mutations.
- [ ] Add recovery/restart tests verifying exact current_links after unlink,
      remove and restore; history links are not live links. Tampered active link
      index, dangling current target and cross-mission target must fail
      recovery. Do not relax validation to accommodate transport decisions.
- [ ] Run these tests plus existing `test_api.py`, `test_references.py`,
      `test_conference_api.py`, `test_recovery.py`, `test_concurrency.py` using
      the bounded backend command. Commit
      `feat: enforce transport decision links`.

## Task 3: Advisory review inside the existing event snapshot

**Files:** Create the three review/window backend files; modify event
models/feed. Create `tests/operator/test_transport_review.py`,
`test_transport_feed.py` and
`tests/integration/test_operator_transport_review.py`. Extend existing
production source/live-timing tests without changing their predictor
implementations.

**Interfaces:**

```python
def derive_transport_review(
    records: list[SavedRecord], events: list[OperationalEvent],
    sources: list[SourceCapture], *, as_of: datetime, H: int,
) -> TransportReview: ...
```

It receives reconciled, current snapshot events, not another source capture.
`communication_windows(records, *, as_of) -> list[CommunicationWindow]` returns
call/prep/established/connected context with record/version/scope IDs, nullable
boundaries and scheduled/reported basis. `TransportReview` includes `as_of`,
`H`, `actual_routing='unknown'`, activities, and assessment rows with
decision/service/call/conference IDs, event/source references,
dependent_versions, time_basis, freshness and status
`overlap|possible_impact|unknown|no_overlap_found`. Distinguish
`change_vs_activity` from `communications_vs_restriction` assessment subjects.

- [ ] Write failing pure tests for half-open/touching intervals, instantaneous
      applications, missing end/start, planned future change, retrospective
      activity with insufficient evidence, actual versus scheduled activity,
      completed call plus still-connected participation, established conference
      without participants and no saved assumption for an unscheduled change.
- [ ] Add relevance tests: three independent requested/intended/applied targets,
      unknown actual routing despite satisfactory check, multiple overlapping
      X/Ka/PoP events, explicit associations only, unlinked possible impact,
      mission-versus-leg scoping and no cross-leg/service-name routing
      inference.
- [ ] Run pure tests red; implement window/correlation functions. Model results
      remain authoritative for availability/fallback classifications. A disabled
      or fresh empty source differs from absent/stale/misaligned source. Never
      reconstruct past restriction overlap from current live ETA. Historical
      activity comparison requires known recorded intervals; otherwise unknown.
- [ ] Write feed tests: one adapter capture; matching H and dependencies; source
      or journal revision racing capture causes existing retryable snapshot
      error; source preview/stale timing yields unknown; every pinned page
      carries the same complete review; no new journal/occurrence/ack write on
      review refresh.
- [ ] Add `transport_review: TransportReview | None = None` to EventSnapshot for
      backward decoding; new server attaches populated review inside existing
      guarded validation boundary, after event reconciliation and before issuing
      its token. Use the same complete snapshot horizon as the feed and state
      that horizon in review; never summarize only a returned page. A model
      publication change invalidates/rebuilds review through existing
      mechanisms.
- [ ] Add integration tests through actual ProductionEventSources and
      PopStatusService: 45-minute departure delay, speed change, route
      deviation/ rejoin, accepted route revision, modeled X plus Ka plus actual
      #348 PoP window overlapping synthetic call/prep. Assert operative due/end
      times and unchanged existing threshold/occurrence identity; stale
      speed/route/coverage yields partial/unknown. Hash original decisions
      before/after all captures.
- [ ] Run new tests plus `test_production_live_timing.py`,
      `test_production_event_sources.py`, `test_event_api.py`,
      `tests/integration/test_operator_event_sources.py`. Commit
      `feat: correlate transport decisions with existing live events`.

Continue with
[Tasks 4–5 and release checks](2026-10-18-operator-transport-ui-acceptance.md).

## Execution handoff

Native execution was selected after PR #380 review comment 6250720466 approved
the specification and plan. Implementation, review corrections and simulation
acceptance are recorded in the [verification report](../../reports/2026-10-18-operator-transport/README.md).
The original steps below remain the approved plan; the report records actual
commands, outcomes, adjustments and cleanup. No merge has been performed.
