# Operator workflow audit

Source baseline: `origin/dev` at `1a3e77d3`, fetched 18 October 2026. Issue:
[376](https://github.com/bcl1713/starlink-dashboard/issues/376). Status: source
audit for design review; product UI is unchanged.

The functional foundation supports the mission narrative. The main design
problem is finding and coordinating those functions: a narrow, long page mixes
awareness, unopened display controls, multiple editors and record lists. Saved
records have strong backend authority, but presentation and draft handling vary
by subsystem.

## Evidence boundary

This audit reads current components, types, hooks, API routes and predictor
adapters and compares the existing committed acceptance screenshots. Existing
reports are prior evidence, not a fresh execution of every journey. No new
production Docker/browser parity or elapsed-time measurements are claimed here.
The proposed mockups use explicitly synthetic records. They are design evidence,
not acceptance evidence or connected operational software.

Paths below are relative to the repository root. `C` means
`frontend/mission-planner/src/components/operator/`; `H` means
`frontend/mission-planner/src/hooks/api/`; `B` means
`backend/starlink-location/app/operator/`.

## Feature parity and action matrix

Every row is a preservation requirement. Proposed destinations are explained in
[the design review](design-review.md). “Common editor” means a contextual
desktop side panel or a mobile full-screen editor, with record details and
history nearby.

| Capability and current entry                                                 | Supported transitions and relationships                                                                                                                                                                               | Current friction or limitation                                                                                           | Proposed entry and preserved secondary actions                                                                                                                                          | Source and verification anchor                                                                                                                                                                  |
| ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Mission selection: URL `mission_id`, journal Mission ID form, Missions links | Mission, preflight, leg, between legs, postflight; previous/next leg associations                                                                                                                                     | Raw mission/leg IDs; mission switch lives deep in Journal; latest recorded scope is explicitly not telemetry phase       | Persistent mission selector with readable itinerary/leg names; visibly pinned draft target; scope chooser in common editor; Missions owns itinerary                                     | `pages/OperatorJournalPage.tsx`; `C/OperatorBrief.tsx`; `types/operator.ts`; `pages/OperatorJournalIdentity.test.tsx`                                                                           |
| Quick brief: summary above Display tools                                     | Next requirement separately from overdue; risk, issues, unknown time and incomplete pages                                                                                                                             | Many labels repeated; loaded-page summary may be incomplete; snapshot refresh separate from events                       | Persistent current activity and next requirement, with separate attention queue; source status detail; incomplete coverage stays visible                                                | `C/OperatorBrief.tsx`, `OperatorBrief.test.tsx`; page brief query                                                                                                                               |
| Schedule, reschedule and retrospectively log calls: Communications           | Tentative/scheduled/delayed/completed/cancelled; signed minute/hour shift preserves known duration; unknown duration retained; configurable prep with new planned default 10 minutes                                  | Always-visible editor; raw conference reference; explicit ISO date strings; planned vs actual entry scattered in details | Add call; Scheduled/Log actual modes; labeled UTC date/time; conference lookup; edit/reschedule from call; advanced timing and all nullable fields retained                             | `C/OperatorCommunications.tsx`, `CallEditor.tsx`, `callDraft.ts`, `callTiming.ts`, `CallList.tsx`; communications and call editor tests                                                         |
| Call correction, removal and restoration                                     | Versioned replacement, tombstone/restore; relationship checks prevent invalid removal; never closes conference or participation                                                                                       | Repeated action groups; history separated from context                                                                   | Call detail → Edit, History, More → Remove; History includes removed filter and Restore; cancellation is a status edit                                                                  | `C/CallList.tsx`; `services/operator.ts`; `B/references.py`; `CallList.test.tsx`                                                                                                                |
| Reusable conferences: collapsed Communications disclosure                    | Create, establish, verify, interrupt, restore conference connection, close; intended/configured transport, coordinator, optional timestamps                                                                           | Customer protection hidden behind disclosure; verification easily confused with customer success                         | Communications → Conferences; active conference beside participants; direct lifecycle actions; advanced correction fields and history                                                   | `C/OperatorConferences.tsx`, `ConferenceEditor.tsx`, `ConferenceCard.tsx`, `conferenceCommands.ts`; conference tests                                                                            |
| Independent customer participation                                           | Join/leave/interrupt; restore connection creates NEW interval linked to interruption; correct/remove/restore record distinct from restoring connection; call and/or conference association                            | Raw call ID in row; independent state hidden; must not infer connected from established                                  | Connected customer rows in Now and Communications; direct Leave; interruption/restore in detail; Join on conference; selectors for links; continuity discrepancy remains visible        | `C/ParticipationEditor.tsx`, `ParticipationRow.tsx`, `conferenceProtection.ts`; `B/conference_actions.py`; participation/conference tests                                                       |
| Protected activity and modeled overlap                                       | Connected reports protected with unknown time; conference/call windows separate; optional source failures do not stop controls                                                                                        | Several overlapping context panels; no single concise protected-activity context                                         | Active customer context remains visible during Transport entry; inline overlap advisory with source detail; no acknowledgment gate                                                      | `H/useOperatorProtection.ts`; `C/TransportReview.tsx`; `B/transport_windows.py`, `transport_review.py`                                                                                          |
| Issues and follow-ups: Issues                                                | Create, update, monitor/open, resolve/reopen, reschedule/clear follow-up, remove/restore; resolution clears follow-up and reopen does not resurrect it                                                                | Long editor beside exception list; activity and audit are separate unexplained actions                                   | Attention row → Update/follow up; Issues view; concise issue editor; operational Activity vs immutable History clearly labeled                                                          | `C/OperatorIssues.tsx`, `IssueEditor.tsx`, `IssueFollowups.tsx`; `B/issue_actions.py`, `issue_followup.py`; issue tests                                                                         |
| Historical issue correction                                                  | Select historical message, correct effective UTC/text; correction does not replay resolve/reopen; original revision preserved                                                                                         | Specialized correction workflow hard to discover                                                                         | Issue detail → Activity → Correct update; show effective and recorded UTC; immutable History beside it                                                                                  | `C/IssueActivity.tsx`, `IssueCorrection.tsx`, `issueActivity.ts`; `B/issue_activity.py`; `IssueAudit.test.tsx`                                                                                  |
| Manual capability and redundancy assessments                                 | Independent functional/redundancy values, observation times and precision; edit/remove/restore/history; legacy data preserved                                                                                         | Readiness data below problems; repeated fields; unknown can look like missing administration                             | Issues → Capabilities; exception summary in Now; separate functional/backup observations in detail; never require duplicate crew forms                                                  | `C/CapabilityAssessments.tsx`, `CapabilityEditor.tsx`; `types/operator.ts`; issue/capability tests                                                                                              |
| Operational events: sticky strip → Open events                               | Call prep/start, follow-ups, restrictions, PoP; active/upcoming/overdue/unknown/history; acknowledgment of supported occurrence only                                                                                  | Headline shows counts rather than actionable activity; full timeline takes another opening step                          | Now includes actionable timeline; separate future requirement remains pinned despite overdue backlog; acknowledgment only where backend offers it                                       | `C/OperatorEventStrip.tsx`, `OperatorEventFeed.tsx`, `eventFormatting.ts`; `H/useOperatorEvents.ts`; `types/operatorEvents.ts`                                                                  |
| Local cues: Local alerts popover                                             | In-app cue, sound, vibration; enable/test browser capability; delivery failure; cross-tab coordination and deduplication                                                                                              | Settings compete with operational actions; best-effort semantics must remain clear                                       | Header Alerts control; enabled/muted/failure state; same local preferences and foreground lifecycle                                                                                     | `C/OperatorAlertSettings.tsx`, `useEventAlerts.ts`, `eventAlerts.ts`, `eventEmitter.ts`, `eventDeliveryLock.ts`; alert tests                                                                    |
| Airborne modeled timing and live PoP                                         | Backend live route-aware boundary ETA; preflight planned UTC; live unavailable does not fall back to old schedule; real PoP publication identity                                                                      | Risk summaries and saved timeline context can differ from live feed                                                      | Live events authoritative for airborne advisory timing; basis chip (Live ETA / Planned / Unavailable), expanded provenance; no frontend prediction                                      | `B/production_live_timing.py`, `production_pop_events.py`, `production_event_sources.py`, `event_sources.py`; existing `docs/reports/2026-10-18-operator-events/live-eta/`                      |
| Transport intentions and reports: Transport                                  | Up to 32 service rows; intended/requested/applied/checked independently optional; applied-only supported; exact/approximate/unknown times; reason optional                                                            | Repeated checkbox groups; raw linked IDs; deep page position                                                             | Persistent Record move action; default Reported Applied mode, service + transport; add services; independent stages and optional checks disclosed; full timing and association controls | `C/OperatorTransport.tsx`, `TransportEditor.tsx`, `TransportServiceRow.tsx`, `transportForms.ts`; `types/operatorTransport.ts`; transport tests                                                 |
| Transport correction and checks                                              | Replacing application clears old check unless explicit replacement check; historical reports retained; reference removal/restore rules                                                                                | Check replacement semantics can disappear during visual simplification                                                   | Decision detail → Correct; show clearing check in editor; More → Remove/Restore; History; routing stays unknown                                                                         | `C/TransportDecisionList.tsx`; `B/transport_actions.py`, `transport_models.py`; transport tests                                                                                                 |
| Manual journal observation and correction: Journal                           | Note/call observation, all scope/time semantics, edit/remove/restore, optional audit note and operator label                                                                                                          | Large default editor; manual mission IDs; observation action scrolls to lower form                                       | Persistent Note action; short observation editor; details disclose timing/scope; browse and correct in History                                                                          | `C/JournalEditor.tsx`, `JournalList.tsx`; `pages/OperatorJournalPage.tsx`; journal/editor tests                                                                                                 |
| Immutable audit and provenance                                               | Per-record paged history, original/replacement values, actual/planned/recorded UTC, operator/source/version and removed state                                                                                         | Raw relationships; repeated histories across panels; no consolidated text search in record API                           | History view filters loaded records and explicitly shows incomplete pages; record detail → full paged immutable revisions; readable links; no claim of backend full-text search         | `C/JournalHistory.tsx`, `RevisionDetails.tsx`; `B/queries.py`, `projections.py`; journal history tests                                                                                          |
| Shared Overview display settings                                             | Shared visibility groups (link/metrics/map/panels/aircraft/boundaries), history window, Normal/Communications/Weather preset save/apply with versions                                                                 | Large settings block precedes communications; global effect needs to stay explicit                                       | Display tools drawer, supported groups and preset actions; global scope label; Configuration link; no fullscreen command                                                                | `C/OperatorDisplayTools.tsx`, `OverviewPresetsCard.tsx`; `pages/OverviewLinkSettingsCard.tsx`, `OverviewBoundarySettingsCard.tsx`, `OverviewHistorySettingsCard.tsx`; display tests             |
| Overview window discovery and recenter                                       | Same-browser connected peer selection; no/multiple/lost peers; acknowledgment/unsupported/timeout/expired/failure; open Overview                                                                                      | Easily mistaken for cross-device control; needs explicit target with multiple peers                                      | Display tools → target window + Recenter; optional header shortcut only after unambiguous selection; shared settings and local window command have distinct scope labels                | `pages/OverviewDisplaySettingsCard.tsx`; `hooks/useOverviewDisplayController.ts`; existing display acceptance                                                                                   |
| Mission ZIP and plan import                                                  | One ZIP: existing customer PDF path, planning data, telemetry per leg, journal/current/history, checksums/timing; preparation, cancellation, failure/download states; normal import does not restore Operator records | Export lives elsewhere; unrelated legacy docs sometimes describe integration as future                                   | Header Mission records link to existing mission page/export; preserve ExportDialog/ImportDialog, no duplicate export engine/status invention                                            | `components/missions/ExportDialog.tsx`, `ImportDialog.tsx`; `services/export-import.ts`; `backend/starlink-location/app/mission/package/operations_archive.py`; archive report and export tests |
| Save/receipt/conflict/store recovery across all commands                     | Frozen retry key/body/time; expected version; epoch/store identity; save acceptance vs current reread; 409 reconcile; invalid/unavailable store                                                                       | Recovery text/actions vary; pending state must survive navigation; success cannot be optimistic                          | Common transaction status by action; same hooks/contracts; retained draft and explicit reconcile; store change quarantines old save; pending target always visible                      | `H/useOperatorJournal.ts`, `operatorReadSession.ts`, `useOperatorEvents.ts`; `services/operator.ts`; identity/recovery tests                                                                    |

## Saved state and read ownership

`types/operator.ts` defines full record time semantics, payloads, provenance,
associations, pagination and command receipts. `types/operatorTransport.ts` and
`types/operatorEvents.ts` add independent report stages and event source
identity. These remain backend contracts. `services/operator.ts` calls health,
paginated records, single record and history, and typed
create/update/remove/restore routes under `/api/v2/operator`. Writes carry
`Idempotency-Key` and `X-Operator-Store-Epoch`; replacements carry
`expected_version`. `services/operatorEvents.ts` validates the identity and
generation of every event page before assembling a snapshot and acknowledges the
supported occurrence.

`H/operatorReadSession.ts` shares health reads at 15 seconds. Event polling uses
15 seconds visible / 60 seconds hidden; record queries are keyed by mission,
store identity and type. Presets currently poll at five seconds when mounted.
The redesign must not mount a separate event hook for every awareness surface or
unmount the transaction owner when changing views. Hidden heavy settings should
remain lazy; displaying a new view must not reset a frozen save or start
duplicate polling. Pagination must not silently become a complete mission
summary.

Issue/capability drafts use `H/useOperatorIssueDraft.ts`; transport uses
`H/useOperatorTransportDraft.ts`, both session storage with explicit failures.
Frozen pending commands are retained across reload by `H/useOperatorJournal.ts`
only for callers enabling `durable: true` (issues, capabilities and transport);
the default is false for generic journal, calls and conference/participation.
Other pending commands remain in memory while their owner stays mounted. In
contrast, the unsent Journal editor, calls and conference/customer drafts use
React state; their unsent content is not uniformly recoverable after reload.
`OperatorJournalPage` aggregates journal/call dirty flags, while issue/transport
have independent owners. Central mission/navigation handling therefore requires
deliberate preservation across every editor; the baseline does not establish a
universal draft registry.

## Workflow findings

Working by source contract: independent conference/customer lifecycle; planned
and retrospective calls; quick applied-only reports; issue correction without
replaying lifecycle; immutable tombstones/history; exact retries; live ETA and
PoP adapters; one existing mission package. Preserve all of these rather than
replacing them with summary-only cards.

Awkward: anchor links move through a long page; critical customer state is
inside a closed disclosure; editors are open without an immediate task; names
are not resolved consistently; source explanations repeat; mission choice is
below the operational sections. The stored summaries, feed and protection views
have different freshness and pagination boundaries, which must remain
inspectable even when reduced to compact indicators.

Missing in the baseline: a cohesive priority workspace, consistent relationship
lookups, universal unsent draft recovery and a measured whole-mission usability
baseline. These are design/verification work, not evidence of missing backend
record operations. Do not infer a new routing controller, predictor, database
search endpoint or archive engine from these gaps.

## Initial interaction baseline

Counts below are source-derived navigation/command activations starting at the
Operator page top, with the mission already selected and relevant data loaded.
Typing and native selector operations are excluded. They are not timed user
measurements. Scroll distance, keyboard use, data entry and error recovery must
be measured separately in the implementation acceptance run.

| Journey                    | Current source-derived path                                            | Recommended target                                            | What still needs measurement                                                 |
| -------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Inspect next event         | Read strip, Open events (1) for details                                | Read pinned requirement, detail (1)                           | Recognize customer vs preparation; future visibility with overdue items      |
| Add scheduled call         | Communications anchor, Schedule call, Save (3)                         | Add call, Save (2)                                            | UTC entry, optional prep and relationship entry                              |
| Change call time           | Communications anchor, Edit call, Save (3)                             | Visible requirement → Reschedule, Save (2)                    | Shift vs absolute time; unknown duration; other calls via list               |
| Applied-only transport     | Transport anchor, fill existing editor, Save (2) plus Applied checkbox | Record move, Save (2), Applied mode already selected          | Service/transport selection and advisory comprehension                       |
| Issue follow-up            | Issues anchor, Add update/follow up, Save (3)                          | Attention → Update, Save (2)                                  | Future/unknown follow-up, resolved issue correction                          |
| Observation                | Record observation scroll/focus, Save (2)                              | Note, Save (2)                                                | Less scroll, short fields, keyboard handling                                 |
| Recenter selected Overview | Display anchor, Show controls, Recenter (3)                            | Display tools, Recenter (2)                                   | Target choice required with multiple windows; timeout feedback               |
| Correct historical entry   | Journal anchor, locate/filter entry, Edit, Save (at least 3)           | History, find entry, Edit, Save (at least 3)                  | Loaded-page search coverage and audit navigation; no claimed count reduction |
| Prepare/export mission     | Mission planning link, existing mission export control, Export         | Mission records link, existing mission export control, Export | Existing preparation/download latency; no claimed reduction                  |

## Design questions

The updated issue also requires a task-based shipped Operator guide, annotated
desktop/mobile screenshots, mission quick reference and discoverable Help entry.
Treat those as acceptance checklist items, with each procedure validated against
real shipped controls and first-time completion without verbal coaching. See
[revision 3](revision-3.md); prototype orientation is not the full product
guide.

The initial recommendation prioritizes reported connected customers and
next-call preparation during high workload. Confirm whether transport/problems
or schedule management should dominate instead. Also review the quick-action
wording and the mobile split between persistent awareness and a dedicated
editor: neither should imply that logging a report changes physical routing.
