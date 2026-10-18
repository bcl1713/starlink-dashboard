# Operator events plan: Tasks 3–5

Part of the [approved plan](2026-10-18-operator-events.md).

## Task 3: Pure unified event derivation and stable occurrences

**Files:** Create `event_projection.py`, `event_identity.py`; extend
`event_ledger.py`; create `test_event_projection.py`, `test_event_identity.py`.

**Interfaces:**
`derive_events(inputs: CapturedEventInputs, *, as_of: datetime, policy:
EventPolicy) -> list[OperationalEvent]`;
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
`select_eligible(events: list[OperationalEvent], *, as_of: datetime) ->
list[OperationalEvent]`
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
`acknowledge(request: AckRequest, *, key: str, epoch: str, runtime:
OperatorRuntime) -> AckReceipt`
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

Continue with [Tasks 6–8 and handoff](2026-10-18-operator-events-frontend.md).
