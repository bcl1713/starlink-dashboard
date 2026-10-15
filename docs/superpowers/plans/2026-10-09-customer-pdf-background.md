# Customer PDF Background Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement inline.

**Goal:** Prepare current customer PDF pages after saves and assemble fast
mission downloads without PowerPoint files.

**Architecture:** A durable per-leg SQLite store and single elected coordinator
own cancellable renderer processes. Export reads consistent cached snapshots and
PDFs, merges pages and evidence, and generates only lightweight data and CSVs.

**Tech Stack:** Python, SQLite, filelock, pypdf, existing Node/Chromium
renderer.

**Spec:** `docs/superpowers/specs/2026-10-09-customer-pdf-background-design.md`

## Global Constraints

- Work only in the feature worktree based on origin/dev; submit a PR to dev.
- Use existing renderer qualification, process ownership, and safe warning
  codes.
- Saves do not wait for rendering; superseded results never publish.
- Mission ZIPs contain no PPTX files, including with PDFs explicitly disabled.
- Checks have wall-clock limits; stop and verify every owned runtime resource.

## Review Focus

- A save while publication races must prevent obsolete results becoming current.
- Changes to another leg must preserve unrelated ready pages.
- Route, POI, and renderer changes must invalidate affected cached content.
- Restart and multiple API processes must not duplicate active rendering.
- Export evidence must describe the exact merged PDF and ordered saved snapshot.

## Tasks

1. Add failing tests for default enablement and data/CSV-only ZIPs; remove
   package PPTX generation and update export copy. Run focused package checks.
2. Add tests for cache supersession, restart, deletion, input identity, and
   atomic publication. Implement `slide_cache` identity, serialization, and
   SQLite store. Separate `prepare_export_snapshot` from input capture.
3. Add worker cancellation and coordinator ownership tests. Implement durable
   reconciliation, owned child preparation, save invalidation, and app
   lifecycle.
4. Add PDF merge/evidence and ready-export tests. Implement cached export
   snapshot retrieval, ordered PDF/evidence assembly, and existing omission
   isolation.
5. Clip the circular logo in CSS. Run backend/frontend checks and isolated
   production-image/browser acceptance, record timings and cleanup, then review,
   commit, push, and open the PR against dev.

## Progress

- Design reflects the user's clarification: customer PDF only, remove PPTX from
  mission downloads. Existing per-leg export API remains compatible.
- Implementation, targeted regression checks, and independent code review are
  complete. Review fixes cover optional-cache failure isolation, prepared-input
  retention, persisted POI consistency, and renderer revision invalidation.
- Full backend suite: 2,482 passed and 20 skipped. Full frontend suite: 1,367
  passed; production frontend build passed. Acceptance contracts: 45 passed.
- Production-image acceptance measures ready export latency against full
  rendering and checks superseding saves, artifact reuse, restart persistence,
  actual PDF geometry/fonts/raster output, browser download, and scoped cleanup.
