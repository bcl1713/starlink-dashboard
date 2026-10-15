# Customer Briefing HTML-to-PDF Runtime Task

Required Task 3 companion to the
[checkpoint plan](2026-10-08-customer-briefing-html-pdf-checkpoint.md). All its
Global Constraints and execution gates apply. This document describes future
implementation, not a completed runtime or measured performance claim.

## Task 3: One request-owned renderer and shared deadline

**Files:** Reuse `F/mission-export.html`, `F/vite.mission-export.config.ts`,
`F/src/mission-export/{main.tsx,scene.tsx,protocol.ts,framing.ts,framing.test.ts}`.
Create
`F/src/mission-export/{map-stage,briefing-render,render-budget,render-owner}.mjs`
and corresponding `.test.mjs` files. Create
`F/src/mission-export/briefing-render.browser-test.mjs` for real-process checks.
Create `B/app/mission/exporter/map_inputs.py` and
`B/tests/unit/test_map_inputs.py`; modify `customer_document.py` to populate its
map input. Modify only the `build:mission-export` script in `F/package.json` and
ignore `F/dist-mission-export` in root `.gitignore`; preserve dependency lock
versions. Create
`tools/acceptance/customer-briefing/Dockerfile.html-pdf-checkpoint` and its
`.dockerignore`. No production Dockerfile/Compose edits.

**Interfaces:** Extract retained

```text
build_map_input(snapshot_leg: LegSnapshot, trial_leg: TrialLeg) -> tuple[dict | None, tuple[str, ...]]
```

and its pure route interpolation helpers from `trial_maps.py` into
`map_inputs.py`; do not copy the old process/deadline/static renderer.
`mapInput` holds the first tuple value; record the second in evidence, never
customer diagnostics.

```text
createRenderBudget({budgetMs=60000, clock=performance.now, pdfReserveMs=20000, cleanupReserveMs=3000}) -> RenderBudget
```

Captures start once. Methods: `remainingMs()`, `workRemainingMs()` (excluding
cleanup reserve), `mapRemainingMs()` (excluding PDF reserve), and `elapsedMs()`;
nonpositive work allowances raise `RenderDeadlineError`. Store `startedAt` and
`deadlineAt` on the same monotonic clock. All stages receive this object; none
creates a timer budget. Test-only shorter budgets scale reserves explicitly,
never production.

`openRenderOwner({assetRoot,outputRoot,ownershipPath,budget}) -> Promise<RenderOwner>`
starts one scoped listener and browser, recording ownership before launch. Owner
exposes `browser`, `origin`, `newContext(options)`, and `close()`; tracks
pages/contexts, browser PID/PGID, listener, and temporary paths. Its `close()`
eagerly closes contexts, browser, and listener, reaps owned descendants, removes
runtime temp files, and returns verified cleanup results.

`renderMapInContext({owner,budget,input}) -> Promise<MapStageResult>` renders
all planned scene views with existing readiness/digest/framing checks and closes
its context in `finally`; never launches a browser. Result fields: `status`
(`primary` or `unavailable`), `pngs` (data URLs), `viewIds`, `warnings`,
`framing`, `markers`. Checkpoint routes require one complete fitting view. A
multi-view route cannot silently lose views; fail this bounded checkpoint.

```text
renderBriefing({payload,outputRoot,assetRoot,ownershipPath, budgetMs=60000,fault=null}) -> Promise<RenderReport>
```

Starts the one budget at entry before validation/launch/composition, calls map
stage then Task 2 composer, loads a fresh document context, measures fit,
screenshots print styling, prints PDF, and closes owner before successful
return. CLI:
`node src/mission-export/briefing-render.mjs <payload.json> <output-dir> <asset-root>`.
Reject output paths outside the request directory; do not retain runtime
servers.

`RenderReport` fields: `schemaVersion=1`, `status` (`success` or `failed`),
`legId`, `snapshotFingerprint`, `sharedBrowser`, `launchCount`,
`browserIdentity`, `assetHashes`, `map`, `fit`, `stages`, `totalMs`, `cleanup`,
`errorCode`, and `artifacts` (`htmlPath,pngPath,pdfPath`; null on failure).
`stages` records `startup,map,html,pdf,teardown` with start/duration offsets
from the single request clock; composition/preview costs belong to `html`. `fit`
records page geometry/count, visible row IDs, loaded fonts, label/marker bounds,
and overflow findings. No success with incomplete cleanup or `totalMs>60000`.

- [ ] Write `test_map_input_preserves_exact_outage_markers_and_dateline` in
      `test_map_inputs.py`; assert exact timed interpolation and captured route
      immutability. Run the named test expecting missing-contract assertions.
- [ ] Extract only pure map inputs/helpers and adapt the retained pure tests.
      Reuse scene/protocol/framing and dedicated Vite entry from `575730a8`;
      inspect imports against current overview modules. Add the build script;
      run backend map-input tests,
      `npm run test:unit -- src/mission-export/framing.test.ts`, and
      `timeout --kill-after=10s 10m npm run build:mission-export`.
- [ ] Write budget tests with a controlled monotonic clock:

  ```js
  let now = 0;
  const budget = createRenderBudget({ clock: () => now });
  now = 10000;
  assert.equal(budget.mapRemainingMs(), 30000);
  now = 39000;
  assert.equal(budget.mapRemainingMs(), 1000);
  now = 40000;
  assert.throws(() => budget.mapRemainingMs(), RenderDeadlineError);
  assert.equal(budget.workRemainingMs(), 17000);
  now = 60000;
  assert.throws(() => budget.remainingMs(), RenderDeadlineError);
  ```

  Add `budget passed unchanged to every stage` and `teardown consumes budget`.
  Run Node tests and save RED failures before implementing budget methods.

- [ ] Write owner/map/coordinator tests: `one launch two isolated contexts`,
      `map cutoff preserves PDF reserve`, `map failure reclaims card`,
      `startup and font failures omit artifacts`,
      `print rejection cleans owner`,
      `SIGTERM closes contexts and reaps browser`, and
      `cleanup failure forbids success`. Assert launch count 1, distinct
      contexts, same budget object, all close/reap calls, and empty deliverable
      paths on failures. Failures must be injected at the named boundary, not by
      missing dependencies.
- [ ] Implement owner/map/coordinator modules. Use one deadline watchdog, begin
      abort/cleanup at deadline minus 3000 ms, and prohibit starting maps after
      the 20000 ms PDF reserve boundary. If maps fail/cut off, close their
      context and reclaim map space; primary checkpoint qualification later
      rejects this fallback. Use the remaining allowance for every
      wait/launch/screenshot; bound PDF calls without letting abandoned work
      survive browser teardown.
- [ ] Bundle map PNG, APO patch, DejaVu regular/bold, and CSS as data/inline
      assets in final HTML. Await `document.fonts.ready`, both intended font
      faces, image decode, and explicit composition readiness. Block remote
      requests; serve only the owned asset root and reject traversal.
- [ ] Inspect every `[data-fit]` element using real bounding/scroll dimensions;
      require exact single-page geometry, all required rows visible, no off-page
      essential text, and no row splitting. Check SVG labels/callouts separately
      from true bar bounds; a five-minute red interval must retain width
      `5/480`. An oversized title/table fails; never hide it with overflow
      clipping.
- [ ] Print with

  ```js
  page.pdf({
    width: "13.333333in",
    height: "7.5in",
    scale: 1,
    margin: { top: "0", right: "0", bottom: "0", left: "0" },
    printBackground: true,
    displayHeaderFooter: false,
    preferCSSPageSize: true,
  });
  ```

  Record fit and output identities. Use a fresh document context per request,
  print media, fixed 1280×720 viewport and pixel ratio 2.5 for a 3200×1800
  page-element PNG preview. This matches the CSS-inch page at 96 px/inch;
  screenshot `.briefing-page` rather than including viewport margins.

- [ ] Define the dedicated image using Node 22.22.2 trixie and Python 3.11
      trixie stages adapted from the retained feasibility image. Install locked
      Playwright 1.63.0 browser/OS requirements, DejaVu Sans, and Poppler.
      Package Python app/tests, map entry, composer/CSS, APO patch, and required
      local globe textures. Use non-root UID 1000 and revision label
      `ACCEPTANCE_CANDIDATE_SHA`; hash browser, fonts, assets, lockfile, OS
      package inventory, and image ID into the runtime manifest. Do not install
      LibreOffice.
- [ ] Run scoped backend/Node/framing checks and map-entry build; commit
      `feat: render HTML briefing with one bounded Chromium owner` before the
      exact-SHA image build. Fixes require a new clean candidate and rerun.
- [ ] Build from repository root under the 45-minute wall limit using
      `-f tools/acceptance/customer-briefing/Dockerfile.html-pdf-checkpoint`,
      `--build-arg ACCEPTANCE_CANDIDATE_SHA=<full-sha>`, and task-owned tag
      `starlink-dashboard-briefing-html-pdf:<sha-first-12>-<run-id>`. Record
      image/ownership identities; preserve configured proxy and CA trust.
- [ ] Run the real-browser cases in a scoped disposable
      `docker run --rm --name briefing-html-pdf-runtime-<run-id>` executing
      `node --test src/mission-export/briefing-render.browser-test.mjs`: print
      dimensions/fit, font identities, narrow red callout, long-title/table
      overflow, missing font/image, unknown X, remote URL/traversal rejection,
      hung map/print, SIGTERM, and cleanup failure. Generate payloads with Task
      1 fixture helpers and Task 2 Python serializer inside the image before
      rendering. Record/remove/audit the owned container on every exit. Unit
      mocks prove orchestration only; real processes prove lifecycle/fit. Task 4
      later invokes this same module via `--runtime-tests`.

## Runtime ownership and acceptance limits

Read workspace cloud-Docker guidance and discover the actor's configured socket
without clearing `DOCKER_HOST`/context. Builds use a 45-minute wall limit with
10-second termination grace. Browser checks use an outer 10-minute wall limit;
individual failed renderer subprocesses have a 70-second emergency wall limit
and 10-second kill grace. These guards cannot grant stages new rendering budgets
or qualify a render that exceeds its single 60-second deadline.

Successful map/PDF contexts are separate and closed eagerly; browser/listener
remain owned only until final teardown. Failed cleanup makes the render fail.
Gracefully terminate known owned processes first and force/reap only identified
survivors. Record exact leftovers if host verification is blocked. No broad
process killing, Docker prune, persistent browser, shared Compose project, or
shared volumes. Checkpoint evidence must include wall and stage timings so
emergency guard behavior cannot be mistaken for successful budget compliance.
