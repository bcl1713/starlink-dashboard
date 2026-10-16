# Starshield PoP Transitions Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Integrate the shared forecast with simulation, UI, and customer PDFs.

**Architecture:** Consume the catalog, forecast, and observation contracts in
the [main plan](2026-10-16-starshield-pop-transitions.md); do not duplicate
them.

**Tech Stack:** Existing Python, React/TypeScript, Playwright, and PDF renderer.

**Spec:**
[Approved design](../specs/2026-10-16-starshield-pop-transition-design.md).

## Global Constraints

All constraints, Review Focus cases, path prefixes, and shared contracts from
the main plan apply. Execute Tasks 4–7 after Tasks 1–3, in order.

## Review Focus

Tasks 5–6 cover SOF/outage/DST overlaps and catalog supersession during capture;
Task 4 covers simulation isolation. See the main plan for the full review list.

## Task 4: Position-driven simulated PoPs and synthetic IPs

**Files:** Create `B/app/simulation/pop.py` and
`B/tests/unit/test_simulation_pop.py`. Modify `B/app/simulation/coordinator.py`,
`B/main.py`, and the observation provider from Task 3. Extend
`B/tests/unit/test_ground_entry_point_refresh_policy.py` and
`B/tests/integration/test_simulation_run_lifecycle.py`.

**Interfaces:** `SimulationPopResolver(catalog: PopCatalog)` with
`update(latitude: float, longitude: float) -> PopObservation` and
`reset() -> None`. Return standard `GroundEntryPoint` values through the Task 3
observation contract; assign the initial sorted catalog IDs stable addresses
`192.0.2.1` through `192.0.2.6`. Keep mapping identity stable when catalog
ordering changes; catalog reload may rebuild the resolver and reset its
lifecycle state.

- [ ] Write failing tests for no-route position updates, stable IP within a
      region, IP and city change at a boundary, anti-meridian movement,
      previous-winner ties, invalid position, reset/seek, and switching back to
      live mode. Patch external DNS/HTTP discovery to raise if invoked during
      simulation.
- [ ] Run the new simulation tests and refresh-policy testsExpect red.
- [ ] Implement simulated selection from actual emitted position, including
      replay frames. Keep normal simulation suppression of external egress
      discovery. Publish metrics/status via a mode-specific provider without
      contaminating the production resolver cache. No artificial packet loss or
      outage is introduced.
- [ ] Add a planned replay test crossing the fixture boundary at T: assert the
      first changed simulated IP coincides with T within one emitted frame and
      geometric tolerance. Add speed, seek, route-free, mode-switch, and reset
      tests.
- [ ] Repeat the focused command and simulation lifecycle integration tests;
      expect pass. Commit as
      `feat: simulate geographic PoPs and synthetic egress IPs`.

## Task 5: Planner and Overview advisory presentation

**Files:** Create `F/src/types/pop.ts`,
`F/src/components/timeline/PopTransitionMarkers.tsx`, and its `.test.tsx`.
Modify `F/src/services/{timeline,status}.ts`, `F/src/types/timeline.ts`,

```text
F/src/components/timeline/{TimelinePreviewSection,CoverageSequence,TimelineTable}.tsx
```

, `F/src/pages/OverviewPage.tsx`, and
`F/src/pages/simulation-run-projection.ts`. Create
`F/src/pages/pop-advisory-projection.ts` and its `.test.ts` to keep
interpretation outside the large Overview component.

**Interfaces:** TypeScript types mirror backend wire models. Component
`PopTransitionMarkers({forecast, startUtc, endUtc, onSelect})` renders only
outlined, accessible, keyboard-selectable markers; selection provides transition
details outside timeline rows. `projectPopAdvisories(status)` returns display
records; it never changes transport/status fields.

- [ ] Write failing tests asserting ten-minute marker bounds, no text child
      inside timeline rows, UTC city/center details, equal advisory treatment
      with/without Ka/X, unknown versus empty forecast, and
      early/overdue/mismatch display. Verify stale responses cannot replace a
      newer route revision.
- [ ] From F run

```text
timeout --kill-after=10s 10m npm run test:unit -- src/components/timeline/PopTransitionMarkers.test.tsx src/pages/pop-advisory-projection.test.ts
```

Expect red.

- [ ] Implement markers, legend/details, and active live advisory display. Reuse
      current timeline scale and simulation clock; handle zero-duration/absent
      bounds safely. Include a marker even if availability is nominal. Do not
      add a toggle, in-row label, PoP editor, or new transport posture category.
- [ ] Add overlap tests preserving SOF and real outages, plus mobile keyboard
      access and obsolete-revision rejection. Run focused tests and existing
      timeline, status projection, and simulation projection tests; expect pass.
      Commit as
      `feat: show PoP transition advisories in planning and live views`.

## Task 6: Customer PDF, captured evidence, and cache invalidation

**Files:** Modify

```text
B/app/mission/exporter/{snapshot_inputs,snapshot_views, customer_projection,customer_view,customer_document,customer_evidence}.py
```

, `B/app/mission/slide_cache/{capture,identity}.py`, and
`F/src/mission-export/briefing/{timeline,document,pdf-expectations}.mjs`. Create
`B/app/mission/exporter/customer_pop.py` for advisory partition helpers. Extend
existing `test_customer_projection.py`, `test_slide_cache.py`, customer document
tests, and briefing timeline/document tests. Add sanitized fixtures under
`B/tests/fixtures/customer_briefing/`.

**Interfaces:** `partition_pop_windows(intervals, forecast: PopForecast)` in
`customer_pop.py` returns intervals split at clipped advisory bounds, preserving
the original decisions/posture and attaching transition occurrence IDs. Extend
customer models with default-empty IDs; use those IDs when selecting/merging
rows. `customer_document` emits additive `popTransitions` with full UTC bounds
and `popTransitionIds` on relevant intervals/rows.

- [ ] Write failing tests for a nominal advisory row retaining Starshield and
      Nominal posture, overlapping Ka/SOF impacts, multiple simultaneous
      transition IDs, boundary clipping, DST clock identity, and no accidental
      row merging across an advisory edge. Assert the interval partition still
      covers the flight exactly.
- [ ] Run focused backend customer tests and, from F,

```text
timeout --kill-after=10s 10m node --test src/mission-export/briefing/timeline.test.mjs src/mission-export/briefing/document.test.mjs
```

Expect relevant failures.

- [ ] Capture catalog bytes/fingerprint with snapshot dependencies and use the
      captured catalog for rebuilding. Include catalog identity in capture
      tokens, leg fingerprints, and machine-readable forecast evidence. Test
      catalog edits during capture reject stale publication and trigger
      preparation; unrelated live mismatch advisories must not enter planning
      exports.
- [ ] Integrate advisory partition/row selection without calling outage
      classifiers with advisory reasons. Add unlabeled outlined PDF markers and
      exact event copy “Starshield PoP transition possible — brief call
      interruption.” Add explanatory note “PoP transitions may briefly interrupt
      calls (typically 1–2 seconds). Marked windows indicate possible transition
      timing.” Preserve ET table formatting, exact UTC evidence, pagination, and
      remaining-comms/posture semantics.
- [ ] Repeat focused commands plus existing customer pagination and cache tests;
      expect pass. Commit as
      `feat: include PoP coordination windows in customer briefs`.

## Task 7: Production acceptance, review, and integration

**Files:** Create `tools/acceptance/pop-transitions/{run.py,seed.py,README.md}`,
`F/e2e/pop-transitions.spec.ts`, and
`tools/tests/test_pop_transition_acceptance.py`. Extend the existing customer
briefing production seed/probe only to expose the new sanitized fixtures. Update
`docs/features/mission-planning.md` and
`docs/development/customer-briefing-exports.md` with operational behavior and
the deferred PoP-management scope.

**Interfaces:** Runner command from repository root:

```text
timeout --kill-after=10s 45m python3 tools/acceptance/pop-transitions/run.py --candidate-sha <full-committed-sha> --evidence-root <owned-path>
```

. Reuse repository acceptance Compose/browser lifecycle helpers and production
Dockerfiles/Nginx; do not introduce a fake substitute deployment.

- [ ] First add runner tests for rejection of dirty/mismatched candidates,
      artifact identity checks, bounded failures, and teardown after browser/PDF
      failure. Run the bounded uv/pytest tools-test command and verify red
      before implementing.
- [ ] Implement a task-specific Compose runner with private
      data/volumes/loopback ports, signal/exit cleanup, PID/process-group
      ownership records, browser-context closure, and verified teardown.
      Preserve configured Docker context/DOCKER_HOST. Record candidate/image
      identity, actual API responses, screenshots, PDF raster and text/geometry
      checks, and evidence hashes. Separate deterministic provider fixtures from
      observations about actual Starshield behavior.
- [ ] Seed a boundary-crossing mission, no-crossing mission, dateline mission,
      overlapping outage/SOF mission, and route-free simulation. Browser checks
      must observe changed synthetic IP/city at the modeled boundary through
      actual APIs, early/late/mismatch advisory cases, and preserved service
      states/preference. Inspect actual exported PDF marker bounds, absence of
      in-row labels, readable ET coordination rows, note, continuation pages,
      and unchanged remaining comms.
- [ ] Run focused backend/frontend tests, applicable full suites, Python lint,
      TypeScript build/ESLint, Markdown checks, and renderer tests under
      explicit time limits. Use repository Python 3.11 and Node engine
      requirements. Resolve failures; after a timeout prove the previous process
      tree stopped before retry.
- [ ] Commit the acceptance runner/docs, then run production acceptance against
      that exact committed SHA. Preserve evidence under a task-owned path,
      record its candidate identity, and verify no owned
      processes/listeners/Compose containers/networks/disposable volumes remain.
      Do not leave a preview running.
- [ ] Obtain the execution method's required code review, resolve findings, and
      rerun affected checks after changes. Push the feature branch and open a PR
      to `dev`, linking #348 and exact-candidate acceptance evidence. Wait for
      required checks and review before merge; do not claim completion from unit
      tests alone.
- [ ] After merge, verify the PR merged into `dev`, remove its worktree and
      local/ remote feature branches and task-owned temporary files. Keep
      open-PR worktrees and acceptance evidence; preserve shared runtime
      configuration and credentials.
