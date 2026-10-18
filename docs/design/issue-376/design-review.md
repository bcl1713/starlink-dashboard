# Operator workspace design review

Draft for issue 376. No structure or visual design is approved yet. Product code
and API behavior remain unchanged. The [source audit](audit.md) identifies the
preservation requirements and current limitations.

The intended user is the mission communications manager handling simultaneous
customer calls, conference reuse, changing estimates and unresolved problems.
The workspace must make current activity, next preparation and decisions
visible, and place each action beside its context. Overview stays passive;
Missions owns plans and the existing ZIP; Configuration owns global/provider
settings.

## Three different information architectures

| Concept                            | Organizing principle                                                                                                                  | Same busy mission scenario                                                                                                                                                                                                                | Tradeoff                                                                                                                                                                                                                                           |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A. Mission workspace — recommended | Persistent Now/Next awareness; a working area for Operations, Communications, Transport, Issues and History; contextual detail/editor | Two connected customers remain visible. Next preparation is separate from overdue follow-ups. Record move opens beside protected activity. Leave a customer without closing the shared conference; reschedule the next call from its row. | Strong balance across duties; requires disciplined shared state and compact navigation. Mobile editor must retain a small awareness strip.                                                                                                         |
| B. Event desk                      | A chronological event list is the primary workspace; select an event to open its record and actions                                   | Calls/preparation, follow-ups, PoP and restrictions interleave. Select next prep to reschedule; choose a connected interval in a pinned activity area; add unscheduled move from a global action.                                         | Best for event sequence and provenance. Persistent conferences, untimed calls and capabilities need a separate entity shelf; crowded events can bury important customer state.                                                                     |
| C. Communications board            | Call schedule plus persistent conference lanes; issues/transport/history in a utility rail                                            | Reuse ground bridge across two call rows; move from call to customer interval and transport context; urgent unscheduled call inserted with explicit time/status edit.                                                                     | Best for call-heavy periods. Problems, postflight corrections and multi-service transport become secondary; a time grid can suggest false duration precision and compress poorly on mobile. No drag-to-change-time without explicit saved command. |

All three preserve the audit matrix and the same source contracts. B and C are
structural alternatives, not reduced-feature proposals. All retain preflight,
untimed activity, between-leg issues and postflight archive navigation.

## Recommended structure

At desktop width, use the available operational canvas rather than a centered
1280px document. A compact global header retains existing application
navigation. Below it, a mission/leg context bar and explicit simulation/source
state precede a three-part working surface:

- A 280px mission rail contains current customer participation, next
  requirement, and quick actions. It remains visible across working views.
- The central working area defaults to Operations: active communications,
  chronological upcoming events and exception-oriented attention. Navigation
  changes the working area to Communications, Transport, Issues or History.
- A contextual panel opens for the selected record or action. It replaces nearby
  secondary context rather than covering the current customer and next-call
  rail. One active editor has a clearly named target and receipt state.

Operations is a working view, not nine collapsed subsystems. Communications
contains call list plus reusable conferences and customer intervals; Transport
contains reports and advisory review; Issues contains problems, follow-ups and
capabilities; History contains observations and accessible records/revisions.
Display tools and local alert preferences open from the header. Mission records
goes to the existing mission detail page, where preparation/export already work.

Connected activity uses “Reported connected”; a scheduled window uses
“Scheduled”. An established conference never implies a connected customer.
Observed/modelled source details remain available without repeating a paragraph
on each row. Use text plus symbols/color, restrained amber for actionable
attention, and explicit unknown/stale indicators. Never label a model gap as a
service outage.

## Visual review package

Open [the visual gallery](mockups.html) in a browser. It contains the
recommended concept at exactly 1920×1080, 390×844 and 844×390 in normal, busy
and failed-write states. State links and view controls are design navigation
only; all mission records are synthetic. Every depicted operational action maps
to an existing capability in the audit. No backend is connected; preview Save
does not report an accepted operational write.

The normal state has one reported customer and upcoming preparation; busy has
two customers, competing preparation, an overdue issue and modeled advisories.
The failed-write state shows an uncertain save with its pinned mission target,
frozen retry and retained draft, while last-known awareness remains labeled.
Dedicated previews expose call, transport, issue-follow-up, observation and
display editor layouts. These mockups are review artifacts; functional browser
acceptance and actual time-to-action remain subsequent work.

### Portrait at 390×844

Keep the mission bar compact. Put current customer and next requirement above a
short view switcher; the default Operations view presents only the highest
priority current rows, followed by the next timed events and attention. A bottom
action dock offers Add call, Move and Note; the Issues view exposes New issue.
The More view menu exposes History, Display tools, Alerts and Mission records.
It is a 44px-or-larger control rather than a horizontally scrolling tab row.

An action opens a full-screen editor with a compact Now/Next strip and the
explicit mission target. Primary Save stays in reach above safe-area insets; the
editor scrolls, not the whole underlying workspace. Browser keyboard reduces the
usable height; controls must remain reachable without hiding validation. Closing
retains the draft; discard is deliberate. A pending command remains visible and
cannot be silently re-targeted by choosing another mission.

### Landscape at 844×390

Use a compact top context bar, a 240px awareness rail and a working list beside
it. Do not stack the portrait cards or occupy most of the height with a sticky
header. Opening an editor replaces the working list; Now/Next remains visible.
Long forms have one scroll region and a reachable footer. A mobile editor may
require vertical scrolling; no horizontal scrolling is acceptable.

## Key quick-action flows

| Action              | Entry and minimum useful fields                                                                     | Disclosed fields and retained semantics                                                                                                                                                                                         |
| ------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Add/change call     | Add call or next requirement → Reschedule; Scheduled/Log actual mode, UTC date/time, optional party | Type, coordinator, prep (new planned default 10, zero and unknown retained), duration/unknown end, conference lookup, scope/leg, actual exact/approximate/unknown times, note and status; signed shift remains available        |
| Reuse conference    | Communications → conference → Customer joined; direct lifecycle actions                             | Unknown customer accepted as today; select related call afterward or in detail; Join/Leave distinct from establish/close; Restore connection vs Restore record distinct                                                         |
| Applied-only move   | Move → service, Reported Applied transport, Save                                                    | Intended/Requested/Checked independently optional; add service rows, report UTC/precision, reason, call/conference lookup and scope; active-call overlap advisory never blocks Save; changing application clears previous check |
| Follow up issue     | Attention → Update; update text and optional follow-up UTC                                          | Priority, responsible party, mitigation, status and links; Monitor/Resolve/Reopen remain actions; historic correction opens selected update without replaying lifecycle                                                         |
| Observation         | Note → short title and optional text, Save                                                          | Observation time remains unknown unless explicitly supplied or explicitly chosen as now; scope/leg, precision/end semantics, call observation type, operator label and audit note remain accessible                             |
| Display recenter    | Display tools → selected same-browser window → Recenter                                             | Explicit choice with multiple/lost peers; acknowledgment state and existing settings/presets; no remote fullscreen or fabricated cross-device recenter                                                                          |
| Find/correct record | History → record → Edit or Activity → Correct update                                                | Loaded-record text filtering labels incomplete pages; immutable revisions remain paged and inspectable; removed-record Restore revalidates references                                                                           |
| Export/import       | Mission records → existing Missions controls                                                        | One existing mission ZIP, existing PDF and preparation/download/cancel semantics; imported plan does not restore Operator records; no second export destination                                                                 |

Readable selectors resolve IDs from existing mission/leg and record reads;
unresolved historical targets display a missing-link label and retain original
identity in details. No auto-association may silently connect a customer. Offer
the selected call/conference as an explicit default when starting from its row;
unknown/unassigned always remains an option where permitted by the contract.

## Lifecycle and failure presentation

| Situation                      | Workspace behavior                                                                                                                                                           |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Sparse preflight               | Planned timing is labeled; show next preparation and unassigned/untimed requirements; create/reuse conferences; no invented customer connection                              |
| Routine airborne               | Current customers, next requirement and concise backend live ETA/PoP events; source basis available on expansion                                                             |
| High workload                  | Current participation and next future requirement remain pinned; overdue backlog separate; direct contextual actions and nonblocking transport warnings                      |
| Between legs                   | Explicit mission context and chosen record scope; issues and shared conferences are not automatically closed; next leg selected from itinerary                               |
| Postflight                     | History/issue closure and Missions archive navigation; retrospective times distinct from recording times; preserve unresolved work                                           |
| Loading/no mission/disabled    | No temporary zero-count all-clear; explicit loading, Choose mission/Browse missions, or feature-disabled state; keep Configuration boundary                                  |
| Stale/offline/missing provider | Label last-known/as-of; unknown model coverage does not stop operator reports; unavailable store blocks writes with draft retained; no scheduled-time airborne fallback      |
| Pending/lost receipt           | Saving then outcome uncertain; exact retry retains command identity/body/times; receipt accepted and reread failed are distinct; do not display Saved until contract permits |
| 409/two clients                | Show saved version alongside retained draft; explicit reread/reconcile; never overwrite automatically or replace an active draft with a poll                                 |
| Changed store/restart/restore  | Quarantine old-epoch request; explicit target/store recovery; no silent replay into replacement store; retain immutable history                                              |
| Draft storage failure          | Show failure beside draft, retain in memory where possible, avoid claiming reload recovery; navigation must not silently discard content                                     |
| Relationship validation        | Explain affected named record, provide link to correct it; restore targets before dependent records; no cascading delete or invented lifecycle change                        |
| Export failure                 | Existing Missions preparation/failure/download UI remains authoritative; archive/storage unavailable cannot become successful empty history                                  |

## Review and delivery boundaries

The requested approval covers concept A or a named alternative, priority order,
desktop/portrait/landscape hierarchy, and quick-action flows. The initial
priority assumption is connected customers and next-call preparation; the
operator can correct it during review. Approval of this draft does not claim
usability timing, functional acceptance or aircraft readiness.

After explicit visual approval, record that decision and the approved artifacts
in the issue, write the implementation plan and review the written spec. The
plan must address a reversible whole-workspace switch, shared transaction/draft
ownership, accessibility, performance, tests and backout. No implementation plan
or product changes are included in this review package.

Acceptance must execute the issue's complete mission narrative against the real
production Docker/Nginx stack, at all three viewports, including
normal/busy/error states, keyboard/touch/overflow, predictor/flight lifecycle,
two clients, lost receipt/409/store recovery, archive extraction and
clean-instance plan import. Record actual elapsed times and interaction counts
against the same baseline scenario, feature-by-feature parity, source/PR
identity and resource teardown. Existing source-derived counts in the audit are
targets for that measurement, not a substitute for it.
