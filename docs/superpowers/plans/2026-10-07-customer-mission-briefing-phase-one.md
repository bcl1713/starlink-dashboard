# Customer Mission Briefing Phase-One Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task after user review. Steps use checkbox
> syntax. This handoff authorizes planning only.

**Goal:** Add an automatic customer trial deck to the normal mission ZIP while
preserving the established deck and direct single-leg PowerPoint download.

**Architecture:** Capture committed inputs once, prepare each leg once without
publication, and freeze a shared export snapshot. Feed existing legacy builders
and a separate trial projection/builder from that snapshot. Generate
synchronous, request-owned maps with a bounded browser stage and explicit
fallback.

**Tech Stack:** Python 3.11, Pydantic, python-pptx, zoneinfo; React Three Fiber,
Three.js, Vite and locked Playwright.

**Spec:**
[Approved presentation design](../specs/2026-10-07-customer-mission-briefing-trial-design.md).
Read the
[phase-two boundary](../specs/2026-10-07-mission-slide-background-generation-design.md)
and
[technical and acceptance companion](2026-10-07-customer-mission-briefing-phase-one-acceptance.md)
before execution. The companion is part of this plan.

**Baseline:** Latest fetched `origin/dev`, full SHA
`d77efd81c06e66755afd89ac55f31652bca297ce`, the merge of
[PR #307](https://github.com/bcl1713/starlink-dashboard/pull/307). Final merged
spec text takes precedence over earlier discussion. This plan adds no
application code; generated deck evidence below is future implementation work.

## Global Constraints

- Add `exports/mission/mission-customer-briefing-trial.pptx`, labeled “Customer
  briefing — Trial”; preserve all legacy filenames and import behavior.
- Generate from mission data, fixed rules, and templates; no AI services or
  manual slide authoring. Direct single-leg PPTX stays legacy.
- Every leg has a takeoff-to-landing axis and its own T-zero; exclude ground
  time.
- ET uses `America/New_York`; every displayed window has explicit ET endpoints,
  dates where needed, and correct EST/EDT. Zulu and T-plus are secondary.
- Row order: overall posture, Commercial Ka, Starshield, X-Band MILSATCOM, SOF /
  AR restrictions. Overall row height is at least twice a transport lane.
- Only overall posture uses green/amber/orange/red. All lanes use neutral plain
  Up, hatched Down, or genuinely indeterminate `?`; no asterisks or risk styles.
- Known Up counts 3/2/1/0 mean Nominal / Degraded / Limited / elevated risk /
  Communications unavailable. Any unknown means Posture uncertain.
- Restrictions never reduce Up count without independent availability evidence.
  Reuse existing 15-minute SOF configuration and full resolved AR periods.
- Graphics cover the full leg. Tables filter that partition, preserving exact
  boundaries and IDs, active causes, source identities, and remaining
  capability.
- Keep source records unsplit in the appendix; promote only material
  transitions.
- Preserve APO Patch.jpg aspect ratio and restrained APO branding. Starshield
  names only a transport. Keep text/tables editable and assets embedded offline.
- Widescreen, light backgrounds, grayscale labels/patterns; main text >=18 pt,
  primary times/window labels >=20 pt, supporting clocks/appendix >=14 pt.
  Paginate instead of shrinking. Small metadata cannot carry essential facts.
- Both decks use one immutable snapshot. Preserve rebuild/cache fallback and
  missing-data labels; never write export results into mission/timeline storage.
- Trial failure omits the entire trial file and preserves the legacy package
  with manifest/result warnings. Map failure uses a labeled fallback.
- Bound the entire extra map stage to 60 seconds by default, across all legs and
  views; cleanup browser descendants and temporary images on every exit path.
- Phase two, including save triggers, durable jobs, cancellation/restart,
  publication, cache leases/backfill and pending/retry UI, is excluded. It
  starts only after explicit user acceptance of representative trial
  layout/semantics. Legacy replacement requires a separate explicit decision.

## Review Focus

1. Concurrent saves and parent-footer reloads must not mix revisions (Task 1).
2. Cached normalized states lacking provenance must yield uncertainty rather
   than invented usability or total outage (Task 2).
3. Short flights and simultaneous boundaries must retain both SOF labels and
   brief outages without overlapping table rows (Task 2).
4. Failed browser startup/textures, missing route, and large multi-leg exports
   must honor the shared deadline and clean up resources (Tasks 3 and 5).
5. Long customer text and many windows must remain readable after actual PPTX
   rendering, with every essential fact on primary pages (Tasks 4 and 6).

Backend paths below are relative to `backend/starlink-location/`; frontend paths
are relative to `frontend/mission-planner/`. Inspected integration points and
renderer/fixture files are in the companion. New exporter modules are
`snapshot.py`, `snapshot_views.py`, `trial_projection.py`, `trial_clocks.py`,
`trial_maps.py`, `trial_layout.py`, and `trial_pptx.py`.

## Task 1: Capture once and preserve legacy exports

**Dependencies:** None. **Files:** Create snapshot modules; modify package
`__main__.py`, exporter `__main__.py` and `pptx_builder.py` to accept explicit
snapshot context. Add `tests/unit/test_export_snapshot.py`; extend
`test_package_adjusted_export.py`, `test_package_export_adjusted_times.py`,
`test_package_exporter.py`, and `test_pptx_builder.py`.

**Interfaces:**

```python
capture_export_snapshot(mission_id: str, route_manager: RouteManager, poi_manager: POIManager) -> ExportSnapshot
```

`ExportSnapshot` contains fingerprint, metadata, ordered
`tuple[LegSnapshot, ...]`, source payloads and warnings. Each leg contains
committed leg JSON, effective route JSON or None, timeline JSON or None,
canonical source records, resolved restrictions, UTC bounds or None, preparation
origin and warnings. Store canonical JSON bytes and immutable tuples, not
mutable Pydantic graphs inside a frozen dataclass. `SnapshotViews(snapshot)`
returns private model copies and read-only manager views for legacy consumers.

- [ ] Add `test_snapshot_isolated_from_later_save_and_builder_mutation`: mutate
      parent name, departure, route and POIs after capture; both decks, CSVs and
      exported source files retain captured values; subsequent export sees new
      values; assert one preparation per leg and no later source rereads.
- [ ] Add `test_capture_uses_prepare_without_publication` and
      `test_snapshot_rebuild_cache_missing`: fail rebuild, use copied cache with
      labeled provenance; missing cache remains explicit. Fail spies on mission,
      timeline and POI write functions. Cover feasible/unavailable route
      splices.
- [ ] Run these tests to observe missing-contract failures. Capture parent/leg
      files under active-leg then parent lock; release before heavy work. Copy
      routes/KML, relevant POIs, satellite and coverage inputs/configuration
      before preparation. Resolve source revisions/content digests; inputs that
      change during capture must trigger one whole-capture retry or explicit
      unavailability.
- [ ] Use read-only copied views with `prepare_mission_timeline`; preserve
      default coverage discovery without POI publication or mission/timeline
      writes. Freeze results once. Pass snapshot timelines to all package
      exporters, footer/cover metadata explicitly, and captured map inputs
      through adapters. Keep optional arguments for callers outside package
      export; direct PPTX output remains established. Do not change
      save/mutation routes.
- [ ] Run focused tests and the legacy comparison in the companion. Expect PASS,
      unchanged source models, one shared snapshot, legacy content/layout
      equivalent ignoring only listed volatile metadata. Commit Task 1.

## Task 2: Resolve trial intervals, clocks and coordination rows

**Dependencies:** Task 1 and map feasibility. **Files:** Create
projection/clocks; add `tests/unit/test_trial_projection.py`,
`test_trial_clocks.py` and fixtures. Reference reducer/rules/AR files; do not
alter their domain calculations.

**Interfaces:** `project_trial_leg(leg: LegSnapshot) -> TrialLeg`;

```python
classify_transport(state: TransportState | None, sources: tuple[SourceRecord, ...]) -> UsabilityDecision
```

`format_clocks(timestamp: datetime, takeoff: datetime) -> ClockLabels` (ET,
UTC/Zulu, relative strings). Immutable `TrialLeg` owns bounds, full
`tuple[TrialInterval, ...]`, filtered coordination rows, unsplit sources and
notes. Each interval has stable leg-local ID, UTC endpoints, ordered usability
decisions, posture, restrictions, active source IDs/causes, material limitations
and known remaining transports.

- [ ] Add `test_reason_specific_usability` for every companion rule, including
      conflicting evidence and degraded-without-reason. Assert pure X/Ku warning
      is plain Up with limitation; Ka coverage gap is Down; two Down plus `?` is
      Posture uncertain, never Communications unavailable.
- [ ] Add `test_nested_outages_partition_and_filtered_ids` using F02, and
      `test_half_open_brief_outage_and_short_sof` using F03/F04. Assert full
      contiguous coverage, union durations, exact IDs/bounds, all active causes
      and remaining transport names; no duplicate source-outage rows.
- [ ] Add `test_resolved_ar_and_missing_timing_note` for F05 and
      `test_quiet_nominal_only_standard_sof` for F01. Keep full AR with no X
      conflict and unchanged Nominal count. Preserve unresolved timing as an
      untimed note above the table and unsplit sources in appendix data.
- [ ] Add `test_et_midnight_dst_and_per_leg_tzero` with exact F07/F08 values.
      Run focused tests and confirm failures before implementation.
- [ ] Implement companion classification rules from canonical transport
      evidence, not aggregate status/call posture. Sweep sorted UTC boundaries
      half-open; combine simultaneous endpoints before evaluating the next
      interval. Clip restrictions to flight, aggregate active sources, merge
      only adjacent identical classification/posture/causes/context, then assign
      IDs. Fill uncovered availability with `?`; missing whole-flight bounds
      gets a missing-data leg page rather than fabricated times.
- [ ] Filter existing intervals for SOF/AR, any Down, Limited/unavailable,
      uncertainty, material coordination or usability limitations. Keep quiet
      Nominal intervals in graphics only. Never bridge omitted intervals or
      renumber rows. Preserve all source records before display partitioning.
      Use ZoneInfo and UTC arithmetic for elapsed time; plan-basis labels and
      re-export guidance explain shifted absolute conditions.
- [ ] Rerun tests; expect PASS for every fixture assertion. Commit Task 2.

## Task 3: Prove and package deterministic overview maps

**Dependencies:** Task 1; map IDs depend on Task 2. **Files/interfaces:** Use
companion architecture and file list. Produce

```python
render_trial_maps(snapshot: ExportSnapshot, legs: tuple[TrialLeg, ...], budget_seconds: float = 60.0) -> tuple[LegMapResult, ...]
```

Each result has leg ID, ordered PNG views, label, status and safe warnings.

- [ ] Run the companion feasibility gate before Task 2 implementation: packaged
      non-root runtime, local assets, fixed camera/reference time, real WebGL
      readiness and one short/dateline/polar/multi-view route. Preserve PNGs,
      timings and runtime identity; fallback-only runtime fails this gate.
- [ ] Add `test_trial_map_deadline_fallback_and_cleanup`,
      `test_trial_map_key_effective_inputs` and renderer readiness/framing
      tests. Fail textures, startup, context loss and timeout; assert labeled
      fallback, no blank slide and no surviving owned processes/temp images.
- [ ] Implement the dedicated scene and child renderer as specified in the
      companion. Use snapshot-only inputs and one monotonic stage deadline;
      cache within the request by full content key. Use labeled neutral static
      route fallback; if no route/image is possible, use a visible explanatory
      route-data card. Trial fallbacks must also use neutral styling.
- [ ] Run bounded renderer tests and image builds. Expect real maps and fallback
      cases to pass, no runtime network dependency, and verified cleanup. Commit
      Task 3; record measured feasibility before Task 4 integration.

## Task 4: Build editable, paginated customer slides

**Dependencies:** Tasks 2 and 3. **Files:** Create trial layout/PPTX modules;
add `tests/unit/test_trial_pptx.py`. Reuse APO Patch.jpg without editing it.

**Interface:**

```python
build_trial_pptx(snapshot: ExportSnapshot, legs: tuple[TrialLeg, ...], maps: tuple[LegMapResult, ...]) -> bytes
```

Returns a validated deck or raises `TrialGenerationError`.

- [ ] Add `test_trial_slide_contract_and_editability`,
      `test_trial_dense_pagination`, and `test_trial_source_appendix`. Assert
      row order/heights, font minima, lane text/patterns, editable tables and
      text, preserved source IDs, repeated legends/headers/clocks, embedded
      images and all primary windows. Run to confirm contract failures.
- [ ] Implement widescreen 13.333 x 7.5-inch trial slides, optional compact leg
      index, and independent leg pages. Header includes Leg N of M, locations
      with fallback names, departure/arrival ET and flight duration. Put small
      maps beside the dominant timeline and ET table; exact table columns and
      quiet-leg copy are in the companion. Use proportional bars and linked
      numbered callouts for brief windows. Consecutive panels preserve IDs,
      original table boundaries, continuation marks and full-flight coverage.
- [ ] Paginate measured text/table content at the required font sizes. Separate
      neutral SOF/AR row, count labels, fixed source-backed implications and
      prediction caveat; never invent shutdown instructions. Put all three
      clocks, unsplit sources/advisories and minor transitions in the appendix.
- [ ] Run tests and render F01/F02/F06/F09; inspect clipping and grayscale
      before package integration. Expect PASS and readable primary pages. Commit
      Task 4.

## Task 5: Add flag, isolated ZIP inclusion and visible warnings

**Dependencies:** Tasks 1–4. **Files:** Modify package
`__main__.py`/`__init__.py`, `app/models/config.py`, `config.yaml`,
`app/mission/routes_v2.py`, backend `main.py` CORS exposure, frontend
`src/services/export-import.ts`, `src/types/export.ts`,
`src/components/missions/ExportDialog.tsx`; add package, endpoint and
ExportDialog tests; extend config/export service tests.

- [ ] Add `test_trial_flag_file_set_and_direct_pptx_preserved`,
      `test_trial_failure_preserves_legacy_package`, and
      `test_trial_warning_download_result`. Inject
      projection/map/PPTX/validation failures and assert valid legacy ZIP, no
      partial trial file or manifest success, safe warnings visible after
      download. Run to confirm failures.
- [ ] Add top-level `SimulationConfig.customer_briefing_trial_enabled=False`,
      using `STARLINK_CUSTOMER_BRIEFING_TRIAL_ENABLED`; capture once per export.
      Disabling skips trial projection/render/build and restores original file
      set. No mission migration, user toggle or worker configuration.
- [ ] Add `export_mission_package_result(...) -> PackageExportResult` with
      `stream: IO[bytes]`, `warnings: tuple[str, ...]`, and
      `trial_status: Literal['disabled', 'included', 'failed']`. Preserve
      `export_mission_package(...) -> IO[bytes]` as compatibility wrapper. Build
      legacy exports first; isolate all trial stages; validate completed trial
      bytes before writing the sole new ZIP entry and manifest entry. Trial
      status/warnings are additive manifest fields when enabled.
- [ ] Endpoint returns ZIP with `X-Mission-Export-Trial-Status` and bounded safe
      JSON `X-Mission-Export-Warnings`; expose via CORS. Add
      `exportMissionResult(...) -> Promise<{blob: Blob; warnings: string[]}>`,
      preserving existing Blob wrapper. ExportDialog downloads normally,
      displays warnings without automatic two-second dismissal, and never claims
      trial success on failure. This is synchronous export feedback, not
      phase-two UI.
- [ ] Rerun flag/failure/legacy/source-import tests. Expect exact legacy file
      set when disabled, both decks when enabled, safe partial-information
      labels, and legacy-only success with warning on trial failure. Commit
      Task 5.

## Task 6: Produce acceptance decks and return for customer review

**Dependencies:** All prior tasks. Follow companion fixtures, commands, evidence
and rollout gates. Add its acceptance runner/tests and generate paired decks.

- [ ] Verify applicable CI gates on final SHA and isolated production-path
      export through Nginx. Run all fixture assertions; open/render extracted
      PPTX files offline. Preserve evidence and verify runtime teardown. Commit
      runner/docs.
- [ ] Return paired legacy/trial decks, rendered contact sheets/grayscale pages,
      warning/fallback examples and timings for customer review. Record whether
      the customer can locate reduced redundancy, total outage, remaining
      transports and SOF/AR in a few seconds. Require explicit layout/semantics
      acceptance before any phase-two implementation; do not replace legacy.
