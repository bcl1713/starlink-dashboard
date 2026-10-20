# Operator transport decisions and model-risk review — #369

Status: reviewed for implementation planning, with the link-integrity correction
requested in PR #380 comment 6250609309 incorporated. The user authorized
planning; product implementation requires separate plan approval.

Parent: #361. Existing baseline: `origin/dev` at `76277248` (PR #379).

## Purpose and boundaries

Give the mission communications manager a concise account of intended service
transport, requested changes, reported application and operator checks,
alongside the communications activity and modeled restrictions relevant now and
ahead. Examples: “VTC requested on X-band; operator reports Starshield applied”
and “IPTV moved to Ka to preserve Starshield bandwidth.”

All decisions are human reports. Operator Checked means someone reported
checking the result; it does not establish which network carried traffic. Actual
routing remains unknown. Neither configuration reports nor Starshield traffic
establish SDR, OSPF or call routing. No commands to routing, SDR or aircraft
systems exist.

Keep the current Operator feature gate, local HTTP deployment and single mission
manager/counterpart model. Preserve Overview, Missions, Configuration, existing
conference lifecycle, notification policy and mission-package contracts. The
broader interface redesign and operations-package integration remain issues #376
and #370. No infrastructure, approval workflow or confidence acknowledgment is
added.

## Approach and alternatives

Extend #362 with a typed transport-decision record and correlate its reports
with the existing #368 event snapshot, including #379 live ETA data. This
retains one write authority and one prediction/publication authority.

Using conference configuration fields alone cannot describe IPTV, multiple
services or independent requests and checks. A separate assignment database and
prediction pipeline would duplicate persistence, source freshness and ETA logic.
Neither alternative is selected.

## Durable decision contract

Add `transport_decision` as an additive record/payload type through the existing
Operator record API, complete-replacement revisions, journal sequence,
provenance, idempotent receipts, expected-version conflicts and remove/restore
semantics. Retain schema-v1 envelope conventions; document the additive type as
requiring this application version. Existing `transport_report` remains a report
of transport availability, not a service allocation.

One record describes one decision affecting one or more service rows. A row has
a stable UUID, a nonblank service label (suggestions include secure voice, VTC
and IPTV; custom labels allowed), and the following independent optional
reports:

| Field              | Meaning                                                                                     |
| ------------------ | ------------------------------------------------------------------------------------------- |
| Intended transport | Intended choice: Starshield, Ka, X or explicitly Unknown                                    |
| Requested          | Whether a change was requested, target transport and optional UTC time/precision            |
| Reported Applied   | Whether an operator reports application, reported transport and optional UTC time/precision |
| Operator Checked   | Whether an operator reports a check, optional UTC time/precision, result and optional note  |

Each report has an explicit present/absent discriminator. A present report with
unknown time or transport differs from no report. Check results are
`satisfactory`, `issue_reported` or `unknown`; never “path verified.” Requested
and applied transports may differ from each other and from intent. A check is
associated with the application report in its own row, or is a standalone result
when no application report exists. Do not require or synthesize earlier stages.

Changing an application report clears a prior check from the current revision
unless the same submitted revision explicitly supplies a replacement check. The
editor makes that clearing visible. Earlier application/check pairings remain in
immutable history. Intent/request edits alone do not erase application facts.

Decision fields include optional reason, optional notes, optional call and
conference references, and optional planned change start/end. Reuse mission,
leg, preflight, between-leg and postflight scope. The UI generates the required
base title from service labels; it does not demand another title field.
Operational reason is separate from the automatic audit description. Changes and
corrections receive automatic audit text when an operator gives no reason.

Allow 1–32 rows per decision, service labels up to 200 characters, reason up to
1000 and notes up to the existing 8000-character limit. Reject duplicate row
IDs; allow the same label across separate decisions and across distinct rows
where the operator deliberately describes separate activity. References, if
supplied, must satisfy existing same-mission/type rules. Preserve existing
`dependency_conflict` semantics: an active decision blocks removal, type change
or cross-mission movement of its call/conference target. Explicitly unlink or
remove the decision first; do not cascade or permit active dangling links.
Unlinking appends a revision and retains the historical reference. Restoring a
decision revalidates its stored links and fails if a target is removed, missing,
wrong-type or in another mission; restore/reconcile targets before retrying.
Moving a decision across missions requires clearing or replacing its links in
that same update. Recovery rebuilds links only from current nonremoved records
and validates both ends with the same rules. Historical references can display
removed/missing targets without becoming active links.

### Time and historical changes

Every operator-entered time is editable or clearable in a correction: planned
change start/end, request time, application time and check time. Each report
time uses exact/approximate/unknown precision; null means unknown. UTC is
explicit in entry and display. Reuse existing actual-time acceptance tolerance
and reject malformed/future actual reports; future intention belongs in planned
time. Validate start/end ordering, but do not require chronological ordering
between request, application and check: retrospective reports can describe
unusual sequences. Show the entered facts without silently normalizing them.

Server acceptance `recorded_at`, command IDs and journal sequence remain
immutable audit metadata, distinct from editable reported times. A correction
appends a revision; history exposes original and corrected values and when each
was saved.

A later operational move creates another decision, rather than editing an old
application into a new move. Editing corrects the original decision or completes
its reports. For example, IPTV can move to Ka at 16:10, then back to Starshield
at 17:00 in a second decision, while the original reason/time remains
inspectable. Multiple service rows commit atomically in one record revision;
rows can have different target/applied transports and times. Adding a later
application is not an automatic completion of the request or a conference status
change.

No authoritative current-routing projection is added. The list shows separate
decisions with their own scope/time; unknown or contradictory reports remain
visible. Never infer configuration across legs or choose facts by save order.

## Persistence and API integration

Extend `models.py`, `payloads.py`, public DTO unions in `api_models.py`, typed
relationship derivation/validation and matching frontend types. Use existing
`/api/v2/operator/records`, record history, remove and restore endpoints. Public
provenance remains operator-reported and is not caller-selectable trusted data.
Use existing store identity, API epoch, simulation-run and mission admission.

The initial SQLite migration restricts record types with a CHECK constraint.
Introduce numbered migration 003 to admit the new type; never edit migration 001
or its checksum. Preserve all existing rows, foreign keys, indexes, immutable
revision/receipt triggers and journal sequence high-water mark during the
transactional table rebuild. Exercise rollback and foreign-key integrity checks.
No parallel decision store or writable transport-assignment cache is introduced.

Before upgrade, use existing backup/restore tooling. An older application must
fail explicitly on the newer schema. Backout restores the pre-upgrade backup
with the matching old version, preserving the newer backup separately; do not
strip decision records or downgrade a database in place. With the feature off,
normal missions and Overview remain available without opening the Operator
store.

## Risk correlation using existing snapshots

Add a small pure correlation module, not a predictor. Its inputs are decision,
call, conference and participation records at a journal high-water mark, plus
the already captured event snapshot and its sources. Its output is ephemeral
review context. Attach it additively to the existing event snapshot response,
computed within its existing version/publication admission and snapshot token
boundary. No second adapter capture, new timer, source projection or prediction
service is allowed. Pinned pagination includes the same review result for every
page; the UI must not derive an all-clear from the first page of a truncated
feed.

Keep the module separate from prediction physics and ledger reconciliation.
Existing event kinds, occurrence IDs, acknowledgment generations and
notification thresholds retain their meaning. Review rows reference those
existing event IDs and source revisions; they do not manufacture new restriction
notifications. Do not write journal decisions or new durable risk entries on
snapshot refresh.

### Operative timing and freshness

Consume `OperationalEvent.due_at`, `end_at`, `state`, `time_basis`, freshness
and matching `SourceCapture` from `event_feed.build_snapshot`. Production
continues through `ProductionEventSources`, `refresh_boundary_times` and the
existing live PoP producer. Preflight permits `planned_utc`; airborne requires
`live_route_eta` for restrictions and the actual #348 live PoP publication for
PoP advisories. `planned_due_at` and `planned_end_at` are reference details only
in flight.

Do not add delay offsets, buffers, a second ±5-minute handover window or a new
ETA calculation. Use the actual #348 advisory window and classification. Passed
boundary timestamps identify present model state; they are not historical
crossing observations. Unknown/ambiguous route progress, stale position/speed,
missing coverage/catalog, misaligned sources, changing-source previews and
`live_unavailable` yield explicit unknown or partial assessment. Last known
context may remain visible with its age, never as a fresh all-clear.

Position/speed/route updates recompute review context through existing feed
refresh/invalidation. Departure delay, deviation/rejoin and speed changes move
restriction timing and the current overlap assessment together. Operator times
and reasons are never changed. Historical decisions are displayed from journal
revisions; no historical overlap claim is reconstructed using today's route.
Capturing an original prediction assessment as a durable decision fact is out of
scope; a reason manually entered at the time remains exactly as entered.

### Communications and change windows

Show these independently alongside restrictions and decisions:

- Upcoming scheduled/delayed calls and their existing preparation lead windows.
- Active call intervals, including an actually started call until its recorded
  end/completion, and scheduled intervals covering now; label which basis
  applies.
- Established conferences without inferring customer presence from
  establishment.
- Connected participation linked to calls and/or conferences, using #366
  records.

Known call windows extend from existing preparation start through planned end;
actual start/end take precedence for current activity. Missing end remains
open-ended/unknown rather than inventing a duration. Connected customer activity
is protected even when a call or transport association is unknown. A completed
or cancelled call is not a future requirement; it cannot close a shared
conference or end an independently connected participation record.

Review planned change intervals against communications windows, and reported
application instants against activity at that reported time where recorded
intervals establish it. For a decision with no planned time and no application
report, the editor may show “if changed now” context explicitly labeled as a
preview; it must not save that assumed time. A retrospectively entered time with
insufficient historic activity evidence yields unknown historical overlap.

Use half-open intervals `[start, end)` and instant membership
`start <= t < end`; touching endpoints alone do not overlap. An unknown required
boundary yields possible overlap/unknown, not no overlap. Known ongoing activity
extends through now, without asserting when it will end. Future change overlap
with its unknown end is possible, not guaranteed.

For scheduled calls/preparation, compare the operative restriction windows with
the relevant intended/requested/reported transports independently. For planned
change warnings, include intent and requested targets, and preserve reported
applied mismatches. Only explicit call/conference links associate a decision
with a specific customer session; matching the label “VTC” alone proves no link.
Unlinked decisions still show mission/leg communications nearby and warn of a
possible impact when relevance is unknown. Mission-scope records are visible
alongside applicable legs; a leg-scoped decision does not match another leg.

Keep every overlapping restriction and its provenance; do not collapse a Ka
restriction plus X concurrency restriction plus PoP transition into one outage.
Unknown actual routing stays explicit even with a requested/applied match or a
satisfactory check. Use existing continuity classifications for availability:
Starshield stays modeled available unless explicitly disabled/marked down;
unknown PoP or handover timing is no service outage. The existing sole-usable-
Starshield full-window planning rule and usable Ka/coordinated concurrency-only
X fallback stay unchanged. Generic X concurrency availability does not establish
that an operator coordinated fallback.

Review results distinguish known overlap, possible impact with unknown
relevance, unknown assessment and no overlap found in available inputs. The
latter is not a service guarantee. Include dependent record versions and
event/source identities so clients can show snapshot age and detect superseded
context. A stale review never prevents recording a decision.

## Operator experience

Add a Transport section to the existing responsive Operator shell. Keep the
existing event strip and reuse the page's event query. Present a concise
decision list, a service-row editor and adjacent communications/restriction
context. Desktop can place context beside the editor; mobile stacks it with the
relevant summary visible before optional details. Use keyboard-accessible
controls and text labels rather than color alone.

Default entry asks for services and whichever fact the operator wants to record.
Intent, Requested, Reported Applied and Operator Checked appear separately; each
can be added directly. Optional reason, notes, scheduling and relationships stay
progressively disclosed. No scheduled call, conference, reason, verification or
earlier workflow stage is required. Unknown times/transports are supported.
Provide “Record another move” and “Correct this decision” as distinct actions.

Show optional check wording near its control: “Operator-reported check; actual
routing unknown.” Avoid repeating a modal disclaimer. Illustrative cards:

- “VTC — Requested X-band · Reported Applied Starshield · Not checked.”
- “IPTV — Reported Applied Ka at 16:10 UTC · Preserve Starshield bandwidth.”
- “Change overlaps active customer communications” with activity links and
  timing.

Warnings are inline advisories, including during saving; there is no confirm-to-
proceed dialog, required acknowledgment or protected-call save block. No
separate sound/vibration notification class is added; existing restriction
notifications continue using their existing policy and refreshed ETAs.

Reuse durable store-bound drafts, frozen idempotent retry, saving/saved cues,
explicit conflicts and changed-store reconciliation. Never show success until a
receipt arrives. An uncertain network outcome keeps the submitted command frozen
and retries with its original key; editing then saving uses a new command only
after reconciliation. Mission/leg switches must preserve the draft's original
association and cannot silently move it. Do not silently overwrite another
client's changes or queue background mutations while offline.

## Verification and acceptance

The [acceptance specification](2026-10-18-operator-transport-acceptance.md) is a
required part of this design. It defines backend contracts, real predictor/ETA
integration, production desktop/mobile journeys, failure/restart controls,
migration checks and resource cleanup.

## Review and next gate

The posted review and user instruction authorize implementation planning after
this integrity correction. Product changes require subsequent plan approval.
