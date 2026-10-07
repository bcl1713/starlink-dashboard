# Draft customer mission briefing trial design

Add an automatic second PowerPoint for a recurring customer who reads it before
a live brief. For each leg, show communications and coordination restrictions,
their causes, and remaining capability. Evaluate it alongside the existing deck.

This is a design for review, not an implementation or a replacement decision.

## Customer requirements

- One export action produces the existing deck and an additional trial deck.
- Generation uses mission data, fixed rules, and templates without AI services,
  manual authoring, or an operator arranging slide content.
- Each leg has its own takeoff-to-landing timeline and T-zero. Ground time
  between legs is excluded, even when it spans several days.
- Overall communications posture is the dominant visual; individual transports
  explain why posture changes using consistent Up and Down treatments.
- A separate row shows SOF and AR coordination restrictions without implying a
  transport outage.
- Eastern time is the customer clock. Every event has explicit Eastern start and
  end times; Zulu and takeoff-relative times are secondary references.
- Use APO organizational branding and overview-style route maps where feasible.

## Existing integration points

Single-leg decks use the exporter entry point and shared `pptx_builder.py`.
Combined decks and ZIP assembly are in
`backend/starlink-location/app/mission/package/__main__.py`. The package lists
`exports/mission/mission-slides.pptx` and per-leg `slides.pptx` in its manifest.

The overview uses React Three Fiber and Three.js through `CityLitGlobe`,
`GlobeRouteRibbon`, and `OverviewMapController`; exported maps currently use a
separate static renderer. `TransportState` distinguishes available, degraded,
and offline, while legacy status groups two affected transports as critical.
Derive trial posture independently without changing models or legacy output.

The rule engine already creates 15-minute post-takeoff and pre-landing SOF
windows. AR uses resolved plan timing and overrides. Safety context is separate
from transport availability; normalized call-posture labels must not determine
the trial's transport-count posture.

## Trial export contract

The normal ZIP gains `exports/mission/mission-customer-briefing-trial.pptx`,
labeled "Customer briefing — Trial" and listed in the manifest. Preserve legacy
slides, filenames, CSVs, routes, and imports. Direct single-leg PowerPoint
downloads remain legacy; separate trial files for each leg are out of scope.

A feature flag enables the deployed trial for evaluation. Disabling it restores
the original file set without migration. Customers need no extra export steps.

[Phase two](2026-10-07-mission-slide-background-generation-design.md)
After deck validation, it generates on save and assembles caches on export.

Both builders share immutable metadata, ordered legs, routes, and timelines.
Preserve rebuild/cache behavior and label incomplete trial data. Export never
writes back to mission or timeline storage.

Trial failure preserves the legacy package, omits incomplete trial files, and
reports a warning in the manifest and export result. Map-only failure uses a
labeled legacy map. Never deliver an empty map or falsely report trial success.

## Slide structure

### Optional mission leg index

An optional small index lists legs and ET departures/arrivals. Omit a large map,
generic introduction, ground time, and a mission-spanning communications axis.

### Primary briefing for each leg

The header shows Leg N of M, origin to destination, departure ET, arrival ET,
and flight time. Missing locations use route or leg names with a missing-data
note. Each leg covers takeoff through landing with its own T-zero.

Place a small route/context map alongside the main content. The largest visual
is the communications timeline, with these rows in order:

1. Overall communications posture.
2. Commercial Ka.
3. Starshield.
4. X-Band MILSATCOM.
5. SOF / AR restrictions.

The overall posture row is at least twice a transport lane's height and uses the
strongest labels and contrast. Green/amber/orange/red risk colors appear only
here. All transport lanes share plain neutral Up and hatched Down treatments;
restrictions use a separate neutral pattern with SOF/AR labels.

Eastern time is the main axis. Zulu and T-plus references are smaller and
aligned to the same anchors. Bars are proportional to duration. A numbered
callout connects a short event to its table entry without exaggerating its
duration. Repeated legends explain posture, transport state, and restrictions.

Place the primary ET table beneath or beside the timeline; use adjacent slides
if needed. Divide long legs into consecutive panels with shared window numbers,
repeated headers, legends, time ranges, and continuation marks. Never join legs.
Paginate rather than shrink text or timeline rows.

### Primary event and coordination table

For every leg, show a compact chronological table with these columns:

- Start (ET).
- End (ET).
- Event / impact.
- Communications remaining.
- Overall posture / customer implication.

Build one chronological, non-overlapping partition of the flight into customer
coordination windows. Split at changes in transport usability, overall posture,
active SOF/AR restrictions, or material customer-facing causes. Each window has
one row aggregating every active cause and source event identity. Include quiet
Nominal intervals so rows cover takeoff through landing without gaps.

Source outages and synthesized overlaps are inputs to that partition, not
additional overlapping table rows. Retain unsplit source records in the
appendix. For a Ka outage 04:10-08:15 ET and X outage 05:30-07:00 ET, show three
rows: 04:10-05:30 Ka down / Degraded; 05:30-07:00 Ka + X down / Limited; and
07:00-08:15 Ka down / Degraded. Name the remaining transports in each row.

The table and overall-posture bar use the same window boundaries and
identifiers. Both SOF windows, full AR periods, and single outages remain
visible, with every start/end explicit in ET. Zulu and T-plus are smaller
secondary references.

Explain source-backed causes, name usable transports, and distinguish reduced
redundancy, elevated risk, unavailability, and activity restrictions. A
restriction-only row identifies unchanged posture and required coordination. Do
not infer a shutdown or invent an operator instruction from a safety label.

Use fixed wording and source-backed reason labels. Promote internal transitions
only for posture or coordination changes; other detail stays in the appendix.
Continuations repeat columns and leg data without duplicating time windows.

Window numbers link the timeline, table, and map when coordinates exist.
Optional detail cards supplement the primary table for complex events.

### Reference appendix

Keep paginated source timeline states, all three clocks, reasons, advisories,
and lower-level transition details for the later live briefing. Essential SOF,
AR, and outage information must already be present in the primary leg pages.

## Communications posture and transport display

Derive posture from independently classified transport availability, not from
the existing aggregate critical label or normalized call-posture wording. For
intervals with a known Up or Down classification for all three transports:

- Three Up: "Nominal", green.
- Two Up: "Degraded", amber; two transports remain and this is not an outage.
- One Up: "Limited / elevated risk", orange.
- Zero Up: "Communications unavailable", red.

Posture is a prediction, not a throughput guarantee. Labels supplement colors.

Available maps to Up and offline maps to Down. Degraded does not automatically
mean either. Before implementation, document reason-specific presentation rules
against the existing source events and availability semantics. For example, the
reducer represents a Ka coverage gap as degraded even though its cause is no
coverage; classification must consider that cause rather than the enum alone.
Use plain Down for supported unavailability and plain Up for supported
usability. Put degraded limitations only in event-table text: no asterisk, extra
lane style, or risk color. Reserve "?" for genuinely indeterminate usability.
Keep the mission model and legacy calculations unchanged.

An unclassifiable degraded or missing state uses a neutral hatched "?" marker
with a linked explanation. It is neither Up nor Down. The overall row shows
"Posture uncertain", known usable transports, and the unresolved limitation; do
not display a definitive count-based posture or an all-unavailable claim.
"Communications unavailable" requires all three independently classified Down.

Split intervals at transport-state, restriction, and material event boundaries.
Merge adjacent display intervals only when classification, posture, causes, and
coordination context match. Never merge across leg boundaries or hide a brief
complete outage inside a longer limited window. Half-open intervals prevent
touching outage boundaries from creating a false overlap.

Summaries exclude ground time; uncertainty prevents blanket availability claims.

## SOF and AR coordination restrictions

Each leg automatically includes the existing SOF blocks from takeoff to takeoff
plus 15 minutes, and from landing minus 15 minutes to landing. Resolve them from
the leg's adjusted departure and arrival; reuse existing rule configuration
rather than introducing a separate buffer setting. Clamp windows to the flight
interval. On a flight shorter than 30 minutes, preserve both SOF labels where
they overlap without double-counting restricted duration.

Show the full resolved AR period as an activity-restricted coordination window,
not only its start/end markers or periods with X-band conflicts. Use current
waypoint timing, AR overrides, and applicable resolved manual AR windows from
the same snapshot. Missing AR timing is a clearly labeled note above the table,
not a fabricated or overlapping timed row.

SOF and AR appear in the dedicated restriction row and the primary event table.
They must not lower the transport Up count unless independent mission data
establishes transport unavailability. When an outage overlaps a restriction,
show both: the transport lanes and posture reflect availability, while the
restriction row reflects coordination. Aggregate overlapping restriction labels
and outage causes within each coordination-window row.

## Clock behavior and departure changes

Convert ET using `America/New_York` with date-correct EST/EDT; derive Zulu from
UTC. Include dates across midnight and distinguish repeated daylight-saving
times. Derive T-plus from that leg's adjusted takeoff, not export time or the
first timeline segment. Primary panels cover takeoff through landing; any
pre-departure appendix reference uses T-minus. Each leg has its own T-zero.

Label each leg's planned departure basis. Printed ET and Zulu times stay tied to
that plan, while relative times aid rescheduling. Absolute outages and
time-dependent conditions may change relative to the aircraft after a departure
shift; re-export when underlying assumptions or predictions change.

## Overview style maps

A dedicated export scene shares the overview's globe textures, route geometry,
and styling. Render the immutable export snapshot at a fixed resolution and
planned reference time, without animation, live aircraft data, dashboard
controls, or unrelated overlays. No AI or manual browser interaction is needed.

Use the project's packaged browser runtime and local bundled assets. Wait for
scene readiness, set a reproducible camera, and return high-resolution PNGs.
Verify renderer feasibility before trial implementation; do not depend on an
external screenshot service.

Keep maps small on primary leg pages. Long routes need multiple views when they
cannot fit on one visible hemisphere. Never show an occluded route through the
planet. Fit labels and event markers within the crop, including polar and
dateline routes. Use neutral routes and numbered event markers; risk colors stay
on the main posture row. Label lighting as a planned-time illustration, not
lighting at every point throughout the flight.

Cache keys include effective route geometry, adjusted departure, leg identity,
reference time, availability data, renderer version, and framing. Bound the
whole extra rendering stage to 60 seconds by default, then use labeled legacy
map fallbacks. Change that limit only after representative measurements. Clean
up task-owned browser processes and temporary images on every exit path.

## Presentation rules

Use the existing organizational mark at
`backend/starlink-location/app/mission/assets/APO Patch.jpg`. Preserve its
aspect ratio and use restrained APO branding. Starshield names a transport only;
it must not appear as a deck masthead, organizational mark, or tagline.

Use widescreen slides, whitespace, and consistent alignment. Keep main body text
at least 18 points and primary time and window labels at least 20 points.
Supporting clock labels and appendix text stay at least 14 points. If content
does not fit, paginate rather than reduce the font. Metadata footers can be
smaller, but must not carry essential information.

Use light backgrounds for reading and printing, and dark globe styling only
where it aids the map. Labels, patterns, and legends work in grayscale. Text and
tables remain editable PowerPoint objects; embedded maps and other assets allow
offline opening.

## Verification and evaluation

Use synthetic fixtures plus suitable existing missions. Verify:

1. One export includes both decks and manifest entries; disabling the trial
   restores the legacy file set. Compare legacy structure, text, and styling,
   ignoring volatile document metadata.
2. Both builders share the snapshot, adjusted departures, splices, cached
   fallback, and revisions. Days-long ground gaps never join leg timelines; each
   leg starts at its own T-zero.
3. Known Up counts map to Nominal, Degraded, Limited / elevated risk, and
   Communications unavailable. Touching boundaries do not overlap, and brief
   complete outages remain visible.
4. Usable degraded states render plain Up, unavailable ones Down, and genuinely
   indeterminate ones "?". Limitations stay in table text; no lane asterisk or
   extra risk style. Uncertainty never becomes falsely all-unavailable.
5. Every leg shows both 15-minute SOF windows and full resolved AR periods in
   the restriction row and ET table. Restriction-only fixtures keep Nominal
   posture and available transports. Test short flights and overlapping SOF, AR,
   and outages without losing separate causes.
6. Table windows partition each leg without overlaps or gaps and align with the
   posture bar. Test nested Ka/X outages, SOF/AR overlaps, and touching
   boundaries. Rows aggregate causes and source identities; unsplit records stay
   in the appendix. Remaining capability and ET start/end times are unambiguous.
7. Check ET, Zulu, and relative times across midnight, DST, adjusted departures,
   AR overrides, and multiple legs. Dates and EST/EDT disambiguate times.
8. Maps automatically fit short, long, polar, and dateline routes. Failed
   textures, rendering, or timeouts use labeled fallbacks and clean up
   resources.
9. Missing routes, timelines, and restriction timing are explicit. Trial failure
   still delivers the original export and a visible warning.
10. Render dense events, long text, and many legs. Check posture-row height,
    legibility, pagination, APO branding, transport-only Starshield naming,
    offline opening, editable text, grayscale use, and font minima.

Compare both decks with the recurring customer before promotion. Within a few
seconds of scanning any leg, the customer should identify reduced redundancy,
communications unavailability, remaining transports, and SOF/AR restrictions.
Ask the customer to locate those windows on representative pages and record
readability feedback and export timings. Replacing the established deck requires
a separate explicit user decision; this spec covers the parallel trial.
