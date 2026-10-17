# Operator journal — simulation and acceptance task details

Part of the [implementation plan](2026-10-17-operator-journal.md). These steps
specify future checks; none have been run or claimed for this documentation PR.

## Task 8: Deterministic local integration harness

**Files:** Create backend `tests/operator/fixtures.py`,
`tests/operator/test_integration.py`, `test_mode_isolation.py`,
`tests/fixtures/operator/demo.json`; create repository tools
`tools/acceptance/operator-journal/seed.py`, `scenario.py`, `compose.yml`; test
`tools/tests/test_operator_journal_fixture.py`.

**Interfaces:** `make_demo(clock: Clock) -> dict` returns synthetic mission A/B,
two legs, typed record commands and fake observation inputs.
`seed_demo(root: Path, *, clock: Clock, mode: str) -> dict` uses real mission
storage and Operator service; returns saved IDs, store epoch and initial H.
`ScenarioClock` implements Task 1 Clock with test-only
`advance(seconds: float) -> None`. Fixture startup injection runs only in the
acceptance image/config; no production HTTP endpoint to change clocks, skip
identities, or erase data. Seed idempotency keys derive from synthetic
scenario/run identity. No sensitive or downloaded source samples.

- [ ] Write `test_integration.py::test_real_pop_and_flight_boundaries`: feed
      synthetic route/config/time/observations to actual
      `PopStatusService.snapshot` and mission forecast adapters. Assert unknown
      PoP timing remains advisory, Starshield modeled available, Ka/coordinated
      concurrency-only X preserve the existing full-window rule. Save an
      Operator decision source reference without another prediction engine or
      automatic routing action.
- [ ] Advance existing `FlightEventRuntime` with synthetic #349 observations
      across off-blocks/on-blocks and a second leg. Assert unchanged capture
      IDs, sealed revisions, gaps and export lifecycle; Operator entries stay
      associated with their explicit mission/leg, no automatic reassignment or
      conference close. Compare baseline telemetry ZIP contents/checksums using
      existing builder tests.
- [ ] Add `test_mode_isolation.py::test_mode_restart_and_optional_provider`:
      mode mismatch refuses access, deterministic restart/seed creates no extra
      rows, unreachable optional provider does not block journal writes. Real
      source time is distinct from recording/prediction time; stale/unknown
      source stays labeled.
- [ ] Add tool fixture test asserting synthetic names/IDs, no network discovery,
      all roots scoped to task volumes, same fake-clock sequence gives same
      semantic results, and transport reports cannot be labeled measured routing
      verification.
- [ ] Run backend `tests/operator/test_integration.py` and
      `test_mode_isolation.py`, and root

  ```sh
  timeout --kill-after=10s 10m uv run --with pytest pytest tools/tests/test_operator_journal_fixture.py -q
  ```

  expect missing fixture seam. Implement a test-only startup wrapper injecting
  runtime clock/providers through existing constructors, leaving production
  default factories intact. Compose override uses real backend/Nginx services
  and private volumes, no mandatory external service or port collision with
  shared runtime.

- [ ] Rerun those tests plus existing backend
      `tests/integration/test_mission_telemetry_archive.py`,
      `tests/unit/test_pop_status_continuity.py`, `test_telemetry_package.py`;
      expect pass. Commit
      `test: add deterministic Operator integration scenarios`.

## Task 9: Production browser, failure, and cleanup evidence

**Files:** Create `tools/acceptance/operator-journal/run.py`, `failures.py`,
`tools/tests/test_operator_journal_acceptance.py`; frontend
`playwright.operator-journal.config.ts`, `tests/e2e/operator-journal.spec.ts`;
update `docs/operations/operator-journal.md`; evidence
`docs/reports/2026-10-17-operator-journal/` (use actual run date if later).
Reuse lifecycle patterns from `tools/acceptance/pop-transitions/run.py` and
`tools/tests/test_pop_transition_acceptance.py`; do not introduce another shared
acceptance platform or edit shared development Compose/runtime configuration.

**Interfaces:** CLI

```sh
python tools/acceptance/operator-journal/run.py --candidate <full-SHA> --project <task-project> --evidence <absolute-directory>
```

validates clean full HEAD and OCI revision labels.
`run_failure_suite(owner, *, origin: str) -> dict` uses recorded owned
containers/processes only. Ownership file records project, config, temporary
paths, private volumes, session/PID/PGID, image identity, fixture IDs and
evidence roots before allocation.

- [ ] Write runner tests for dirty/mismatched/short candidate rejection,
      incorrect image identity, scoped private-volume teardown, early failure
      and timeout child reaping. No broad process kill or Docker prune; tests
      exercise runner behavior, not just grep its source. Run

  ```sh
  timeout --kill-after=10s 10m uv run --with pytest pytest tools/tests/test_operator_journal_acceptance.py -q
  ```

  expect runner absent.

- [ ] Implement runner with exit/INT/TERM cleanup, explicit subprocess deadlines
      and owned PGIDs, borrowed provisioned browsers, and actor Docker
      context/socket preserved. Use 60-minute build/acceptance maximum and
      10-second forced-stop grace, with progress records while running. No
      internet at test runtime; report missing provisioned dependencies instead
      of fetching them silently.
- [ ] Write Playwright journey using two independent contexts: desktop 1920×1080
      and mobile 390×844 then 844×390. Create late 1430–1442Z observation at
      1600Z, edit an end 1545→1535, fix typo/leg, inspect history,
      remove/restore without reason prompts. Verify default/supplied reason
      attribution, UTC, current-row uniqueness and pending/saved/error
      accessibility cues.
- [ ] Exercise concurrent version conflict; lose one mutation acknowledgment
      after backend commit using browser response handling (label the
      injection), retry exact key, inspect persisted SQLite counts through owned
      backend, refresh both clients. Stop/restart only owned backend to test
      reconnect persistence; optional provider stays unreachable, critical
      journal still usable.
- [ ] In owned disposable stores run subprocess termination before/after commit,
      committed WAL recovery, a genuinely constrained/full volume and read-only
      failure, backup restore/epoch rejection, missing DB and bad schema
      failure. Verify no silent empty store or false success, and baseline pages
      remain usable. Inspect default projection artifacts without requesting
      audit: schedule/status chronology, actual versus recorded times,
      removed-record activities, association move boundaries, common H, and
      checksums. Inspect explicit audit separately.
- [ ] Configure Playwright to use the already-owned production origin; no Vite
      webServer. Runner executes

  ```sh
  timeout --kill-after=10s 20m npx --no-install playwright test --config playwright.operator-journal.config.ts
  ```

  from the frontend. Browser assertions hit real API/Nginx, not fulfilled
  fixture API routes. Close contexts and browser in finally; save
  screenshots/trace with synthetic identities.

- [ ] Run focused backend `tests/operator`, related #348/#349 integration tests,
      frontend unit suite/build, and canonical scoped Python/TS/doc lint. Verify
      the runner tests pass. Commit code/harness before final production runs
      with `test: verify Operator journal production failure paths`.
- [ ] From repository root run

  ```sh
  timeout --kill-after=10s 60m python tools/acceptance/operator-journal/run.py --candidate "$(git rev-parse HEAD)" --project starlink-operator-362-final --evidence /tmp/starlink-operator-362-final-evidence
  ```

  Reserve a unique task-owned directory/project first; evidence path must not
  already belong to another run. Expect zero exit plus all candidate, browser,
  failure, projection and baseline checks green. If code changes, rerun against
  the new committed SHA; do not claim evidence for a different candidate.

- [ ] Verify owned PID/PGID/listeners gone, project-filtered
      containers/networks/ disposable volumes empty (approved host check if
      hidden). Preserve sanitized evidence and open-PR worktree, remove owned
      temporary artifacts. Commit evidence separately, distinguishing tested
      product SHA from evidence-only commit SHA. Production behavior changes
      require a new tested candidate; documentation-only evidence additions do
      not rewrite the observed candidate identity.
- [ ] Request whole-branch review, push feature branch, submit PR against `dev`
      with tests/versions/candidate/evidence/migration/backout/cleanup. Required
      CI and repository exact-head policy still apply to the PR's final head; if
      evidence commit changes that head, run required checks for that head
      rather than claiming product-SHA evidence alone satisfies every merge
      gate. No merge or aircraft readiness claim is authorized by this plan.

## Evidence checklist

- [ ] Production image IDs/SHA, fixture/run mode, versions, commands and exit
      codes.
- [ ] Desktop/mobile portrait/landscape captures and two-client conflict/retry
      proof.
- [ ] Crash barriers, restart integrity, full/read-only error proof and restore
      epoch.
- [ ] Sanitized current/activity/audit examples and component snapshot/checksum
      data.
- [ ] Overview/layout/history and planning/telemetry export baseline
      comparisons.
- [ ] Migration/backout instructions and explicit zero-owned-resource teardown.

Full call/conference workflows and real mission-package wiring remain later
child deliverables. This gate proves #362 foundation behavior only, entirely
with synthetic data; aircraft/terminal availability is not a prerequisite or a
claim.
