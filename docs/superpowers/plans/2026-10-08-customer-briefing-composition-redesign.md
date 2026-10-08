# Customer Briefing Composition Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Produce a polished, editable customer briefing that makes reduced
capability, remaining transports, and SOF/AR restrictions apparent within
seconds.

**Architecture:** Keep immutable snapshots and the canonical availability
projection. Add a pure customer view, compact clock formatting, measured page
planning, and separate evidence serialization. The PPTX and evidence use one
page plan and publish as one optional artifact pair after validation.

**Tech Stack:** Python, frozen dataclasses, python-pptx, Pillow/DejaVu font
measurement, pytest, existing offline route renderer, pinned
LibreOffice/Poppler, Docker Compose, existing production Nginx and platform
browser acceptance.

**Spec:**
[Approved composition redesign](../specs/2026-10-08-customer-briefing-composition-redesign.md),
revision `5bb2d45cc5183351fc1861bba2fe8e76df9d3b0f`, approved in
[PR #309 review](https://github.com/bcl1713/starlink-dashboard/pull/309#issuecomment-6059460812)
and the current user request. The subsequent
[plan review](https://github.com/bcl1713/starlink-dashboard/pull/309#issuecomment-6059815129)
clears Tasks 1–2 once its four corrections, incorporated here, are applied. The
spec's opening status predates that approval. Execution-method selection remains
pending; Tasks 3–6 still require explicit primary-page visual acceptance.

## Global Constraints

- Continue in PR #309's isolated feature worktree. Keep the PR draft and the
  trial default-off.
- No merge, rebase, legacy replacement, phase-two work, or shared runtime
  changes belong to this redesign.
- Generation remains deterministic, template-driven, offline-capable, and free
  of AI authoring.
- A normal leg has one primary slide, containing its full-flight timeline and
  coordination table together.
- A pathological leg has a maximum of three customer pages.
- Five-leg missions must have fewer than fifteen customer slides. Five slides
  are valid and desirable when each leg fits one page. Six-to-twelve is a likely
  range with legitimate continuations or a useful index, never a minimum.
- No cover, diagnostics, source appendix, or automatic detail pages.
- Never meet the budget by shrinking below the type scale, dropping a material
  window, or merging across a distinct operational condition.
- Preserve the canonical `?` classification and uncertain overall posture. An
  unknown transport never counts as Up or Down.
- SOF and AR remain coordination restrictions. They do not lower an availability
  count without independent outage evidence.
- Customer formatting never exposes microseconds. Preserve exact bar geometry;
  do not round the underlying intervals.
- Use packaged DejaVu Sans regular/bold files for both measurement and PPTX
  text; verify the same files in the offline reader and prove rendered fit.
- Native editable table cells have 14–16 pt text; title 28–32 pt, timing/posture
  18–22 pt, transport labels 16–18 pt, prediction footer 10–12 pt.
- Add `exports/mission/mission-customer-briefing-evidence.json` alongside the
  trial PPTX and list it in the manifest.
- Trial failure adds neither partial artifact to the delivered ZIP. Disabling
  the trial preserves the legacy file set.
- Do not expand to dense/long or multi-leg implementation until that page is
  explicitly accepted visually.
- Customer missions and geometry remain private local evidence.

## Review Focus

1. Internal source churn must not multiply equivalent customer rows, but a quiet
   gap, changed confidence, brief outage, or AR boundary must remain distinct
   (Tasks 1 and 3).
2. Incomplete X planning must not hide known outages or turn confirmed
   capability into a definitive posture rating; changing uncertainty must stay
   visible (Tasks 1 and 3).
3. Subminute boundaries, midnight, and DST folds must retain exact geometry and
   unambiguous, outward-rounded labels (Tasks 1 and 3).
4. Long names, absent endpoints/maps/timing, and many real limitations must
   preserve minimum typography and completeness or fail safely (Tasks 2 and 4).
5. Evidence validation failure after PPTX creation must leave a complete legacy
   ZIP with neither optional artifact nor orphan manifest entry (Task 5).

## Execution boundaries and verification commands

Use the existing worktree `.worktrees/customer-mission-briefing-phase-one` on
`feat/customer-mission-briefing-phase-one`. Primary checkout remains on `dev`.
This is continuation of the open PR, not a new branch from current `dev`. Do not
resolve its recorded conflicts in this pass.

Tasks 1–2 are the first-page checkpoint. Tasks 3–6 are deferred until explicit
visual acceptance of Task 2's fully assessed primary page. Plan approval alone
does not clear that later gate. If visual acceptance requests changes, revise
only the checkpoint implementation and render it again before broadening scope.

All paths below are relative to this worktree. Backend commands run from
`backend/starlink-location` using the repository's tracked Python/uv selection:
`timeout --kill-after=10s 10m uv run pytest <selection> -q`. A failing test must
fail for its named contract, not a missing dependency or collection error. Tools
commands run from the worktree root with the configured Python test environment:
`timeout --kill-after=10s 10m python3 -m pytest <selection> -q`. Commit each
independently passing task on the existing branch.

Before any test/build/render launch, record command, PID/PGID, paths, limits,
and any Compose project/volumes. Reuse existing ownership runners where
possible; install exit/signal cleanup for new resource-owning runners. Preserve
the actor Docker configuration. Stop and audit owned resources immediately after
checks, including failures; keep evidence and the open-PR worktree. Neither API
success nor LibreOffice rendering qualifies real browser or desktop PowerPoint
acceptance. Missing CI/browser authority remains an explicit gate.

## File and interface map

- Keep `app/mission/exporter/trial_projection.py`, `trial_clocks.py`, snapshot
  modules, legacy exporters, and source import files as canonical inputs.
- Create `app/mission/exporter/customer_clocks.py` for display-only clocks.
  `CustomerRange(start: str, end: str, approximate: bool)` is frozen.
  `format_customer_range` takes `start: datetime`, `end: datetime`,
  `departure: datetime`, and keyword-only `second_precision: bool = False`;
  returns `CustomerRange`. It rejects naive instants, rounds outward, adds
  dates/offsets when needed, and never mutates inputs.
- Create `app/mission/exporter/customer_view.py` for fixed wording and grouping.
  Frozen `CustomerRow` fields: `id: str`, `start_time: datetime`,
  `end_time: datetime`, `clock: CustomerRange`, `impact: str`, `remaining: str`,
  `posture: str`, `interval_ids: tuple[str, ...]`,
  `source_ids: tuple[str, ...]`. Frozen `CustomerLegView` fields: `leg_id: str`,
  `title: str`, `subtitle: str | None`, `date_label: str`, `timing_label: str`,
  `notice: str | None`, `intervals: tuple[TrialInterval, ...]`,
  `rows: tuple[CustomerRow, ...]`, `legend_required: bool`.
  `project_customer_leg` takes `captured: LegSnapshot`, `trial: TrialLeg`,
  keyword-only `leg_number: int`, `leg_count: int`; returns `CustomerLegView`
  and handles one leg only.
- Create `app/mission/exporter/customer_pages.py` for measured planning. Frozen
  `CustomerPage` fields: `leg_id: str`, `slide_number: int`,
  `kind: Literal["primary", "continuation"]`,
  `utc_bounds: tuple[datetime, datetime] | None`, `row_ids: tuple[str, ...]`,
  `show_map: bool`. `plan_customer_pages` takes
  `views: tuple[CustomerLegView, ...]` and `maps: tuple[LegMapResult, ...]`;
  returns `tuple[CustomerPage, ...]` and uses layout measurement, not
  interval-count limits. Initially supports the two separate one-leg checkpoint
  inputs only; Task 4 generalizes it after visual approval.
- Modify `app/mission/exporter/trial_layout.py` for the approved grid, colors,
  typography and measured fit; `trial_pptx.py` for native objects and
  validation. Preserve `build_trial_pptx(snapshot, legs, maps) -> bytes` for
  existing callers; add keyword-only
  `views: tuple[CustomerLegView, ...] | None = None` and
  `pages: tuple[CustomerPage, ...] | None = None`. Supplied views/pages are
  validated; omitted values are derived once. Package assembly supplies both.
- Create `app/mission/exporter/customer_evidence.py`. `build_customer_evidence`
  takes `snapshot: ExportSnapshot`, `legs: tuple[TrialLeg, ...]`,
  `maps: tuple[LegMapResult, ...]`, `views: tuple[CustomerLegView, ...]`,
  `pages: tuple[CustomerPage, ...]`; returns `bytes` and emits canonical
  schema-version-1 JSON. `validate_customer_evidence` takes `data: bytes`,
  `snapshot: ExportSnapshot`, `pages: tuple[CustomerPage, ...]`; returns `bytes`
  and rejects mismatched coverage/identity.
- Modify `app/mission/package/__main__.py` to assemble/validate the pair before
  writing either file. Preserve `PackageExportResult` and external HTTP/UI
  status/warning contracts. Update acceptance tools and tests to trace raw data
  through evidence instead of appendix slides.

## Task 1: Normal-leg customer contracts and checkpoint inputs

**Files:** Create `customer_clocks.py`, `customer_view.py` under
`backend/starlink-location/app/mission/exporter/`; create
`backend/starlink-location/tests/unit/test_customer_clocks.py` and
`test_customer_view.py`; create fixtures
`backend/starlink-location/tests/fixtures/customer_briefing/composition-assessed.json`
and `composition-incomplete-x.json`. Extend the existing fixture helper only if
required; preserve F01–F10.

**Interfaces:** Consumes `LegSnapshot`, `TrialLeg`, `TrialInterval`,
`project_trial_leg`, `ensure_utc`, `EASTERN`. Produces `CustomerRange`,
`CustomerRow`, `CustomerLegView` and the two projection functions above.

- [ ] Write `test_checkpoint_pair_has_independent_assessment_and_known_risks`:
      use a synthetic KADW→PAED leg on 2026-10-20, 10:00–17:00 UTC, with sourced
      endpoints and valid timed geometry. All three transports have an assessed
      available basis throughout. Prove Ka Down at 12:00–13:00 UTC, Starshield
      Down at 12:15–12:45 UTC, and X Down at 12:25–12:30 UTC, wholly inside the
      Ka/Starshield overlap. Assert exactly that five-minute 0-Up interval and
      surrounding 3/2/1-Up postures, no `?`, and both independent SOF windows
      (10:00–10:15 and 16:45–17:00 UTC). The secondary retains Ka/Starshield
      risks but removes X availability and outage proof, leaving X unresolved
      throughout.
- [ ] Write `test_customer_view_groups_equivalent_adjacent_sources` and
      `test_unknown_x_has_one_notice_and_keeps_known_outages`. Assert equivalent
      source-ID changes share a row with all interval/source mappings; quiet
      nominal spans create no row. Secondary notice is exactly
      `X-Band planning incomplete — confirmed transport capability shown below.`;
      row qualifier is `Assessment incomplete`, known remaining names persist,
      and no unknown state becomes Up/Down. Rows show fixed customer wording,
      never arbitrary raw reason text, hashes, rules, or window numbers.
- [ ] Write `test_customer_range_ordinary_minutes_and_outward_rounding`: normal
      labels use `HH:MM ET`; fractional-minute starts floor and ends ceil with
      `approximate=True`; exact UTC intervals remain byte-for-byte unchanged.
      Write `test_endpoint_pair_and_single_name_fallback`: endpoint names win;
      absent pairs use one leg name, never the same route title across an arrow.
- [ ] Run the new tests RED using the bounded backend command. Implement the
      pure contracts and basic one-leg grouping/wording; retain canonical
      posture values for evidence and select neutral confirmed-capability
      wording in the view when any decision is `?`. Preserve original intervals
      in `view.intervals`.
- [ ] Run the new tests plus `tests/unit/test_trial_projection.py` and
      `tests/unit/test_trial_clocks.py` GREEN. Commit the checkpoint input/view
      contracts: `feat: project compact customer briefing views`.

## Task 2: Editable first-page pair and visual acceptance checkpoint

**Files:** Create `customer_pages.py`; modify `trial_pptx.py`,
`trial_layout.py`, and `tests/unit/test_trial_pptx.py`; create
`tools/acceptance/customer-briefing/composition_checkpoint.py` and
`tools/tests/test_customer_briefing_composition_checkpoint.py`; update
`tools/acceptance/customer-briefing/README.md`.

**Interfaces:** Consumes Task 1 views, existing `LegMapResult`/`MapView`,
`render_trial_maps`, bundled APO patch, fixed font measurement, and offline
rendering. Produces the one-page implementation of `plan_customer_pages`, the
extended `build_trial_pptx`, and a checkpoint runner CLI:

```bash
python3 tools/acceptance/customer-briefing/composition_checkpoint.py \
  --sha <full-clean-HEAD> --evidence <new-private-directory>
```

- [ ] Write `test_assessed_primary_is_one_editable_slide` and
      `test_incomplete_x_primary_is_one_neutral_slide`: each input produces one
      16:9 page containing full-flight timeline plus a four-column native table.
      Assert titles 28–32 pt, timing/posture 18–22 pt, transport labels 16–18
      pt, cells 14–16 pt and footer 10–12 pt. Overall lane is at least twice a
      transport lane height; exact UTC boundaries align across all five lanes.
      Assert assessed green/amber/orange/red blocks and neutral transport lanes;
      SOF uses blue/gray independently. Secondary uses a neutral overall band,
      confirmed capability labels and exactly one incomplete-planning note.
- [ ] Write `test_short_outage_keeps_exact_width_and_readable_callout`,
      `test_map_card_preserves_aspect_ratio_without_diagnostic_text`, and
      `test_missing_map_reclaims_space_without_extra_slide`. Native title/table
      objects remain editable; media relationships are embedded. The map is a
      successful intended overview-style render for the primary checkpoint; a
      static fallback cannot qualify that page. Verify aspect ratio, crop,
      marker legibility and grid alignment in its full-resolution preview. Test
      real static fallback separately afterward, retaining the no-map case. The
      first leg gets a compact legend and an unobtrusive Trial label.
- [ ] Write `test_measurement_and_pptx_use_same_packaged_font`: every native
      text run uses DejaVu Sans with matching regular/bold measurement files.
      Record file hashes; reject reader substitution. Verify long titles,
      table-cell line breaks and measured bounds against actual offline renders
      and the accepted checkpoint page before trusting page-planner fit.
- [ ] Run RED. Implement the header navy/APO gold/light body, shared ET axis,
      dominant posture band, quiet Up/Down/? lanes, blue/gray restriction lane,
      short-window callouts, integrated/reclaimable map card, and compact table.
      Remove source appendix/window-detail/automatic map pages from the new
      composition. Defer continuation and multi-leg implementation to Task 4.
      Replace old tests that require raw source text or appendix pages; retain
      canonical, validation, offline asset and editable-object tests.
- [ ] Write `test_primary_checkpoint_rejects_static_map_fallback` and runner
      tests for clean-SHA/unique-path checks, two-deck manifest, render failure
      reporting, timeout/signal cleanup and scoped ownership. Implement the CLI
      using existing `Owner` conventions and pinned offline render image. Record
      fixture/snapshot/deck hashes, slide counts, map status, reader/font
      identities, PDF outputs and full-resolution color/grayscale PNGs (at least
      1800 pixels wide). Both files must be actual editable PPTXs. Runner
      failure must report a primary map fallback as a failed visual checkpoint,
      never a successful review candidate.
- [ ] Run focused backend/tools tests GREEN; commit
      `feat: compose first-page customer briefing checkpoint`. Render the clean
      committed candidate under `timeout --kill-after=10s 20m`, inspect both
      full-resolution pages, and audit teardown. Retain diagnostics privately.
      Rendering failure is not a visual approval and must remain reported.
- [ ] Deliver the two PPTXs and color/grayscale previews with a concise visual
      assessment of hierarchy, table readability, all four posture colors,
      branding, spacing, rendered metric fit and intended map integration.
      Record which page is the fully assessed primary. Request explicit visual
      acceptance of that primary page. **STOP here. Do not execute Tasks 3–6
      until that acceptance arrives.**

## Deferred tasks and plan review

[Tasks 3–6](2026-10-08-customer-briefing-composition-redesign-follow-up.md)
cover material grouping/clock edges, dense and multi-leg budgets, exact evidence
and atomicity, then production/browser/customer qualification. This companion is
part of the implementation plan; its entry gate is explicit primary-page visual
acceptance after Task 2. The documents are split to meet the repository's
300-line documentation limit.

Spec coverage: Tasks 1–2 deliver the first-page pair; Task 3 covers semantics
and clocks; Task 4 covers density/incomplete data/budgets; Task 5 covers exact
provenance/atomicity; Task 6 covers production, browser, scan, desktop editing,
and final acceptance. Each Review Focus item has named tests in its owning task.
One immutable view/page plan feeds both artifacts; no second availability engine
or legacy modification is planned.

Recommend native execution through Tasks 1–2 because they share customer
view/layout interfaces and must stop for visual feedback before generalization.
The user reviews both plan documents and chooses native or subagent-driven
execution before implementation. Preserve that choice for deferred tasks; visual
checkpoint acceptance remains a separate required decision.
