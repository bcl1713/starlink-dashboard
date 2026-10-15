# SIGMET Encounter Timing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add plan-bound passage UTC and time-overlap evidence to geographic
SIGMET notices while preserving attention and acknowledgement behavior.

**Architecture:** Extend the authoritative route capture with immutable waypoint
times and a separate encounter revision. A bounded pure calculator enriches
cached geographic spans; the shared backend response and browser owner carry
strict v2 evidence into existing cards and expanded details.

**Tech Stack:** Existing Python 3.11, FastAPI, Pydantic, TypeScript, Zod,
React/TanStack Query, pytest, Vitest, Playwright and Docker. No new
dependencies.

**Spec:**
[Approved timing-only design](../specs/2026-10-15-sigmet-encounter-context-design.md).

Status: Approved for native implementation on 2026-10-15. Tasks 1–4 implemented;
production acceptance and independent review passed. PR targets `dev`. Worktree:
`.worktrees/sigmet-encounter-spec`; branch: `feat/sigmet-encounter-context`;
inspected base `b373324d`.

## Global Constraints

- Planned-altitude comparison is excluded permanently from this feature.
- Preserve eligibility, attention order, map filtering, acknowledgement and
  manual selection; retain reported SIGMET vertical bounds.
- Use effective route waypoint UTC, never live speed, aircraft position,
  observed departure adjustment, replay clock or total duration to fill gaps.
- Interpolate `t(f) = t0 + f * (t1 - t0)` only with aware times `t0 < t1`.
- Compare closed passage intervals with half-open validity
  `[valid_from, valid_to)`; a touch at expiry does not overlap.
- Aggregate: any overlap wins; all known nonoverlaps yield no-overlap; otherwise
  unknown. Preserve unknown counts even when overlap is known.
- Introduce `route-sigmets-v2`; preserve mutation contracts and endpoint paths.
- Keep geographic/notice keys unchanged; timing changes get a separate digest.
- Retain 20,000 points, 500 advisories, 100,000 aggregate spans, 8 MiB results;
  browser budgets stay 16 MiB encoded, 32 MiB decoded, 16 MiB GPU, four
  operations.
- Existing five-second polling and eight-second controlled propagation remain.
- No new controls, camera changes, poll announcements, altitude status or
  poller.
- Work only in this feature worktree. Push a PR against `dev`; preserve the
  worktree while open. Commits use the connected GitHub account’s command-scoped
  noreply identity.
- Record owned resources before checks; use wall limits and cleanup handlers;
  verify scoped teardown after success, failure or cancellation.

## Review Focus

1. Same geometry with edited times must update evidence without reopening a
   cleared notice; Task 2 pins geometry reuse and acknowledgement stability.
2. A→B→A edits and simultaneous reads can share digest values; Tasks 2/3 pin
   observation ordering instead of sorting hashes or using notice revisions.
3. Missing altitude or zero height must not affect timing; Tasks 1/4 pin an
   altitude-free KML and live-altitude independence.
4. Minute rounding near expiry must not change classification; Tasks 1/3 pin
   exact milliseconds and deterministic date-aware display.
5. Partial evidence and selected-only reports must not suggest continuous or
   confirmed passage; Tasks 3/4 pin gaps, counts and unavailable wording.

## File map and commands

Aliases below expand relative to the task worktree:
`B = backend/starlink-location`, `W = B/app/services/aviation_weather`,
`F = frontend/mission-planner`, `A = F/src/pages/aviation-weather`,
`R = tools/acceptance/aviation-weather`.

New files: `B/app/models/sigmet_encounters.py` (strict evidence types),
`W/route_encounters.py` (pure calculation and digest),
`B/tests/unit/test_route_sigmets_encounters.py`, `A/sigmet-encounter-text.ts`,
`A/sigmet-encounter-text.test.ts`, `A/SigmetEncounterDetails.tsx`,
`A/SigmetEncounterDetails.test.tsx`,
`B/tests/fixtures/route-sigmets/altitude-free-timing.kml`,
`docs/reports/2026-10-15-sigmet-encounter-context.md`. Other modified files are
named in tasks. Avoid unrelated refactors.

Backend focused command, from B (substitute named test files):

```bash
timeout --kill-after=10s 10m uv run --with-requirements requirements-dev.txt --with-requirements requirements-gfs.txt pytest tests/unit/test_route_sigmets_encounters.py -q
```

Frontend focused command, from F (substitute named test files):

```bash
timeout --kill-after=10s 10m npm run test:unit -- src/pages/aviation-weather/sigmet-encounter-text.test.ts
```

Use tracked Python/Node versions and provision dependencies only as needed.
Before resource-owning commands write a local ownership ledger under
`test-results/sigmet-encounter-context/`: command, shell PID/process group,
session, paths, and any Compose project/volumes. Do not commit that ledger or
credentials. All test steps below use the bounded commands above.

## Task 1: Immutable route evidence and pure timing calculation

**Files:** New backend files in the map; modify `B/app/models/route_sigmets.py`,
`W/route_context.py`, `B/tests/unit/test_route_sigmets_context.py`.

**Interfaces:** Capture immutable `EncounterPlan` and calculate
`EncounterEvidence` using the
[Task 1 contract](2026-10-15-sigmet-encounter-contracts.md#task-1-interfaces).

- [ ] Write failing calculator tests using a 00:00–00:10 UTC segment and
      fractions .25/.75: passage is 00:02:30–00:07:30 exactly. Assert touch at
      valid-from overlaps, touch at expiry does not, exit at valid-from
      overlaps, midnight works, and 1 ms before expiry stays overlap.
- [ ] Add missing/naive/equal/reversed time and invalid segment-index tests;
      assert unknown reason and one-for-one evidence. Assert mixed known
      no-overlap plus unknown aggregates unknown; overlap plus unknown retains
      overlap and unknown_count=1. Disjoint spans remain distinct.
- [ ] Add context tests: timing-only edits change encounter revision but leave
      geographic key unchanged; rename and clock ticks change neither; current
      running/completed simulation uses its selected artifacts. A deep-copy
      mutation cannot alter the captured plan. No altitude affects the digest.
- [ ] Run focused tests and confirm behavioral failures before implementation.
- [ ] Implement strict evidence types, frozen capture and linear calculator;
      normalize aware timestamps to UTC milliseconds before hashing; reject
      invalid evidence combinations and nonfinite numeric values. Do not change
      time eligibility or interpret height. Hash after releasing route locks.
- [ ] Run context/calculator tests and existing geometry/identity tests; require
      PASS. Commit `feat: calculate planned SIGMET passage timing`.

## Task 2: Coherent v2 snapshots and bounded runtime integration

**Files:** Modify `B/app/models/route_sigmets.py`, `W/route_runtime.py`,
`B/tests/unit/test_route_sigmets_runtime.py`,
`B/tests/unit/test_route_sigmets_contracts.py`,
`B/tests/unit/test_route_sigmets_api.py`, `B/app/api/route_sigmets.py` if
needed.

**Interfaces:** Consume Task 1 evidence; publish coherent strict v2 snapshots
using the
[Task 2 contract](2026-10-15-sigmet-encounter-contracts.md#task-2-interfaces).

- [ ] Write runtime failures for same-geometry timing edits: geographic worker
      call count stays unchanged, passage changes, persisted acknowledgement and
      attention order stay unchanged. Pin A→B→A and delayed worker/reconcile
      completions: old evidence cannot publish after the later observation.
- [ ] Add off/no-route/source-unavailable and selected-only contract tests;
      require null plan when no context, no fabricated selected spans, strict v2
      and unchanged acknowledgement/selection requests. Reject wrong-length
      evidence, inconsistent status/count and response size over 8 MiB.
- [ ] Add cancellation/shutdown tests for enrichment and a simulated calculator
      failure: retain geographic entries with unknown/unavailable-plan evidence
      when representable. Current altitude mutation changes neither evidence nor
      notice eligibility. Capture data under locks, calculate outside them.
- [ ] Run runtime/contracts/API tests; confirm new assertions fail.
- [ ] Implement enrichment using the existing owned `_thread` path. Use a
      two-entry LRU bounded by aggregate 8 MiB serialized evidence and keyed by
      geometry identity, encounter revision and bulletin validity; clear it on
      disable/close. Existing geometry cache key remains geometry-only. Check
      whole-response limits; fail explicitly without truncating spans.
- [ ] Run all `tests/unit/test_route_sigmets_*.py`; require PASS. Commit
      `feat: publish coherent v2 SIGMET encounter snapshots`.

## Task 3: Strict browser migration and shared passage presentation

**Files:** Modify `F/src/services/route-sigmets.ts` and its test,
`F/src/test/route-sigmet-fixtures.ts`, `A/route-sigmet-source.ts` and its test,
`A/SigmetAttentionCard.tsx`, `A/RouteSigmetSettings.tsx` and its test,
`A/RouteSigmetNotices.test.tsx`; create frontend files in the map. Update all
remaining tracked v1 snapshot fixtures found with
`rg -n 'route-sigmets-v1' backend frontend tools`.

**Interfaces:** Consume v2 snapshots; share decoder, formatter and detail
components using the
[Task 3 contract](2026-10-15-sigmet-encounter-contracts.md#task-3-interfaces).

- [ ] Write decoder tests rejecting v1, extra fields, inconsistent evidence,
      nonfinite times, unsafe integers, missing v2 ordering metadata and
      oversized results. Migrate defaults centrally; do not silently accept v1
      fallback.
- [ ] Write source lifecycle tests with equal acknowledgement revision but newer
      observation revision; assert stale same-instance completion is rejected.
      An instance change is accepted only from the current request epoch; do not
      numerically compare revisions across different service instances. Preserve
      existing feed identity, abort, write-serialization and budget guards.
- [ ] Write formatter tests pinning UTC independently of host timezone: same-day
      `Planned passage 14:20–14:32 UTC · Time overlap`;
      cross-midnight/historical values include dates. Round nearest minute for
      summary only; details preserve exact milliseconds. Multiple disjoint spans
      say `Planned passage     summary` and disclose unknown_count. Missing
      timing says `Planned passage     unavailable · Missing waypoint times`;
      selected-only says `Encounter     unavailable — no route intersection`.
      No-overlap uses neutral text.
- [ ] Add component tests showing per-span details and source/method evidence,
      retained vertical bounds, unchanged attention
      count/paging/acknowledgement, and no repeating live announcements when
      only polling timestamps change.
- [ ] Run selected service/source/formatter/component tests; confirm failures.
- [ ] Implement strict v2 schemas, source ordering and shared components.
      Replace the obsolete passage-time-unevaluated Configuration copy; retain
      that altitude is not evaluated, actual UTC governs eligibility and
      simulation uses planned dates. Keep existing actions and map emphasis
      untouched.
- [ ] Run frontend unit suite, ESLint and production build, each with a
      10-minute wall limit. Require PASS; record existing build warnings. Commit
      `feat: display planned passage evidence on SIGMET notices`.

## Task 4: Altitude-free production journey, evidence and PR

**Files:** Modify `R/generate_fixtures.py`, `R/backend_fixture.py`,
`R/runner.py`, `F/tests/e2e/route-sigmets-production.spec.ts`,
`F/tests/e2e/support/route-sigmets-probe.ts`,
`tools/tests/test_route_sigmets_acceptance.py`,
`docs/features/overview-weather.md`, `docs/api-reference-index.md`; create
sanitized KML fixture and evidence report from the map.

**Interfaces:** Extend the existing proof receipt with `encounter` flags:
`altitude_free`, `time_boundaries`, `plan_edit_ack_preserved`,
`selected_only_unknown`, `partial_evidence`, `two_screen_sync`,
`responsive_details`, `no_altitude_filter`. `require_pass` requires all true,
existing source-shaped replay proof and complete cleanup. Missing flags fail.

- [ ] Add fail-closed runner tests for each missing flag. Create a minimal
      synthetic KML matching the supplied shape: 2D coordinates, clampToGround,
      waypoint UTC descriptions. Do not commit the user's complete flight route.
      Exercise normal route ingestion rather than supplying constructed times
      directly to the calculator. Assert resolved times match waypoint values.
- [ ] Extend the production browser journey with two independent contexts
      through Nginx: known overlap/nonoverlap, missing endpoint,
      disjoint/partial spans, historical simulation, selected-only unknown. Edit
      timing with unchanged geometry and a cleared notice; verify both displays
      converge within eight seconds and the notice remains acknowledged. No
      altitude changes may hide notices or alter evidence. Verify future-valid
      reports remain ineligible.
- [ ] Capture 1920×1080 and 390×844 cards and expanded details; inspect dates,
      unknown counts, vertical bounds and clipping. Retain existing map-label,
      paging, disposal and dated upstream-replay scenarios. Record allocation
      peaks including old-plus-new evidence inside existing weather budgets.
- [ ] Run focused runner tests under `timeout --kill-after=10s 10m`; run all
      route-SIGMET backend tests and frontend unit/lint/build checks after any
      corresponding edits. Require PASS before candidate commit.
- [ ] Update API/operator docs with v2 fields and migration, fixed assumptions,
      no altitude source, and no suppression for no-overlap. Commit candidate
      `test: verify timing-only SIGMET encounter workflow`.
- [ ] Read cloud Docker guidance and inspect the configured actor daemon without
      clearing DOCKER_HOST/context. Record the runner-generated private project,
      processes, ports, volumes and evidence directory. From worktree root run:

```bash
timeout --kill-after=10s 40m tools/acceptance/aviation-weather/run.sh "$(git rev-parse HEAD)" "$AVIATION_ACCEPTANCE_BROWSER"
```

Use the existing provisioned browser endpoint; if absent, provision through
documented acceptance setup rather than guessing an endpoint. Require the
runner's PASS receipt, exact candidate provenance, all encounter flags,
screenshots and cleanup receipt. No skipped browser cases count as PASS.

- [ ] Verify no task-owned process/listener/container/network/disposable volume
      remains, using approved host inspection if PID namespaces hide processes.
      On timeout verify the old tree stopped before retry. Preserve evidence;
      never prune shared resources or leave preview services running.
- [ ] Record results and limitations in the evidence report. Any subsequent
      product/test/runtime change needs fresh exact-commit acceptance. A
      documentation-only evidence commit may cite the tested candidate
      explicitly.
- [ ] Obtain whole-branch review using requesting-code-review, resolve findings
      with focused regression checks and rerun applicable acceptance. Push this
      feature branch and open a PR against `dev`; include proof and known
      limits. Preserve its worktree while open. After a confirmed merge remove
      only this worktree, feature branches and task-owned temporary files.

## Plan self-review and handoff

Coverage checked: authoritative timing capture, mathematical boundaries,
provenance/precision, unchanged notice identity, stale-response ordering, v2
migration, partial/selected evidence, UI copy, limits, owned cleanup,
altitude-free ingestion and production two-screen evidence each have an owning
task above. No altitude comparison, new provider or independent poller is added.
Tasks are sequential because each consumes the prior task's contract.

Recommend native execution in this session because the four tasks share the same
route capture and snapshot contract. Obtain user plan review and execution
choice before implementation. Use the verified connected GitHub identity for
command-scoped commits; do not infer an author email from existing commits or
change global Git configuration.
