# Customer Briefing Pagination and Runtime Tasks

Required Tasks 3–4 companion to the
[production plan](2026-10-08-customer-briefing-production.md). Its constraints,
definitions, verification commands, and approval gate apply. These tasks are
approved implementation, not completed verification.

## File and interface boundaries

Python owns canonical projection, display cells, and mission payload/evidence.
Node owns browser measurements, page assignment, composition, printing, and
runtime ownership. Neither pagination nor HTML may classify availability. Use
version 2 for mission documents/reports/evidence; preserve version-1 checkpoint
entrypoints and evidence without silently changing their meaning.

`MissionPayload` is a JSON dict with `schemaVersion=2`, `snapshotFingerprint`,
`missionId`, and ordered `legs`. Each leg keeps the existing
header/flight/intervals/rows/mapInput contract plus `mapInputDiagnostics` and
`displayCells`. Leg/row identities are scoped together; row IDs from different
legs cannot collide in evidence lookup.

`PagePlan` is a JSON dict with `schemaVersion=2`, `snapshotFingerprint`,
`missionId`, and ordered `pages`. Each page has
`page,legId,legPage,legPageCount,kind` (`primary|continuation`),
`flightStartUtc,flightEndUtc`, `rowStartUtc,rowEndUtc` (nullable only for no-row
pages), and `rowIds`. Flight bounds describe the primary timeline; row bounds
describe that page's table. They cannot substitute for each other or be inferred
from ground gaps.

### Task 3: Plan readable continuation pages

**Files:** Modify `B/app/mission/exporter/customer_document.py`,
`customer_evidence.py`,
`F/src/mission-export/briefing/{document.mjs,briefing.css}`. Create
`F/src/mission-export/briefing/pagination.mjs` and `pagination.test.mjs`. Tests:
`B/tests/unit/test_customer_document.py`, `test_customer_evidence.py`,
`F/src/mission-export/briefing/document.test.mjs`,
`F/src/mission-export/briefing-render.browser-test.mjs`. Create synthetic
dense/two-page/three-page/over-budget/five-leg fixtures in
`B/tests/fixtures/customer_briefing`; do not edit accepted sample PDFs.

**Interfaces:**

```text
build_customer_mission_document(snapshot: ExportSnapshot) -> dict
planBriefingPages({payload, measure, budget}) -> Promise<PagePlan>
composeMissionBriefing(payload, pagePlan, assets) -> string
build_customer_mission_evidence(snapshot, payload, page_plan, report) -> bytes
```

The mission builder projects each captured leg in order using
`project_trial_leg` and `project_customer_leg` with correct N/M. Extract a
shared leg-payload helper that selects the matching captured leg without the
checkpoint's single-leg guard. Keep that guard in the v1 wrapper; the v2 builder
passes the full mission fingerprint through every leg.
`measure({legId,kind,rowIds,continued})` returns actual print-layout fit,
cell/row bounds, essential-label collisions, and available content bounds. The
coordinator supplies it from one loaded-font document context; it neither
launches a browser nor creates a deadline. The planner returns page assignments
only after validating canonical row coverage and maximum three pages per leg.

- [x] Write `five normal legs produce five pages`,
      `wrapped rows choose the measured boundary`,
      `continuation labels consume space`, `every row exactly once`,
      `three pages accepted fourth rejected`, and `oversized row fails`. Assert
      no source-record pagination, no filler, no quiet gap merging, unchanged
      row IDs/clocks/cells, no repeated material rows, and no ground span across
      legs. Synthetic measure tests prove planning only.
- [x] Add backend tests for multi-leg identity/fingerprint/partition validation,
      missing flight bounds, empty mission, missing routes, missing AR timing,
      stale cache uncertainty, duplicate leg IDs, and nonchronological row data.
      Missing useful map is allowed with reasons; missing valid flight bounds
      fails the whole optional pair with a `data` code.
- [x] Run focused backend/Node tests; retain actual contract RED assertions.
- [x] Implement mission payload and pure page composition. Keep the accepted
      primary page for fitting normal legs. Repeat leg header, planned timing,
      relevant notice, table columns, compact legend/caveat, row range, and page
      numbering on continuations. Omit their map and full-flight timeline. Add
      explicit page breaks, none after the last page, and row break avoidance.
- [x] Implement largest-fitting contiguous row-prefix selection using real
      measurements at accepted fonts/column widths. Reserve continuation copy
      before measuring; verify the final combined document again after local
      counts are known. No arbitrary fixed row count, hidden overflow, row
      splitting, clipping, font reduction, or speculative extra page.
- [x] Add real-browser two-/three-page examples with long causes and remaining
      lists; print and verify every actual PDF row using Task 2. Check exact
      page geometry, no blank page, no overlapping essential labels, per-leg
      ceiling, five-leg budget, and visible continuation/page-range copy.
- [x] Exercise midnight and DST fold ranges, colliding/subminute boundaries,
      changing unknown state without outage, nested brief total outage,
      restriction-only rows, short-flight SOF overlap, full AR plus outages,
      adjusted departure/splice, and long quiet legs. Assert exact canonical
      mappings and printed clock precision at each page boundary.
- [x] Reject a timeline that remains unreadable at the accepted full-flight
      scale; preserve a reproducer and request a separate timeline-panel design
      if representative required inputs expose that limitation.
- [x] Validate version-2 evidence covers all ordered legs, sources/intervals,
      exact clocks, page rows, map input reasons, verified PDF cells, artifact
      hashes, fit, and cleanup. Reject missing/duplicate rows or any wrong
      fingerprint/leg association. Retain version-1 schema tests. Public
      artifact references name only the delivered PDF and its hash. Preview/HTML
      hashes may record diagnostic identities without implying those files exist
      in the ZIP; remove their local paths from public reports.
- [x] Run focused semantic, composition, actual-PDF, and page-budget controls;
      commit `feat: paginate mission briefings at measured row boundaries`.

### Task 4: Render the whole mission under one owner and deadline

**Files:** Modify
`F/src/mission-export/{briefing-render,render-owner,map-stage,render-budget}.mjs`
and their corresponding test files. Add
`F/src/mission-export/briefing-pdf-stage.mjs` and `briefing-pdf-stage.test.mjs`
for bounded verifier-process ownership. Modify
`F/src/mission-export/briefing-render.browser-test.mjs`,
`B/app/mission/exporter/customer_pdf.py`,
`tools/acceptance/customer-briefing/html_pdf_generate.py`.

**Interfaces:**

```text
renderMissionBriefing({payload, outputRoot, assetRoot, ownershipPath,
                       budgetMs=60000, fault=null}) -> Promise<RenderReportV2>
verifyPdfInOwner({owner, budget, pdfPath, expectations}) -> Promise<dict>
```

`RenderReportV2` includes mission identity/fingerprint, page plan, per-page fit
and cell bounds, per-leg map results/input reasons, stage offsets/durations, one
launch/browser identity, hashes, actual-PDF row verification, cleanup, total
elapsed ms, safe error code, and final artifact names. Artifact paths are
relative; only successful fully qualified reports contain deliverables. Preserve
`renderBriefing` as a one-leg checkpoint wrapper with its v1 report.

- [x] Write `one mission one launch`, `same budget object all legs`,
      `map cutoff skips later legs`, `print and verify share remaining time`,
      `teardown charged once`, `late acquired context closed`, and
      `cancel during pagination closes owner`. Advance a controlled clock
      through multiple legs and prove none receives another 60 seconds.
- [x] Add map tests for dateline/polar routes, invalid timed input, failed
      texture/readiness, and multi-view framing. Never silently select the first
      view of a route that needs more: reclaim the map card and retain exact
      input/stage/framing reasons. Successful maps remain endpoint-only as
      accepted; no new event markers or map-only continuation pages.
- [x] Run unit tests for RED; implement orchestration with one render-budget
      object, browser, and scoped listener. Render maps in leg order, close each
      fresh map context eagerly, and stop maps when the shared reserve is
      reached. Missing maps do not discard known transport risks.
- [x] Use a fresh document context for measurement/final assembly. Await
      font/image/composition readiness, remeasure every page, screenshot page
      elements, and print the assembled mission PDF once. No PDF merge library,
      separate browser per leg, sleeps, or external resource fetch.
- [x] Invoke Task 2's production verifier CLI with the remaining work allowance.
      Register its PID/PGID before waiting; reap it on timeout/signal/failure.
      Validate all rows/fonts/dimensions before closing owner. All work and
      teardown still finish within 60,000 ms; actual-PDF inspection has no
      independent allowance that extends the render.
- [x] Add real processes for slow fifth-leg map, hung measurement/print/
      verification, failed startup/fonts/assets, signal during each stage, owner
      cleanup failure, and late child/context acquisition. Assert no optional
      artifacts on failure and no owned process/listener survives.
- [x] Run three cold representative five-leg renders in a clean exact-SHA image.
      Require intended useful maps for the primary representative control, five
      pages for normal legs, one browser, verified all-row PDF, and recorded
      timing margin. Compare text, exact SVG geometry, page assignments, decoded
      preview pixels, and normalized PDF structure. Keep fallback controls
      distinct.
- [x] If cold runs exceed the deadline, stop qualification and revise the
      design. Do not increase the budget or claim the emergency wall limit
      qualified success.
- [x] Commit `feat: render multi-leg briefs under one bounded browser owner`.

## Pagination-stage handoff

Return actual dense/two-/three-page and five-leg PDFs, print previews,
color/grayscale rasters, paired evidence, every-row verification, cold timing,
determinism, and cleanup audits. Customer review must cover continuation
readability and the scan task on representative legs.

Keep visual acceptance pending until the user accepts these new examples.
Production wiring can follow its approved plan, but production acceptance and
merge cannot claim readable pagination before that gate passes.
