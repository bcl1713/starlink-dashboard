# Customer briefing HTML-to-PDF trial

Status: architecture direction selected by the user; written spec awaiting
review. Implementation planning follows written-spec approval. Product code and
rendering work have not started on this branch.

## Purpose and authority

For each flight leg, the customer must identify within seconds when
communications capability is reduced, why, what remains available, and when
SOF/AR coordination restrictions apply. The result is a polished operational
brief with approximately one page per normal leg.

The user selected HTML/CSS/SVG rendered by headless Chromium to PDF and
explicitly confirmed that native PowerPoint editability is not a requirement.
This follows the
[architecture comment on #309](https://github.com/bcl1713/starlink-dashboard/pull/309#issuecomment-6060595532)
and preserves the earlier composition and visual acceptance requirements. The
[last checkpoint review](https://github.com/bcl1713/starlink-dashboard/pull/309#issuecomment-6059880351)
establishes the nested outage fixture, successful intended map render, desirable
five-page mission, and mandatory first-page visual gate.

This spec supersedes the presentation format, composition, typography,
pagination, and acceptance path of the original trial design and the native-PPTX
composition redesign on #309. Old plans and acceptance evidence remain
historical; their approvals do not authorize execution of a new implementation
plan.

## Restart boundary and retained work

Use `.worktrees/customer-briefing-html-pdf` on
`feat/customer-briefing-html-pdf`, based on `origin/dev` at `3276aa06`. Keep the
primary checkout on `dev`. Preserve #309, its worktree, uncommitted
checkpoint-runner changes, and private evidence without modification.

The retained implementation reference is #309's committed checkpoint `575730a8`.
It contains immutable snapshot modules, `trial_projection.py`,
`trial_clocks.py`, customer wording/clocks, route-map rendering, frontend export
scene, and Chromium packaging. Selectively bring necessary code and its semantic
tests into the new branch during approved implementation; audit it against
current `dev` and this spec. Do not wholesale merge the old branch or carry its
native trial PPTX builder, Pillow layout engine, LibreOffice checkpoint
pipeline, or old slide-content tests into the new presentation path. Legacy
PowerPoint dependencies remain where the existing export needs them.

Retain the canonical data/projection contracts and provenance machinery. Audit
customer-view grouping, uncertainty changes, endpoint fallback, and wording
before reuse; existing code is useful input rather than proof of acceptance.

The trial stays default-off and additive. No legacy replacement, merge,
promotion, phase-two background worker, new external rendering service, or
shared runtime configuration change is part of this restart.

## Selected architecture

Use a static local HTML template with CSS Grid/Flexbox, ordinary HTML tables,
and an SVG timeline. Embed PNG maps returned by the existing overview-style
renderer. Reuse packaged Chromium and its pinned browser/asset dependencies. No
interactive dashboard or live subscriptions enter the document.

Rendering the globe directly inside each briefing page is an alternative, but
couples PDF readiness and pagination to WebGL lifecycle. Embedded completed maps
provide a simpler boundary and preserve the proven map scene. Native PPTX
objects and a PPTX wrapper of rendered images are deferred product decisions.

The data flow is:

1. Capture one immutable export snapshot, including effective timing and routes.
2. Produce the canonical transport/posture/restriction projection.
3. Produce a pure customer view: wording, display clocks, material rows,
   notices.
4. Render useful route maps from that same snapshot.
5. Compose fixed 16:9 HTML pages with exact-duration SVG geometry.
6. Load the document in packaged Chromium, await fonts/images/layout, and
   inspect fit. Later continuation planning uses actual browser layout
   measurements.
7. Print the complete accepted page document to PDF and validate its page count.
8. Serialize and validate paired evidence from the same snapshot and page plan.
9. Publish both optional files together into the normal legacy ZIP.

Keep focused interfaces for canonical projection, customer view, HTML
composition, browser rendering, evidence serialization, and package publication.
Composition cannot independently infer transport availability. Export cannot
write back to mission/timeline storage or recapture data between the two
artifact builders.

## Artifact and failure contract

The enabled trial adds exactly these mission artifacts, listed in the manifest:

- `exports/mission/mission-customer-briefing-trial.pdf`
- `exports/mission/mission-customer-briefing-evidence.json`

Legacy `mission-slides.pptx`, per-leg PPTXs, CSV, JSON, KML, import content,
filenames, and existing download behavior remain intact. The new trial does not
emit a customer PPTX. Disabling it restores the legacy file set.

Build the PDF/evidence pair in request-owned temporary storage. Validate both
before adding either to the ZIP or manifest. Any trial projection, composition,
overflow, timeout, PDF validation, or evidence failure returns the complete
legacy package with neither optional artifact and the existing safe warning /
status-header and persistent download-feedback behavior. Expose concise warning
codes rather than private source content or internal errors.

Map-only failure may use a useful static fallback or reclaim map space, with
details recorded in evidence. It never creates a customer failure page and
cannot qualify the primary visual checkpoint.

## Page composition and typography

Each fixed print page is 13.333333 by 7.5 inches, with zero browser margins,
scale 1, print backgrounds enabled, and no browser headers/footers. Screen
previews use the same page geometry and print styling. Each page breaks
explicitly; PDF pagination must not create an extra blank page or split a table
row.

Use a light body, dark navy header/section accents, restrained APO gold, minimal
borders, deliberate whitespace, and a consistent alignment grid. Integrate the
existing APO patch in a fixed header position while preserving its aspect ratio.
Starshield appears as a transport name only.

The reading order is leg identity/timing, dominant overall posture, transport
lanes, SOF/AR restrictions, coordination table, and geographic context. The
header contains `LEG N OF M — origin → destination`, a source-backed optional
geographic subtitle, compact departure/arrival ET and flight duration, and a
small trial label. Resolve airport identifiers/names first, route endpoint
labels next, then a single leg name or `Leg N`; never duplicate the route title
across an arrow.

Use bundled DejaVu Sans regular/bold as the initial reproducible typeface,
loaded locally with explicit font readiness. No external font fetch or silent
font substitution qualifies acceptance. Target title 28–32 pt, timing/posture
18–22 pt, transport labels 16–18 pt, coordination table 14–16 pt, and
nonessential footer 10–12 pt. Browser-measured fit and rendered readability
replace Pillow measurement and Office font-parity requirements.

The overall posture band is at least twice a transport lane's height. Under it
align Commercial Ka, Starshield, X-Band MILSATCOM, and a separate SOF/AR lane on
one ET-first axis. Only definitive overall posture uses green/amber/orange/red;
transport states use quiet neutral Up/Down/unknown treatments. Restrictions use
a distinct blue/gray treatment. Labels and selective patterns preserve meaning
in grayscale.

Use a compact multi-row table with ET, Event / impact, Communications remaining,
and Posture columns. It normally shares the primary page with the timeline. Use
concise customer wording and restrained badges. Keep internal IDs, hashes,
rules, DTOs, raw JSON, and renderer diagnostics in evidence. A small useful map
card aligns to the page grid, with legible route/endpoint/event markers. Reclaim
its space when geographic context is unnecessary. Keep legends compact and
prediction caveats in a small footer.

## Semantics and exact geometry

Keep canonical Up/Down/unknown classification and the three/two/one/zero-Up
mapping: Nominal, Degraded, Limited / elevated risk, Communications unavailable.
An unknown transport counts as neither Up nor Down. Missing X planning uses a
single leg-level notice, an X lane marked `?`, and a neutral overall band naming
confirmed capability. Known Ka/Starshield outages remain visible. Use Assessment
incomplete qualifiers without repeating the missing-planning explanation in
every row. Never imply all transports are unavailable while one is unknown.

Preserve both standard fifteen-minute SOF windows, full resolved AR periods,
short-flight SOF overlap, and independently established outages. SOF/AR does not
reduce availability counts. Timing comes from the adjusted flight snapshot.

SVG bar positions and widths derive from exact UTC boundaries relative to that
leg's departure/arrival. Do not round geometry or widen short events. Use
leader-line/callout labels for narrow material intervals, including brief total
outages, while maintaining their true duration.

Table grouping may combine adjacent canonical intervals only when customer
states, restrictions, material causes, limitations, and confidence agree.
Internal source-ID churn alone does not create a row. Preserve every underlying
interval/source mapping in evidence. Never merge across a quiet gap, leg
boundary, AR boundary, short total outage, or material uncertainty change.
Unknown-state changes that affect coordination must appear even without a
confirmed outage.

Keep exact ET/Zulu/T-plus instants in evidence. Customer labels normally use
HH:MM ET with the date in the header, dates for midnight crossings, and EST/EDT
or offsets to disambiguate DST folds. Never expose microseconds. Round displayed
risk starts down and ends up when necessary, mark approximation compactly, and
use second precision for subminute windows or colliding material boundaries.
Zulu/T-plus remain secondary; each leg has its own T-zero. Ground time never
joins leg axes. Departure changes require re-export.

## Readable pagination and page budgets

A normal six-to-eight-hour leg has one primary page with a full-flight timeline
and customer table. A genuinely dense/long leg may need two pages; three is the
absolute pathological-leg ceiling. The representative five-leg mission has fewer
than fifteen pages. Five pages are valid and desirable when each leg fits; there
is no six-page minimum or automatic cover/index.

After visual acceptance, use Chromium's actual text/element bounds to plan
continuations at explicit customer-row boundaries. Keep the first page as the
leg summary. Long timeline panels require a demonstrated readability need and
explicit time ranges. Show every material row once. Never paginate per source
record or automatically produce detail/appendix pages.

Do not satisfy a page budget by shrinking required text, clipping overflow,
omitting risks, or conflating distinct conditions. Unreadable or over-budget
content fails the optional trial safely. The first checkpoint supports only the
two agreed normal-leg examples; general pagination is a later gated extension.

## Browser determinism, ownership, and evidence

Use pinned Chromium/Playwright, bundled fonts/assets, fixed viewport/pixel
ratio, fixed print options, explicit timezone/locale, and snapshot-derived
timestamps. Disable animation and live-clock content. Wait for fonts, decoded
images, and an explicit composition-ready signal; a sleep is not readiness.
Escape customer strings as text and allow only bundled assets, embedded image
data, and scoped loopback resources. No external asset or screenshot service is
required.

Retain the existing 60-second map-stage ceiling. The whole new render pipeline
(maps, HTML layout, PDF printing, and renderer cleanup) additionally shares a
60-second monotonic deadline for this design. This is a stricter combined
contract to verify at the checkpoint, not an already-proven performance claim.
Measure cold runs before generalizing; if the combined budget cannot pass, stop
and revise the design instead of silently increasing a timeout. Verify that the
production export proxy accommodates legacy export plus the bounded trial
without broad timeout changes.

Record ownership before launching child processes, browser contexts/listeners,
Compose projects, private volumes, and temporary paths. Use exit/signal cleanup
and wall-clock limits with forced-termination grace. Close/reap children and
verify task-owned resources are gone after success, failure, or cancellation.
Preserve the actor's Docker daemon/context and other tasks' resources.

Versioned evidence records snapshot fingerprint, canonical intervals/decisions,
all exact clocks, unsplit source records, restriction/confidence data, customer
row mappings, page assignments, map/fallback results, runtime/font/asset
identities, fit results, timings, and cleanup outcome. Private geometry stays
local.

Determinism means repeated identical inputs in the same pinned runtime produce
the same customer text, SVG geometry, page count/assignments, and decoded
preview pixels. Validate PDF page dimensions, text, ordering, and rendering too.
Raw PDF byte identity is not required because creation metadata and document IDs
can vary; normalize only identified volatile metadata in structural comparisons.

## Mandatory first visual checkpoint

Before dense/long or multi-leg implementation, render these two separate
one-page examples from canonical synthetic fixture data:

1. Fully assessed primary leg, eight hours from 10:00 to 18:00 ET on 25 October
   2026, with meaningful source-backed endpoints. Ka Down 12:00–13:00;
   Starshield Down 12:15–12:45; X Down 12:25–12:30. Independently classify all
   transports throughout the flight. Guarantee visible Nominal green, Degraded
   amber, Limited orange, and a five-minute Communications unavailable red
   interval. Include takeoff/landing SOF independently of transport state. The
   intended overview-style map render must succeed; inspect aspect ratio, crop,
   markers, and page-grid integration.
2. A separate incomplete-X leg proving that a single notice and neutral
   Assessment incomplete band preserve known Ka/Starshield risks and confirmed
   remaining capability. It cannot substitute for the primary color review.

For each, deliver self-contained HTML, full-resolution PNG from print styling,
the actual Chromium PDF, and paired evidence JSON. Inspect the PDF render
against the HTML preview so preview acceptance qualifies the delivered format.
Include grayscale observations. Test static-map fallback separately; it cannot
pass the primary checkpoint.

Stop and obtain explicit primary-page visual acceptance for hierarchy, all four
posture colors, typography, table readability, APO branding, whitespace, and map
integration. Do not generalize merely because content tests or geometry checks
pass. Record the scan test: identify reduced capability, losses, remaining
transports, and SOF/AR in seconds without explanation. Customer review remains
necessary; automated checks cannot establish it.

## Subsequent verification and Superpowers handoff

After approval of this written spec, use writing-plans to create a fresh
checkpoint-only implementation plan. The user reviews that plan and selects
execution before coding. The plan audits/selectively reuses retained semantic
work, defines meaningful RED-to-GREEN tests, and stops at the two-page visual
checkpoint. Native-PPTX Tasks 1–2 and their follow-up plan remain stopped.

Only after the primary page passes visual review, plan dense/long/multi-leg
composition, atomic ZIP integration, and final acceptance. Verify grouping,
changing uncertainty, midnight/DST, subminute outages, AR/SOF overlaps, missing
data, over-budget failures, font/asset failure, PDF/evidence failure, timeout,
and cancellation cleanup. Compare legacy output with fixed clocks and explain
only genuinely volatile metadata exclusions.

Run applicable static/unit checks and fresh isolated exact-commit production
Docker/Nginx export and rendered-browser enabled/disabled/warning download
journeys. Require applicable CI on the exact head. Old evidence and API-only
success do not qualify the new renderer or browser UI. Record environment blocks
explicitly. Desktop PowerPoint editing and cross-reader native-object checks are
removed from the new trial acceptance contract; offline PDF reading and actual
output rendering replace them.

Keep the new PR draft during design/checkpoint review. Retain open-PR worktrees
and acceptance evidence, stop all task runtime resources promptly, and clean up
task branches/worktrees after eventual merge into `dev` per workspace policy.
