# SIGMET attention and map inspection

Status: proposed for review. This supersedes the presentation and inspection
behavior in the earlier route-linked SIGMET design; its geometry and resource
limits continue to apply.

## Intent

Overview is a ten-foot display. It should attract attention to actionable
SIGMETs without filling the screen with operational status. Configuration is a
compact place to manage relevant advisories, rather than a catalogue of the feed.
Users can inspect other SIGMETs directly on the map.

The user approved acknowledgement from Overview and shared, persistent manual
selections tied to the current route. Manual selections remain until
acknowledged, expired, or cancelled.

## Overview

- The attention set is the union of unacknowledged, confirmed geographic route
  intersections and unacknowledged manual selections. Count each bulletin once,
  including when it has multiple polygons or is both intersecting and selected.
- With an empty attention set, render no SIGMET status box, count, placeholder,
  detail cards, or reserved panel space. Unknown intersection results do not
  create automatic notices. Silence does not change the underlying weather or
  geometry result into an assertion that the route is clear.
- The status box contains only `SIGMETS: N`. Remove route names, source labels,
  incomplete/unknown counts, overflow prose, and the coverage disclaimer from
  the Overview attention area.
- Give pending cards bright borders and a slow, smooth pulse. The status box
  pulses in the color of the highest-priority pending card. Match each card's
  color to its map emphasis; keep the color stable across ordering and refreshes.
  Respect reduced-motion preferences with a steady bright border.
- Show concise cards: bulletin identifier, hazard/severity, and either route
  segment or `Selected`. Expand to view full report, vertical bounds, and validity
  times. Do not imply altitude or passage-time matching has been evaluated.
- Each card offers Acknowledge. Remove it only after the server confirms the
  action. Show a compact error on that card if saving fails.
- Preserve a maximum of three expanded attention cards in the desktop rail.
  Provide compact previous/next controls when needed; every pending advisory must
  be reachable and included in the count. A newly selected bulletin is brought
  into view. Mobile uses the same information without horizontal overflow.

## Map inspection

Keep SIGMET polygons available on the map so users can select a bulletin that
does not intersect the route. The default filter applies to automatic attention
cards, not to hiding every other selectable polygon. Retain an optional map-only
intersecting filter, clearly labelled as a polygon visibility preference; it
does not broaden Configuration or change the attention count.

Clicking or tapping a polygon opens its details and adds that bulletin to the
shared attention set. Label a nonintersecting selection `Selected`, never
`Intersecting`. Clicking an already pending bulletin focuses its existing card
without adding duplicates. Clicking a cleared bulletin explicitly reopens it.
For overlapping polygons, show a compact chooser of the hit bulletins rather
than silently choosing one. Preserve globe dragging and existing station picking.
Provide keyboard-accessible inspection for SIGMETs rendered in the current map
view; do not add a global feed list to Configuration.

Manual selection requires a current route context and a current, eligible report.
Without a route, map inspection may show report details but cannot create a
route-owned persistent selection. Disable that action with a local explanation.

## Configuration

Show compact Pending and Cleared sections containing confirmed route
intersections and active manual selections only. Use one summary row per
bulletin, with identifier, hazard/severity, origin (`Intersecting` or `Selected`),
and an action. Full report text is collapsed by default. Cleared is collapsed
by default. Remove the unknown, future, and unrelated feed catalogues.

Acknowledging a route intersection moves it to Cleared and offers Show again.
Acknowledging a selected-only bulletin removes it from both sections; clicking
its polygon can select it again. If a bulletin is both selected and intersecting,
acknowledging it clears both reasons and retains its intersection in Cleared.

Keep acquisition/evaluation diagnostics and save failures accessible in collapsed
details in Configuration. They do not populate the Overview attention box.

## Shared state and contracts

Extend the existing backend notice service and bounded persistent notice store
to track selection separately from computed intersection. The backend remains
authoritative; component state and browser storage do not own selections.
Represent selection origin explicitly in the response. Do not manufacture route
spans to make a manually selected bulletin fit the existing intersection model.

Add an idempotent selection mutation carrying the current route context and
bulletin semantic identity. Validate it against the current admitted feed under
the existing route/state locking rules. Reject stale-context and stale-report
mutations with a conflict response and refresh the client. Retain the existing
acknowledgement identity protections and no-store response behavior.

Scope state to the existing ordinary-route or simulation-run context. Changing
routes stops showing the previous route's selections; returning to a retained
context restores its still-eligible state. Refreshes and other connected
displays converge through the existing shared polling source. Expired and
cancelled reports disappear. An amended selected bulletin follows its known
lineage and returns as pending for the new semantic report, as an intersecting
amendment does. Never carry acknowledgement to a semantically changed report.

Maintain bounded state sizes and context retention, atomic updates, worker
cancellation, shared data ownership, GPU budgets, and disposal. Migrate existing
notice state explicitly; do not discard acknowledgements or silently overwrite
unrecognised/corrupt state. Preserve existing API consumers through compatible
additions where possible; update all in-repository consumers together when a
contract must change.

## Acceptance

Verify zero-result silence, concise counts, bulletin deduplication, stable colors,
motion preferences, and pending-card navigation. Verify compact Configuration
with a large feed and only a few relevant bulletins.

Exercise actual map picking for intersections, nonintersections, overlaps,
dateline polygons, and hidden far-side polygons. Test click-versus-drag behavior
and keyboard inspection. Verify selection, acknowledgement, reopening, failed
saves, and stale mutations in both views and across two browser contexts.

Backend tests cover restart persistence, route/run switches, state migration,
amendments, expiry, cancellation, duplicate selection, and concurrent mutations.
Production-browser acceptance uses the synthetic route/feed and the real API
and renderer. Capture Overview with no attention, new attention, selected-only
attention, and Configuration with Pending and Cleared on desktop and mobile.
Run acceptance with explicit wall-clock limits and verified resource cleanup.

The existing LAN review instance remains running at the user's request. Do not
replace it during implementation; deploy the revised review build separately
until its checks pass, then report the new URL for critique.
