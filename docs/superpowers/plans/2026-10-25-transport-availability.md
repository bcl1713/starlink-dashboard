# Mission Transport Availability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking.

**Goal:** Plan X-band, Ka, and Starshield availability per mission or leg, and
record in-flight failures with consistent coverage, restorable POIs, and
operational events.

**Architecture:** Keep mission defaults and timed operational history in
mission-owned state, with per-leg planned overrides and a shared
effective-availability resolver. Pass resolved availability into both planning
paths and all live projections; preserve POI records while changing their
applicability. Publish changes under repository admission with revision checks
and invalidate dependent projections.

**Tech Stack:** Existing Python 3.11, Pydantic, FastAPI, React, TypeScript,
TanStack Query, pytest, Vitest, and Playwright; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-25-transport-availability-design.md`

## Global Constraints

- X-band, Ka, and Starshield use identical availability scopes and timing
  semantics.
- Available means eligible for the existing coverage and operating rules.
- An active operational failure forces that transport unavailable regardless of
  the planned setting.
- Operational failure timestamps use the authoritative mission clock, including
  simulation mode.
- Estimates and backup gaps never block saving a valid plan.
- Overview remains a customer-facing map: no new controls, diagnostics, or raw
  timestamps.
- Retain generated POIs and their identities when availability changes.
- Every test/build/acceptance command has an explicit timeout and forced
  termination grace period; record and clean up owned runtime resources.

## Review Focus

- A failure must not end when the active leg changes or the itinerary adds
  another leg; Task 1 and Task 3 test this.
- Restore must release only the operational override, preserving planned
  unavailability and hard RF restrictions; Task 1 and Task 2 test this.
- Missing X geometry must not prevent saving or calculating a plan with X
  unavailable; Task 2 tests an empty satellite catalog.
- Retained POIs must not leak through alternate map feeds or regain overdue
  alert cues after restore; Task 4 and Task 6 test this.
- Older editor payloads, package imports, and replay state must not erase or
  contaminate mission availability; Task 3 tests these paths.

## Task 1: Shared model and temporal resolution

**Files:** Create `backend/starlink-location/app/mission/availability.py` and
`availability_models.py`; modify `app/mission/models.py`; test in
`tests/unit/test_transport_availability.py`.

**Interfaces:** `MissionAvailability` owns `revision`, planned defaults keyed by
X/Ka/Ku, and timed failure/restoration history. `TransportConfig` gains optional
per-transport planned overrides. The resolver interfaces return eligibility and
interval boundaries:

```python
def resolve_availability(
    mission: Mission, leg: MissionLeg, at: datetime
) -> dict[Transport, bool]: ...

def availability_boundaries(
    mission: Mission, leg: MissionLeg, start: datetime, end: datetime
) -> tuple[datetime, ...]: ...
```

`resolved_leg_availability(mission: Mission, leg: MissionLeg) -> LegAvailability`
returns an immutable snapshot of eligibility, failures, revision, and run
context.

- [ ] Write parameterized tests `test_mission_default_and_leg_override`,
      `test_failure_crosses_leg_boundary`, `test_restore_releases_only_failure`,
      `test_legacy_starshield_false`, and `test_half_open_failure_window`.
      Assert X/Ka/Ku default eligible; leg override wins over mission default;
      operational failure wins over both; eligibility changes exactly at
      failure/restoration time. A new leg inherits mission defaults and any
      active failure.
- [ ] Run from `backend/starlink-location`: expect missing-interface failures
      from:

```bash
timeout --kill-after=10s 10m uv run --with-requirements requirements.txt \
  pytest tests/unit/test_transport_availability.py -q
```

- [ ] Implement the interfaces above with timezone-aware timestamps, validated
      transport keys, immutable failure history, and legacy Starshield fallback
      only when no new explicit setting exists.
- [ ] Repeat the focused test command; expect all cases pass. Commit
      `feat: model mission transport availability`.

## Task 2: Capability and planning integration

**Files:** Modify `app/mission/timeline_preparation.py`,
`planning/{models,types,inputs,grid,evaluate,optimizer,canonical,legacy,review}.py`,
`itinerary_import/editing.py`, `pop_continuity.py`, and `pop_capabilities.py`;
create `tests/planning/test_transport_availability.py`; extend
`tests/unit/test_mission_timeline.py`.

**Interfaces:** Add optional keyword
`availability: LegAvailability | None = None` to `prepare_mission_timeline`;
omitted means legacy defaults resolved from the leg. The caller supplies the
immutable snapshot from Task 1 when a parent mission exists. Persist snapshot
identity in planning inputs, and include its boundaries in evaluation grids.
Both legacy and planning-policy calculations produce unavailable states for
ineligible transports before continuity and fallback classification.

- [ ] Write `test_unavailable_x_needs_no_satellites`,
      `test_availability_applies_to_legacy_and_managed_timelines`,
      `test_failure_splits_interval_without_rewriting_past`,
      `test_disabled_starshield_releases_concurrency_only_x`,
      `test_failed_x_cannot_protect_pop_window`, and
      `test_all_transports_unavailable_is_saveable`. Assert no X geometry
      lookup/optimization requirement when X is unavailable throughout the leg;
      no proposed swaps in unavailable windows; usable Ka still protects
      continuity.
- [ ] Run the following command; verify new assertions fail before
      implementation.

```bash
timeout --kill-after=10s 10m uv run --with-requirements requirements.txt \
  pytest tests/planning/test_transport_availability.py \
  tests/unit/test_mission_timeline.py -q
```

- [ ] Carry snapshots through manual previews, itinerary drafts, canonical
      projection, and optimizer inputs. Split partial failures at their
      boundaries, preserve independent manual outages and hard RF blocks, and
      apply availability before call-capability evidence fallback can turn an
      explicit failure into unknown.
- [ ] Repeat the focused command and existing planning-policy/continuity tests;
      require passing output. Commit
      `feat: apply transport availability to mission profiles`.

## Task 3: Mission commands and durable publication

**Files:** Create `app/mission/availability_service.py` and
`availability_routes.py`; modify `app/mission/routes_v2.py`, `storage.py`,
relevant itinerary revision/package paths, and router registration; create
`tests/integration/test_transport_availability_routes.py`.

**Interfaces:** `GET /api/v2/missions/{mission_id}/availability` returns
revision, defaults, leg overrides, history, and effective state. `PUT` at that
route saves mission defaults or specified leg overrides with `expected_revision`
and `command_id`. `POST /api/v2/missions/{mission_id}/availability/actions`
accepts transport, action `unavailable` or `restore`, optional reason,
`expected_revision`, and `command_id`; effective time comes from the mission
clock. Responses return the confirmed saved availability view. All changes
regenerate affected profiles through Task 2.

- [ ] Write `test_stale_revision_rejected`,
      `test_duplicate_action_is_idempotent`,
      `test_regeneration_failure_does_not_publish_partial_change`,
      `test_restart_and_leg_change_keep_failure`,
      `test_itinerary_revision_preserves_availability`,
      `test_package_roundtrip_keeps_state_and_import_inactive`,
      `test_legacy_editor_does_not_erase_availability`, and
      `test_simulation_failure_does_not_affect_live_mission`. Assert journal
      storage being disabled does not prevent mission commands.
- [ ] Run the following command; expect route/behavior failures.

```bash
timeout --kill-after=10s 10m uv run --with-requirements requirements.txt \
  pytest tests/integration/test_transport_availability_routes.py -q
```

- [ ] Prepare under repository admission; capture rollback state for mission,
      timelines, and POIs. Preserve planning-manifest ownership. Pass snapshots
      to detached exporters/event producers. Validate mission/run at acceptance
      and invalidate identities/caches only after successful publication.
- [ ] Wire existing add/edit/revision/import writers to preserve owned
      availability and resolve new legs correctly. Repeat the focused tests and
      relevant existing mission route/package tests. Commit
      `feat: persist mission transport availability commands`.

## Task 4: Restorable POIs and consistent live events

**Files:** Modify `app/models/poi.py`, `app/mission/models.py`,
`app/mission/timeline_builder/{pois,event_pois}.py`,
`app/services/poi_manager.py`, `app/services/overview_upcoming_pois.py`,
`app/api/overview_upcoming_pois.py`, `app/services/active_x_link.py`,
`app/operator/{production_event_inputs,production_event_sources,event_projection,event_eligibility}.py`,
and map/export projections. Create
`tests/integration/test_availability_projections.py`.

**Interfaces:** Generated POIs and timeline map POIs expose
`transport_active: bool = True` and optional `inactive_reason`. This is distinct
from the existing route/mission lifecycle `active` field. Determine
applicability from canonical POI kind and Task 1 snapshots. Availability-only
updates retain stable POI IDs and raw schedule/geometry; route revisions may
replace obsolete points through existing rules. Operator event occurrences use
existing retirement/history rules and fresh generations on restoration.

- [ ] Write `test_failure_retains_poi_ids_but_hides_active_cues`,
      `test_restore_returns_future_pois_without_duplicates`,
      `test_restore_does_not_revive_elapsed_actions`,
      `test_other_transports_and_manual_pois_survive`,
      `test_event_heads_and_local_cues_retire`, and
      `test_projection_cache_invalidates_on_availability`. Assert all three
      transport kinds, saved map_pois, Overview feed, active X link, and
      exported maps agree.
- [ ] Run the following command; verify failures describe the missing behavior.

```bash
timeout --kill-after=10s 10m uv run --with-requirements requirements.txt \
  pytest tests/integration/test_availability_projections.py -q
```

- [ ] Preserve the baseline generated POI set and update applicability without
      the existing delete/recreate behavior on availability-only changes. Keep
      generic call-outage advisories derived from effective capability. Update
      every active projection to exclude inactive transport cues while history
      retains original records; restore only still-relevant actions and never
      resurrect acknowledged/elapsed occurrences.
- [ ] Repeat focused tests plus existing generated-POI, operator-event,
      Overview-upcoming, and active-X tests. Commit
      `feat: make transport mission cues inactive and restorable`.

## Task 5: Planning and operator controls

**Files:** Create
`frontend/mission-planner/src/services/transportAvailability.ts`,
`hooks/api/useTransportAvailability.ts`, and
`components/planning/TransportAvailabilityControls.tsx`; integrate
`pages/MissionDetailPage.tsx`, `pages/LegDetailPage.tsx`,
`components/planning/PlanningLegReview.tsx`,
`components/operator/workspace/{TransportView,TransportAssignments,TransportCatalogManager}.tsx`;
update mission/POI/timeline types and map filtering. Add colocated Vitest tests.

**Interfaces:** `useTransportAvailability(missionId)` reads the Task 3 view and
exposes guarded planned updates and operator actions, using confirmed server
responses. `TransportAvailabilityControls` renders mission defaults or leg
inheritance/overrides. Operator controls clearly label
`Unavailable for rest of mission` and `Restore`; they do not require a reason or
confidence acknowledgment.

- [ ] Write tests `mission_defaults_and_leg_inheritance`,
      `operator_failure_and_restore`, `save_failure_retains_confirmed_state`,
      `planned_unavailable_remains_after_restore`,
      `unavailable_transport_not_offered_for_assignment`, and
      `inactive_pois_hidden_in_all_route_maps`. Assert controls for X-band, Ka,
      and Starshield; existing reported service assignment remains with
      unavailable indication and no fabricated reroute.
- [ ] Run from `frontend/mission-planner`; verify new behavior fails initially:

```bash
timeout --kill-after=10s 10m npm run test:unit -- \
  src/components/planning/TransportAvailabilityControls.test.tsx \
  src/components/operator/workspace/TransportView.test.tsx
```

- [ ] Implement controls using existing UI, save feedback, revision guards, and
      dependent query invalidation, independently of journal initialization.
      Link catalog help to availability controls; keep assignment history and
      filter inactive POIs in fallback and saved-timeline maps.
- [ ] Repeat focused tests, then `timeout --kill-after=10s 10m npm run build`
      and relevant existing mission/operator tests. Commit
      `feat: add planning and operator transport availability controls`.

## Task 6: Acceptance and review

**Files:** Add
`frontend/mission-planner/tests/e2e/transport-availability.spec.ts`, a scoped
runner under `tools/acceptance/transport-availability/`, and evidence under
`docs/reports/2026-10-25-transport-availability/`; update
`docs/missions/itinerary-planning.md` and the operator workflow guide.

**Interfaces:** Acceptance uses a task-specific Compose project and exact
committed candidate SHA, exercising production images and the Nginx route. The
runner records ownership and cleans up on success, failure, and signals; the
evidence includes screenshots, command outcomes, candidate SHA, and teardown
verification.

- [ ] Add browser journeys for mission-wide planning, per-leg override, live
      failure halfway through a leg, subsequent leg activation, and restoration.
      For each transport assert retained POI IDs, inactive map/event cues during
      failure, recovered future cues after restoration, and correctly
      recalculated coverage. Include all-unavailable and failed-save cases.
- [ ] Run focused backend/frontend suites and canonical formatting/type/lint
      gates for changed files with explicit time limits. Commit before
      acceptance so the candidate is exact.
- [ ] Read cloud Docker instructions, discover the actor's configured daemon
      without changing DOCKER_HOST/context, and run
      `timeout --kill-after=10s 40m tools/acceptance/transport-availability/run.sh`.
      Require passing production/browser assertions and preserved rendered
      evidence.
- [ ] Stop and verify all owned workers, browsers, listeners, containers,
      networks, and private volumes are gone. Request a whole-branch code
      review, fix findings, and repeat only affected checks. Push the feature
      branch and create a PR against dev with validation and any remaining
      limitations.
