# Customer Briefing Production Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> or superpowers:subagent-driven-development to implement this plan
> task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Deliver readable mission PDFs and complete evidence as a default-off
addition to real legacy export ZIPs, with production-path acceptance.

**Architecture:** First strengthen actual-PDF and diagnostic evidence. Then
extend the accepted one-page renderer with measured row continuation and one
mission browser/deadline. Finally integrate captured legacy exports, atomic
optional publication, production packaging, and persistent UI feedback.

**Tech Stack:** Python 3.11, pytest, Node 22.22.2, locked Playwright
1.63.0/Chromium, HTML/CSS/SVG, bundled DejaVu Sans, Poppler, React/TypeScript,
Docker/Nginx, existing ZIP/PPTX builders.

**Spec:**
[Production completion design](../specs/2026-10-08-customer-briefing-production-design.md)
and
[governing HTML-to-PDF design](../specs/2026-10-08-customer-briefing-html-pdf-design.md).
The user approved this design and all three plan files for native execution on
2026-10-08. Approval authorizes implementation; broader acceptance remains
gated.

## Execution status — 2026-10-09

Tasks 1–7 are implemented and independently reviewed in PR #314. Production
qualification combines the complete PDF/browser/lifecycle/fault case receipts at
`960ae0ba` with final actual ZIP imports at `aa64cc9f`. Application/runtime
sources, resolved dependencies/base images and installed assets match. A
redundant full rerun was stopped at the user’s request. The baseline runner’s
raw timestamp-encoding comparison failure is retained; it is not an application
import defect. No new-head full-matrix pass is claimed.

[Review samples and provenance](../../samples/customer-briefing/production/README.md)
record the three new PDFs and actual omitted-download feedback. Runtime
resources are removed and evidence is preserved outside the worktree. Task 8
remains open for explicit customer acceptance and final PR integration. Default
stays off.

## Global constraints

- Planning branch: `docs/customer-briefing-production-plan`, worktree
  `.worktrees/customer-briefing-production-plan`, fresh `origin/dev` at
  `f1ee64f42faa9f7a2f02a80d5f22dd324d459902`. That checkpoint changed docs only.
  Approved implementation uses `feat/customer-briefing-production` in
  `.worktrees/customer-briefing-production` from the same fresh base.
- Implementation starts only after explicit plan/design approval and execution
  selection, in its own feature worktree from newly fetched `origin/dev`.
- Preserve `customer-mission-briefing-phase-one` and its files/resources. Do not
  merge or edit that worktree. PR #312 is a completed checkpoint.
- Preserve accepted sample content and removed definitive posture callouts;
  incomplete-X confirmed-capability labels remain. Acceptance covers two
  synthetic examples only; private historical pending flags are superseded.
- Fixed 13.333333×7.5 inch print pages: zero margins, scale 1, backgrounds on,
  no browser headers/footers; CSS page 1280×720, preview 3200×1800.
- Retain accepted 30/20/17/14/10 pt title/timing/lane/table/footer scale and
  bundled regular/bold DejaVu Sans. Never shrink, truncate, clip, or omit risks.
- Normal leg one page, dense leg up to two, pathological leg at most three;
  representative five-leg mission fewer than fifteen, five when all fit.
- One request-owned browser and 60,000 ms monotonic rendering deadline for all
  legs/pages/stages, including PDF verification and teardown; 20,000 ms PDF
  reserve and 3,000 ms cleanup reserve. No per-leg reset or budget increase.
- Exact UTC geometry and evidence; ET primary, exact Zulu/T-plus retained.
  Unknown is neither Up nor Down. SOF/AR never independently lowers Up counts.
- Default-off/additive: preserve legacy files/import behavior and API download
  filename. No promotion, legacy replacement, shared configuration edits,
  external service, persistent browser, or background rendering worker.
- Actual PDF row verification and retained map-input reasons precede broader
  acceptance. DOM inspection alone is insufficient.
- Record ownership before launching temporary resources; wall limits with forced
  termination grace; teardown before handoff, including failed checks.

## Review focus

1. Repeated identical cell text can conceal an omitted row: match all four cells
   by page-local bounds, order, and multiplicity (Task 2).
2. Wrapped text, midnight/DST, and subminute windows can cross page boundaries:
   no split row or changed timing/uncertainty semantics (Tasks 3–4).
3. Legacy builders can reread parent metadata, ground-entry data, or timelines
   after capture: poison all live reads and compare complete output (Task 5).
4. Five legs, late map acquisition, disconnects, and concurrent requests can
   exceed one owner/deadline or leak descendants (Tasks 4, 6, 8).
5. PDF/evidence/ZIP insertion failure can publish half a pair or erase download
   feedback: inject each boundary and inspect ZIP/manifest/UI (Tasks 6–8).

## Sequencing and verification conventions

Tasks 1–2 are evidence prerequisites. Tasks 3–4 are the pagination/runtime stage
defined in the
[pagination companion](2026-10-08-customer-briefing-production-pagination.md).
Tasks 5–8 are the production stage defined in the
[integration companion](2026-10-08-customer-briefing-production-integration.md).
Read all three plan files and both specs before execution. Each stage can be a
separate PR against `dev`; preserve dependencies and use fresh worktrees.

`B` means `backend/starlink-location`; `F` means `frontend/mission-planner`;
other paths are repository-relative. Install dependencies only when
implementation is approved. Use:

| Check                 | Working directory | Command                                                                                                                                     |
| --------------------- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Backend selection     | B                 | `timeout --kill-after=10s 10m uv run --python 3.11 --with-requirements requirements-dev.txt pytest <selection> -q`                          |
| Node selection        | F                 | `timeout --kill-after=10s 10m node --test <selection>`                                                                                      |
| Frontend selection    | F                 | `timeout --kill-after=10s 10m npm run test:unit -- <selection>`                                                                             |
| Tools selection       | Root              | `timeout --kill-after=10s 10m uv run --python 3.11 --with pytest --with psutil pytest <selection> -q`                                       |
| Full gates            | Root              | `timeout --kill-after=10s 30m ./tools/verify <static\|backend\|frontend>`                                                                   |
| Fresh image builds    | Root              | `timeout --kill-after=10s 45m <recorded exact-SHA build>`                                                                                   |
| Production acceptance | Root              | `timeout --kill-after=10s 30m tools/acceptance/customer-briefing/run-production.sh --candidate-sha <full-sha> --evidence-root <owned-path>` |

Import/setup failures are not meaningful RED evidence. Record failed assertions,
implement minimally, rerun the owning selection, commit passing changes, and
broaden only for changed interfaces or unresolved concerns. If a wall guard
fires, verify the old owned process tree is gone before retry. Use the actor's
configured Docker daemon; never clear its context/DOCKER_HOST.

### Task 1: Retain map diagnostics and canonical display cells

**Files:** Modify `B/app/mission/exporter/customer_document.py`,
`customer_evidence.py`, `F/src/mission-export/briefing/document.mjs`, and
`tools/acceptance/customer-briefing/html_pdf_generate.py`. Create
`B/app/mission/exporter/customer_display.py`. Tests:
`B/tests/unit/test_customer_document.py`, `test_customer_evidence.py`,
`test_customer_display.py`, `F/src/mission-export/briefing/document.test.mjs`.

**Interfaces:** Preserve
`build_customer_document(snapshot, view, trial) -> dict` and
`build_map_input(leg, trial) -> tuple[dict | None, tuple[str, ...]]`. Add pure
`display_row(row: dict) -> tuple[str, str, str, str]` in `customer_display.py`:
ET, impact, remaining, posture, in column order. Version-1 payloads gain
additive `mapInputDiagnostics: list[str]` and row `displayCells: list[str]`.
Evidence records diagnostics separately from map render status/warnings; no
source diagnostic enters visible HTML.

- [x] Write `test_map_input_diagnostics_survive_document_and_evidence`: missing,
      malformed, timing-mismatched, and marker-density inputs retain exact
      returned reasons even if runtime map failure adds another warning. Assert
      success reasons are also retained and input is not mutated.
- [x] Write `test_display_cells_preserve_accepted_customer_copy`: exact existing
      Ka/X-Band shortening, comma-separated remaining transports, Elevated
      risk/Unavailable/Incomplete table wording, ET punctuation, approximation
      marks, midnight dates, DST offsets, and second precision. Test escaped
      HTML separately; display values remain plain strings.
- [x] Run named backend/Node tests and save contract assertion failures.
- [x] Keep both map-builder results. Move existing table-only copy transforms to
      `display_row` (use exact accepted `Elevated risk` spelling). The composer
      renders supplied cells as escaped text, with its current transformation
      fallback for historical version-1 payloads.
- [x] Require four display cells per generated row; validate row identity and
      canonical mappings independently of formatting. Thread diagnostics into
      evidence and checkpoint reports without recapturing/rebuilding map data.
- [x] Run scoped checks and inspect generated display payloads for both accepted
      fixtures; no new visible words or definitive timeline callouts.
- [x] Commit: `feat: retain briefing map diagnostics and display contracts`.

### Task 2: Verify every delivered PDF row

**Files:** Create `B/app/mission/exporter/customer_pdf.py` and
`B/tests/unit/test_customer_pdf.py`. Modify
`F/src/mission-export/briefing-render.mjs`, `briefing/document.mjs`,
`briefing-render.browser-test.mjs`,
`B/app/mission/exporter/customer_evidence.py`, and
`tools/acceptance/customer-briefing/{html_pdf_inspect,html_pdf_generate}.py`.
Tests: `B/tests/unit/test_customer_evidence.py`,
`tools/tests/test_customer_briefing_html_pdf_checkpoint.py`.

**Interfaces:** Production-safe verifier:

```text
verify_customer_pdf(pdf_path: Path, expectations: dict, *,
                    timeout_seconds: float) -> dict
```

`expectations` version 1 contains page count/size, ordered page assignments,
per-page `tableBodyBoundsPt`, and per-row
`legId,rowId,page,displayCells,cellBoundsPt`. The browser records four measured
cell rectangles per row, relative to that page, converted to pt. Verifier output
contains `verified,pageCount,pageSizePt,rows,fonts`; each row has assigned page,
matched cells, order, and in-bounds result. Use Poppler `pdfinfo`, `pdffonts`,
and `pdftotext -bbox-layout` with a shared caller's remaining time, not a fresh
timeout for each subprocess. The verifier owns/reaps its subprocesses. CLI JSON
input/output exposes the same contract for the Node coordinator; the production
image runs it with application code.

- [x] Write failures for missing, duplicate, reordered, wrong-page, wrong-cell,
      wrapped, split, and off-page rows; repeated SOF/transport text must not
      satisfy another row. Reject a wrong remaining transport or time even when
      selected phrases elsewhere match. Assert NFC/whitespace normalization
      preserves meaningful punctuation, dates, signs, offsets, and seconds.
- [x] Run focused verifier/evidence tests for RED. Unit fixtures for Poppler
      output prove parsing only; add actual PDF mutations in the browser suite.
- [x] Measure stable `[data-row-id]` and cell selectors in print layout. Extract
      PDF words within each expected cell with a 0.75 pt edge tolerance;
      reconstruct wrapped lines in geometric reading order. Reject ambiguous
      cross-cell allocation, unmatched expected words, and unmatched words
      within the measured table-body region (including extra table rows). Check
      intended embedded fonts and every page's exact geometry.
- [x] Make evidence qualification require complete `pdfValidation.rows` matching
      expected IDs/order/cells. Preserve existing artifact hash, snapshot,
      geometry, cleanup, and deadline checks.
- [x] Run real-process PDFs with a middle row removed, same text duplicated,
      swapped rows, changed remaining transport, a wrapped cell, and split row.
      A real bad PDF must fail even if DOM fit/report claims all IDs are
      present.
- [x] Requalify both accepted examples with all-row verification, intended map
      success, color/grayscale inspection, and unchanged customer composition.
      Do not reinterpret this as dense/multi-leg or production acceptance.
- [x] Commit: `feat: qualify every coordination row in delivered PDFs`.

## Approval and execution handoff

Recommended approach: native execution, with a fresh whole-branch review at each
stage. The payload, page-plan, deadline, and package interfaces are tightly
coupled; maintain one implementer's context while independently reviewing
completed stages. Subagent-driven execution is available if selected.

User approval explicitly preceded Tasks 1–8. Approval is not evidence that the
feature is implemented or production-accepted; Task 8 retains those gates.

Self-review: both prerequisites have dedicated tasks; pagination, versioned
evidence, single-owner lifecycle, immutable legacy reads, ZIP atomicity, API/UI
warnings, image build contracts, and production acceptance are covered in Tasks
3–8. All five review-focus risks have named test cycles. Remaining visual
acceptance and deployment decisions are explicit gates.
