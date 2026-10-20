# Starshield Conditional Call Outages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development to implement this amendment task by
> task. Steps use checkbox syntax for tracking. Preserve the already selected
> execution method; do not restart completed geographic/simulation work.

**Goal:** Count full transition windows as planned communications outages only
where no usable alternative exists, including concurrency-only X fallback.

**Architecture:** Add one pure call-continuity projection over forecast windows
and explicit transport capability intervals. Planning, status, simulation, and
PDF adapters consume its classifications while retaining physical evidence and
the normal Starshield preference. Resume the existing acceptance task after the
new semantics and presentation pass their own reviews.

**Tech Stack:** Existing Python/Pydantic, React/TypeScript, Vitest, Playwright,
and production HTML-to-PDF pipeline; no new runtime dependencies.

**Spec:**
[Approved revised design](../specs/2026-10-16-starshield-pop-transition-design.md).

## Global Constraints

- “Show every predicted transition, but classify its full 10-minute window as a
  planned communications outage only where Starshield is the sole usable call
  transport.”
- “Keep the normal Starshield preference without automatically switching
  services.”
- “X is a fallback only if removing the Starshield concurrency restriction would
  make it usable.”
- “Unknown capability remains unresolved rather than fabricating confirmed
  availability or a confirmed all-service outage.”
- Exact PDF event text: `Starshield Transition Window`.
- Exact PDF legend text: `Starshield Transition`; no text in marker rows.
- Preserve one-line PDF cells, existing font minimum, fit checks, and
  pagination.
- The physical Starshield lane/telemetry must not claim ten minutes of RF loss.
- No call scheduling interface, automatic routing, or automatic X activation.
- X-specific optimizer costs remain X-specific; do not overload their fields
  with overall communications outage totals.
- Half-open UTC bounds, flight clipping, service-change splitting, and union
  accounting prevent double counting. Fixed canonical windows stay T−300/T+300.
- Work in the existing isolated feature worktree/PR #353. Preserve the pending
  four legend tests and evidence; do not reset or replay completed tasks.
- Bound test/build commands with `timeout --kill-after=10s`; record and clean
  owned processes, listeners, Compose resources, and temporary paths.

## Review Focus

1. X has concurrency plus an independent AR/geometry block: it is not fallback
   even if a legacy reason string prominently mentions Starshield (Task 8).
2. Ka returns partway through a window: count only the no-alternative portion,
   while preserving the full visible forecast marker (Tasks 8–9).
3. Two windows overlap a real outage: union total seconds; do not inflate
   attribution or lose independent outage reasons (Tasks 8–9).
4. A cached/unknown capability cannot establish recoverable X: report unresolved
   continuity rather than guessing either available or confirmed outage (Task
   8).
5. The actual PDF can retain old copy or posture despite passing substring
   tests: verify exact legend region, one-line cells, and conditional hero band
   (Task 10).

## Files and shared interfaces

Use `B = backend/starlink-location`, `F = frontend/mission-planner`. Create
`B/app/services/pop/continuity.py` and `continuity_models.py`; keep them
independent of mission storage, renderer models, telemetry networking, and UI.
Create `B/app/mission/pop_continuity.py` for capability extraction/publication.

Frozen Pydantic records in `continuity_models.py`:

```text
CapabilitySpan(start_utc, end_utc, ka, x, starshield, x_concurrency_only,
               existing_call_outage, source_ids)
CallContinuityInterval(start_utc, end_utc, classification,
                       transition_ids, usable_alternatives, source_ids)
CallContinuityProjection(revision, intervals,
                         planned_communications_outage_seconds,
                         pop_call_outage_seconds, longest_call_outage_seconds)
```

Times are aware UTC datetimes. Capability values are `available`, `unavailable`,
or `unknown`; `x_concurrency_only` is a boolean backed by explicit evidence.
Classification is `ordinary`, `advisory`, `x_fallback`, `planned_outage`,
`existing_outage`, or `unknown`. IDs/alternatives are immutable tuples of
strings. Numeric totals are finite nonnegative seconds. Existing confirmed
outages classify as `existing_outage` before applying transition rules. Overall
outage totals union `existing_outage` and `planned_outage`;
`pop_call_outage_seconds` counts only additional `planned_outage` spans,
excluding already existing outages. Add typed wire fields under
`call_continuity` on mission timelines and status responses; absent fields from
old payloads render as unavailable, never a confirmed zero-outage result.

## Task 8: Shared continuity projection and mission/status integration

**Files:** Create the three backend modules above,
`B/tests/unit/test_pop_continuity.py`, and
`B/tests/unit/test_mission_pop_continuity.py`. Modify
`B/app/mission/{models,timeline_preparation,pop_status}.py`,
`B/app/api/status.py`, and timeline statistics attachment only where needed to
publish the new projection/totals. Reuse existing call-availability and planning
capability evidence; keep X optimizer evaluation unchanged.

**Interfaces:**

```text
project_call_continuity(forecast: PopForecast,
                        capabilities: Sequence[CapabilitySpan],
                        *, start_utc: datetime, end_utc: datetime)
    -> CallContinuityProjection
capabilities_from_timeline(timeline: MissionLegTimeline)
    -> tuple[CapabilitySpan, ...]
attach_call_continuity(timeline: MissionLegTimeline) -> None
```

- [ ] Write failing tests with a 12:00Z crossing: known sole Starshield produces
      exactly 600 outage seconds from 11:55Z to 12:05Z; Ka or independently
      usable X produces zero; X blocked solely by concurrency produces
      `x_fallback` and zero. Add concurrency+AR/elevation/manual/swap cases that
      still produce 600. Assert the supplied physical states and forecast bounds
      are unchanged. In the test module, define the `sole_starshield` fixture as
      keyword arguments for a 11:50Z–12:10Z flight containing the 12:00Z
      crossing, with known Ka/X unavailable and Starshield available throughout.
      Pin its expected totals:

  ```python
  def test_sole_starshield_counts_full_window(sole_starshield):
      result = project_call_continuity(**sole_starshield)
      assert result.planned_communications_outage_seconds == 600
      assert result.pop_call_outage_seconds == 600
      assert result.longest_call_outage_seconds == 600
  ```

- [ ] Run the focused command from B; verify missing-behavior failures before
      implementation:

  ```sh
  timeout --kill-after=10s 10m uv run --with-requirements requirements.txt \
    pytest tests/unit/test_pop_continuity.py \
    tests/unit/test_mission_pop_continuity.py -q
  ```

- [ ] Implement a boundary sweep using flight, capability, and transition
      bounds. An active window with known Starshield and both alternatives
      confirmed unusable is `planned_outage`; recoverable concurrency-only X is
      `x_fallback`. A confirmed alternative prevents a transition outage even if
      another is unknown. Otherwise unknown evidence remains `unknown`. Invalid
      intervals/revisions fail closed.
- [ ] Extract independent X capability from `planning_interval.physical_x_state`
      and raw constraints for policy timelines. Legacy extraction must retain
      all independent constraint evidence; do not release X from a reason
      substring or merely because its policy state is offline. Existing actual
      outages survive unchanged. Missing prerequisite evidence is unknown.
- [ ] Publish the projection after forecast attachment on prepared mission
      timelines, then add overall totals to statistics without reinterpreting
      `PlanningEvaluation.outage_seconds`, `critical_seconds`, or X
      optimization. Status uses matching active route/capability revisions and
      the existing mission clock/ETA basis; reject stale or misaligned
      capability data rather than mixing planned times with a shifted live
      forecast. Reuse prepared active inputs; do not rebuild the full mission or
      perform network discovery per poll.
- [ ] Add tests for Ka returning at 12:00Z (300 seconds), overlapping windows
      (union), overlap with existing call outage (no duplicate total),
      unknown/stale evidence, no route/catalog, disabled Starshield, and live
      completion/reset. Persistent live mismatch/overdue warnings do not extend
      saved planned totals.
- [ ] Run the focused tests plus existing mission, call-availability, planning
      policy, status, and simulation regressions; expect pass. Commit
      `feat: classify conditional Starshield call outage windows` and report
      exact source evidence/clock contracts for Task 9.

## Task 9: Planner, dashboard, simulation, and PDF continuity presentation

**Files:** Modify `F/src/types/{pop,timeline}.ts`,
`F/src/services/{timeline,status}.ts`,
`F/src/components/timeline/{PopForecastPanel,TimelinePreviewSection}.tsx`,
`F/src/pages/pop-advisory-projection.ts`,
`F/src/pages/OverviewPopAdvisories.tsx`, and their focused tests. Modify
`B/app/mission/exporter/{customer_pop,customer_projection,customer_view, customer_document,customer_evidence}.py`
and focused customer tests. Modify
`F/src/mission-export/briefing/{timeline,document,pdf-expectations}.mjs` and
their existing tests; add focused adapters if needed to keep new modules small.

**Interfaces:** Consume Task 8's `call_continuity` directly. Extend captured
customer payload/evidence with that same projection. Preserve original physical
usability decisions separately from call-continuity posture/remaining services.

- [ ] Update meaningful existing tests to replace the obsolete “always advisory,
      never change call outage totals” invariant. Add red integration assertions
      for sole-Starshield, Ka alternative, X-only concurrency fallback, and
      hard-blocked X. Keep the invariant that measured transport data and normal
      preference do not change. Marker bounds/text rules remain unchanged.
- [ ] Implement shared display: every window remains visible; no-alternative
      spans show planned communications outage/posture and new outage totals.
      Recoverable X shows an explicit planned fallback, without implying
      activation or requiring a scheduled call. Retain the existing X-outage
      metric label.
- [ ] Apply the shared projection to customer intervals after exact splitting.
      Planned outage portions show Communications unavailable and no usable
      secure-call transport; physical Starshield remains connected in its lane.
      X-only concurrency fallback prevents outage and is identified in
      details/table without changing exact short event/legend labels. Preserve
      other event impacts. Include continuity IDs/classification in row merge
      keys, source evidence, and cached renderer identity. Keep forecast-only
      exports free of live observations.
- [ ] Replace the explanatory note with concise text explaining possible call
      drops/reestablishment, conditional full-window planned outages, and
      coordinated fallback; use the canonical payload note in the renderer
      rather than duplicate its wording. Keep one-line table cells and existing
      fit/pagination limits.
- [ ] Run focused frontend Vitest and backend customer/continuity/cache tests,
      then renderer timeline/document/pagination/PDF-expectation tests with
      bounded commands. Assert partial overlap, simultaneous windows, preserved
      physical lanes, correct hero/posture/remaining-call services, unchanged
      UTC/ET bounds, explicit unknowns, and no text inside timeline markers. Run
      affected type/build and lint checks; commit
      `feat: present conditional PoP call outages consistently`.

## Task 10: Resume production qualification and final review

**Files:** Resume original Task 7 in `tools/acceptance/pop-transitions/`,
`tools/tests/test_pop_transition_acceptance.py`, and
`F/tests/e2e/pop-transitions.spec.ts`. Update operational docs and its report.

**Interfaces:** Existing exact-candidate runner command and ownership/evidence
contract remain unchanged. Preserve the pending four failing exact-legend tests;
finish their implementation before qualification. All prior evidence is a
checkpoint, not proof of the new semantics.

- [ ] Extend the real mission fixtures and actual-image probes to cover known
      sole Starshield, Ka alternative, concurrency-only X fallback, and
      concurrency plus independent AR/geometry restriction. Assert 600/0/0/600
      seconds, exact bounds, unchanged measured transport evidence, and no
      automatic switch.
- [ ] Complete independent exact legend-region and canonical marker geometry
      checks. Browser tests cover visible planner and active Overview markers,
      mobile selection, actual position-driven normal/dateline replay, and
      separately attributed synthetic early/late/mismatch responses. Actual PDFs
      must prove conditional posture, short labels, one-line overlap cells, and
      continuation fit.
- [ ] Consolidate runner changes before committing a candidate. Run the affected
      complete backend/frontend/static tiers and renderer/runner checks with
      explicit bounds. Prior live-startup/config fixes require the pending
      backend full rerun; do not discard those failures or weaken their
      assertions.
- [ ] Execute the existing exact committed SHA production runner, inspect actual
      PDF rasters/browser screenshots, preserve candidate and artifact
      identities, and verify all owned resources are gone. Obtain task review
      and whole-branch review, resolve required findings, update PR #353 with
      truthful final evidence, and retain the open-PR worktree. No merge without
      the user's authorization.

## Handoff

Self-review maps every revised spec rule to Tasks 8–10 and the five Review Focus
cases to explicit tests. Earlier completed tasks remain completed; this
amendment changes their call-continuity assumptions rather than repeating their
geometry, resolver, or simulation implementations. Review this written amendment
before execution, using the already agreed subagent-driven method.
