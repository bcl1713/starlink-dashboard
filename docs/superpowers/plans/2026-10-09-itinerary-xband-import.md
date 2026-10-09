# Itinerary import and AR review implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans.
> Complete checkbox steps task-by-task after plan approval.

**Goal:** Persist itinerary-derived expected legs, attach KMLs, and review ARs.

**Architecture:** Typed manifests remain separate from executable MissionLegs.
Pure parser/matcher outputs enter a revision-checked, recoverable store through
a small planning router. Existing leg screens host draft and legacy reviews.

**Tech Stack:** Python 3.11, Pydantic 2, pypdf, FastAPI, React, Vitest.

**Spec:** [Design](../specs/2026-10-09-itinerary-xband-planning-design.md) and
[contracts](../specs/2026-10-09-itinerary-xband-planning-contracts.md).

## Global constraints

The [main plan](2026-10-09-itinerary-xband-planning.md) owns exact values, API
routes, deadlines, workspace rules, and commands for every task here. No
executable leg exists before reviewed save; no parser result invents no ARs.

## Review focus

Tasks 2–4 pin unsupported AR sections, duplicate route occurrences, stale
writes, and draft reload. Task 3 additionally pins publication failure and
startup recovery; the evaluation plan completes the policy/optimizer
prerequisites.

## Task 1: Typed planning records and occurrence anchors

**Files:** Under `backend/starlink-location/`, create
`app/mission/planning/{__init__,models,identity}.py`,
`tests/planning/{conftest,cases,test_models}.py`; modify
`app/mission/models.py`. Under `frontend/mission-planner/`, create
`src/types/planning.ts` and extend `src/types/{mission,aar,satellite}.ts` with
optional legacy-compatible fields.

**Interfaces:** `models.py` produces these Pydantic DTOs:

- `RouteAnchor`: route ID/content hash, segment index, fraction in [0,1],
  occurrence ID, source UTC time, coordinates, and timing mode
  `route_bound|fixed_utc|elapsed`; elapsed mode carries an offset in seconds.
- `ItineraryAR`: ID, track, source page/row/text, entry/exit UTC, source
  altitude, confirmed units, optional anchors,
  `matched|ambiguous|unresolved|excluded`, confirmed flag and exclusion note.
  Source time precision is explicit.
- `ExpectedLeg`: stable ID, ordinal, endpoints, UTC bounds, AR rows, optional
  `route`, draft, review record and installed leg ID, and retired flag.
- `PlanningDraft`: optional initial X satellite, anchored swaps, permitted IDs,
  AR corrections, existing manual overlays/outages/splice, departure adjustment,
  locks, `prefer_starshield_v1`, and optional evaluation context.
- `PlanningManifest`: schema version 1, revision, source revisions, expected
  legs, proposals, review records, and retained route bindings/history.
- `EvaluationContext`: seed times, candidates C, boundaries B, input identity,
  version, source hashes, chosen height profile and disclosed assumptions.
- `PlanningEvaluation`: context, half-open intervals with physical/policy states
  and reason identities, outage seconds, swap count, longest gap and backup
  gaps.
- `PlanningProposal`: ID, expected revision/input identity, context, proposed
  draft, baseline/candidate evaluations, state `ready|failed|stale`, and errors.
- `SourceRevision`: ID, owner, kind, filename, hash, owned relative path and
  expiry; public responses omit storage paths. `ItineraryPreview` carries parsed
  values, field errors, source evidence, preview ID and confirmable flag.
- `ReviewRecord`: installed input identity, AR confirmations/exclusions, gap
  acknowledgment and save time. `PlanningView` exposes expected-leg cards with
  their input identities, review/computation status, draft and review records.
  `RouteBinding` carries immutable route/source IDs, content hash and filename;
  RouteBindingPreview adds discrepancy errors and matched AR candidates.

Define the main plan's request/response DTOs in this module; no free-form
mutation body. `PlanningView` derives card status from input/review identity.
Extend `AARWindow` and `XTransition` with optional anchors, and TransportConfig
with optional policy/context; omitted fields preserve historical behavior.
`identity.planning_identity(inputs: dict) -> str` canonicalizes UTC, finite
numbers and ordered records; storage IDs are separate from content hashes.

- [ ] **Step 1:** Write `test_models.py` assertions:

  ```python
  assert ExpectedLeg.model_validate(expected_leg_without_route).route is None
  assert legacy_leg.model_dump(exclude_none=True) == legacy_round_trip
  with pytest.raises(ValidationError):
      RouteAnchor.model_validate({**anchor_fields, "fraction": 1.01})
  assert planning_identity(before) != planning_identity(after_ku_outage_edit)
  assert planning_identity(before) != planning_identity(after_manual_lock_edit)
  ```

  Create `cases.py` synthetic itinerary/route factories and `conftest.py`
  fixtures rooted in pytest `tmp_path`, without modifying shared
  `/tmp/test_data` stores.

- [ ] **Step 2:** Run the main backend command selecting
      `tests/planning/test_models.py`; expect missing types/behavior.
- [ ] **Step 3:** Implement DTO validation and identity; mirror JSON schemas in
      TypeScript. Require confirmed altitude units before geometric conversion.
      Reject NaN/inf, invalid UTC windows and contradictory anchor timing modes.
- [ ] **Step 4:** Rerun the focused check; all assertions pass. Run existing
      `tests/unit/test_mission_models.py` to verify legacy contracts.
- [ ] **Step 5:** Commit `feat: define itinerary planning records and anchors`.

## Task 2: Bounded PDF extraction and primary-route AR matching

**Files:** Create `app/mission/planning/{extract,match,deadlines}.py`,
`tests/planning/{test_extract,test_match,test_deadlines}.py`. Modify
`app/mission/timeline_builder/{aar,calculator}.py` for optional anchor
resolution.

**Interfaces:**

```python
extract_itinerary(pdf_bytes: bytes) -> ItineraryPreview
match_ar_windows(leg: ExpectedLeg, route: ParsedRoute) -> list[ItineraryAR]
resolve_anchor(anchor: RouteAnchor, route: ParsedRoute, adjustment: datetime | None) -> datetime
run_bounded(fn: Callable[..., T], args: tuple, seconds: float) -> T
```

`deadlines.py` owns spawned process handles, timeout termination/reaping, and
typed deadline errors. Functions passed to it are module-level/picklable.
Extraction returns leg/AR source evidence and field errors; match returns
candidate occurrences rather than collapsing names into a dictionary.

- [ ] **Step 1:** Generate sanitized PDF/KML fixtures using existing pypdf and
      synthetic XML. Test `test_rotated_utc_columns_and_five_ar_windows`,
      `test_unknown_ar_section_is_not_empty`, `test_scan_only_is_rejected`,
      `test_primary_route_excludes_alternates`, and
      `test_duplicate_same_position_collapses_but_repeat_occurrence_survives`:

  ```python
  assert [len(leg.ars) for leg in parsed.legs] == [3, 0, 2]
  assert parsed.legs[2].ars[1].exit_utc.date() > parsed.legs[2].ars[1].entry_utc.date()
  assert matched_ar.exit_anchor.occurrence_id == expected_arex_occurrence
  assert unknown_section.has_field_errors and not unknown_section.confirmable
  ```

  Add partial-segment interpolation, antimeridian, fixed/elapsed overrides,
  departure delta applied once, 10 MiB rejection and killed-worker cleanup.

- [ ] **Step 2:** Run `test_extract.py test_match.py test_deadlines.py`; expect
      missing extraction, ambiguity, and bounded-worker behavior.
- [ ] **Step 3:** Extract rotated text with pypdf text tokens/source positions;
      validate recognizable itinerary/AR sections and UTC columns. Apply the
      approved same-minute candidate rule and occurrence-aware resolution. Use
      run_bounded for the 10-second parser; never log raw operational PDF
      content. Keep legacy name/coordinate resolvers for missing anchors.
- [ ] **Step 4:** Rerun these tests and existing KML/timeline tests; require no
      live parser children after successful, failed, or timed-out parsing.
- [ ] **Step 5:** Commit
      `feat: extract itineraries and match refueling anchors`.

## Task 3: Owned sources, draft persistence and transactional planning API

**Files:** Create `app/mission/planning/{store,sources,service,routes}.py`,
`tests/planning/{test_store,test_api}.py`; modify `main.py`,
`app/mission/storage.py`, and scoped marker operations in
`app/services/poi/manager.py` or its existing public facade.

**Interfaces:**

```python
PlanningStore(root: Path, route_manager: RouteManager, poi_manager: POIManager)
PlanningStore.read(mission_id: str) -> PlanningView
PlanningStore.save_draft(mission_id: str, leg_id: str, request: SaveDraft) -> PlanningView
PlanningStore.commit_reviewed(mission_id: str, leg_id: str, request: SaveReviewed, artifacts: TimelineArtifacts) -> PlanningView
PlanningStore.recover() -> None
SourceStore.stage(data: bytes, kind: Literal["pdf", "kml"], owner: str | None, filename: str) -> SourceRevision
PlanningService.create(request: ConfirmItinerary) -> PlanningView
PlanningService.preview_route(mission_id: str, leg_id: str, data: bytes, revision: int) -> RouteBindingPreview
PlanningService.accept_route(mission_id: str, leg_id: str, request: AcceptRouteBinding) -> PlanningView
```

`service.py` composes parser/matcher and immutable sources. Add main-plan API
routes through draft save/read; availability/proposal/reviewed handlers arrive
in Tasks 5–7. File IDs never depend on upload names; stage outside locks, then
recheck expected revision under global activation lock before parent lock.

- [ ] **Step 1:** Pin `test_confirm_creates_expected_cards_not_executable_legs`,
      `test_accept_upload_assigns_selected_leg_not_filename`,
      `test_two_tabs_stale_save_has_no_writes`,
      `test_idempotent_create_and_expired_preview`, and
      `test_transaction_failure_and_restart_restore_owned_state`:

  ```python
  assert created.mission.legs == [] and len(created.expected_legs) == 3
  assert stale.status_code == 409 and after == before
  store.recover()
  assert store.read(mission_id) == previous_committed_view
  assert unrelated_metadata_after == unrelated_metadata_before
  ```

  Inject failure after each mission/leg/timeline/owned-POI write. Readers must
  observe the previous or next coherent record, never half a reviewed plan.

- [ ] **Step 2:** Run `test_store.py test_api.py`; expect unmet endpoints and
      CAS.
- [ ] **Step 3:** Implement typed metadata persistence with a durable
      owned-write journal, staged files, rollback, and startup recovery before
      serving planning readers. Coordinate relevant mission/timeline/owned-POI
      readers with the same commit gate; avoid restoring entire shared POI
      files. Enforce 24-hour staging expiry and remove failed/abandoned owned
      staging. Binding a new route creates Needs review; first acceptance can
      request the later proposal service only after it exists. Recover before
      app readiness.
- [ ] **Step 4:** Rerun focused tests; extend existing mission storage/CRUD
      tests for metadata preservation and inactive behavior. No computation runs
      while a synchronous persistence lock is held.
- [ ] **Step 5:** Commit `feat: persist itinerary drafts and route bindings`.

## Task 4: Itinerary creation and AR-first leg review UI

**Files:** In the frontend create `src/services/planning.ts`,
`src/hooks/api/usePlanning.ts`, `src/services/planning.test.ts`,
`src/components/planning/{CreateFromItinerary,ExpectedLegCards,ARReview}.tsx`,
and colocated tests. Modify
`src/pages/{MissionsPage,MissionDetailPage,LegDetailPage}.tsx`,
`src/pages/LegDetailPage/useLegData.ts` and
`src/components/aar/AARSegmentEditor.tsx`.

**Interfaces:** `planningApi` mirrors the main API table;
`usePlanning(missionId)` returns PlanningView and revision-aware mutations.
`ARReview` consumes ItineraryAR rows and returns corrected rows; expected-leg
routes use stable IDs in the existing URL, resolved from manifest before
requiring MissionLeg.

- [ ] **Step 1:** Test rotated-format extraction correction, selected-leg
      upload, AR-before-X tab order, altitude-unit confirmation, unknown section
      errors, no-AR confirmation, exact/interpolated map spans, and draft
      reload. Assert failed uploads keep their input/corrections and stale saves
      explain 409.
- [ ] **Step 2:** Run the main frontend command for the new component/service
      tests; expect missing itinerary controls and draft routing.
- [ ] **Step 3:** Add Create from itinerary alongside existing manual creation;
      render card statuses/actions from PlanningView. Route accepted uploads
      directly into review; preserve manual controls and unsaved-change guard.
      Until Task 7, expose manual draft edits without promising auto
      optimization or allowing reviewed save without a validated X plan.
- [ ] **Step 4:** Run focused Vitest plus existing mission/leg tests; check
      accessible field errors, focus return, keyboard upload and mobile layout.
- [ ] **Step 5:** Commit `feat: add itinerary creation and refueling review`.
