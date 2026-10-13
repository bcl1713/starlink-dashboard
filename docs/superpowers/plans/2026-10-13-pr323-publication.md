# PR323 Reviewed Publication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the selected reviewed itinerary atomically and preserve
accurate approved/current/count state after reload.

**Architecture:** Prepare canonical artifacts outside commit locks, recheck all
selected bindings/decisions, and publish through one existing journal
transaction. Reuse the mission controller for the final action and add
lightweight list counts.

**Tech Stack:** Python 3.11, existing planning journal and timeline artifacts,
FastAPI, React/TypeScript, pytest, and Vitest.

**Spec:**
[Approved design](../specs/2026-10-13-pr323-operator-and-export-repair.md).

## Global Constraints

- [Parent constraints](2026-10-13-pr323-repairs.md) apply. This is Task 5 of the
  [operator plan](2026-10-13-pr323-operator.md), on existing PR323.
- Retain explicit executable-plan approval, inactive installed legs, and source
  ownership/history. An invalid entry commits none of the selected batch.
- Preparation/transport, map eligibility, the mission controller, and batch
  proposal application must be implemented before this task.
- Preserve the stored/package mission schema; list count fields are list-only.

## Review Focus

- Incomplete AR/no-AR/plan/gap approval must prevent executable publication.
- Foreign or duplicate leg/route/POI ownership must not replace another scope.
- Journal interruption must recover the entire prior or committed batch.
- A specific map limitation must appear before the final approval action.
- Metadata-only lists and refreshes must not display a false zero-leg count.

## Task 5: consolidated final review and atomic inactive publication

**Files:** Create backend `app/mission/planning/publication.py`; modify planning
`models.py`, `review.py`, `store.py`, `routes.py`, and `service.py`. Create
`app/mission/list_views.py` and modify `app/mission/routes_v2.py` for
lightweight list counts. Create frontend
`src/components/planning/ItineraryFinalReview.tsx`; modify
`PlanningLegReview.tsx`, `ExpectedLegCards.tsx`, `services/planning.ts`,
`pages/MissionDetailPage.tsx`, `hooks/usePlanningMissionController.ts`,
`components/missions/MissionCard.tsx`, `MissionList.tsx`,
`services/missions.ts`, `src/types/mission.ts`, and `src/types/planning.ts`. Add
backend `tests/planning/test_batch_publication.py`; extend
`test_reviewed_save.py` and `test_packages.py`; add frontend
`ItineraryFinalReview.test.tsx` and `components/missions/MissionList.test.tsx`;
extend `ExpectedLegCards.test.tsx` and backend
`tests/unit/test_mission_storage.py`.

**Interfaces:** Define `ReviewedLegRequest(leg_id, review: SaveReviewed)` and
`PublishReviewedBatch(expected_revision, entries, idempotency_key)`. Define
frozen `PreparedReviewedLeg` in `publication.py` with leg ID, review request,
`TimelineArtifacts`, evaluation, input/environment identities, and map
diagnostics. `PreparedReviewBatch` contains the captured mission revision and
`tuple[PreparedReviewedLeg, ...]`. Reject empty/duplicate entries and require
every nested review's expected revision to equal the batch revision.
`prepare_reviewed_batch(service, mission_id, request) -> PreparedReviewBatch`
captures one revision and produces per-leg `TimelineArtifacts`, evaluation,
input/environment identity, review request, and map diagnostics.
`PlanningStore.commit_reviewed_batch(mission_id, request, prepared) -> PlanningView`
rechecks every entry and commits all legs/timelines/owned POI scopes/reviews in
one journal. Expose POST planning
`/missions/{mission_id}/reviewed-publications`. Single-leg publication uses the
same preparation/commit path with one entry.

In `list_views.py`, define `MissionListItem` as the list-only public mission
shape with optional `leg_count: int | None`, and
`list_mission_summaries() -> list[MissionListItem]`. Count canonical executable
leg files under the read gate, excluding archived/timeline files, without
loading each full leg. Add this field only to list responses, preserving
stored/package mission schema. Frontend list cards use the reported count;
missing counts show unresolved state instead of interpreting metadata-only
`legs: []` as zero.

- [ ] **Step 1: Pin approval and atomicity.** Add
      `test_invalid_leg_prevents_batch_publication`,
      `test_batch_journal_recovery_is_atomic`, and
      `test_published_batch_is_inactive_and_idempotent`. One incomplete AR/gap
      decision or stale binding installs zero batch legs. Inject interruption
      before/after journal commit marker and prove recovery yields the whole
      old/new state, never partial publication. Reject duplicate leg/route/POI
      ownership and conflicting active legs. Valid retry is idempotent; all
      installed legs are inactive. Unchanged previously reviewed decisions are
      retained. Map limitations from the map plan appear before publication,
      with actionable per-leg details. Add
      `test_mission_summary_preserves_leg_count` and browser
      `metadata-only list does not flash zero legs`.
- [ ] **Step 2: Run RED.** Backend selection:
      `tests/planning/test_batch_publication.py`
      `tests/planning/test_reviewed_save.py` `tests/planning/test_packages.py`
      `tests/unit/test_mission_storage.py`. Frontend selection:
      `src/components/planning/ItineraryFinalReview.test.tsx`
      `src/components/planning/ExpectedLegCards.test.tsx`
      `src/components/missions/MissionList.test.tsx`.
- [ ] **Step 3: Implement final review/publication.** Prepare selected canonical
      timelines and scene checks outside commit locks. Recheck revision, inputs,
      environment, approvals, and ownership under the existing lock order. Reuse
      the journal's existing `route_ids` POI scope for selected installed routes
      while preserving unrelated records; commit all artifacts/reviews together.
      The UI displays every required AR/no-AR/plan/gap decision and one Publish
      reviewed plans action, with durable progress/error recovery and no
      automatic activation/publication.
- [ ] **Step 4: Run GREEN and reload controls.** Repeat selections plus backend
      `test_final_review_regressions.py test_poi_projection.py test_canonical.py`.
      Verify original/clone/package evaluations, current review status, and
      unchanged sources. While data is unresolved or refreshing show
      loading/current observed counts rather than a false zero-leg state.
      Inspect the real rendered journey using the parent acceptance task; unit
      tests do not certify the 20-action target.
- [ ] **Step 5: Commit.** Commit as
      `feat: publish reviewed itinerary legs in one atomic action`.
