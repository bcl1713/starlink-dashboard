# Operator conferences backend implementation steps

Continues the [implementation plan](2026-10-17-operator-conferences.md). Its
Global Constraints and Review Focus apply.

## Task 1: Typed conference and participation contracts

**Files:** Modify backend `app/operator/payloads.py`, `api_models.py`,
`time_models.py`, `app/api/operator.py`; create
`tests/operator/test_conference_api.py` and `test_participation_api.py`.

**Interfaces:** Produce `ConferencePayload`, `ParticipationPayload`,
`ConferenceCreate`, `ConferenceUpdate`, `ParticipationCreate`,
`ParticipationUpdate` in existing public unions. Conference status is nullable
with unknown interpretation; fields and enums match the spec. Participation adds
nullable `participant`, nullable `state` (unknown/connected/interrupted/left),
and nullable UUID `resumes_participation_id`. Existing target requirement
remains.

- [ ] Write `test_conference_unknown_defaults_do_not_rewrite_history`,
      `test_public_conference_and_participation_roundtrip` and
      `test_connected_unknown_time_can_leave_without_invented_start`. Assert old
      missing fields decode unknown; raw revision/receipt JSON is unchanged;
      unknown identity/duration/schedule saves; end-only is rejected; future
      actual timestamps respect the existing 60-second tolerance. Use existing
      api_helpers.create and record_data/service/api fixtures.
- [ ] Run

```sh
timeout --kill-after=10s 10m uv run --with-requirements requirements.txt pytest tests/operator/test_conference_api.py tests/operator/test_participation_api.py -q
```

confirm failures concern new contracts/public type restrictions.

- [ ] Add nullable persisted payload fields; add public DTOs and expand the
      writable set only to journal_entry/call/conference/participation. Validate
      verified_at and configuration_reported_at with existing UTC parser and
      acceptance-clock tolerance. Keep issue/risk/transport-report private.
- [ ] Run the same focused command plus existing `test_call_api.py`,
      `test_api.py`, `test_models.py`, and `test_public_type_races.py`; require
      PASS.
- [ ] Commit `feat: expose typed conference and participation records`.

## Task 2: Transition, relationship and audit integrity

**Files:** Create backend `app/operator/conference_actions.py`; modify
`commands.py`, `references.py`; test in new `test_conference_actions.py` and
existing `test_references.py`, `test_recovery.py`, `test_projections.py`.

**Interfaces:**

```ts
validate_conference_update(current: SavedRecord | None, replacement: RecordInput, clock: Clock) -> None
```

enforces invariant timestamp and state combinations on every write.

```ts
conference_audit_reason(current: SavedRecord | None, replacement: RecordInput) -> str | None
```

supplies precise automatic reasons after the existing receipt/version guards.
Full-replacement corrections remain valid: these helpers cannot distinguish an
explicit historical correction from an operational command; UI builders in Task
3 guard action-specific preconditions. The API validates content, not an
invented action opcode.

- [ ] Write `test_verification_requires_established_conference`,
      `test_configuration_change_clears_verification`,
      `test_resume_link_rejects_cycles_and_wrong_targets`,
      `test_call_completion_does_not_mutate_conference`, and
      `test_retry_after_remote_edit_replays_original_receipt`. Assert audit
      reasons distinguish connection restoration and tombstone restoration;
      stale versions leave all revisions unchanged. Configuration changes
      carrying stale verification are rejected; valid replacements explicitly
      clear it. Backdated corrections become latest snapshots and preserve prior
      revisions.
- [ ] Run

```sh
timeout --kill-after=10s 10m uv run --with-requirements requirements.txt pytest tests/operator/test_conference_actions.py tests/operator/test_references.py -q
```

require relevant new failures.

- [ ] Integrate helpers after receipt/version checks inside the transaction.
      Extend derive_links for resumes_participation_id with explicit expected
      type participation; preserve existing call/conference link semantics.
      Require an interrupted predecessor, identical nullable call/conference
      targets, same mission and no cycle. Evaluate incoming links on corrections
      too; reject an incompatible predecessor correction with
      dependency_conflict rather than silently breaking restoration history.
      Protect referenced predecessors from removal. Unknown identities need not
      match strings.
- [ ] Preserve raw history and receipts. Existing databases cannot contain the
      new predecessor field, so absent legacy fields derive no new links: verify
      recovery with old fixtures without adding a speculative migration. Test
      new predecessor index survives backup/restore, recovery and projections;
      if that premise fails, revise spec before storage changes.
- [ ] Run

```sh
timeout --kill-after=10s 15m uv run --with-requirements requirements.txt pytest tests/operator -q
```

require PASS. Commit
`feat: preserve conference lifecycle and participation audit integrity`.
