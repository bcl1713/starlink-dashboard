# Operator design reference — approved prototype

Pinned revision: `9ca6297844240eaad86ecdc27e541e01e2e721ef`.
This is a portable copy of the approved fictional-data prototype, not production code.
The owner authorized this sanitized public reference-only branch for issue #425. The hosted Site remains owner-private; this source needs no owner browser session. Application branches are unchanged.

## Give this to Codex

Read this reference folder directly from the immutable commit linked in issue #425:
“Read README.md, run dist/ locally, and use its organization, workflows and stable
controls as the reference for issue #425. Fit the existing application's styling;
do not enforce exact colors, typography or pixels. Inventory and retain existing
Operator controls, including live Overview controls absent from this demo. Do not
copy demo persistence, fixed time or simplified models into production.”

## Run

From this reference folder run:

    python3 -m http.server 8080 --directory dist --bind 127.0.0.1

Open http://127.0.0.1:8080 . No install, build, authentication or API is needed.
Use a fresh browser profile/origin for the initial scenario, or click Reset demo.
The prototype uses localStorage key `operator-design-v3`; browser changes are local.
DM Sans / IBM Plex Mono load from Google Fonts when network access permits;
system fonts are the fallback. Font network access is not required for behavior.

## Reference contract

- Persistent mission context and timeline; shared Operations, Transport, Issues,
  Notes and History navigation. Timeline focuses the corresponding work, never
  performs a state change. Desktop parallel conference/call lanes; narrow screens
  stack them and retain a horizontal timeline strip.
- Established includes successful two-way distant-end testing. No separate Verify
  or Tested action. Conference reuse and customer connection remain independent.
- Establish and Close replace one another in the same fixed primary action slot.
  Reserved title/facts/status regions prevent jumping. No reorder during toggles.
  Idle Close is immediate, no dialog; active calls/connected customers guard it.
  Future scheduled calls and history remain; a later call needs establishment.
- Schedule call can create/select a reusable conference inline without losing the
  draft, or select Direct point-to-point with no dummy conference. Direct transport
  is optional and unspecified coverage is unknown, never implied healthy.
- KA commercial, X-band, Starshield; ad hoc transports can be added. Known outage
  overlap appears on affected call and conference with interval and customer.
  It is advisory only, with no automatic switching/blocking. Predicted PoP
  transitions are distinct from known outages; ad hoc coverage is unavailable.
- All times 24-hour Zulu, with explicit dates for overnight calls. Fixed hour
  00–23 / minute 00–59 selectors avoid browser AM/PM localization. Notes default
  Now, no required precision selection, with occurrence separate from recorded time.
- Cancel/reschedule retain history. Quick capture available across views. Notes
  include a simulated failed save retaining text/time for retry.

## Matching-state review checklist

1. Initial Alpha active, Bravo preparing and KA outage overlapping Bravo.
2. Schedule filled call → inline conference creation → intact draft and selection.
3. Direct call → establish → start → customer connected, no extra test gate.
4. Idle and future-only conference establish/close cycles: same button/card location,
   neighbors stable, active/connected close disabled, no confirmation dialog.
5. Overnight call Oct 28 23:55 → Oct 29 00:15; dates retained and timeline ordered.
6. Move a KA call outside outage: its overlap warnings disappear.
7. Ad hoc assignment: no integrated schedule / health unknown.
8. Cancel/reschedule retained in History; note-save retry retains draft.

Compare structure and workflow, not exact cosmetic pixels. Existing app styles
prevail. Include existing live Overview controls and other production features in
an explicit parity inventory rather than dropping them because the demo omits them.

## Verification and limits

Desktop browser flows above were tested during creation. Conference action/card
bounding rectangles remained identical across idle and future-only toggle states;
neighboring cards stayed fixed. Time controls and midnight preparation rollover
were tested under New York, Singapore and Honolulu with en-US/h12 defaults.
Responsive CSS exists but physical phone/device testing was not performed.
No formal screen-reader, contrast or WCAG conformance audit was performed.

The prototype has a fixed fictional clock, localStorage-only persistence,
review-only History, no capability editor, no actual live Overview controls,
no real synchronization, and no hardware/API integration. It is design reference,
not production architecture. Customer-brief PDF behavior is outside the demo;
its Washington DC time exception remains separate and 24-hour.

No screenshots are included: older static concepts predate the approved refinements.
Run the pinned source for an accurate interactive reference and capture matching
states in the implementation environment if needed.

## Contents and privacy

Only dist/index.html, dist/style.css, dist/app.js, this README and checksums are
included. No hosting manifest, Site credentials, Git metadata, account identity,
browser state, operational data, or private repository content is included.
This publication is owner-authorized. It does not broaden the hosted Site's visibility.

Implementation must follow Overview #426 and preserve its changes. The current issue
#425 requirements supersede historical proposal wording in the frozen demo. Use the
existing application's styling and Title Case; the exact dist bytes are retained
for reproducibility, not as permission to copy prototype limitations into production.
