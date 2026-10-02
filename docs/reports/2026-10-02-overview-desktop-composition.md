# Overview desktop composition — #219

Date: 2026-10-02 Status: desktop visual acceptance recorded; PR checks pending

## Change and delivery boundary

Ordinary and native fullscreen 1920×1080 views share one composition: four top
clocks, five 440px metric cards on the left, planning information at upper
right, legend/map exceptions at lower right, and departure/arrival below the
central map area. The fullscreen entry control sits beneath the planning card.
The 1920px layout reserves a central clear region at least 900px wide and 500px
high under the covered long-content/error fixtures.

The same globe, uPlot instances, operational queries and derivations remain in
place. Natural lighting, initial camera `[0, 0, 22]`, 45-degree field of view,
manual orbit/zoom, GEO geometry and 3–28 zoom range are unchanged. The initial
globe size remains the baseline camera's; operators can zoom and orbit. Mobile
stage/gesture work remains #220, with the existing reachable flow retained.

The desktop threshold is actual container size: at least 1500px and 93.75rem
wide, 1012px and 63.25rem high. Shorter viewports or enlarged root text use
normal flow. Tests cover root sizes 8/12/16/24px, ordinary/fullscreen
transitions and 390×844, 844×390 and 360×800 interim layouts without horizontal
overflow.

Supported glass uses 80% navy with 10px backdrop blur; unsupported blur uses 90%
navy. Text and plots have no foreground blur. Conservative white-backdrop
contrast checks require secondary labels to reach 4.5:1, following the
[W3C contrast-minimum threshold](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).
This verifies the sampled CSS colors, not full accessibility conformance or
physical reading distance. Clock query messages now use the same readable
surface. Fixed satellite states use 24px copy; selected identifiers longer than
24 characters wrap at 20px/24px. Full accessible strings remain present.

## Candidate and migration inventory

Base: `d3862415cafbc96f5efce6b6d42c16e0b182f4e1` (`dev`, #233). Branch:
`feat/219-desktop-composition`, worktree `/tmp/starlink-219`. Frame commit:
`a56861169f0a33bfc3dd2da486dc8c4fd2b649f3`. Readability implementation:
`9f6c12a4b15d882402aad4d0bedc74113f379e2c`. Fit/readiness and runtime-discovery
follow-up: `d50d4138eca1fc337880cfa4a49445749885f98c`. The exact published
capture SHA is recorded in the final manifest; publication was authorized for
checkout.

[Approved plan](../superpowers/plans/2026-10-02-overview-desktop-composition.md)
and
[responsive design](../superpowers/specs/2026-09-30-responsive-overview-design.md)
define the scope. #216, #217 and #218 are already part of the selected baseline.

| Element                  | Disposition | Verified result                                   |
| ------------------------ | ----------- | ------------------------------------------------- |
| Separate current metrics | Removed     | Already removed by #216; five valid readouts only |
| Three-column history     | Reflowed    | One five-card rail; shared uPlot/query pipeline   |
| Upcoming POIs table      | Replaced    | #217 arrival panel retained; map POIs retained    |
| Detailed legend          | Reused      | #218 conditional layers and separate map status   |
| History-window editor    | Reused      | Accessible Configuration editor persists changes  |
| Four clocks/fullscreen   | Moved       | One clock group/control; navigation restored      |
| Old bottom wrapper/CSS   | Removed     | Metrics wrapper renamed; duplicate rules deleted  |
| Mobile fallback          | Reused      | Single tree remains reachable pending #220        |

DOM checks reject duplicate panels, the legacy POI table and a hidden Overview
history combobox. The Configuration control and diagnostic region remain
reachable. Fullscreen/resizing preserve canvas and plot identity; Configuration
navigation intentionally remounts the page and tests persisted duration on
return. A separate existing test covers duration change on a mounted plot.

## Verification record

Canonical frontend: 356 tests in 68 files and the production build pass. ESLint,
Prettier, markdown naming/formatting and diff whitespace checks pass. The full
static gate was attempted five times, including authenticated GitHub access; its
link checker stops at a pre-existing pinned GitHub specification URL with
HTTP 503. The authenticated contents API confirms that pinned file exists.
Acceptance typing-policy tests pass separately (3/3) in the existing pytest
environment. No failing link was excluded to make the gate green.

The final serial headed desktop/readability/planning run passes 21/21 cases. The
earlier broad run of 60 cases yielded 49 passed, 10 failed and one not run.
Seven failures were corrected layout/test-oracle issues: visual baseline,
arrival positioning, fullscreen readiness, capture budget, enlarged phone clocks
and stale provenance timing. Corrected focused runs pass 6/8 and then 2/2 for
the remaining phone/fullscreen cases. The mounted-duration and provenance tests
pass. Assertions for stationary labels, plot-only translation, sample gaps,
rebase and tab resume remain in place.

Three motion failures remain under SwiftShader: painted one-second and
five-second rebases, and an intermittent DPR2 retained-sample jump. The exact
unchanged dev baseline reproduces both painted failures (4/7 selected cases
pass), and a DPR2 repeat reproduces the jump (2/3 pass). No tolerance was
relaxed. These are an acceptance limitation, not a claim of a green broad motion
suite. Raw logs and archived browser output are retained in
`/tmp/issue219-evidence/`; final desktop logs are `desktop-final-browser.log`,
`phone-near-final.log` and `frontend-final.log`. Baseline logs are
`baseline-motion-browser.log` and `baseline-dpr2-repeat.log`.

## Rendered evidence and runtime limits

Completed implementation evidence is stored in
`/tmp/issue219-evidence/cdp-reviewed/`:
`/tmp/issue219-evidence/cdp-reviewed/manifest.json`,
`/tmp/issue219-evidence/cdp-reviewed/production-ordinary.png`,
`/tmp/issue219-evidence/cdp-reviewed/production-fullscreen.png`,
`/tmp/issue219-evidence/cdp-reviewed/camera-continuity.json` and
`/tmp/issue219-evidence/cdp-reviewed/video-contact-sheet.png`. The manifest
records the actual WebM filename, per-capture geometry, UTC time, API response
classes, SHA, Chromium version and renderer. Evidence files are local session
artifacts; the remote branch contains source and this record.

Chromium 153.0.8010.12 connects through CDP on localhost 9229 with ANGLE Vulkan
SwiftShader. The read-only React devtools hook observes renderer camera pose; it
does not write camera or scene state. Native mouse orbit/zoom, fullscreen,
resize and exit preserve position/quaternion within 0.001 and keep the same
canvas/plot nodes. Natural solar calculation is exercised at 00:00Z (dark
Africa-facing terrain) and 12:00Z (bright terrain). Manual pose captures show
representative short route, POI/destination and GEP labels in the open central
area. Unchanged nowrap globe labels can pass behind panels for 120-character
names; arrival-panel names wrap completely. Marker-label layout is not solved.
Capture-only wheel batches use the shipped handler for populated backdrop
stills; they do not prove physical device input timing.

Production project `issue219-control` runs on the actor-owned rootless Docker
socket `unix:///run/user/1002/docker.sock`, with isolated named volumes and
loopback ports: Nginx 15219, backend 18219 and Prometheus 19219. Images use the
unchanged production Dockerfiles and exact archived candidate source. The Nginx
API proxy returns 200 for status, routes, selection, history settings and
catalog; backend health is 200 and the Prometheus scrape target is UP. Raw real
responses are in `/tmp/issue219-evidence/production-smoke.json`. Configuration
saves 900 seconds through the real PUT API and Overview returns with LAST 15
MIN. No shared data or production deployment is involved.

The fresh simulation has no route, selected satellite or catalog entries; its
status emits an invalid longitude and no GEP. Real captures truthfully show
position/GEP unavailable. Other captures intercept APIs over the same production
assets and supply valid aircraft/GEP, route, POI/destination and configured GEO
positions. Their source times match fixed browser UTC; frozen history can
truthfully reach its overscan limit and show Waiting for fresh history. Forced
fallback disables only the optional backdrop-support rule; it verifies styling,
not a blur-incapable browser. No product lighting/camera substitution is made.

Physical ten-foot reading distance and device interaction remain pending an
operator assessment. Brian requested remote publication to check out the work;
that assessment cannot be inferred from this session's browser. Existing motion
failures and the external link-check failure remain recorded limitations. No
merge, deployment or issue closure is included in this record.

## Execution decisions and risks

1. Reuse lockfile-matched installed modules through a symlink to the prior
   worktree. Risk: shared dependencies must remain unmodified.
2. Run localhost browser processes with sandbox escalation after socket EPERM.
   Risk: isolated test processes run outside the filesystem sandbox.
3. Center narrow arrival assertions on actual scroll content, after unchanged
   dev reproduced the classic 15px scrollbar mismatch. Risk: a centering defect
   could be missed; containment and overflow assertions remain.
4. Test Configuration persistence across navigation, which necessarily remounts
   Overview. Risk: that path cannot prove live instance continuity; mounted
   duration changes have separate coverage.
5. Use 14px secondary observation age alongside 16px network state, after
   wrapping made the header 83.59px high and starved chart rows. Risk: physical
   ten-foot readability of secondary age remains unassessed.
6. Give clock loading/error messages existing glass styling to fix dark
   inherited text. Risk: the message briefly covers more backdrop.
7. Increase supported glass from 50% to 80% after the conservative contrast
   check measured 2.15:1. Risk: geography behind panels is less visible; the
   central region stays open.
8. Give four software fallback captures a bounded 120-second budget after the
   default 60 seconds expired. Risk: slower failure feedback; fit/contrast
   assertions are unchanged.
9. Refresh the inspected visual baseline and obsolete arrival/1024px oracles for
   approved geometry/typography. Risk: a visual defect could be incorporated;
   before/after images were inspected and pixel tolerance retained.

10. Batch capture-only wheel events through the shipped handler after software
    acknowledgements reached 14.8 seconds each. Risk: captures cannot establish
    physical input timing; native CDP mouse continuity is checked separately.

11. Wait for navigation removal before fullscreen geometry checks. Ordinary
    width now already matches the fullscreen rail. Risk: settled checks do not
    establish transient entry-frame paint.
12. Reflow fallback clocks using font-relative container widths after enlarged
    digits overflowed the two-column grid (351px in 345px content). The initial
    button-width hypothesis was disproved and its bound removed. Risk: narrow or
    enlarged-text layouts gain vertical clock rows; stage/gestures are
    unchanged.

13. Advance provenance-fixture time to the frozen observation plus 12 seconds,
    explicitly crossing the 10-second stale threshold. Risk: this checks source
    age projection rather than wall-clock timer precision.

14. Prefer the actor's configured rootless Docker socket over a generic plugin
    root-socket example, and record discovery in AGENTS.md and a runtime guide
    in both this branch and the original workspace for future sessions. Risk:
    rootless storage/capabilities differ; the acceptance project is isolated.

## Independent review

One fresh-context whole-branch review of implementation `d50d4138` found no
Critical, Important or Minor source findings. It read the complete diff, plan,
specification, ledger, available stills, test logs, real API smoke and camera
pose record. It independently checked diff whitespace. Full review:
`/tmp/issue219-evidence/independent-review.md`.

The reviewer declined eight retained behaviors or incomplete evidence areas; the
executor dispositions and risks are:

1. Keep existing nowrap globe labels and record long-name occlusion. Full names
   remain in the arrival panel. Risk: long marker labels can be hidden by
   panels.
2. Preserve approved initial camera/FOV and manual zoom. Risk: the initial globe
   remains small; no automatic framing improvement is claimed.
3. Retain unchanged chart renderer and motion assertions, report baseline
   failures separately. Risk: a hardware-visible motion defect may remain.
4. Leave the mobile stage/gesture redesign to #220. Risk: interim touch behavior
   is less capable than the planned dedicated mobile experience.
5. Publish for Brian's physical assessment, leaving ten-foot acceptance pending.
   Risk: physical readability/input may differ from software evidence.
6. Truthfully omit invalid simulated positions and absent GEP rather than change
   backend scope. Risk: real simulation map geometry can stay unavailable.
7. Limit browser/fallback claims to Chromium and forced styling checks. Risk:
   other browsers, actual blur absence and physical input timing are unverified.
8. Complete video inspection and refreshed exact pushed-SHA evidence as executor
   work. Risk: the review covers stills/source, not independent continuous
   replay.

No deferred source minors were reported. Branch publication is authorized for
checkout; it does not imply a merge-ready acceptance result.

## Operator acceptance and responsive follow-up

On 2026-10-02 Brian confirmed that the visuals pass in the specified 1920×1080
environment and authorized a PR to `dev`, with merge when ready. This records
visual acceptance at that target; it does not establish a separately measured
ten-foot reading distance or remove the renderer and external-link limitations
above. Earlier pending-assessment/publication-only statements are the historical
execution record before this decision.

Brian's personal display is 3000×2000 at 150% scaling, giving approximately
2000×1333 CSS px before browser chrome. In that environment, panels use the full
width and scrolling is cumbersome: some panel regions scroll while others pass
wheel events to the globe. Brian selected
[issue #220](https://github.com/bcl1713/starlink-dashboard/issues/220) for this
responsive fallback and input work alongside mobile portrait and landscape. Its
acceptance boundary now explicitly includes actual container measurements,
consistent mouse-wheel/trackpad scrolling over panels, gaps and the globe,
reachable content and preservation of deliberate globe interaction. These
follow-ups do not block the accepted #219 visual target.

A fresh pre-PR run of `./tools/verify frontend` passes all 356 tests in 68 files
and the production build. The published implementation matches the reviewed
`d50d4138` source; subsequent commits contain documentation only. CI and the
final review remain the integration gates. No deployment or release to `main` is
authorized by this handoff.
