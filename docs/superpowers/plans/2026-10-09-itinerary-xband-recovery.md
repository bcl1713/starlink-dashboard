# Itinerary recovery and acceptance implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans.
> Complete checkbox steps task-by-task after plan approval.

**Goal:** Preserve reviewed/manual work through route and itinerary revisions,
round-trip every required source, and prove the complete production workflow.

**Architecture:** Revision previews stage an explicit mapping before a
transactional commit. One source-closure inventory serves ownership checks,
archive packaging, snapshots and deletion. Acceptance exercises normal APIs and
production images with task-owned resources.

**Tech Stack:** Existing JSON/filelock storage, ZIP/snapshot exporter, React,
Playwright, Docker Compose and repository acceptance helpers.

**Spec:** [Design](../specs/2026-10-09-itinerary-xband-planning-design.md) and
[contracts](../specs/2026-10-09-itinerary-xband-planning-contracts.md).

## Global constraints

Read the [main plan](2026-10-09-itinerary-xband-planning.md); Tasks 1–7 precede
these tasks. Imports/replacements never overwrite another mission's route.
Retirement archives work outside activatable executable legs. Runtime checks use
the actor's configured daemon and task-specific project, ports and volumes.

## Review focus

Task 8 pins unresolved remapping and retirement of active legs. Task 9 pins
legacy shared routes, corrupt package graphs and unfinished mission exports.
Task 10 pins process/container cleanup and recovery after interrupted commits.

## Task 8: Staged KML replacement and itinerary revision reconciliation

**Files:** Create backend `app/mission/planning/revisions.py` and
`tests/planning/test_revisions.py`; extend planning/{service,store,routes}.py
and adapt `app/mission/routes_v2.py` to delegate owned-plan replacements.
Frontend create `src/components/planning/RevisionReview.tsx` and its test;
extend services/planning.ts, usePlanning.ts, MissionDetailPage.tsx and ARReview.

**Interfaces:**

```python
preview_revision(current: PlanningManifest, incoming: ItineraryPreview) -> RevisionPreview
PlanningService.preview_revision(mission_id: str, data: bytes, revision: int) -> RevisionPreview
PlanningService.apply_revision(mission_id: str, request: ApplyRevision) -> PlanningView
PlanningStore.commit_revision(mission_id: str, request: ApplyRevision, revised: PlanningManifest) -> PlanningView
```

RevisionPreview contains preview ID, expected revision, source hash/revision,
field/leg/AR diffs, proposed stable mappings, unresolved mappings and conflicts.
ApplyRevision carries preview ID, expected revision, explicit mappings,
correction resolutions and lower-source-revision override if needed. It does not
carry fabricated final executable legs from the browser.

- [ ] **Step 1:** Write
      `test_changed_waypoint_names_retain_old_anchors_and_locks`,
      `test_departure_adjustment_is_preserved_once`,
      `test_revision_reorder_requires_mapping_when_ambiguous`,
      `test_retirement_archives_leg_but_cannot_retire_active_leg`, and
      `test_identical_revision_is_noop_and_lower_revision_needs_override`:

  ```python
  assert staged.old_source_hash == installed.source_hash
  assert staged.unresolved_lock_ids == {old_lock_id}
  assert staged.adjustment == installed.adjustment
  assert canceled.installed_plan == installed
  assert active_revision.status_code == 409 and after == before
  ```

  Pin unchanged legs staying Reviewed, changed AR/manual corrections requiring
  resolution, missing routes, midnight shifts, and retry without duplicate ARs.

- [ ] **Step 2:** Run `tests/planning/test_revisions.py` and RevisionReview
      Vitest; expect missing previews, retired archives and conflict resolution.
- [ ] **Step 3:** Implement staged source/mapping previews through Task 2
      helpers and Task 3's owned transaction machinery. Never call unchanged
      destructive legacy replacement for itinerary-owned records. Accepted
      replacement updates a draft only; reviewed save installs it. Move retired
      installed legs into manifest history atomically and retain every source
      reference. Delegate legacy DELETE for a planning-managed leg to the same
      CAS-checked retirement transaction: reject active legs, remove its
      executable binding from live cards, archive the installed leg/draft and
      sources, and invalidate proposals/increment revision without orphan IDs.
      Unmanaged deletion keeps its historical response and owned-source guards.
      Revision confirmation applies the entire validated diff or none,
      preserving explicit corrections and unresolved rows. Retain source
      revisions and invalidate context/review identities only on affected legs.
- [ ] **Step 4:** Rerun focused checks plus existing route replacement tests;
      confirm legacy behavior remains compatible except required ownership
      protection. Test cancel/failed stage and stale preview with identical
      installed route, POIs, timeline, manual choices and active flags. Pin
      managed legacy DELETE, stale DELETE, and retained source closure; deleted
      installed-leg IDs appear only in archived history, not live cards.
- [ ] **Step 5:** Commit `feat: reconcile itinerary and route revisions safely`.

## Task 9: Source closure, collision-safe archives and owned deletion

**Files:** Create backend `app/mission/planning/packages.py` and
`tests/planning/{test_packages,test_source_lifecycle}.py`; extend
planning/sources.py, `app/mission/{routes_v2,storage}.py`,
`app/mission/package/{__main__,snapshot_export}.py`,
`app/mission/exporter/{snapshot_inputs,snapshot_views}.py`.

**Interfaces:**

```python
source_closure(mission: Mission, manifest: PlanningManifest | None) -> tuple[SourceRevision, ...]
stage_package(zf: ZipFile, target: Mission | None, sources: SourceStore) -> PackageImportPlan
commit_package(plan: PackageImportPlan, expected_revision: int | None) -> PlanningView
SourceStore.release_owned(mission_id: str, references: tuple[SourceRevision, ...]) -> None
```

`PackageImportPlan` is a validated immutable staged mission/manifest/source
graph with ID remaps and active-reference checks. It uses content hashes
independently of storage IDs. Snapshot payloads include every accepted
draft/retired/prior KML, PDF revision, policy and evaluation context, not only
Mission.legs resources.

- [ ] **Step 1:** Test `test_roundtrip_with_zero_executable_legs`,
      `test_partial_review_and_retired_history_roundtrip`,
      `test_collision_with_other_active_mission_remaps_complete_graph`,
      `test_missing_file_and_invalid_archive_path_do_not_commit`,
      `test_owned_delete_preserves_legacy_shared_route`, and
      `test_remapped_context_preserves_canonical_cost`:

  ```python
  assert roundtrip.expected_legs[0].draft.locks == original_locks
  assert roundtrip.context.boundaries == original_context.boundaries
  assert collision_import.imported_route_id != foreign_route_id
  assert foreign_snapshot_after == foreign_snapshot_before
  assert owned_sources_after_delete == [] and foreign_sources_after == foreign_sources_before
  ```

  Delete failures are retryable and identify remaining owned paths. Export with
  absent retained bytes fails explicitly rather than emitting an incomplete ZIP.

- [ ] **Step 2:** Run test_packages.py and test_source_lifecycle.py; expect
      missing manifest source enumeration, staging rollback and foreign
      ownership guards.
- [ ] **Step 3:** Route dependency snapshots/export through source_closure.
      Store PDFs under mission-owned source paths and KMLs under immutable route
      IDs. Validate archive paths, hashes, anchors and every referenced asset
      before commit; remap all bindings/history/locks together. Revalidate
      imported review/context against current satellite inputs, and persist all
      legs inactive. Extend legacy package import to enforce collision/ownership
      protection while keeping its field/format compatibility. Roll back staged
      sources after failure; deletion releases only verified unreferenced owned
      bytes and cache entries, with no global prune operation.
- [ ] **Step 4:** Rerun focused tests plus existing mission-package endpoint
      POI, mission storage, exporter and retirement integration tests. Compare
      source inventories before/after failed import, deletion and package
      round-trip.
- [ ] **Step 5:** Commit
      `feat: preserve planning sources across package lifecycle`.

## Task 10: Rendered production acceptance and operator documentation

**Files:** Create
`tools/acceptance/itinerary-planning/{run.sh,compose.yml,seed.py}`,
`tools/acceptance/browser/itinerary-planning.mjs`,
`frontend/mission-planner/tests/e2e/itinerary-planning.spec.ts`,
`docs/missions/itinerary-planning.md`, and scoped runner contract tests under
`tools/tests/test_itinerary_planning_acceptance.py`. Extend
docs/missions/README.md and configuration/upload documentation for PDF limits
without altering KML/ZIP limits. Reuse existing exact-SHA image/build and
browser-provisioning helpers.

**Interfaces:** `run.sh [--check]` uses project `starlink-itinerary-planning`
and port 15322 after an ownership/port preflight. `seed.py` creates synthetic
PDFs, KMLs and configured satellites through the normal API; it never reads the
provided operational attachments. The browser journey returns structured steps,
screenshots, console/network errors and final resource ownership evidence.

- [ ] **Step 1:** Write acceptance assertions for itinerary-first confirmation,
      three expected legs, selected-leg KML upload, five AR windows, no-AR leg,
      provisional errors, policy outage, manual swap/lock, re-optimize/Apply,
      reviewed save/next-leg/resume, second-tab 409, revision replacement,
      retirement, package collision and round-trip. Pin keyboard/mobile review
      and the absence of preview activation or terminal commands. Runner tests
      verify owned cleanup on normal exit, TERM, deadline and injected failure.
- [ ] **Step 2:** Run the scoped runner contract tests; expect unmet ownership
      and cleanup contracts. Defer the rendered journey until its owned runner
      exists; do not start an untracked server for this red check.
- [ ] **Step 3:** Build the runner around a clean committed candidate archive,
      normal production Dockerfiles, and Nginx API path. Preserve DOCKER_HOST,
      proxy and CA configuration. Record source path, PIDs/groups, command
      sessions, Compose project/private volumes before startup. Trap
      EXIT/INT/TERM; close browser contexts, terminate/reap children and remove
      only this project's containers/networks/volumes. Retain evidence with the
      candidate SHA; verify host-owned survivors/listeners through approved host
      commands. Document upload/review order, policy labels, manual locks,
      assumptions, resolution limits, correction/resume and revision handling
      for operators.
- [ ] **Step 4:** Run focused planning tests and applicable legacy regressions,
      frontend unit suite/build, format/lint and docs checks. Then from repo
      root commit the complete Task 10 candidate as
      `test: prove itinerary planning workflow in production`; verify a clean
      tracked worktree before running:

  ```bash
  timeout --kill-after=10s 30m tools/acceptance/itinerary-planning/run.sh
  ```

  Require exact-candidate API/browser evidence and zero owned resources after
  cleanup. Keep this HEAD unchanged for review/PR evidence; any fixes need a new
  commit and rerun. Builds requiring more time get a separately explicit bounded
  limit; after a timeout verify the old tree is gone before rerunning. Do not
  keep the acceptance project running while the PR waits for review.

- [ ] **Step 5:** Obtain whole-branch review, push the feature branch and
      submit/update its PR against dev with exact-head checks and evidence.
      Follow workspace cleanup after merge; preserve unrelated branches, runtime
      and credentials.
