# Prototype orientation and discoverability

The user reported difficulty navigating the downloaded demo. This is a usability
finding before design approval. The latest [standalone HTML](review-v2.html)
opens with Start here when opened without scenario parameters. Start here / Help
remains visible afterward. Product implementation and design approval remain
pending; this revision does not create an implementation plan.

## Friction and changes

The report does not contain a click-by-click session. These specific friction
points come from inspecting the previous preview, rather than attributing
unobserved mistakes to the user.

| Previous affordance                                | Friction                                                                                              | Change                                                                                                                                                          |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A/B/C, Comms, Move and source links mixed together | Concept comparison, reset and view switching looked interchangeable; abbreviations needed explanation | Demo options separates named concepts and synthetic scenarios; reset warns that it clears local edits. Ordinary working views use full names.                   |
| No orientation inside the download                 | Fixture and supported interactions had to be inferred                                                 | Start here explains navigation, the busy mission, editor entry/exit, a practice sequence and the interaction legend. It is reopenable and keyboard dismissible. |
| Placeholder actions wrote status at the bottom     | Clicking could appear to do nothing, especially on mobile                                             | Visible Illustrated only badges; these controls open a purpose/limitation explanation while preserving the underlying view and draft.                           |
| More and generic workspace-tools wording           | History/Display/Alerts/export were hard to locate                                                     | Tools explicitly lists History, Overview display controls, local alerts and mission ZIP examples. Help names the path.                                          |
| Save resembled an operational write                | No backend exists in this prototype                                                                   | Preview save performs local validation/feedback; orientation explicitly distinguishes in-page drafts from reload/reset recovery.                                |
| Drafts and Keep draft as exit clues                | Closing, returning home and resuming were unclear                                                     | Drafts / close, Keep draft & return, and the persistent Review retained work → Resume move path.                                                                |

## Using the standalone file

Download `review-v2.html` and open it in a browser. CSS/JavaScript are embedded;
no server, other files or internet are needed. Start here appears on an ordinary
open. Choose Start here / Help to reopen it.

1. Start at Operations: find Echo's 14:35 UTC call and 14:25 preparation.
2. Communications → Customer left Alpha. Bridge A stays established. Interrupt
   Bravo, then Restore Bravo connection to inspect the separate interval
   behavior.
3. Transport opens Record applied move. Enter service/transport and Preview
   save. Empty service triggers validation; the active-call advisory requires no
   acknowledgment.
4. Keep draft & return goes to Operations. Review retained work → Resume move
   returns the entered value within this page.
5. Mission / scope separates active flight from record association. Tools lists
   History, Display, Alerts and mission ZIP examples. Illustrated only actions
   explain their intended destination instead of silently doing nothing.
6. Demo options compares layouts or resets planned/unavailable/keyboard
   scenarios. Reset/reload clears demo edits; normal view switching does not.

Interactive previews include navigation, forms, local conference/customer and
issue commands, draft parking and validation. History search, observation entry,
real export/import, display recenter, alert delivery and external mission
changes are illustrated destinations. Unmarked cards/times are synthetic
reference data. The drawn keyboard is a layout constraint, not a real mobile OS.

## Mandatory shipped Operator guide

The updated issue 376 requires a comprehensive repository guide, reachable from
the final UI's **Help / User guide** without obscuring live mission context.
Author and validate it alongside the actual implementation. This orientation is
not that guide and does not satisfy the issue's completion criterion.

Proposed files: `docs/operations/operator-user-guide.md` and a one-page
`docs/operations/operator-quick-reference.md`. Help must use the maintained
documentation in the deployment's offline environment; the final presentation
belongs to the approved design and later implementation plan. Do not invent
shipped click instructions from mockups.

Required coverage:

- Setup/prerequisites; navigation and mission/leg/scope selection; annotated
  screenshots of the actual desktop/mobile controls.
- Synthetic preflight, airborne, between-leg and postflight walkthroughs;
  concise high-workload mission checklist and quick reference.
- Calls/VTC planning, resequencing, ad-hoc and retrospective entries; UTC,
  preparation, duration and exact/approximate/unknown time behavior.
- Reusable conferences versus customer participation; establish/verify,
  join/leave/interrupt/restore and correction/immutable history.
- Transport intended/requested/applied/checked reports; live ETA/PoP semantics;
  reports do not route or independently verify traffic.
- Issues, mitigation, follow-ups, capability/redundancy observations and
  historical correction; notes, search coverage and immutable audit history.
- Foreground alerts; shared Overview presets/settings and explicit same-browser
  recenter target/receipt behavior.
- One mission ZIP: preparation/download/failure, customer PDF extraction, plan
  transfer, telemetry and Operator archive; ordinary import does not restore
  destination Operator history.
- Stale/unavailable feeds, offline browser, unsent/pending saves, uncertain
  receipt and exact retry, conflict/reconciliation, changed store and export
  failures; recovery without duplicate records or silent retargeting.

Every procedure must map to a real production-browser journey at the shipped
commit. Check labels, navigation, receipt/error behavior and screenshot
viewport/state; use sanitized synthetic examples. Guide/quick-reference delivery
and Help discovery become explicit parity/acceptance checklist entries.

First-time operator acceptance must run without verbal coaching, using
onboarding and Help. Record task completion/time/interactions, mis-selection,
help retrieval, recovery and specific confusion. Fix avoidable UI
terminology/navigation problems; document the remaining complexity. Automated
prototype checks do not establish that human acceptance or the accuracy of a
not-yet-shipped guide.
