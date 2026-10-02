# Overview planned satellite and rendered layers — #218

Date: 2026-10-02
Status: ARCHIVED execution record; rendered acceptance pending

## Change

The upper-right card follows issue #213's text hierarchy:
`X-BAND / selected ID / PLANNED SATELLITE`. Empty selection, loading and failed
selection have explicit text. It contains no illustration, connection indicator
or update age. Selection remains planning data when catalog geometry is missing.

The lower-right legend contains only enabled Aircraft, Planned route, Track
history, Ground entry point and Planned satellite link layers. Its predicates
match the scene's existing draw guards. The planned link sample is thicker than
the track and preserves the existing blue/red configured azimuth-rule styling.
Short exceptions appear separately in Map status, including last-known warning
text after a failed refresh. Aircraft/GEP geometry survives route failure.

Configuration now owns the shared history-window editor and detailed map
analysis. Saved custom durations, GET/PUT failures, pending changes and query
invalidation remain covered. POI names and configured satellite IDs remain
accessible independently of visual-label occlusion. Paint containment prevents
the fixed globe from intercepting desktop navigation and the phone menu.

The current scrolling fallback, natural lighting, globe camera, chart renderer
and arrival provenance are retained. Desktop camera/composition tuning belongs
to #219; the mobile globe-stage interaction belongs to #220.

## Candidate and execution

Base: `7ea084979fa237e4e1403bd26e9556ced36de1fd` (`dev`, #230).
Branch: `feat/218-planned-satellite-legend`.
Implementation candidate: `0b422529cc79dca18d077fc0e637717ef4327e55`.
Worktree: `/tmp/starlink-218`; the existing arrival branch was preserved.

[Approved implementation plan](../superpowers/plans/2026-10-02-overview-planned-satellite-legend.md)
and [responsive design](../superpowers/specs/2026-09-30-responsive-overview-design.md)
provide the delivery boundary. The issue #213 concept was inspected as a visual
reference; it is not a screenshot of the implemented candidate.

## Verification

- Canonical frontend gate: 353 tests in 68 files passed; production build passed.
- Canonical static gate: formatting, lint, documentation naming/links and
  acceptance-policy checks passed with the exact selected base SHA.
- Final focused Chromium run: 13/13 passed after the fixture/readiness fixes.
  Across the serial runs, all 43 applicable non-motion-oracle cases passed.
  A broad rerun recorded 40 passed, four failed and one skipped: the two
  screenshot/fullscreen fixture defects and skipped custom-window case passed
  in the final run; the two chart-motion failures also occur on the baseline.
- An initial broad run passed 43/45 checks. Two existing retained-sample motion
  checks failed under software rendering; all three DPR variants subsequently
  passed unchanged in a focused run. The exact unchanged dev baseline also
  reproduced the same jump (6/9 repeated baseline checks passed, 3 failed).
  Motion limits were not relaxed; broad rendered
  acceptance remains pending a suitable renderer or a separate chart fix.
- Navigation hit-target checks failed before paint containment and passed on
  desktop and 390px phone layout after it.
- The POI baseline is refreshed only after settled route/status responses and
  inspected manually. Native fullscreen re-entry waits for the actual fullscreen
  element and 440px chart geometry before asserting containment.

Fixtures cover planning selection, normal/warning styling, retained geometry
under errors, invalid catalog recovery, route failure, long identifiers, text
at 20px root size, shared-duration navigation, mounted uPlot duration changes,
arrival/POI containment and existing painted trace/envelope motion.

## Rendered and production evidence

The isolated production project is `issue218-control`, with separate named
volumes and loopback ports: Nginx 15218, backend 18218, Prometheus 19218.
It uses the unchanged repository Dockerfiles, Nginx API proxy and simulation
backend. Real API smoke checks cover status, no selected satellite, route list,
history settings and the healthy Prometheus scrape target. No deployment or
shared application data is changed.

Exact-candidate CDP evidence and renderer metadata are recorded in
`/tmp/issue218-evidence/<candidate SHA>/manifest.json`, with screenshots and a
short WebM recording. The manifest distinguishes real simulation/API behavior
from intercepted status/catalog/selection/route fixtures over the production
assets. Desktop evidence uses 1920×1080 in ordinary and native fullscreen;
phone evidence uses 390×844, 844×390 and 360×800. Manual orbit/zoom captures bright
terrain and dark ocean without changing the product camera defaults. An opaque
fallback capture forces the existing CSS fallback tokens.

Browser: Chromium 153.0.8010.12. Renderer: ANGLE Vulkan SwiftShader (Subzero).
CDP connects to localhost port 9228. The completed manifest records the actual
video filename and response statuses. The screenshots were inspected for card
hierarchy, enabled-layer samples, separate failure/warning text and contrast on
bright terrain, dark ocean and the forced opaque fallback. The final capture
completed successfully; all three phone viewports had no horizontal overflow.

## Execution decisions

- Contain app-content painting so the fixed globe cannot intercept navigation.
  Risk: clipping another route's content; portal dialogs remain outside and
  desktop/phone navigation tests pass.
- Give acceptance runs separate artifact directories after a concurrent output
  collision. Risk: lost evidence paths; final runs are serial and retained.
- Preserve the existing chart renderer and report its baseline-reproduced
  SwiftShader motion failures separately. Risk: a hardware-visible chart defect
  remains; broad rendered acceptance is explicitly pending.

## Limits and publication

Chromium uses SwiftShader software rendering in this environment. Physical
phone interaction and ten-foot reading distance have not been assessed. The
forced opaque capture verifies styling, not a browser lacking blur support.
Satellite error/warning and route-failure captures use explicitly identified API
fixtures with valid aircraft/GEP coordinates; real production no-selection and
settings persistence are separate. The real simulation emitted an out-of-range
longitude and no GEP during capture. Existing projection guards correctly omit
those markers; the selected-link fixtures explicitly supply valid coordinates.

Exact-candidate evidence is complete. Independent review precedes handoff.
The candidate is local. A green broad motion suite is not claimed.
Push/PR creation requires an integration choice; merge,
deployment and issue closure are outside the approved implementation scope.
