# Overview Customer Flight Events and Shared Advisories

Status: Proposed; awaiting design approval before implementation.

Source: [Issue #426](https://github.com/bcl1713/starlink-dashboard/issues/426).
Owner correction in this session: implement the customer view through the
existing customizable Overview presets, rather than URL-based audience modes.
This supersedes the issue's proposed independent per-window audience mechanism.
Inspected base: `origin/dev` at `882a7c1e651cb6fa51034503378566454521e7b4`.
Worktree: `.worktrees/issue-426-overview`; branch: `feat/issue-426-overview`.

## Intent and Boundaries

Make the passive Overview readable on the customer big screen while retaining
concise transport awareness in both customer and operational windows. Customers
see the next flight event; operators can acknowledge individual advisories once
for all polling Overview clients. System-generated labels use the vocabulary in
issue #426, with Title Case, Starshield, KA and X-Band. Touched time surfaces
use 24-hour Zulu with explicit date rollover.

Extend the existing customizable presets; keep shared map layers, unrelated
Overview panels and manual destination behavior. Keep detailed diagnostics in
Operator. Do not change transport commands, call establishment, conference
creation, prediction models, the broader Operator redesign in #425,
user-authored text, API transport enum values, or historical records. Do not
introduce estimate acknowledgments or plan save gates. The customer briefing PDF
retains its daylight-aware America/New_York, 24-hour exception.

## Existing Behavior and Findings

- `overview-arrival.ts` selects NEXT POI from route-ordered typed events without
  consulting map visibility. Consequently a hidden transport event still takes
  the next-event slot. Departure, movement, arrival, manual destination,
  freshness and replay time already have separate branches to preserve.
- `OverviewArrivalPanel.tsx` and its projector compare display strings,
  including `SCHEDULED DEPARTURE` and `LANDING`. Those comparisons must become
  semantic keys before changing text.
- `OverviewPopAdvisories.tsx` selects the first raw status PoP window. It does
  not use the shared acknowledgment ledger and does not support KA or X-Band.
- The existing event feed already projects PoP windows, modeled transport
  restrictions and combined call outages. It persists occurrence/severity
  acknowledgments and preserves history. Audible eligibility deliberately
  excludes PoP windows; it is unsuitable as the Overview visibility predicate.
- `event_eligibility.py` supplies a backend `threshold_at`: restriction start
  minus 300 seconds; PoP window start with no additional lead. These provide a
  supported visibility boundary without a new frontend outage threshold.
- `readEventSnapshot` assembles pinned pages, but needs explicit validation of
  incomplete terminal pages and source mode/run identity as well as its existing
  token/generation checks. Partial results must never publish.
- Operator exposes the actual operating context separately from the mission
  selected for browsing. Its identity includes store, epoch, mode and the
  journal's operating-context/run identity. Overview must use the active
  context, health and event snapshot together, including event-level leg and
  replay/context fields.
- Existing generated POIs are persisted. Changing generators alone would leave
  old wording on already prepared missions.

## Approaches

The recommended approach follows the owner's session correction: extend the
existing shared settings and customizable presets, plus a narrow read-only
client of the existing shared event feed. It preserves one source of prediction
and acknowledgment truth and avoids mounting audio or command controllers in
Overview.

Extending the raw status banner would require adding acknowledgment and source
identity semantics to another data path. A new Overview-specific server feed
would duplicate the existing snapshot/ledger boundary. Neither fits the
requirement to reuse the current event system. A separate URL audience mode was
explicitly rejected by the owner. Applying presets keeps the existing
installation-wide behavior; independently configured per-window modes are no
longer part of this design.

The following details are implementation proposals derived from the issue and
code, rather than additional owner-confirmed requirements.

## Customizable Presets and Flight Events

Add `Customer` alongside `Normal`, `Communications` and `Weather` in the
existing preset card, with the same `Save Current As Customer` and
`Apply Customer` workflow. Preserve the existing `/overview` launch and popup
discovery; there is no special customer URL or separate launch mode.

Add a shared boolean `next_flight_events_only`, defaulting to false, with a
`Flight Events Only` switch for the upcoming/next-event panel in existing
Overview display controls. Include it in the existing settings validation,
confirmed reads/writes, preset capture, versioned save and apply paths. Any
preset can save either value; the Customer name does not hard-code behavior or
lock panels/layers. As with existing presets, an unsaved Customer slot must be
configured and saved before it can be applied. Do not invent built-in panel
defaults or overwrite saved bundles.

Older settings omit the new field and retain all-event selection. Applying an
older saved preset also explicitly restores the all-event default rather than
accidentally retaining a previously applied customer filter. Preserve existing
optimistic-concurrency checks, unknown-field retention and partial weather-save
error reporting. The new preset slot is additive; existing saved versions and
settings remain intact. Applying any preset still updates all displays on the
installation, as the current UI describes. Reload reads confirmed shared state.

Pass the confirmed flight-only setting into the arrival projector. When enabled,
filter candidates by the typed flight kinds `departure`, `arrival`, `aar_start`,
`aar_end` before the current next-event selection. Keep the response and
map-layer selection intact. Preserve route ordering, unique destination
selection, untimed candidate handling, anticipated/estimated provenance, source
freshness and mission clock. Generated manual AR remains a typed flight event;
arbitrary user POIs do not gain a new classification.

Add stable section keys for scheduled departure, next event, landing,
destination and ground movement states. Render `Next Flight Event` when
flight-only selection is enabled and `Next POI` otherwise. Use semantic keys for
scheduled-time prefixes and landing-specific empty states. Preserve existing
landing deduplication when the destination is itself next. A missing customer
flight candidate produces a flight-specific unavailable/empty state; it never
falls back to a transport event.

## Shared Advisory Reader

Add a narrow Overview hook using the existing operating-context API, Operator
health and complete event snapshot reader. Reuse React Query keys where the
semantics match; mount no acknowledgment mutation, pending-command recovery,
audio, vibration or transport-action controller.

The read scope is active mission, active leg, store ID, API epoch, source mode
and operating-context/replay identity. Require context and health to agree.
Validate the snapshot against that identity and each displayed event against the
active leg and replay/context. Discard old results immediately when the scope
changes. No selected Operator browsing mission enters this scope. An unavailable
or inconsistent context produces a restrained unavailable cue.

Poll events every 15 seconds while visible and 60 seconds while hidden, with
refresh on focus/visibility/online. Follow the existing single bounded retry for
retryable snapshot-change conflicts. Refresh context with a bounded query so
mission/leg/mode switches invalidate the event scope promptly. Use monotonic
time since receipt for client freshness, independently of mission time; replay
time must not make an old response appear fresh. The receipt-age budget is 45
seconds while visible and 150 seconds while hidden, tested independently of the
mission clock.

Assemble every pinned page before publishing a snapshot. Reject repeated or
excessive cursors, inconsistent page identities, and a truncated terminal page.
A failed or partial refresh must never replace a complete snapshot with an empty
successful result. Validate mission, store, epoch, mode/run, generation, token
and high-water mark across pages.

## Advisory Visibility and Meaning

Use a pure projection over the complete snapshot and validated active scope. All
simultaneous matching advisories render in the existing Overview glass theme. Do
not select just the first event.

A visible advisory must satisfy all of these conditions:

1. It is a modeled PoP transition window or supported restriction for the active
   mission/leg/context. Unknown PoP observations, mismatches and overdue
   handover diagnostics remain Operator-only.
2. It is active and fresh, its source is aligned and fresh, and its notification
   is available, not retired and not acknowledged. Respect existing backend
   transport eligibility and ledger retirement. Preview/unstable candidates must
   not masquerade as durable current occurrences.
3. It has valid start/end bounds and backend `threshold_at`. Mission time is at
   or after that threshold and strictly before the end. This means PoP windows
   appear during the full transition window; restrictions can appear during the
   backend's existing five-minute approach period. No independent frontend
   prediction or invented outage cutoff is introduced.

Do not require `notification.eligible`: its audio policy intentionally excludes
PoP and some low-significance restrictions. Preserve the distinction between
approaching and current windows and between modeled, planned and observed
information. Handover alone is not an outage; coverage/window ending is not
proof of restoration. X concurrency-only restrictions retain that
classification.

Headlines follow issue #426: `Starshield Transition Window` with
`Brief Interruption Possible`; transport-specific
`Service Interruption Expected` or `Service Degradation Expected`;
`X-Band Concurrency Restriction`; and
`Customer Communications Interruption Expected` for combined call outage. Add a
structured display classification if needed to distinguish concurrency from
generic degradation; never infer classification from title text. Keep API
enums/IDs and ledger identity inputs unchanged.

A fresh, complete, aligned snapshot with no visible events renders no strip,
without an all-clear claim. Failed/stale reads, incomplete coverage or unknown
alignment render a brief `Transport Advisories Unavailable` or stale equivalent
in the Overview theme, alongside any independently valid advisories where
appropriate. Never fall back to raw status PoP banners.

## Acknowledgment and Identity

Use the existing Operator occurrence/severity acknowledgment command and durable
receipt path. Overview only reads its confirmed result. Preserve uncertain-write
retry with the original idempotency key/body, 409 conflict handling, 503 failure
handling, concurrent acknowledgment behavior and Operator history.

After a confirmed acknowledgment, each Overview client suppresses that
occurrence on its next successful poll or focus refresh. Reload retains
suppression through the backend ledger. Do not optimistically hide an event
after an uncertain write. Ordinary ETA drift and cosmetic title edits retain
identity. Material route/boundary/occurrence, transport generation and severity
changes continue to rearm according to the existing ledger. No second dismissal
store or database migration is planned.

## Vocabulary and Time

Use explicit kind-to-label tables covering every kind in issue #426. Update the
known generation sources in `timeline_builder/pois.py`, `event_pois.py`,
`pop_pois.py` and the shared event title projection. Preserve endpoint names and
supported satellite from/to detail. Keep scheduled departure distinct from
detected takeoff and inferred movement distinct from confirmed landed state.

Provide a read-time display adapter for persisted generated POIs. Restrict
legacy label normalization to recognized generated kind/template combinations;
preserve arbitrary/user-edited text and user-managed POIs. Add presentation
metadata if necessary to keep endpoint names separate from semantic labels. Do
not rewrite stored POIs, historical event JSON or IDs for cosmetic changes.
Current generated event titles can be presented consistently without rewriting
history or changing schedule/family keys.

Remove forced uppercase styles from affected event headings/metadata, and
replace text-driven control flow with semantic keys. Use `Starshield` exactly,
with `KA` and `X-Band` for display; preserve internal `Ka`, `X` and `Ku` values.
Do not mechanically title-case arbitrary text.

Touched arrival and event time formatting uses fixed 24-hour Zulu independent of
browser locale, with the date on cross-day boundaries. The affected preset and
acknowledgment surfaces add no time inputs. If an existing input must be
touched, use explicit 24-hour Zulu entry/parsing rather than relying on a
locale-controlled native time widget. Inventory remaining app-wide readout and
input follow-through separately; do not expand into PDF or whole-app rewrites.

## Remaining App-Wide Time Follow-Through

The following inspected surfaces remain outside this focused change unless
implementation directly touches them:

- Native locale-dependent time widgets in `components/operator/UtcDateTime.tsx`
  and datetime widgets in the legacy call/issue/transport editors.
- Mission timing and flight-event forms, plus Data Export date/time inputs.
- ADS-B retry messages using `toLocaleTimeString()`.
- Configurable operational clock zones and their settings; preserve that
  established configuration here rather than redesigning unrelated panels.

Audit those separately for the owner's app-wide 24-hour Zulu convention. The
customer briefing PDF remains the sole intended Washington, DC time exception.
This inventory records remaining work; it does not certify those surfaces
already meet the convention.

## Verification and Delivery

Before implementation, approve this design and write the task-by-task plan. Then
use focused failing tests before the corresponding behavior changes.

- Extend arrival tests for both modes across mixed typed events, ordering,
  no-flight candidate, untimed next event, repeated endpoints, departure,
  landing/postflight, movement, manual destination/AR, stale observations,
  unavailable route and replay/date rollover.
- Extend settings-store/API tests and preset-client tests for strict boolean
  validation, missing-field compatibility, the added preset slot, conflict
  retries and unchanged existing saved bundles.
- Test the flight-only default, settings/preset validation and persistence,
  Customer save/apply, customization in any preset, older preset fallback,
  shared multi-display updates, preserved map settings, semantic section
  rendering and every generated vocabulary mapping.
- Test advisory projection for all transports, simultaneous windows, PoP with
  audible eligibility false, concurrency versus unavailable/degraded, combined
  outage, lead/end boundaries, acknowledgment, retirement and source validity.
- Exercise complete pagination and identity switches, late results, failed
  refresh, stale receipt, source misalignment, 409/503 and uncertain writes.
  Reuse the existing acknowledgment/race/live-ETA backend suites.
- Run two real browser clients against an isolated exact-commit production
  backend and Nginx stack with synthetic inputs: acknowledge in Operator,
  observe Overview clients clear by polling under both preset configurations,
  reload and confirm durable suppression and retained history. Cover material
  rearm, ETA drift and natural expiry.
- Capture desktop 1920×1080 and relevant mobile/keyboard evidence, simultaneous
  advisory layout, clipping/overflow and absence of duplicate controllers. Run
  focused backend/frontend tests, build/lint and applicable CI. Preserve exact
  candidate SHA, scenario results, screenshots and known limitations.

Record resource ownership before acceptance; bound checks with wall-clock
timeouts and termination grace, install cleanup handlers, and verify task-owned
processes, listeners, containers, networks and disposable volumes are gone. Keep
the open-PR worktree and evidence. Push a feature PR against `dev`; do not merge
or deploy as part of this request. Backout is reverting the feature PR; no
schema change or acknowledgment-history deletion is intended. Synthetic
acceptance is software evidence, not flight-readiness certification.
