# Draft customer mission briefing trial design

Add a second, automatically generated PowerPoint to mission exports so customers
can understand expected connectivity before departure. Customers usually read
the deck independently and later attend a live briefing. The existing deck
remains the established output while the customer briefing deck is evaluated.

This is a design for review, not an implementation or a replacement decision.

## Customer requirements

- One export action produces the existing deck and an additional trial deck.
- Generation uses mission data, fixed rules, and templates without AI services,
  manual authoring, or an operator arranging slide content.
- Eastern time is the primary reference because customers schedule in that
  timezone. Zulu and takeoff-relative times remain readable supporting
references.
- Individual outages do not imply a mission connectivity failure. Two transports
  out means reduced redundancy; all three out means loss of connectivity.
- Maps use the visual language of the new overview globe where feasible.
- The trial can be compared with the existing slides before any adoption
  decision.

## Existing integration points

The shared slide builder lives in
`backend/starlink-location/app/mission/exporter/pptx_builder.py`. Single-leg
PowerPoint generation is in the exporter entry point. Combined decks and ZIP
assembly are in `backend/starlink-location/app/mission/package/__main__.py`.
The package already includes `exports/mission/mission-slides.pptx` and per-leg
`slides.pptx` files, with their paths recorded in the export manifest.

The overview renders a textured globe and route using React Three Fiber and
Three.js. Relevant components include `CityLitGlobe`, `GlobeRouteRibbon`, and
`OverviewMapController`. The current exported map uses a separate static
renderer.

`TransportState` distinguishes available, degraded, and offline. Existing
`TimelineStatus` and slide styling classify two or more affected transports as
critical. The trial must derive its own customer-facing presentation from the
individual transport states without changing the model or legacy output.

## Trial export contract

When the trial is enabled, the ordinary mission ZIP gains
`exports/mission/mission-customer-briefing-trial.pptx`. Its cover says
"Customer briefing — Trial" and the manifest lists the additional file.
Existing filenames, legacy slides, CSVs, route files, and import behavior remain
unchanged. The direct single-leg PowerPoint download remains the legacy deck in
this first trial; generating separate trial files for every leg is out of scope.

An export feature flag controls the addition. The deployed trial is enabled for
evaluation; disabling the flag restores the original package contents without a
data migration. No new export choices or manual steps are required for
customers.

Resolve one immutable export snapshot containing mission metadata, ordered legs,
adjusted routes, and their timelines. Both deck builders consume that snapshot
so their planned departures, revisions, and time windows match. Preserve the
existing rebuild and cache fallback behavior; visibly label cached or incomplete
information in the trial deck rather than presenting it as a fresh prediction.
Export generation must not write back to mission or timeline storage.

Trial-generation failure must not prevent delivery of the existing package.
Omit an incomplete trial file and provide a concise export warning through the
manifest and export result. A map-only failure uses the existing static map,
with a small fallback label, while the rest of the trial deck remains usable.
Never leave an empty map slide or silently report successful trial generation.

## Slide structure

### Mission at a glance

Open with mission name, planned departure and arrival in Eastern time, ordered
legs, and a large route image. Fixed sentences summarize predicted availability
and key-window durations. For example, a summary can state that connectivity is
predicted throughout the flight with a period of reduced redundancy. Only make
that statement when all intervals have known data and support it.

Include a compact explanation of the three transports and the availability
legend. Explain that one transport interruption can leave two alternatives.
Describe predictions as expected conditions, not a guarantee of delivered
bandwidth or suitability for every customer activity.

### Connectivity through each leg

Use three aligned horizontal transport lanes and a combined strip above them.
Display existing names with band references: X-Band, CommKa (Ka), and
StarShield (Ku). Keep that order consistent throughout the deck.

Use Eastern time for the main axis. Place Zulu and T-plus references on aligned
supporting rows at the same time anchors. Bars are proportional to duration.
Show takeoff, landing, and relevant existing mission events without crowding.
Clearly differentiate degraded performance from offline intervals using labels
and patterns as well as color.

Long legs divide into consecutive panels with repeated legends, leg names, time
ranges, and page numbers. An interval that crosses a panel boundary carries a
continuation mark. Short events use numbered callouts linked to detailed cards;
minimum visual bar width must not misrepresent their duration.

### Windows that matter

Generate chronological cards for reduced-redundancy windows, connectivity-loss
windows, and periods with uncertain availability. Each card includes prominent
Eastern start and end times, smaller Zulu and T-plus times, duration, the
transports affected, those remaining, and concise source-backed reasons.

Use shared window numbers on the strip, cards, and map where coordinates exist.
Group cards by leg, with at most three per slide. Add pages rather than
shrinking
the type. A leg with no qualifying windows receives an explicit statement to
that effect, not an unexplained missing section.

Use fixed wording and a maintained reason-label dictionary. Preserve unusual
source explanations in the appendix rather than inventing an explanation or an
operator action. Existing advisories remain distinct from connectivity loss.

### Reference appendix

Retain a paginated timeline reference with transport states, all three clocks,
reasons, and relevant existing advisories. Preserve important AAR and transition
events even when their transport combination does not generate a key card.
The customer should not need this appendix to understand the main briefing.

## Availability semantics

Compute presentation intervals from the individual transport states and event
boundaries, not from the existing aggregate critical label. With all states
known and restricted to available or offline, the customer labels are:

- Three available: "All three available", calm green or neutral styling.
- Two available: "Two available", calm styling and no failure label.
- One available: "One remaining — reduced redundancy", amber styling.
- All three offline: "No connectivity predicted", red styling.

Degraded does not automatically mean offline. Show it explicitly in its lane.
Where degradation is present, the combined strip says how many transports are
fully available and notes degradation. Zero fully available transports with a
degraded transport must not be labeled no connectivity. Missing or unsupported
states display "Availability uncertain" and are never counted as available.

At implementation design review, audit the timeline's reason codes against their
actual availability meaning. A reason-specific classification may identify a
degraded interval as unavailable only when an existing documented rule supports
it. Absent that evidence, keep the conservative degraded label. Do not silently
change existing mission calculations to accommodate the new presentation.

Cards cover intervals with at most one fully available transport or uncertain
data; their titles distinguish reduced redundancy, degraded conditions, and
confirmed predicted outage. Adjacent intervals merge only when the transport
states, customer label, reasons, and advisory context match. Do not merge across
leg boundaries or hide a brief complete outage inside a longer amber window.
Use half-open intervals so touching outages do not become a false overlap.

Summaries accumulate durations from those intervals, excluding inter-leg ground
gaps from in-flight totals. Incomplete intervals do not contribute to an
unqualified all-flight connectivity claim. Unknown durations are reported
separately.

## Clock behavior and departure changes

Use `America/New_York` for Eastern conversion, with the correct EST or EDT label
for each timestamp. Zulu derives from UTC. Include calendar dates at midnight
crossings and distinguish repeated Eastern times at daylight-saving transitions.
T-plus derives from the adjusted planned takeoff of that leg, not from export
time or from the start of a pre-departure timeline segment. Supporting negative
offsets use a clear T-minus label. Every leg establishes its own T-zero.

State the planned departure basis on each leg section. A printed deck's Eastern
and Zulu times remain tied to that plan; its relative times provide a reference
when departure changes. Do not claim that availability predictions stay valid
for every departure shift: absolute outage windows and time-dependent conditions
can change relative to the aircraft. Re-export remains necessary when the
underlying mission assumptions or predictions change.

## Overview style maps

Create a dedicated export scene that shares globe textures, route geometry, and
visual styling with the overview, without capturing dashboard controls, live
aircraft state, or unrelated operational overlays. It renders the export
snapshot
at a fixed resolution and planned reference time with animation disabled.

The export service requests images from a bounded renderer using the project's
packaged browser runtime. The renderer uses local bundled assets, waits for
textures and scene readiness, sets a reproducible camera, and returns a PNG.
No AI, external screenshot service, or manual browser interaction is involved.
This integration is a proposed approach; renderer feasibility must be verified
before committing to it for the trial implementation.

Produce a high-resolution image suitable for a widescreen slide. Use the globe
for geographic context and closer route views for detailed windows. Long routes
that cannot fit on one visible hemisphere use multiple views; never draw an
occluded route through the planet or imply it is fully visible. Fit labels and
key-window markers to the slide crop, including dateline and polar routes.

Map condition colors follow the trial's availability rules, not legacy critical
colors. Keep reference lighting labeled as a planned-time illustration; it does
not imply simultaneous lighting at every point along a multi-hour flight.

Cache keys include effective route geometry, adjusted departure, leg identity,
reference time, availability data, renderer version, and framing. Bound the
entire extra rendering stage to 60 seconds by default; on timeout use available
fallback maps and stop the task-owned renderer. Adjust that limit only after
representative performance measurements. Clean up browser processes and
temporary
images on success, failure, and cancellation.

## Presentation rules

Use widescreen slides, generous whitespace, restrained branding, and consistent
alignment. Keep main body text at least 18 points and primary time and window
labels at least 20 points. Supporting clock labels and appendix text stay at
least 14 points. If content does not fit, paginate rather than reduce the font.
Metadata footers can be smaller, but must not carry essential information.

Keep most content on light backgrounds for independent reading and printing.
Use the darker globe treatment where it aids the map. Color is supplementary:
state text, patterns, and legends communicate availability in grayscale too.
Text and tables remain editable PowerPoint objects; maps are embedded images.
Generated decks open offline with all required visual assets included.

## Verification and evaluation

Use synthetic fixtures plus existing suitable mission fixtures. Verify:

1. The normal export includes both decks and correct manifest entries; disabling
   the trial returns the original file set. Legacy slide structure, text, and
   styles stay unchanged, ignoring volatile document metadata in comparisons.
2. Single and multi-leg decks use the same snapshot as legacy exports, including
   adjusted departures, route splices, cached fallback, and source revisions.
3. Separate outages remain calm; real two-transport overlaps create amber
windows;
   three offline transports create red windows. Touching boundaries do not
   overlap. Degraded and missing states never create false no-connectivity
claims.
4. Cards, maps, strip labels, and summary durations agree. No short outage or
   significant advisory disappears through grouping, clipping, or pagination.
5. Eastern, Zulu, and relative times agree across midnight, daylight-saving
   transitions, adjusted departures, pre-departure periods, and multiple legs.
6. Maps render without manual input and fit short, long, dateline, and polar
   routes. Missing textures, unavailable rendering, and timeouts use fallback
   maps and leave no task-owned runtime resources alive.
7. Missing routes or timelines produce explicit incomplete-data labels. Trial
   failure still yields the original export and a visible warning.
8. Render representative decks for visual inspection: dense events, long names,
   long explanations, and many legs remain readable without overlap. Check
   offline opening, editable text, grayscale reading, and the font minima.

Compare the existing and trial decks for the same mission with the user before
promotion. A reader unfamiliar with the mission should be able to identify
departure, arrival, reduced-redundancy periods, complete outages, and the
remaining transports without a live explanation. Record readability feedback
and export timings. Replacing the established deck requires a separate explicit
user decision; this specification authorizes only the parallel trial design.
