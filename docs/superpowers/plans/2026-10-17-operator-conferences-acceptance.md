# Operator conferences acceptance implementation steps

Continues the [#366 implementation plan](2026-10-17-operator-conferences.md).
All Global Constraints and Review Focus requirements from that plan apply.

## Task 6: Real offline integration and production browser evidence

**Files:** Extend

```ts
tools/acceptance/operator-journal/{run.py,seed.py,scenario.py,backend_fixture.py,projection_probe.py,export_probe.py}
```

create `conferences_probe.py`, frontend `tests/e2e/operator-conferences.spec.ts`
and `tools/tests/test_operator_conferences_acceptance.py`. Extend existing
operator harness tests/config to run the new journey.

**Interfaces:** `conferences_probe.main() -> None` follows the existing
communications probe convention: read OPERATOR_ACCEPTANCE_ROOT, open the
existing synthetic store, assert projections and print one JSON result. Register
it through qualify's existing probe(module, destination) helper as
conferences-projections.json. The runner invokes it with the same synthetic
clock/store identity. Existing ownership.Owner and browser_control own all
runtime resources; avoid a second runner lifecycle.

- [ ] Add failing harness tests asserting the new journey/probe are invoked and
      source coverage assertions cannot be omitted. Add real backend integration
      tests for timeline generation through the existing #348
      forecast/continuity code and #349 flight event/archive APIs; fixed UTC
      inputs produce deterministic transitions, default Starshield, Ka and
      coordinated X fallback outcomes.
- [ ] Run

```sh
timeout --kill-after=10s 10m python -m pytest tools/tests/test_operator_conferences_acceptance.py -q
```

confirm failure before runner wiring.

- [ ] Implement synthetic journeys: reuse conference for two calls with idle
      interval, overlapping calls, both joining orders, unknown
      participant/timing, interruption/new interval, correction, independent
      close/completion, conspicuous discrepancy, two-client conflict, held
      response/offline retry, restart and backup/recovery. Assert unsupported
      operator-entered change remains uncovered.
- [ ] Exercise real preflight/leg activation, synthetic flight transition,
      on-blocks and multi-leg archive/package paths. Inject an unreachable
      optional provider and verify controls survive. Keep baseline Overview
      visibility, history/layout and existing export compatibility assertions.
- [ ] Run focused harness tests and backend integration tests with 10-minute
      limits; require PASS. Commit product/harness changes before exact-SHA
      acceptance.
- [ ] Read cloud Docker runtime instructions and verify actor Docker context
      without clearing DOCKER_HOST. Record ownership then run from repository
      root:

```sh
timeout --kill-after=10s 60m python tools/acceptance/operator-journal/run.py --candidate "$(git rev-parse HEAD)" --project starlink-issue366 --evidence docs/reports/2026-10-17-operator-conferences/raw
```

Require successful fresh production-image/Nginx desktop/mobile assertions,
screenshot capture and machine-readable evidence. No success claim on timeout.

- [ ] Verify task processes/listeners/containers/networks/private volumes are
      gone using the runner's scoped host verification. Preserve sanitized
      evidence, not raw contacts/coordinates. Commit
      `test: verify conference workflows in offline production simulation` after
      report preparation in Task 7.

## Task 7: Operational documentation and final review

**Files:** Create `docs/operations/operator-conferences.md` and
`docs/reports/2026-10-17-operator-conferences/README.md`; update
`docs/operations/operator-communications.md` and the specification status only
when execution is approved/completed.

**Interfaces:** Document API payload examples, one-tap workflow, separate
statuses, source/time/coverage table, correction and retry behavior,
retention/export boundary, backup and rollback. No new export or retention
policy is invented.

- [ ] Write synthetic examples for conference reuse, unknown connected customer,
      interruption/new interval and Restore record. State no independent
      call-bearing transport verification, no operator-change correlation before
      #369, and no automatic alerts before #368. Explain saved timeline age and
      partial coverage.
- [ ] Record production candidate SHA, test/tool versions, screenshot links,
      negative/source-coverage assertions and cleanup evidence. Describe
      additive JSON compatibility and pre-upgrade-backup downgrade requirement;
      no untested aircraft readiness claim.
- [ ] Run documented canonical backend/frontend/static checks from
      `docs/contributing/quality-gates.md`, all with explicit wall-clock limits;
      rerun affected checks for fixes. Run Prettier/Markdown checks and
      `git diff --check`. Require all applicable CI gates on final PR head; if
      only documentation changes after acceptance, identify exact tested product
      SHA.
- [ ] Commit documentation/evidence and push feat/operator-conferences. Update
      PR #377 description to the final implemented scope with evidence and
      rollback; request review without merging. Keep the open-PR worktree and
      stop all task runtime resources. Do not close #366 on specification or
      plan approval alone.

## Component file map

Backend contracts: `app/operator/payloads.py`, `api_models.py`, `references.py`,
`commands.py`, `time_models.py`, and `app/api/operator.py`, all beneath
`backend/starlink-location/`. New `app/operator/conference_actions.py` owns
transition validation and automatic audit descriptions without a generic action
engine. Existing recovery/projection modules remain the persistence mechanism.

Frontend types and transport: `src/types/operator.ts`,
`src/services/operator.ts`, `src/services/timeline.ts`,
`src/hooks/api/operatorReadSession.ts` and `useOperatorJournal.ts`, beneath
`frontend/mission-planner/`. New `components/operator/conferenceCommands.ts`
constructs captured commands; `conferenceProtection.ts` contains pure timeline
normalization/overlap logic; `hooks/api/useOperatorProtection.ts` reads
mission-scoped snapshots. `OperatorConferences.tsx`, `ConferenceEditor.tsx`,
`ParticipationEditor.tsx`, `ConferenceCard.tsx` and `ParticipationRow.tsx` keep
each UI responsibility small. Integrate them through existing
`OperatorCommunications.tsx` and history views.

Acceptance extends the existing owned Operator runner, fixtures and probes;
Tasks 6–7 specify browser/projection evidence and operational documentation.
