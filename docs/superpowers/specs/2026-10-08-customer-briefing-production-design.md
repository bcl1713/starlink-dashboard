# Customer briefing production completion design

Status: proposed for user review. This document and its companion plan do not
authorize implementation. The user requested a separate plan and approval before
dense/multi-leg pagination or production integration.

## Authority and accepted baseline

The governing
[HTML-to-PDF spec](2026-10-08-customer-briefing-html-pdf-design.md) supersedes
the original native-PPTX trial. PR #312 merged into `dev` at
`f1ee64f42faa9f7a2f02a80d5f22dd324d459902`; final feature head was `3bdda4e2`,
qualified renderer `0f31ced9`. Both committed synthetic PDFs passed customer
acceptance and the primary five-second scan, as recorded in the
[sample manifest](../../samples/customer-briefing/manifest.json). Historical
pending runtime flags are superseded for those examples only.

Keep their final typography, colors, map, exact geometry, and removed definitive
posture callouts. Keep incomplete-X confirmed-capability labels. Earlier spec
instructions requiring the removed callouts do not override that accepted
simplification. Broader readability and real exports remain unaccepted.

## Outcome and approach

Customers receive an optional, offline mission PDF and machine-readable evidence
in the existing export ZIP. Each leg explains reduced capability, causes,
remaining transports, and SOF/AR restrictions in seconds. Legacy PPTX, CSV,
JSON, KML, import content, and filenames remain compatible.

Use measured row-boundary continuation pages. Compared with automatic browser
pagination, explicit page assignment makes omission, duplication, budgets, and
evidence auditable. Compared with separate leg PDFs, one document retains the
requested artifact names and mission order. No cover or automatic appendix.

Deliver in three reviewable stages: evidence prerequisites, pagination/runtime,
then production packaging and acceptance. Each stage has its own tests; only the
final stage can qualify production integration.

## Prerequisites before broader acceptance

1. Verify every coordination row in the actual PDF, including all four cells,
   order, multiplicity, page assignment, and word bounds. DOM row IDs and a
   selected phrase list cannot prove delivered content.
2. Preserve both results of `build_map_input`: input and diagnostic reasons.
   Evidence distinguishes missing/invalid input, map-stage failure, reserve
   cutoff, unsupported framing, and successful primary rendering. Do not put
   diagnostic reasons on customer pages or reduce them to a generic warning.

The PDF verifier consumes expected display cells and measured cell bounds from
the same payload/page plan. Match PDF words inside the assigned page-local cell
rectangle at the 0.75 CSS-pixel-to-point scale. Normalize Unicode NFC and
whitespace only; preserve dates, offsets, approximation marks, seconds, signs,
and punctuation. A matching phrase in a different row cannot satisfy a cell.
Verify every page is 960×540 pt within 0.01 pt and uses embedded intended fonts.
Reject missing, duplicate, reordered, off-page, or split rows.

## Page planning

Retain fixed 1280×720 CSS pages, printed at 13.333333×7.5 inches, zero margins,
scale 1, backgrounds enabled, browser headers/footers disabled. Measure with the
bundled DejaVu Sans fonts loaded and images decoded. Never shrink the accepted
30/20/17/14/10 pt title/timing/lane/table/footer scale to fit.

Each primary page retains the full-flight timeline, accepted legend, header,
notice, route card when useful, and a chronological prefix of complete rows. If
rows remain, label the table as continued and identify the next page.
Continuation pages repeat leg identity, planned timing/date, notice if needed,
columns, compact legend/caveat, explicit row time range, and page numbering.
They use the space for remaining rows; they do not repeat the map or full-flight
timeline. Every customer row appears exactly once, in canonical order.

Determine the largest fitting contiguous prefix using actual browser row and
cell bounds, then validate the assembled document again. Include repeated
headers, wrapped text, and continuation labels in measurements. One oversized
row or an essential timeline label collision fails safely; clipping, hiding, or
truncating is forbidden. Table continuation is the selected extension. Zoomed
timeline panels require demonstrated readability need and a subsequent reviewed
design; this plan does not silently introduce them.

Normal legs remain one page; dense legs may use two, with three the absolute
per-leg ceiling. A representative five-leg mission must have fewer than fifteen
pages; five fitting legs produce exactly five. This is not a new global
fourteen-page cap on missions with more legs. Never join ground gaps or legs.
Useful single-view maps retain accepted styling; unsupported multi-view framing
reclaims map space with precise evidence rather than dropping route sections.

## Data and runtime contracts

Version-2 mission payloads contain one fingerprint and ordered leg payloads.
Each leg retains its exact UTC interval partition and customer-row mappings.
Page plans contain global page number, leg identity, local page number/count,
kind, flight bounds, displayed row range, and ordered row IDs. Version-2
evidence contains ordered per-leg canonical records, row mappings, page
assignments, map diagnostics, PDF verification, and one render report. Public
artifact references point to the delivered PDF and its hash; local
HTML/preview/ownership paths are excluded from published evidence. Keep
version-1 checkpoint tooling usable; do not reinterpret retained evidence.

Unknown counts as neither Up nor Down. Never infer definitive unavailability
from unknown X. Preserve real confidence changes, half-open boundaries, both
fifteen-minute SOF windows, full resolved AR, short-flight overlap, adjusted
departures/splices, midnight/DST disambiguation, and subminute precision. SOF/AR
alone does not reduce transport availability. Geometry uses exact UTC; ET is
primary and each leg has its own T-zero. Source-ID churn alone is not a customer
event. No reclassification or rounding in the page planner.

Start one monotonic 60,000 ms deadline at mission renderer entry, before payload
validation/browser launch. Reuse one browser and one scoped asset listener, with
separate fresh map/document contexts. All legs, maps, font/image readiness,
measurement, assembly, print, actual-PDF verification, and teardown share it.
Retain 20,000 ms PDF reserve and 3,000 ms cleanup reserve; never reset by leg,
page, context, or subprocess. Skip remaining maps at their shared cutoff.
Close/reap the owner before successful return; cleanup failure forbids the pair.
Cancellation propagates from HTTP request to worker, renderer, and descendants.

## Production integration

Ship pinned Node 22.22.2, locked Playwright 1.63.0/Chromium, map bundle/assets,
fonts, and the independent PDF verifier in the backend production image. Use a
root-context multi-stage build; update Compose and GHCR build contracts
together. No remote renderer, persistent browser, new service, or worker phase.
Build/install only at image construction; retain proxy/CA trust and non-root
execution. Production does not import fixtures or acceptance scripts.

Add `exports.customer_briefing_enabled=false` to backend configuration, with
`STARLINK_EXPORTS_CUSTOMER_BRIEFING_ENABLED` as its override. An enabled server
automatically attempts the pair on the existing export endpoint. The UI does not
need a separate opt-in switch, endpoint, or frontend build flag.

On enabled requests, capture one immutable snapshot before building artifacts.
Use its private views for legacy documents and metadata/routes/POIs as well as
the PDF/evidence. Optional keyword injection supplies timelines, parent
metadata, ground-entry data, and effective map routes to existing builders.
Default standalone/disabled calls retain current behavior. No live re-reads or
storage mutations once snapshot capture succeeds. If capture fails, deliver the
existing legacy export with an omission warning and neither new file.

Stage the pair in a request-private directory. Validate identity, PDF rows, page
plan, hashes, evidence, budget, and cleanup before ZIP insertion. Publish
exactly:

- `exports/mission/mission-customer-briefing-trial.pdf`
- `exports/mission/mission-customer-briefing-evidence.json`

Add both to existing `file_structure.mission_exports` and update statistics.
Keep manifest version 2.0; do not ship previews, ownership logs, or temporary
paths. A ZIP write failure discards that ZIP and rebuilds the complete legacy
package from captured views with neither optional member; no partial pair.
Legacy generation failures retain existing error behavior.

Return HTTP 200 for successful legacy downloads even if the optional brief is
omitted. Add `X-Customer-Briefing-Status: included|omitted` only when enabled;
omission adds `X-Customer-Briefing-Warning` with a safe code: `snapshot`,
`data`, `page-budget`, `overflow`, `runtime`, `deadline`, `pdf`, `evidence`,
`cleanup`, `publication`, or `busy`. Map fallback alone can still be included
and is described in evidence.

The existing UI currently discards response headers and auto-closes success. Add
structured download metadata while retaining the Blob service wrapper. An
omission message says the ZIP downloaded, legacy documents are included, and the
customer PDF was omitted. Keep it visible until dismissed; do not auto-close it
or show source text, identifiers, exceptions, or diagnostics.

Bound concurrent optional renderer ownership to one per API process; a busy
request still receives legacy output with a `busy` warning. Run blocking package
work outside the event loop with cooperative cancellation and wait for owned
worker teardown on disconnect. Close response ZIP handles on all exits.

Measure legacy plus bounded rendering through production Nginx. If the current
proxy cannot accommodate it, allow only an export-route-scoped timeout change
backed by measurements and review; no global API timeout increase. A failing
60-second render revises the design rather than silently extending the budget.

## Completion gates

The [implementation plan](../plans/2026-10-08-customer-briefing-production.md)
defines automated contracts, actual-PDF controls, exact-SHA production-image
acceptance through Nginx, enabled/disabled/omitted browser downloads,
fixed-clock legacy equivalence, concurrency/cancellation, and complete resource
teardown. Retain three cold repeated five-leg requests with deterministic
content, geometry, page assignments, preview pixels, and normalized PDF
structure. Only identified PDF creation metadata/document IDs may be excluded.

Customer acceptance must explicitly cover readable continuations, dense/long
examples, multi-leg output, and production downloads. Checkpoint acceptance does
not qualify them. Keep the feature default-off after delivery; enabling it in
shared production configuration or replacing legacy PPTX needs a separate user
decision. This task authorizes planning and a draft documentation PR only.
