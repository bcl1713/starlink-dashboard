# Shared evaluation and X band optimization implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans.
> Complete checkbox steps task-by-task after plan approval.

**Goal:** Score, propose, edit, and save X-band plans without sacrificing usable
Starshield or changing the evaluation grid after proposal application.

**Architecture:** A pure evaluator supplies physical constraints and operating
policy intervals to canonical timeline preparation. A bounded discrete solver
consumes cached interval costs, while persistence rejects stale results.

**Tech Stack:** Python 3.11, existing geometry/timeline engine, React, Vitest.

**Spec:** [Design](../specs/2026-10-09-itinerary-xband-planning-design.md) and
[contracts](../specs/2026-10-09-itinerary-xband-planning-contracts.md).

## Global constraints

Read the [main plan](2026-10-09-itinerary-xband-planning.md) and complete Tasks
1–4 first. Exact policy, grid, interval, and model limits come from the approved
contracts; no separate optimizer interpretation of availability is permitted.

## Review focus

Task 5 pins unavailable configured satellites and exact policy/geometry data.
Task 6 pins unlocked off-grid edits, stable accepted contexts and deadline
cleanup. Task 7 pins two-tab conflicts, missing satellites and manual choices.

## Task 5: Shared exact boundaries, geometry and operating policy

**Files:** Create `app/mission/planning/{inputs,grid,evaluate}.py` and
`app/mission/effective_route.py`, and
`tests/planning/{test_policy,test_grid,test_canonical}.py`. Modify
`app/mission/{models,timeline_preparation,call_availability}.py`,
`app/mission/timeline_builder/{calculator,events,aar}.py`,
`app/mission/exporter/{customer_projection,snapshot_inputs}.py`, and
`app/services/{active_x_link,active_x_handoff}.py`.

**Interfaces:**

```python
build_inputs(leg: ExpectedLeg, draft: PlanningDraft, route_manager: RouteManager, poi_manager: POIManager, constraints: ConstraintConfig) -> PlanningInputs
prepare_effective_route(leg: MissionLeg, route_manager: RouteManager, normalize_for_simulation: bool = False) -> ParsedRoute
build_context(inputs: PlanningInputs, draft: PlanningDraft) -> EvaluationContext
evaluate_context(inputs: PlanningInputs, draft: PlanningDraft, context: EvaluationContext) -> PlanningEvaluation
```

Define `PlanningInputs` in planning/models.py: immutable route/height/timing
snapshots, AR/overlay/outage intervals, permitted satellite positions,
operational Starshield enablement, ConstraintConfig, policy and canonical input
identity. inputs.py uses the same POI/catalog resolution order as timeline
planning and rejects missing positions. effective_route.py extracts shared
departure/splice preparation from canonical timeline preparation; both callers
use it, preserving simulation normalization. Missing AR units remain an
unresolved review issue, not an invented conversion. grid.py creates/persists
C/B exactly as specified, including every existing swap. evaluate.py returns raw
identities plus physical/policy states independently. With planning policy,
disabled Starshield projects Ku unavailable before transport-choice policy for
canonical timelines, map and export/backup gaps. Ku overrides still apply when
enabled. Overview visibility is never an input.

- [ ] **Step 1:** Write named cases
      `test_ku_preference_counts_conflict_shutdown`,
      `test_ku_outage_or_disabled_releases_only_concurrency_constraint`,
      `test_safety_advice_adds_no_outage`, `test_overlap_counts_once`,
      `test_unlocked_second_level_swap_has_all_buffer_boundaries`, and
      `test_context_survives_removing_seed_swap_after_apply`:

  ```python
  assert conflict_eval.outage_seconds == 60
  assert conflict_eval.intervals[0].physical_x_available is True
  assert conflict_eval.intervals[0].policy_x_available is False
  assert ku_down_eval.outage_seconds == 0
  assert sof_only_eval.outage_seconds == 0
  assert {entry, swap - buffer, swap, swap + buffer} <= set(context.boundaries)
  assert accepted.context.boundaries == proposal.context.boundaries
  ```

  Use finite geometric fixtures or stub only look angles; do not stub policy or
  canonical decisions. Test AR entry/exit half-open behavior, simultaneous
  assignments, exact altitude changes, manual overlays, effective splice route,
  longitude wrap and missing satellite/height assumptions. Pin enablement
  persistence/reload/export and invariance under Overview visibility edits;
  enabling/disabling invalidates context and review identity. Parse/bind
  repeated-visit KML through the API, reload RouteManager, and compare
  preview/canonical costs and positions at both timed visits. Constructed
  ParsedRoute fixtures alone cannot prove the ingestion/timing contract.

- [ ] **Step 2:** Run `test_policy.py test_grid.py test_canonical.py`; expect
      policy restoration and fixed-grid inconsistencies to fail.
- [ ] **Step 3:** Implement grid/evaluator and optional explicit boundaries in
      canonical sampling. Existing calls without policy/context keep legacy
      semantics. Planning calls must use the persisted context; canonical
      assembly exposes policy-shutdown metadata rather than undoing it during
      call normalization. Keep safety call restrictions separate from RF state.
      Customer projection consumes policy evidence, including released conflict
      during Ku outage; it must not infer Down from stale raw text alone.
      Runtime handoff resolution honors occurrence anchors for repeated route
      coordinates. Planned map warnings use the same policy; live telemetry
      overlays retain observed-position/freshness meaning and disclosed inputs.
- [ ] **Step 4:** Assert optimizer-facing evaluation and prepared
      timeline/export produce identical intervals/reasons/cost after
      save/reload; run existing satellite geometry/rules, mission timeline, call
      availability, customer projection, active-X link and handoff tests. Legacy
      fixtures stay unchanged.
- [ ] **Step 5:** Commit
      `feat: share Starshield preference availability scoring`.

## Task 6: Exact discrete optimizer and revision-safe proposal service

**Files:** Create `app/mission/planning/{optimizer,proposals}.py` and
`tests/planning/{test_optimizer,test_proposals}.py`; extend planning/models.py,
service.py and routes.py. Reuse deadlines.run_bounded from Task 2.

**Interfaces:**

```python
optimize(inputs: PlanningInputs, draft: PlanningDraft, context: EvaluationContext) -> PlanningProposal
ProposalService.generate(mission_id: str, leg_id: str, request: GenerateProposal) -> PlanningProposal
ProposalService.get(mission_id: str, leg_id: str, proposal_id: str) -> PlanningProposal
ProposalService.apply(mission_id: str, leg_id: str, request: ApplyProposal) -> PlanningView
```

`GenerateProposal` supplies expected revision and optional idempotency key.
`ApplyProposal` supplies proposal ID, expected revision and input identity. The
service requires a nonempty validated permitted set and current access
confirmation; all generated assignments stay within it. Selection edits
invalidate proposals/review and require reconfirmation, without silently
removing manual assignments or locks (ineligible ones become field errors). The
service captures inputs/context under the store gate, computes outside locks
with a 30-second deadline, and rechecks identity before publishing. Derived
proposal persistence does not increment the user-edit revision; draft
application does. Store immutable proposal payloads under mission-owned planning
storage and manifest references, with stale identity reflected on read.

- [ ] **Step 1:** Implement a test-only exhaustive schedule enumerator for small
      C/permitted sets in tests/planning/cases.py. Test constant-only baseline,
      swaps whose 30-minute buffer erases benefit, unavoidable gaps, policy-free
      alternatives, locked initial/swap choices, overlapping preexisting locks,
      same-instant incompatible locks, deterministic ties, deadline kill/reap,
      excluded/ineligible satellites, unconfirmed access, and late result after
      a tab changes Ku outage, enablement, permitted set or draft timing:

  ```python
  assert candidate_score == min(exhaustive_canonical_scores)
  assert candidate_score <= baseline_score
  assert all(required_lock in candidate.draft.locks for required_lock in locks)
  assert same_input_first.draft == same_input_second.draft
  assert late_result.status_code == 409 and installed_after == installed_before
  ```

  Score tuples are `(outage_seconds, swap_count, stable_schedule_key)`.

- [ ] **Step 2:** Run `test_optimizer.py test_proposals.py`; expect unmet
      solver, deadline, idempotency and stale-result contracts.
- [ ] **Step 3:** Implement shortest-path/dynamic-programming search with state
      tracking current satellite, time, mandatory-lock cursor and buffered
      transition history. Precompute shared per-satellite interval costs and
      prefix sums; compute complete edge costs, including pre-swap buffer time.
      Generated windows cannot overlap another generated window; existing manual
      locked overlaps retain their fixed union cost and exact assignment order.
      Reject no feasible locked schedule without mutating the draft. Do not
      prune candidates unless dominance is proven against the lexicographic
      objective. Reconstruct the winner and fail if canonical cost differs. A
      timeout terminates/reaps only the owned child and returns retryable 503;
      cancellation/shutdown also releases owned workers. No background producer
      survives the request. Proposal read cannot rerun the solver.
- [ ] **Step 4:** Rerun focused tests; measure representative 19-hour synthetic
      legs and configured satellite counts. Report measured duration; exceeding
      the deadline is failure rather than a best-effort optimum. Read/proposal
      requests never change active flags, published timelines or operational
      POIs.
- [ ] **Step 5:** Commit `feat: propose bounded X-band satellite schedules`.

## Task 7: Proposal review, manual locks and validated reviewed save

**Files:** Frontend create
`src/components/planning/{XBandPlanReview,ProposalComparison}.tsx`,
`src/components/planning/*.test.tsx` for these components; modify
`src/{services/planning.ts,hooks/api/usePlanning.ts}`,
`src/components/satellites/XBandConfig.tsx`,
`src/components/timeline/TimelinePreviewSection.tsx`,
`src/pages/LegDetailPage.tsx` and
`src/pages/LegDetailPage/LegMapVisualization.tsx`. Backend extend
planning/{service,routes,store}.py and create
`tests/planning/test_reviewed_save.py`. Adapt existing
`app/mission/routes_v2.py` ordinary leg PUT and parent update delegation; extend
its regression tests. Update frontend `src/services/missions.ts` and
`src/hooks/api/useMissions.ts` with optional typed planning CAS arguments for
managed PUT/DELETE callers; retain unmanaged call signatures.

**Interfaces:** `PlanningService.preview(..., request: PreviewDraft)` returns
PlanningEvaluation without writes. `save_reviewed(..., request: SaveReviewed)`
validates AR confirmations/exclusions and satellite plan, rechecks identity,
prepares artifacts, then calls Task 3's commit_reviewed. Requests include
revision; reviewed save carries input identity and gap acknowledgment. Reviewed
save requires current satellite access confirmation and explicit Starshield
enablement. Managed ordinary PUT uses the same revision/identity checks and
transactional publication, rejects plan changes on active legs, and rejects
route-ID replacement (use staged route APIs). Reconcile changed
transport/timing/AR fields into the draft, clear review/context/proposals and
increment the manifest revision. Retain unchanged provenance/anchors and omitted
planning-only fields; changed legacy coordinates needing anchors become
unresolved until explicit review. Non-plan field changes preserve review but
still increment revision. Unmanaged PUT retains historical behavior. Reviewed
publication uses project_leg_order, preserving itinerary ordinals regardless of
the order in which cards are reviewed. `XBandPlanReview` consumes
draft/proposal/evaluation and emits explicit manual edits/lock toggles;
`ProposalComparison` emits Apply only on user action.

- [ ] **Step 1:** Test auto proposal after first route acceptance, unresolved AR
      provisional state, manual edit without replacement, re-optimize preserving
      locks, Apply comparison, unavailable satellites, stale save/apply and
      cancel/reload. Verify independently that saving draft does not publish
      executable transports; reviewed save creates the first inactive leg:

  ```python
  assert draft_save.mission.legs == []
  assert reviewed_save.mission.legs[0].is_active is False
  assert reviewed_leg.review.input_identity == reviewed_leg.input_identity
  assert failed_review.status_code == 409 and snapshot_after == snapshot_before
  ```

  UI tests assert **X-band outage under Starshield preference**, exact UTC swap
  times, baseline comparison, separate backup/safety guidance, and **Save
  reviewed plan and upload next leg** selects the next unbound expected leg. Pin
  ordinary PUT between planning read and reviewed save: draft reflects the new
  inputs, status is Needs review, old tab gets 409 without any writes. Test
  active managed PUT rejection and unmanaged PUT compatibility.

- [ ] **Step 2:** Run reviewed-save backend tests and new frontend component
      tests; expect missing controls/validated commit behavior.
- [ ] **Step 3:** Add all remaining main-plan proposal/preview/reviewed
      endpoints and revision-aware hooks. The initial accepted upload generates
      one draft proposal; later changes mark it stale and offer Re-optimize
      explicitly. Use a 40-second client proposal timeout to allow server
      deadline/cleanup. Persist drafts before resume, disable reviewed save
      while field errors remain, and reconcile request errors without losing
      manual edits. Reuse existing AR/X/map controls with occurrence anchors and
      accessible actions. Managed legacy edit callers send the current
      PlanningView revision and leg identity; invalidate mission and planning
      queries together on success. Missing/stale CAS errors preserve local
      changes and require reload.
- [ ] **Step 4:** Run focused backend/frontend tests and existing mission/leg
      tests; verify two-tab race, a deleted satellite on reopen, physical/policy
      labels, keyboard locks and mobile review. No fake initial satellite
      fallback.
- [ ] **Step 5:** Commit `feat: review and save proposed satellite plans`.
