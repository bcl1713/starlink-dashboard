# Customer PDF production acceptance plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans. This
> is Task 6 of the [implementation plan](2026-10-14-customer-pdf-size.md).

**Goal:** Qualify the PDF fixes through real production exports and every-page
screen/print comparisons.

**Architecture:** Extend the existing owned acceptance runners and supported
source fixtures. Inspect delivered PDFs independently of renderer success
reports and preserve private original/candidate evidence.

**Tech Stack:** Python 3.11, pypdf, Pillow, Poppler, Docker, and Playwright.

**Spec:** [Approved design](../specs/2026-10-14-customer-pdf-size-design.md).

## Global constraints

All [main-plan constraints](2026-10-14-customer-pdf-size.md#global-constraints)
apply, including advisory file size, private inputs, production paths, explicit
wall-clock limits, and task ownership with verified cleanup.

## Review focus

Exercise the main plan's five review cases in delivered artifacts. Distinguish
zero-error lossless assembly from visual changes caused by resized rasters and
vector hatching; Brian approves the latter. Retained fixture inputs must cover
independent leg preparation, not just pages rendered in one browser document.

## Task 6: Production regression and visual acceptance

**Files:** Create
`backend/starlink-location/tests/fixtures/customer_briefing/mission-pdf-resources.json`.
Extend `backend/starlink-location/tests/unit/customer_briefing_fixtures.py`,
`tools/acceptance/customer-briefing/production_seed.py`,
`production_pdf_probe.py`, `production_controls.py`, and Task 4's inspector.
Modify `tools/acceptance/itinerary-planning/map_pixels.py` and
`export_probes.py` where fixed image dimensions are assumed. Extend
`tools/tests/test_customer_briefing_production.py`; add
`tools/acceptance/customer-briefing/pdf_compare.py` for Poppler/Pillow
comparisons.

**Interfaces:** Fixture name `mission-pdf-resources`: three independently
prepared legs, five pages, many unavailable intervals, three distinct maps.
Comparison CLI:
`pdf_compare.py BASELINE CANDIDATE --output DIR --dpi 72 --dpi 300`; write page
geometry/text equality, pixel differences, and comparison images.

- [ ] **Write probe tests first.** Feed inspectors baseline oversized/duplicated
      resources and assert rejection; then feed corrected assets and assert
      success. Assert five pages, one 263-pixel logo, three distinct maps at
      measured sizes, zero timeline background rasters, and measured reduction
      from baseline bytes. Do not assert `< 5_000_000`. Comparison tests reject
      missing pages or changed text and require zero pixel difference for
      lossless assembly controls.
- [ ] **Run red probe tests.** From repository root:

  ```sh
  timeout --kill-after=10s 10m uv run --python 3.11 --with-requirements backend/starlink-location/requirements.txt pytest tools/tests/test_customer_briefing_production.py tools/tests/test_customer_pdf_resources.py -q
  ```

  Expect failure for absent inspector/comparison behavior, not runtime setup.

- [ ] **Implement production fixture/probe wiring and run green tests.**
      Register `mission-pdf-resources` in source seeding and production
      qualification; qualify its independent cached fragments and actual ZIP.
      Implement the inspector/comparison assertions above. Close comparison
      images and bound/reap Poppler processes on errors/signals. Rerun the red
      command; expect all probe tests to pass.

- [ ] **Commit and run required checks on the candidate.** Run changed-file
      Python/JS lint, backend contract tests from Tasks 1/4/5, frontend unit
      tests, renderer MJS tests and production map build. Commit before
      acceptance; record full candidate SHA and applicable CI results. No
      dirty-tree qualification.
- [ ] **Run production and private itinerary controls.** Use the commands and
      input/evidence options in
      [production acceptance](../../development/customer-briefing-acceptance.md).
      `run-production.sh` already wraps its run with a 120-minute wall-clock
      limit; itinerary `run.sh` uses 30 minutes. Use projects
      `issue327-SHA12-offline-1` and `issue327-SHA12-online-1`, distinct free
      loopback ports and evidence directories. Keep the configured Docker
      endpoint, production Dockerfiles/Nginx, immutable inputs, original
      authorization boundaries, and scoped enablement. Verify the bundled
      helper/PNG without checkout files and with a development bind mount.
- [ ] **Review and hand back evidence.** Record actual PDF/ZIP bytes, page
      counts, all nested images/duplicate groups, text/row validation, map
      dimensions/hash, and import/package results. Compare every page at 72 and
      300 DPI. Compare identical corrected fragments with/without deduplication
      for zero pixel error; separately compare baseline/corrected renderers for
      readability. Obtain Brian's approval of resized logo/maps and vector
      hatching. Verify all owned processes, listeners, containers, networks, and
      disposable volumes are gone. Retain private evidence and the open
      implementation PR; merge/close issue327 only after the required checks and
      visual approval. Missing private inputs blocks final acceptance, not
      independent synthetic work.
