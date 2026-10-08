# Customer Briefing HTML-to-PDF Checkpoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Deliver fully assessed and incomplete-X one-page HTML/PNG/PDF briefs
with exact evidence for customer visual review.

**Architecture:** Audit and selectively reuse #309's immutable snapshot and
canonical/customer projections. A static HTML/CSS/SVG composer and existing map
scene run under one request-owned Chromium coordinator and shared deadline.
Publish checkpoint files only after PDF, evidence, and cleanup validation.

**Tech Stack:** Python 3.11, pytest, Node 22.22.2, HTML/CSS/SVG, existing
React/Three map scene, locked Playwright/Chromium, bundled DejaVu Sans, Docker,
Poppler for PDF inspection only.

**Spec:**
[Reviewed HTML-to-PDF design](../specs/2026-10-08-customer-briefing-html-pdf-design.md),
commit `4766ba42`,
[re-review](https://github.com/bcl1713/starlink-dashboard/pull/312#issuecomment-6061103118).
The review reports both corrections resolved and requests no further spec
changes. This plan awaits user review and execution-method selection.

## Global Constraints

- Continue `.worktrees/customer-briefing-html-pdf`, branch
  `feat/customer-briefing-html-pdf`, draft #312; keep primary on `dev`.
- Preserve #309 and its dirty worktree. Reuse committed `575730a8`, never its
  uncommitted runner changes. No wholesale merge or old PPTX layout machinery.
- Checkpoint only: exactly two separate normal-leg examples. No general
  pagination, dense/multi-leg implementation, API/UI/ZIP integration, promotion,
  background worker, production Dockerfile change, or merge in this plan.
- Legacy PPTX and other source/export behavior stay unchanged; trial remains
  default-off. Checkpoint runner is explicit developer tooling, not a feature
  flag.
- Normal output is one page per leg; later ceilings are three pages per
  pathological leg and fewer than fifteen per representative five-leg mission.
  Five pages for five normal legs is desirable; no filler or technical appendix.
- Print 13.333333 by 7.5 inches, margin 0, scale 1, backgrounds on, browser
  headers/footers off. Preview uses the same print CSS.
- Title 28–32 pt; timing/posture 18–22 pt; transport 16–18 pt; table 14–16 pt;
  nonessential footer 10–12 pt. Use bundled DejaVu Sans regular/bold.
- One request-owned 60-second monotonic deadline includes browser startup, maps,
  HTML composition/readiness/fit, PDF printing, and teardown. No stage reset.
- One browser, separate fresh map/document contexts, one scoped asset listener.
  Alternate separate processes require documented evidence of unsafe sharing;
  they retain the same request owner/deadline/cleanup model.
- Definitive posture alone uses green/amber/orange/red. Unknown counts as
  neither Up nor Down; SOF/AR does not independently reduce availability.
- Exact UTC controls SVG geometry; human ET is primary. Never expose
  microseconds, raw source text, IDs, rules, or hashes in customer pages.
- Intended overview map must succeed for the primary checkpoint. Test fallback
  separately. Do not continue beyond Task 4 without explicit visual acceptance.

## Review Focus

1. Retained fixtures have the wrong date/duration: rewrite every dependent UTC
   boundary and assert exact new ET/UTC expectations (Task 1).
2. Internal source/rule churn or changing uncertainty can distort customer rows:
   preserve real confidence changes without leaking identifiers (Task 1).
3. Long labels, narrow red windows, and incomplete X can defeat visual
   hierarchy: inspect actual print-layout fit, callouts, and confirmed
   capability (Tasks 2–4).
4. Independent map timers or a second browser launch can evade the shared
   budget: exercise slow stages, cutoff, and eager context cleanup (Task 3).
5. Preview/PDF mismatch or partial evidence publication can falsely qualify the
   checkpoint: inspect the delivered PDF and inject post-render failures (Task
   4).

## File boundaries and execution conventions

Paths below are repository-relative. `B` means `backend/starlink-location`; `F`
means `frontend/mission-planner`. Reuse files by reading
`git show 575730a8:<path>` into the new worktree, reviewing their dependencies,
and editing only the listed files. Record the reuse inventory and retained test
selection in checkpoint evidence.

`B/app/mission/exporter` owns snapshot/projection/customer payloads and
evidence. `F/src/mission-export` owns map scene/framing and the combined browser
runtime. Its new `briefing` directory owns pure document/SVG/CSS modules and
their Node tests. `tools/acceptance/customer-briefing` owns isolated checkpoint
orchestration.

Backend checks run from `B`:

```bash
timeout --kill-after=10s 10m uv run --with-requirements requirements.txt pytest <selection> -q
```

Frontend checks run from `F` with fresh worktree dependencies installed via
`timeout --kill-after=10s 10m npm ci --no-audit --no-fund` once execution is
approved. Node unit tests use
`timeout --kill-after=10s 10m node --test <selection>`. Tools checks run from
root:

```bash
timeout --kill-after=10s 10m uv run --python 3.11 --with pytest --with psutil pytest <selection> -q
```

Import/dependency failures are setup problems, not meaningful RED evidence.
Record commands/PIDs/PGIDs/paths before checks; verify timeout cleanup before
retry.

### Task 1: Audit and retain canonical/customer inputs

**Files:** Reuse/create in `B/app/mission/exporter`: `snapshot.py`,
`snapshot_inputs.py`, `snapshot_views.py`, `trial_projection.py`,
`trial_clocks.py`, `customer_view.py`, `customer_clocks.py`. Modify only the
retained injection additions in `B/app/mission/timeline_preparation.py` and
`B/app/mission/timeline_builder/events.py`. Reuse/adapt
`B/tests/unit/{customer_briefing_fixtures,test_export_snapshot,test_trial_projection,test_trial_clocks,test_customer_view,test_customer_clocks}.py`.
Reuse fixtures needed by those tests under `B/tests/fixtures/customer_briefing`;
rewrite `composition-assessed.json` and `composition-incomplete-x.json`.

**Interfaces:** Preserve `LegSnapshot`, `ExportSnapshot`,
`capture_export_snapshot(mission_id, route_manager, poi_manager) -> ExportSnapshot`,
`project_trial_leg(leg: LegSnapshot) -> TrialLeg`, and
`project_customer_leg(captured, trial, *, leg_number, leg_count) -> CustomerLegView`.
Preserve frozen `CustomerRow` clock/impact/remaining/posture and interval/source
mapping fields. Do not reuse `customer_pages.py` or `trial_layout.py`.

- [ ] Stage the retained fixture JSON unchanged first; write fixture-loader
      assertions without importing modules not yet ported. Add
      `test_checkpoint_oct25_eight_hours_and_nested_outages` and
      `test_checkpoint_incomplete_x_keeps_confirmed_risks` in
      `test_customer_view.py`. Assert UTC flight
      `[2026-10-25T14:00:00Z, 2026-10-25T22:00:00Z]`, title
      `LEG 1 OF 1 — KADW → PAED`, `25 Oct 2026`, and
      `DEP 10:00 ET | ARR 18:00 ET | 8h 00m`. Assert all-four posture labels and
      exactly `[16:25Z,16:30Z]` unavailable; incomplete X remains `?`
      throughout. Initially assert JSON boundaries for RED; add projection/view
      assertions after port.

  ```python
  assert data["utc_bounds"] == ["2026-10-25T14:00:00Z", "2026-10-25T22:00:00Z"]
  assert view.timing_label == "DEP 10:00 ET | ARR 18:00 ET | 8h 00m"
  assert (outage.start_time, outage.end_time) == (
      utc("2026-10-25T16:25:00Z"), utc("2026-10-25T16:30:00Z")
  )
  ```

- [ ] Run those tests against retained committed fixtures; expect assertion
      failures for October 20 / seven-hour timing. Save actual RED output.
- [ ] Port the seven modules and exact injection additions after auditing
      imports. Preserve `dev`'s independent X constraints. Retain optional
      defaults: `capture_x_conditions=False`, `discover_coverage=True`,
      `satellite_catalog=None`, `constraint_config=None`; canonical capture opts
      in. No legacy exporter/package/API wiring is copied. Filter snapshot tests
      that rely on old package wiring; retain capture/mutation/cache/source
      tests.
- [ ] Rewrite both fixtures coherently: departure 14:00Z, arrival 22:00Z; Ka
      16:00–17:00Z, Starshield 16:15–16:45Z, X 16:25–16:30Z; SOF 14:00–14:15Z
      and 21:45–22:00Z. Update all route points, bounds, sources, timeline, and
      mission times. Preserve synthetic endpoint geography.
- [ ] Add/run `test_customer_grouping_ignores_internal_rule_identity` and
      `test_customer_uncertainty_change_without_outage_is_material`. Assert
      equivalent adjoining rows group despite IDs/rules; a real confidence
      change remains a row/boundary; no grouping crosses a quiet gap or outage.
- [ ] Run retained semantic/clock/snapshot tests plus existing X propagation and
      timeline-preparation tests. Assert default-call event/timeline/POI
      equivalence with fixed clocks and captured constraints; exact evidence
      stays immutable.
- [ ] Commit only passing scoped changes:
      `feat: retain briefing inputs for PDF checkpoint`.

### Task 2: Compose one customer page with HTML/CSS/SVG

**Files:** Create `B/app/mission/exporter/customer_document.py` and
`B/tests/unit/test_customer_document.py`. Create
`F/src/mission-export/briefing/{document,timeline}.mjs`, `briefing.css`, and
`{document,timeline}.test.mjs`. Reuse APO patch through local asset packaging.

**Interfaces:**

```text
build_customer_document(snapshot: ExportSnapshot, view: CustomerLegView, trial: TrialLeg) -> dict
```

Emits version-1 JSON payload. Fields: `schemaVersion`, `snapshotFingerprint`,
`legId`, `header` (`title,subtitle,date,timing,notice`), `flight`
(`startUtc,endUtc`), `intervals`
(`startUtc,endUtc,posture,decisions,restrictionLabels`), `rows`
(`id,startUtc,endUtc,et,impact,remaining,posture`), and `mapInput` from Task 3's
retained `build_map_input`; internal row IDs are attributes, never visible text.
`decisions` is three state strings (`Up`, `Down`, `?`), in Ka/Starshield/X
order; restriction labels are customer-formatted. Reject multiple/mismatched
legs, naive bounds, unordered/gapped intervals.

```text
composeBriefing(payload, {mapDataUrl, apoDataUrl, regularFontDataUrl, boldFontDataUrl, cssText}) -> string
```

Returns self-contained HTML; `renderTimeline(payload) -> string` returns its SVG
with exact UTC-derived geometry. Neither performs I/O, launches a browser, or
classifies transports.

- [ ] Write `test_document_preserves_geometry_and_safe_customer_fields` and
      `test_document_rejects_identity_and_partition_mismatch`. Assert no raw
      reason token in visible payload, preserved exact boundaries, and one leg
      only.
- [ ] Run the named backend tests; expect missing-contract assertion failures.
- [ ] Implement payload validation/serialization. Keep canonical source data
      separate for Task 4 evidence. Initially allow `mapInput=None`; Task 3
      wires the retained pure map-input builder without launching the old
      renderer.
- [ ] Write Node tests `exact red geometry`, `escaped customer strings`,
      `one incomplete-X notice`, and `no map reclaims grid`. For the eight-hour
      flight assert red SVG fraction `5/480`, both SOF segments, neutral unknown
      band, and no extra pages. `<script>` in a title must become escaped text.

  ```js
  assert.equal(redWidth / flightWidth, 5 / 480);
  assert.equal((html.match(/X-Band planning incomplete/g) ?? []).length, 1);
  assert.ok(!html.includes("<script>customer input</script>"));
  ```

- [ ] Run `node --test src/mission-export/briefing/*.test.mjs`; expect named
      contract failures; then implement the two pure composers and print
      stylesheet. Use 30/20/17/14/10 pt type scale, navy/light/gold grid, hero
      height at least twice transport lanes, four-column table, restrained
      patch/map card. Short labels use callouts without changing width.
      Header/date/notice appear once. Essential table content cannot hide in a
      footer.
- [ ] Define stable selectors `.briefing-page`, `[data-fit]`, `[data-row-id]`,
      `[data-posture]`, and `[data-interval-start]` for fit/evidence
      inspections. Inline bundled fonts/images/CSS into final HTML; do not
      insert diagnostics.
- [ ] Run backend/Node tests. Exact rendered-fit and font checks belong to Task
      3, and visual acceptance belongs to Task 4; string tests cannot qualify
      them.
- [ ] Commit: `feat: compose one-page HTML customer briefing`.

### Task 3: Shared browser/deadline runtime

Implement the
[required runtime task](2026-10-08-customer-briefing-html-pdf-runtime.md). It
defines map reuse, coordinator APIs, browser measurements, PDF/PNG outputs,
reserve values, ownership, fault tests, and the dedicated checkpoint image.

### Task 4: Publish checkpoint evidence and stop for visual review

Implement the
[required checkpoint task](2026-10-08-customer-briefing-html-pdf-evidence.md).
It defines schema validation, atomic local publication, isolated execution,
actual PDF inspection, cold timings/determinism, fallback cases, and cleanup.

## Plan self-review and handoff

Task 1 covers retained semantics and fixture correction; Task 2 covers customer
composition; Task 3 covers exact browser fit, determinism, deadline/lifecycle;
Task 4 proves the actual two delivered pages and atomic evidence. All five
Review Focus items have named checks in their owning tasks. Inspect both
companions before execution; they are part of this plan.

The full spec's dense pagination, mission budgets, ZIP publication, production
proxy/UI journeys, feature-flag integration, legacy package comparison, and
exact-head CI/production acceptance are later work, explicitly gated by visual
approval. The checkpoint cannot claim those checks passed.

User review and execution-method selection precede implementation. Recommend
native execution because these four tasks share tight payload/runtime/evidence
interfaces and stop before production behavior changes. Subagent-driven
execution is available if independent review per task is preferred. Whichever
method is selected, return the actual primary/secondary pages and evidence, and
stop for explicit primary-page acceptance before planning broader
implementation.
