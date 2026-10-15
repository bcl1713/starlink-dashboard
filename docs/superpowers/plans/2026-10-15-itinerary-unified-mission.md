# Automatic itinerary import implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Upload a PDF and KMLs once to create an ordinary editable mission,
then support normal edits and revised itinerary imports without a second editor.

**Architecture:** A server-owned resumable import operation prepares ordinary
Mission/MissionLeg records using existing extraction, geometry and optimization.
Separate provenance records retain baselines and revision snapshots; ordinary
mission data remains authoritative. Transactional conversion moves old itinerary
missions to the shared editor without regenerating accepted plans.

**Tech Stack:** Python 3.11, FastAPI/Pydantic, existing file-backed journals and
bounded workers; React/TypeScript, TanStack Query, Vitest and production
Playwright.

**Spec:**
[Approved design](../specs/2026-10-15-itinerary-unified-mission-design.md).

## Global constraints

- All configured X-band satellites are permitted; no access confirmation UI.
- Preserve exact KML times; compare UTC minutes within ±1 for timing
  equivalence.
- Wider shifts require unique supporting route evidence, not a larger time
  cutoff.
- AR entry uses the departure offset; exit uses the arrival offset.
- Ordinary edits are authoritative; never implicitly regenerate satellite
  choices.
- Preserve mission ID/name on revisions, surviving leg IDs and old snapshots.
- Create inactive missions; revisions cannot replace affected active leg data.
- Keep 16-file/40 MiB route-batch and 10 MiB PDF limits, UTC and source units.
- Use invented public fixtures, bounded workers, explicit wall limits and
  cleanup.
- Work in isolated feature branches from current origin/dev; PRs target dev.

## Review focus

1. Two similar/repeated routes must not associate by upload order (Task 1).
2. Cancellation/restart after a commit must not create a duplicate mission (Task
   3).
3. A route replacement must not retain anchors bound to the old hash (Task 4).
4. A source revision must not overwrite a concurrent takeoff edit (Task 5).
5. Migrated active missions must retain their accepted plans and activation
   (Task 6).

## Files, interfaces and execution order

New backend units live under `app/mission/itinerary_import/`: `models.py` owns
operation/provenance contracts, `association.py` route assignment, `ar.py` AR
resolution, `store.py` durable operations, `service.py` orchestration,
`worker.py` bounded lifecycle, `commit.py` atomic creation, `revisions.py`
merges, `migration.py` conversion and `routes.py` HTTP adaptation. Reuse
planning services through explicit adapters rather than routing ordinary writes
through drafts.

New frontend units live under `components/itinerary-import/` with shared
`services/itinerary-import.ts` and `types/itinerary-import.ts`. Existing mission
and leg pages remain the single editor. Tasks are sequential because each
consumes earlier contracts. Each task ends with its own regression cycle/commit;
do not expose the new creation entry point until Task 7 completes the flow.

Backend paths below are relative to `backend/starlink-location/`; frontend paths
are relative to `frontend/mission-planner/`. Commands run from those directories
unless explicitly marked repository root. Keep each new file under 300 lines.

### Task 1: Deterministic route assignment

**Files:** Create
`app/mission/itinerary_import/{__init__,models,association}.py`; create
`tests/itinerary_import/{__init__,test_association}.py`; reuse
`app/mission/planning/intake.py` and `tests/planning/cases.py` fixtures.

**Interfaces:**
`associate_routes(legs: Sequence[ExpectedLeg], routes: Mapping[str,
ParsedRoute]) -> AssociationResult`.
Define `AssociationResult` with accepted `leg_id -> route_id`, typed unresolved
issues and stored evidence. Accept an edge only if it is forced across all best
admissible one-to-one assignments. Rank endpoint/date evidence before
minute-time equivalence, then consistent shift/duration evidence; lexical IDs
must never settle ambiguity.

- [ ] Write `test_second_precision_is_not_a_discrepancy`: invented PDF 10:00/
      12:00 and KML 10:00:42/12:00:17 yield one match and no issue. Add
      ±1-minute boundaries, unique larger common shift, duration differences,
      midnight, shuffled files, repeated endpoints, contradictory dates and
      missing times. Assert ambiguous repeated routes remain unresolved in
      either file order.
- [ ] Run
      `timeout --kill-after=10s 10m uv run --with-requirements
requirements-dev.txt pytest tests/itinerary_import/test_association.py -q`;
      expect the new behavior tests to fail before implementation.
- [ ] Implement the result schema and pure global assignment; retain seconds in
      the source models. Do not mutate legacy intake behavior before
      integration.
- [ ] Rerun the command; require all tests green. Commit
      `feat: associate itinerary routes with precision-aware evidence`.

### Task 2: Endpoint-relative AR resolution

**Files:** Create `app/mission/itinerary_import/ar.py` and
`tests/itinerary_import/test_ar.py`; modify `app/mission/planning/match.py` only
to extract reusable occurrence/interpolation primitives without changing legacy
semantics. Extend `models.py` with `ARResolution` and provenance fields.

**Interfaces:**
`resolve_import_ars(leg: ExpectedLeg, route: ParsedRoute) -> ARResolution`;
result contains resolved rows and typed issues. Source values, precision,
endpoint offsets, chosen occurrence and derivation remain recorded.

- [ ] Write tests asserting entry 11:30:42 for PDF departure 10:00, entry 11:30
      and KML departure 10:00:42; independently assert arrival-relative exit.
      Cover midnight, changed flight duration, ±1-minute unique occurrences,
      larger track-supported differences, repeated tracks/loops, absent exit
      interpolation, missing/duplicate points and invalid/reversed windows.
- [ ] Run Task 1's backend command with `tests/itinerary_import/test_ar.py`;
      require failures demonstrating absent resolution before implementing it.
- [ ] Implement endpoint-offset resolution and ordered occurrence selection.
      Explicit eligible KML occurrences precede interpolation; an unresolved
      ambiguity or out-of-flight interval becomes an issue, never a clamped AR.
- [ ] Rerun new tests plus `tests/planning/test_match.py`; require green and
      commit `feat: resolve imported AR windows from KML endpoint offsets`.

### Task 3: Durable automatic import and atomic mission creation

**Files:** Create
`app/mission/itinerary_import/{store,service,worker,commit,routes}.py`; extend
`models.py`; wire lifecycle/router in `main.py`; create
`tests/itinerary_import/{conftest,test_operations,test_creation_api}.py`. Reuse
`planning/{extract,canonical,optimizer,journal,sources,deadlines}.py`,
`mission/timeline_preparation.py` and package preparation lifecycle patterns.

**Interfaces:**
`ImportService.start(pdf, kmls, idempotency_key, mission_id=None) ->
ImportOperation`,
`read(operation_id)`, `resolve(operation_id, generation, choices)`,
`cancel(operation_id)` and `close()`. Persist strict `ImportOperation` with
operation ID, generation, stage, issues, mission ID, deadline and state
`queued/running/needs_input/ready/committed/cancelled/failed`.

HTTP: POST `/api/v2/missions/itinerary-imports` (multipart PDF, repeated KMLs,
idempotency key, optional mission ID); GET/DELETE `/{operation_id}` and POST
`/{operation_id}/resolutions`. Start returns 202; invalid uploads 422; stale
generation 409. Reads use sanitized records, not source filesystem paths.

- [ ] Write synthetic API tests for one upload producing ordinary inactive legs,
      ARs, generated X transitions, canonical timelines and provenance. Assert
      all eligible configured X satellites are considered without confirmation.
      Missing/invalid configured geometry becomes an issue; do not invent
      access. Test size/count limits, no satellite options, optimizer failure,
      ambiguous correction, cancellation, timeout, restart, duplicate submit and
      crash after journal commit before returning success: exactly one mission
      exists.
- [ ] Run the backend command against those two new test modules; confirm red.
- [ ] Implement persisted stages and bounded background admission (one active
      operation, eight queued; excess starts return retryable 429). Use a
      20-minute overall deadline including queue time and 10-second termination
      grace; bound inner stages by the remaining allowance. Close/reap workers
      on shutdown/cancel. Recheck source/catalog identity before atomic commit.
      Capture and journal full provenance plus ordinary mission artifacts once;
      do not fake operator review confirmations to invoke old publication APIs.
- [ ] Rerun operations/API tests and existing planning deadline/canonical tests;
      require green and commit
      `feat: generate ordinary missions from durable imports`.

### Task 4: Shared ordinary editing and route replacement

**Files:** Modify `app/mission/{routes_v2,storage}.py`,
`app/mission/planning/legacy.py`; extend import `models.py`/`store.py`; create
`tests/itinerary_import/test_ordinary_edits.py`. Modify frontend
`pages/{MissionDetailPage,LegDetailPage}.tsx` and their existing tests.

**Interfaces:** Add an import-provenance schema version distinct from the legacy
`itinerary_planning` marker. Normal PUT/route replacement updates authoritative
mission values and records field overrides against imported baselines under the
same mission lock. UI branches into the legacy editor only for unconverted data.

- [ ] Write tests that imported and manual legs use the same editor, PUT and
      replacement-route contracts. Assert takeoff changes recompute route-bound
      times, fixed UTC stays fixed, initial Ka edits are ordinary edits, and
      manual satellite edits do not rerun the optimizer. Replace a KML with new
      hash and assert old anchors cannot survive as valid bindings; remap unique
      evidence or expose unresolved fields in the normal editor. Protect active
      route replacement and preserve ordinary activation/export behavior.
- [ ] Run backend `tests/itinerary_import/test_ordinary_edits.py` and frontend
      `timeout --kill-after=10s 10m npm run test:unit --
src/pages/MissionDetailPage.test.tsx src/pages/LegDetailPage.test.tsx`;
      confirm new cases fail, then implement shared paths and provenance
      capture.
- [ ] Rerun both selections and existing mission API/state/timeline regressions;
      require green and commit
      `feat: edit imported missions through ordinary controls`.

### Task 5: Revision preview, merge and commit

**Files:** Create `app/mission/itinerary_import/revisions.py` and
`tests/itinerary_import/test_revisions.py`; extend `models.py`, `service.py`,
`commit.py`, `routes.py`; reuse existing revision/journal primitives.

**Interfaces:** Define `RevisionPreview` with baseline identity, generation,
field changes/conflicts and source identities.
`prepare_revision(operation, current_mission, baseline) -> RevisionPreview`;
`commit_revision(operation_id, generation, resolutions) -> Mission`. POST
`/{operation_id}/commit` commits a ready revision; initial creation commits
automatically when unambiguous.

- [ ] Write three-way merge tests for source-only/manual-only/equal/conflicting
      edits, preserved mission name/ID and surviving leg IDs, added/removed
      legs, unchanged KML reuse and changed occurrences/catalog dependencies.
      Assert whole-source replacement preserves history, takes an explicit
      commit, protects affected active legs and rejects concurrent
      takeoff/catalog edits. Inject journal interruption and verify
      all-or-nothing recovery.
- [ ] Run backend `tests/itinerary_import/test_revisions.py`; require red.
- [ ] Implement field-aware merge and ordinary revision snapshots. Bind previews
      to current mission and catalog/source hashes; invalidate stale commits
      with 409. Recompute affected artifacts; leave unaffected legs untouched.
- [ ] Rerun revision and ordinary-edit tests; require green and commit
      `feat: revise ordinary missions from updated itinerary sources`.

### Task 6: Existing-mission conversion and package compatibility

**Files:** Create import `migration.py` and tests
`tests/itinerary_import/{test_migration,test_packages}.py`; modify
`planning/packages.py`, `mission/package/__main__.py`, `storage.py` and startup
initialization in `main.py`. Preserve existing package/source validation.

**Interfaces:** `migrate_itinerary_mission(mission_id: str) -> MigrationResult`
uses the mission lock/journal, preserves the legacy manifest as archival data
and marks the new provenance version only after durable conversion. Run before
legacy mission writes and during legacy package import; reads must not return
two competing authoritative copies. Startup resumes incomplete journals.

- [ ] Write idempotence/restart tests preserving active installed leg IDs,
      transport choices, timeline values, sources and history byte-for-byte
      where unchanged. Assert installed legs stay editable while unfinished
      expected legs become resumable import work. Test legacy and new ZIP
      round-trips, relocation, deleted missions, missing archived sources and
      tampered paths.
- [ ] Run the two new backend modules; confirm red before migration code.
- [ ] Implement transactional conversion and explicit package schema/version
      dispatch. Reject unsupported required provenance versions rather than
      silently dropping source/revision relationships. Old drafts cannot write
      over converted missions. Preserve normal manual packages unchanged.
- [ ] Rerun new and `tests/planning/test_packages.py` tests; require green and
      commit `feat: migrate itinerary missions without changing accepted plans`.

### Task 7: One-upload UI and normal revision entry point

**Files:** Create frontend `types/itinerary-import.ts`,
`services/itinerary-import.ts`,
`components/itinerary-import/{ImportDialog,
ImportProgress,ImportCorrections,RevisionPreview}.tsx`
and colocated tests. Modify `components/planning/CreateFromItinerary.tsx`,
`pages/{MissionsPage,MissionDetailPage}.tsx`; retire obsolete panels only after
conversion coverage passes. Add normal editor links for resumable import issues.

**Interfaces:** Mirror Task 3/5 strict HTTP contracts in types and client
methods. Persist the operation ID for resume; poll until terminal/needs-input,
abort reads on unmount and invalidate normal mission/timeline queries after
commit.

- [ ] Write tests for PDF plus KML selection, one Generate mission action,
      progress, automatic navigation to ordinary mission and zero confirmation
      clicks on the happy path. Assert no access checkboxes, no separate
      itinerary leg cards/editor, and corrections only for unresolved fields.
      Cover reload/retry/cancel, stale responses and upload limits. Revision
      tests upload PDF/optional KMLs, inspect changed fields, resolve conflicts,
      commit once and preserve a concurrent edit on 409. Include keyboard/mobile
      correction focus and an active-leg explanation with ordinary deactivation.
- [ ] Run
      `timeout --kill-after=10s 10m npm run test:unit --
src/components/itinerary-import src/pages/MissionDetailPage.test.tsx
src/pages/LegDetailPage.test.tsx`;
      confirm red, then implement the UI with existing dialogs/forms/query
      patterns.
- [ ] Rerun selections, full unit suite, lint and production build with wall
      limits; require green and commit
      `feat: import and revise missions in one upload flow`.

### Task 8: Production qualification, review and documentation

Execute the
[acceptance continuation](2026-10-15-itinerary-unified-mission-acceptance.md),
including fail-closed proof tests, exact-SHA production journeys, independent
review, documentation and verified teardown. This task is required before
handoff.

## Plan review and execution handoff

All approved requirements map to Tasks 1–8; the five review-focus cases each
have an owning test cycle. No implementation is included in this planning
branch. Owner reviews the plan and selects native or subagent-driven execution
before product code changes. Recommend native execution for this tightly coupled
set of interfaces, with independent whole-branch review before production
acceptance.


### Task 9: Apply manual-testing feedback

**Authority:** Owner feedback during manual testing, 2026-10-15, supersedes the
intermediate revision-review requirement in the approved design.

**Interfaces:** Keep ordinary mission identity, history, active-leg protection and
source ownership. Apply incoming conflicting source fields automatically; keep
compatible manual edits. Order shared mission views and exports by effective
departure time. Preserve the user's isolated preview data during its update.

1. Reproduce automatic-acceptance and chronological-order failures with tests.
2. Remove the JSON review UI, automatically apply revisions and retain retry and
   concurrency guards. Handle older ready operations without manual approval.
3. Verify source/KML departure order and takeoff overrides through shared storage.
4. Update production acceptance to require automatic revision and chronological
   API order; run full backend, frontend and static gates plus exact-head
   production CSV/PDF/clone qualification.
5. Update the user-requested preview, preserving volumes, and leave it running
   with its ownership and stop command. Push and update the PR against dev.
