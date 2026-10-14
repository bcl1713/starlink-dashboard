# Customer PDF rendering and asset reuse implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task by task. Steps use checkboxes for tracking.

**Goal:** Remove repeated timeline rasters and assembled assets, and size maps
and the logo for their printed placements while preserving customer readability.

**Architecture:** Correct background asset production and deduplicate reusable
resources during cached-leg assembly. Hash final PDF bytes; retain preparation,
evidence, and export contracts.

**Tech Stack:** Node, Playwright/Chromium, SVG, TypeScript/Three.js, Python
3.11, Pillow, pypdf `>=6.0,<7`, and Poppler. Retain existing dependencies.

**Spec:** [Approved design](../specs/2026-10-14-customer-pdf-size-design.md).

## Global constraints

- Use 300 raster pixels per printed inch and `ceil(css_dimension * 300 / 96)`;
  logo placement is 84 by 84 CSS pixels.
- Preserve 960 by 540 point pages, searchable text, timing, warnings, route
  labels, circular logo clipping, and current page/row assignments.
- About 5 MB is advisory. Do not add a universal byte cap, size omission rule,
  JPEG tuning, whole-page rasterization, or ZIP compression changes.
- Preserve evidence schemas, fragment hashes, final PDF provenance,
  cancellation, cache invalidation, and browser-free assembly of ready exports.
- Work in a separate implementation worktree based on current `origin/dev`;
  carry these approved documents through the documentation PR or an explicit
  documentation dependency. Keep the primary checkout on `dev`.
- Record ownership before runtime launch; wrap every test in an explicit
  wall-clock timeout with forced termination grace. Tear down owned resources
  after checks, preserve evidence, and retain open-PR worktrees.
- Before changes, retain a baseline render/export for the sanitized fixture and
  locate the private fixture/evidence recorded in issue327. Keep inputs
  immutable.

## Review focus

- Tiny/fractional map cards: valid placements must survive rounding and viewport
  validation without losing a previously supported route (Task 2).
- Repeated leg/page SVG IDs: unavailable hatching must stay in its own interval,
  including near-zero spans, unknown states, and quiet gaps (Task 3).
- Equal image bytes with unequal masks/color spaces: reuse must preserve image
  semantics, and independently referenced equal profiles must deduplicate (4).
- A ready ZIP captured under the old renderer: changing assets/policy must
  prevent its reuse for a new export; unchanged inputs reuse ready work (Task
  5).
- Production asset paths: an image built without the checkout and a development
  bind mount must both use the resized PNG and include the sizing helper (1, 6).

## Task 1: Shared raster policy and logo derivative

**Files:** Create
`frontend/mission-planner/src/mission-export/raster-policy.mjs` and
`raster-policy.test.mjs`; create
`backend/starlink-location/scripts/resize-briefing-logo.py` and
`app/mission/assets/apo-patch-briefing.png` under that backend directory. Modify
`briefing-render.mjs`, `briefing-mission-layout.mjs`, the backend `Dockerfile`,
and `tools/acceptance/customer-briefing/Dockerfile.html-pdf-checkpoint`. Test in
`backend/starlink-location/tests/unit/test_customer_brand_asset.py`.

**Interfaces:** Export `PRINT_RASTER_PPI = 300` and
`rasterSizeForPlacement({width, height}) -> {width, height}` in the new MJS
module. Require finite positive CSS dimensions and return independently rounded
integer pixel dimensions. The Python utility exposes
`resize_logo(source: Path, output: Path, size: int) -> None` and CLI flags
`--source`, `--output`, `--size`; it runs during asset preparation, never
export.

- [ ] **Write failing policy and asset tests.** Pin these assertions:

  ```js
  const logo = rasterSizeForPlacement({ width: 84, height: 84 });
  const map = rasterSizeForPlacement({ width: 280, height: 270 });
  assert.deepEqual([logo.width, logo.height], [263, 263]);
  assert.deepEqual([map.width, map.height], [875, 844]);
  assert.throws(() => rasterSizeForPlacement({ width: NaN, height: 270 }));
  ```

  `test_logo_derivative_is_png_and_preserves_master` checks PNG/RGB, 263 by 263,
  unchanged master hash, matching color profile, and identical repeat output.

- [ ] **Run red tests.** Frontend, then backend:

  ```sh
  timeout --kill-after=10s 10m node --test src/mission-export/raster-policy.test.mjs
  timeout --kill-after=10s 10m uv run --with-requirements requirements.txt pytest tests/unit/test_customer_brand_asset.py -q
  ```

  Expect missing helper/asset failures, not dependency or environment failures.

- [ ] **Implement the policy and generate the derivative.** Use Pillow LANCZOS
      and fixed PNG encoding settings; preserve color profile and master bytes.
      Generate with `--size 263`. Both renderers load the derivative with
      `image/png` and hash its bytes. Update deployed asset paths and explicit
      Docker COPY lists for the derivative and `raster-policy.mjs`; retain the
      master.
- [ ] **Run green tests and renderer unit checks.** Expect the above tests and
      `briefing/document.test.mjs` and `mission-briefing-render.test.mjs` to
      pass. Production path and bind-mount verification remains Task 6.
- [ ] **Commit:** `fix: size the customer briefing logo for print`.

## Task 2: Maps sized from their final card

**Files:** Modify `briefing-mission-layout.mjs`, `map-stage.mjs`, `framing.ts`,
`protocol.ts`, and `scene.tsx` in `frontend/mission-planner/src/mission-export`.
Test in `briefing-mission-layout.test.mjs`, `framing.test.ts`,
`marker-labels.test.ts`, and `map-stage-budget.test.mjs` there.

**Interfaces:** Consume Task 1's `rasterSizeForPlacement`. Keep
`renderMapInContext({owner, budget, input, viewport, fault})` and its current
`viewport`, `pngHash`, marker/endpoint report fields. Export
`mapFrameInset(width: number): number` from `framing.ts` as `64 * width / 1920`,
preserving the accepted inset in display space.

- [ ] **Write failing placement, framing, and fallback tests.** Include
      `map_raster_tracks_final_pagination`, asserting 280 by 270 gives 875 by
      844; a later 280 by 270.1 measurement gives 875 by 845. Assert final
      viewport/hash report matches the accepted PNG. Pin scaled framing:

  ```ts
  expect(mapFrameInset(875) / 875).toBeCloseTo(mapFrameInset(1920) / 1920);
  expect(mapViewportSchema.parse({ width: 875, height: 250 }).height).toBe(250);
  ```

  Test missing-map reflow, no maps on continuation pages, all marker identities,
  and unchanged unknown/failure behavior. Reject zero/negative/nonfinite sizes.

- [ ] **Run red tests.** From frontend:

  ```sh
  timeout --kill-after=10s 10m node --test src/mission-export/briefing-mission-layout.test.mjs src/mission-export/map-stage-budget.test.mjs
  timeout --kill-after=10s 10m npm run test:unit -- src/mission-export/framing.test.ts src/mission-export/marker-labels.test.ts
  ```

- [ ] **Implement measured sizing.** Return CSS rectangles from page evaluation,
      then apply the shared helper outside the browser context. Keep DPR 1 for
      map screenshots and document DPR 2.5. Use integer viewport limits 1
      through 4096, preserving route/input validation. Replace fixed framing
      insets with the helper. Retain overlay display dimensions; make
      world-space width caps independent of raster sampling density, calibrated
      to their current 1920 reference. Re-render after a changed final
      measurement within the same budget.
- [ ] **Run green tests and build.** Expect both red commands to pass and run
      `timeout --kill-after=10s 15m npm run build:mission-export`. Rendered
      complete route, endpoints, label readability, and actual PNG dimensions
      are Task 6 gates.
- [ ] **Commit:** `fix: render customer maps at their printed resolution`.

## Task 3: Vector timeline hatching

**Files:** Modify
`frontend/mission-planner/src/mission-export/briefing/timeline.mjs` and
`document.mjs`; test `timeline.test.mjs` and `document.test.mjs` alongside them.

**Interfaces:** Extend `renderTimeline(payload, {idPrefix} = {}) -> string`.
Production composition supplies a prefix unique to leg and global page through
`composeBriefing`/`composeMissionPage`; old single-page callers retain a
default.

- [ ] **Write failing hatch geometry and ID tests.** Named tests
      `down_spans_use_clipped_vector_hatching` and
      `mission_timeline_clip_ids_are_unique` assert:

  ```js
  assert.doesNotMatch(svg, /<pattern|<image|fill="url\(#down\)"/);
  assert.match(svg, /<clipPath/);
  assert.equal(new Set(clipIds).size, clipIds.length);
  ```

  Parse rectangles to assert original exact x/width, background `#d2d8df`,
  stroke `#99a4b0`, 8-unit diagonal spacing and the original one-unit stroke.
  Cover subminute/tiny spans, three lanes, unknown/Up gaps, repeated pages, and
  existing posture/SOF/AR/DST assertions without inventing transport
  availability.

- [ ] **Run red tests.** From frontend:

  ```sh
  timeout --kill-after=10s 10m node --test src/mission-export/briefing/timeline.test.mjs src/mission-export/briefing/document.test.mjs
  ```

- [ ] **Implement clipped solid backgrounds and vector strokes.** Preserve
      global pattern phase: diagonal lines satisfy `x + y = 8 * k` in SVG
      coordinates. Bound line generation to each interval's clip bounds, escape
      IDs, and propagate unique page prefixes. Preserve labels, semantic
      attributes, and canonical data.
- [ ] **Run green tests.** Expect the red command to pass. Task 6 must prove no
      nested timeline background images appear in actual Chromium-generated
      PDFs.
- [ ] **Commit:** `fix: draw timeline hatching as clipped vector strokes`.

## Task 4: Deduplicate cached-leg PDF resources

**Files:** Create
`backend/starlink-location/app/mission/slide_cache/pdf_resources.py` and
`tests/unit/pdf_resource_fixtures.py` under that backend. Modify
`app/mission/slide_cache/assembly.py`; test in
`tests/unit/test_customer_pdf_assembly.py`. Create
`tools/acceptance/customer-briefing/pdf_resources.py` and
`tools/tests/test_customer_pdf_resources.py` for independent artifact
inspection.

**Interfaces:** Product helper:
`deduplicate_pdf_resources(writer: PdfWriter, *, cancel=None) -> None`. Fixture
helper: `make_pdf_fragments() -> tuple[ExportSnapshot, dict]`, returning three
independently serialized legs with five pages, equal logos/profiles, distinct
maps, and deliberately unequal mask/color-space controls. Inspection helper:
`image_inventory(pdf_bytes: bytes) -> list[dict]`; report reachable image object
IDs, dimensions, encoded bytes, and semantic grouping including resolved
color-space/decode/mask content, independent of object IDs.

- [ ] **Write failing assembly and inventory tests.** Inspect reachable nested
      Form XObjects, not just page resource dictionaries. Assertions include:

  ```python
  assert len(shared_logo_object_ids) == 1
  assert len(distinct_route_map_object_ids) == 3
  assert len(unequal_mask_or_color_space_object_ids) == 2
  assert sha256(result.artifacts.pdf).hexdigest() == final_evidence_hash
  ```

  Check five ordered pages, unchanged fragment hashes/text/evidence rebasing,
  lower bytes than the unoptimized fixture, orphan removal, and cancellation
  before/after a pass. The equal logo streams must reference separate ICC
  objects initially, reproducing the observed single-pass failure.

- [ ] **Run red tests.** Backend, then repository root:

  ```sh
  timeout --kill-after=10s 10m uv run --with-requirements requirements.txt pytest tests/unit/test_customer_pdf_assembly.py -q
  timeout --kill-after=10s 10m uv run --python 3.11 --with-requirements backend/starlink-location/requirements.txt pytest tools/tests/test_customer_pdf_resources.py -q
  ```

- [ ] **Implement bounded dependency deduplication.** Use the supported pypdf 6
      helper with orphan removal; repeat until the live object count stabilizes,
      bounded by the initial live object count plus one. Check cancellation
      between passes; fail safely if the bound is exhausted. Tests must prove
      resolved semantics and actual shared objects, not merely the helper's
      invocation count. Call before `writer.write`; hash the resulting PDF and
      keep fragment provenance.
- [ ] **Run green tests.** Expect both commands to pass. Task 6 compares the
      same corrected fragments assembled with/without deduplication at 72/300
      DPI, requiring identical pixels, text, dimensions, and page order.
- [ ] **Commit:** `fix: reuse identical assets across cached leg PDFs`.

## Task 5: Cache and package contracts

**Files:** Extend `backend/starlink-location/tests/unit/test_slide_cache.py`,
`test_export_preparation.py`, and `test_customer_export_job.py` in that
directory. Modify `app/mission/slide_cache/identity.py` only if the tests expose
missing coverage of the shipped policy/derivative; retain existing cache/job
interfaces.

**Interfaces:** Use `renderer_revision(refresh=False)` and
`ExportPreparationService.capture_revision()`, `start(mission_id)`,
`status(mission_id, job_id)`, and `open_download(mission_id, job_id)` unchanged.

- [ ] **Write invalidation and package regression tests.** Named tests
      `test_derivative_and_raster_policy_change_renderer_revision`,
      `test_renderer_revision_replaces_current_package`, and
      `test_ready_assembly_preserves_package_contract` assert:

  ```python
  assert revision_after_asset_change != revision_before
  assert updated_job.fingerprint != old_job.fingerprint
  assert unchanged_job.id == updated_job.id
  ```

  Reuse the deployed/local identity fixtures and elected-worker runtime context.
  Supersede pending old-revision jobs. A completed old snapshot remains
  explicitly downloadable, but cannot satisfy a new preparation with the current
  revision. Verify exact members, manifest version/statistics, evidence
  schema/hash, ZIP round-trip, unchanged compression methods, and no
  browser/maps on ready export.

- [ ] **Run tests.** From backend:

  ```sh
  timeout --kill-after=10s 10m uv run --with-requirements requirements.txt pytest tests/unit/test_slide_cache.py tests/unit/test_export_preparation.py tests/unit/test_customer_export_job.py -q
  ```

  Existing coverage may already pass; do not force product changes solely to get
  a red result. Document failures before any necessary identity fix.

- [ ] **Complete any required identity fix and rerun.** Expect all tests to pass
      and all fixture workers/streams to close. Keep schemas and package code
      intact.
- [ ] **Commit:** `test: guard PDF revision and package reuse contracts`.

## Task 6 and final acceptance

Complete
[production regression and visual acceptance](2026-10-14-customer-pdf-size-acceptance.md)
after Tasks 1 through 5. The companion is part of this implementation plan and
includes the required fixture, artifact checks, production controls, and
teardown.
