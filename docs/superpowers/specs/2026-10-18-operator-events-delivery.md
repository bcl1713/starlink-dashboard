# Operator events: acknowledgment, timing and UX

Part of the [approved design](2026-10-18-operator-events-design.md).

## Durable acknowledgment and concurrency

Add migration `002` with notification occurrence state and immutable
acknowledgment rows in the existing database. Occurrence rows hold source
family, accepted anchor, severity tiers, supersession state, minimal sanitized
snapshot, and first/last seen UTC; do not copy telemetry samples. Persist
creation, material schedule/severity changes and retirement, not each forecast
refresh. Event history uses existing source revisions plus these material
notification transitions.

Add `POST /api/v2/operator/events/acknowledge` accepting occurrence ID, severity
generation and snapshot token, with existing idempotency and store-epoch
headers. Validate according to the versioned capture protocol below; reject a
superseded generation with 409 and return refreshed identity. A unique database
constraint on `(store_id, occurrence_id, severity_generation)` ensures two
clients acknowledge once even with distinct request keys. A second
acknowledgment returns the existing durable result, without another
acknowledgment or journal revision. Reuse the command receipt machinery for
exact retries and incompatible key reuse.

### Versioned capture and acknowledgment authority

The snapshot token is server-issued and opaque, bound to store ID/API epoch,
mission/leg, source mode/run/lifecycle, event occurrence/severity generation,
reconciliation generation, source record versions, effective route/catalog/input
identities, and the relevant published model revisions/capture generations. Use
a server-side registry capped at 256 snapshots per runtime, evicting the oldest
issued first, with a two-minute real-monotonic TTL; restarts invalidate tokens,
not acknowledgment history. Expired/unknown tokens return 409 requiring a fresh
feed. Tokens grant no authority to mutate sources.

The feed pins Operator records at high-water H and each independently captured
immutable model publication at its own generation. There is no distributed
transaction and H never claims to pin mission/telemetry stores. Responses expose
all capture identities and times. Pagination uses the same pinned captures.

For a new acknowledgment:

1. Refresh/revalidate the relevant local source publication and its input
   identity outside SQLite. Recompute only via existing source logic when
   required.
2. Acquire the source-publication read guard, then Operator admission and an
   immediate SQLite write transaction, in that order. Re-read relevant Operator
   records and occurrence state inside the transaction. Unrelated journal writes
   need not invalidate a token; changed dependent record versions do.
3. Compare the token's modeled publication/input generations to the guarded
   current publications and verify freshness/alignment. A generation mismatch is
   409; missing, stale, unaligned or unguardable required evidence is 503.
   Return no acknowledgment receipt for either outcome. Scheduled-only events do
   not fail merely because an unrelated modeled feed is unavailable.
4. Reconcile affected generations, insert the uniquely constrained
   acknowledgment and its idempotent receipt, and commit while holding the
   publication guard. Release the SQLite/admission resources before the
   publication guard.

The guard serializes publication/invalidation of the adapter's local immutable
snapshots, not remote reality. All relevant local publishers and source-input
invalidation paths must participate: mark an input generation invalid before a
changed route/catalog/lifecycle/configuration becomes eligible, and publish its
replacement only with matching evidence. Where a source cannot provide this
revision/guard contract, show its events read-only with acknowledgment
unavailable and return 503 rather than promise cross-store atomicity.
Multi-process deployments must share the publication gate/generation state or
conservatively disable modeled acknowledgment; a process-local lock alone is
insufficient there.

A model change between refresh and guard acquisition causes 409. A pending
publication detected before commit aborts acknowledgment. A publisher arriving
while the guard is held waits; acknowledgment refers to the then-current
captured publication and commits before the replacement becomes authoritative.
Later publication reconciles the new generation and cannot acknowledge it
through the old row. This is serialization of local published evidence, not a
guarantee that an aircraft or independently stored input cannot change after
capture.

For calls/issues, source validation and occurrence retirement share the same
Operator transaction. For models, retirement is reconciled against guarded
publication generations; a response never knowingly advertises a superseded
pending generation. An old response already delivered to a browser remains
subject to the documented polling boundary. Exact replay of a committed request
returns its original receipt even after source changes, explicitly identifying
the acknowledged historical generation; it does not acknowledge the replacement.

Acknowledgment only records notification disposition. It never edits a call,
issue, participation or prediction and never hides the event. There is no
unacknowledge control in this slice. Failed/uncertain requests remain visibly
pending, with the same frozen retry request; no successful acknowledgment is
claimed until confirmed. Clients poll current acknowledgment state. A short race
may cue another device before the acknowledgment reaches it; exactly-once
physical sound is not promised.

Acknowledgments are shared across clients; notification delivery settings and
emission history are local. Separate clients may each cue an unacknowledged
event. Same-browser tabs elect one emitter using same-origin coordination with
expiring ownership; lack of coordination support is disclosed and disables
automatic cues in secondary tabs. No persistent delivery claim is treated as
physical delivery.

## Timing, catch-up and freshness

Backend injected `Clock` is authoritative for due status, reconciliation and
notification eligibility. Use its UTC wall time and the existing lifecycle/run
identity. Browser monotonic elapsed time can animate countdowns, but cannot
advance fake mission time or issue an eligible cue without a fresh server
snapshot.

One Operator-level controller polls every 15 seconds while visible; invalidate
on successful relevant mutations, focus and reconnect. One request may be in
flight; abort superseded mission/store requests and discard late results. Hidden
pages poll no faster than 60 seconds when the browser permits, with no delivery
promise. Stop all controller resources when leaving Operator. Do not add
per-editor polls. Cache existing source calculations by their input identities;
a feed read must not run expensive forecasts per client when inputs are
unchanged.

Notify prep and issue follow-up at due time, customer requirement two minutes
before start, and significant modeled restriction five minutes before interval
start. These are notification thresholds, separate from the event's displayed
UTC time. An eligible visible cue requires a successful snapshot at most 30 real
seconds old, current record identity, valid source freshness/alignment, and no
clock regression. Sources keep their existing stricter freshness rules; saved
plans with unknown alignment are labeled partial and cannot produce automatic
restriction cues. Explicitly disabled sources are labeled disabled, not stale or
all-clear.

On first open, refresh, reconnect, visibility return or restart, evaluate
current state, never replay a queue of notification delivery attempts. Catch-up
candidates are unacknowledged calls in prep through planned end (or start plus
15 minutes when end unknown), restrictions still active or starting within five
minutes, and follow-ups due within the preceding 15 minutes. Older unresolved
events remain in Attention without automatic cues. Any candidate also needs a
crossed threshold; future prep or follow-ups do not notify prematurely.

Emit at most one grouped catch-up cue, containing at most three highest-priority
candidates, with a count/link for the rest. Priority: customer requirement,
restriction affecting protected activity, call prep, other significant
restriction, issue follow-up; tie-break by UTC then stable ID. All actionable
rows remain individually visible and acknowledgeable. During continuous
operation coalesce threshold crossings over five seconds, enforce at least 30
seconds between cues, and one automatic cue per occurrence/severity per client.
Deferred candidates are reevaluated against current eligibility instead of
queued indefinitely.

Persist a bounded local emission cache per store/run/mission, retained for seven
days, so refresh does not replay already cued generations. Durable
acknowledgments survive restart; unseen currently actionable generations may
produce one catch-up cue after restart. Muted/disabled delivery does not mark
candidates acknowledged. Enabling delivery uses the same grouped catch-up
policy. Clock regression/seek suspends cues until a fresh consistent lifecycle
snapshot; a changed simulation run gets a separate namespace. Unchanged
occurrences in a rewound run are not replayed.

Missing/stale inputs retain last known rows with their as-of and unknown current
status. They cannot resolve an event, clear Attention, or claim no restrictions.
A fresh source snapshot may supersede or end a prediction; a missing one cannot.
If the store is unavailable, retain read-only last-known display and disable
shared acknowledgment; do not fall back to invented success or local durable
acknowledgments.

## Compact Operator experience

Replace the current snapshot Upcoming summary with a compact page-level strip:
Now, Next and Attention counts, nearest timed requirement, freshness and local
alert status. Keep it accessible while working in Communications, Issues,
Journal or Display Tools through a sticky strip and expandable feed drawer.
Desktop uses a small side drawer; mobile uses a dismissible sheet with
appropriate focus return, keyboard handling and scroll containment. No sheet
opens automatically on a cue. Do not obscure editor fields, save actions or
conflict messages. Opening the feed preserves editor drafts, mission context and
scroll position.

Rows show UTC/time remaining, concise purpose, provenance, modeled advisory
label, protection relevance and acknowledgment state. Source details expand on
demand; source links navigate within Operator without discarding dirty drafts.
Acknowledge is a separate action from opening/editing the source. An
acknowledged row remains visible. Use restrained live-region announcements for
grouped cues and status changes, without announcing every countdown/poll. Labels
and keyboard controls must work without color, motion, sound or vibration.

Local notification controls fit in one popover: in-app cues on/off, sound
on/off, vibration on/off, and a user-gesture Test/Enable sound action. In-app
cues default on; sound/vibration default requested for the high-priority types
in the table, with routine follow-ups vibration-only. No browser permission
prompt or vibration is triggered on page load. Persist preferences per browser;
never confuse requested settings with successful device output. Sound uses a
bundled/generated local tone; no remote audio. Handle suspended audio contexts,
rejected playback, missing vibration API and unsupported mobile browsers without
failing the feed.

Show concise states such as Sound needs interaction, Muted, Vibration
unavailable, Offline—last updated … UTC, and Background delivery not guaranteed.
Hidden-tab notifications and screen-off operation are explicitly best-effort.
Reopening the page does not imply notifications were delivered while it was
closed.

Continue with
[persistence and acceptance](2026-10-18-operator-events-acceptance.md).
