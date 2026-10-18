# Operator events and local alerts

Operator provides one UTC timeline of call preparation and customer
requirements, issue follow-ups, existing PoP advisories and modeled transport
restrictions. Open events from the compact strip while working in
Communications, Issues, Journal or Display Tools. The drawer preserves unsaved
editor drafts.

Events remain visible when cues are muted or unavailable. Acknowledgment records
notification disposition only: it does not complete a call, resolve an issue,
change customer participation or authorize a transport change. Recent history
shows superseded occurrences; source record history retains earlier edits.

## Timing and delivery

Call preparation uses the saved lead, defaulting to ten minutes when a new call
is created. Customer-start cues are eligible two minutes before the planned
start; significant modeled restrictions five minutes before their interval;
follow-ups at their recorded UTC time. Tentative or unknown-time requirements
stay visible without an invented reminder time. Canceled/completed calls,
resolved issues and removed records suppress future cues.

In-app cues default on. Sound and vibration are requested for call preparation,
imminent customer requirements and significant restrictions; routine follow-ups
are silent with optional vibration. Open Local alerts and use Enable sound and
vibration after a user gesture. Device support and audio suspension can prevent
output. The settings display those limitations. Closed or background browser
delivery is not guaranteed; no push notification service is used.

On first open, reconnect or return to a visible tab, one grouped cue contains up
to three currently actionable events and links to the remainder. Missed/older
requirements remain in Attention without replaying an old queue. Continuous cues
coalesce for five seconds with at least thirty seconds between them. Backend UTC
controls eligibility; a browser clock cannot make a future requirement due.

Device-local cue reservations and preferences persist in browser storage. Same-
origin tabs use an IndexedDB lease, plus Web Locks when available. If safe local
coordination is unavailable, automatic cues stop and the timeline remains
useful. Different devices may each cue an unacknowledged event. Neither a
reservation nor successful audio playback proves that someone heard an alert.

## Modeled and unknown information

Modeled restrictions are estimates, never verified outages. PoP windows remain
continuity advisories; unknown PoP observations and unconfirmed handovers do not
mean Starshield is down. Existing continuity calculations account for usable Ka
and coordinated concurrency-only X fallback. No routing action is executed.

A connected customer remains protection-relevant even if the conference is
closed, interrupted or missing. Operator labels the discrepancy and unknown
transport relevance. A planned call ending does not end an operator-reported
connection.

Saved timelines can have unknown input alignment. The feed marks
stale/unavailable sources and retains last-known rows without claiming an
all-clear. Ordinary production model sources currently lack a complete shared
publication/invalidation guard, so their acknowledgment is
read-only/unavailable. Matching mission/leg IDs alone does not certify current
input alignment; automatic restriction cues are withheld when that alignment
cannot be established. Scheduled operational records can still be acknowledged.
A fully participating adapter may enable modeled acknowledgment; the acceptance
fixture exercises that contract with synthetic data.

## Acknowledgment and schedule changes

Acknowledgments are durable and shared across clients. Concurrent clients create
one acknowledgment for the occurrence/severity tier, even with different request
keys. An uncertain response keeps its exact request for retry across reload. Do
not replace a pending request to guess whether it succeeded. An obsolete
token/source returns 409; unavailable required evidence or storage returns 503.
Read current state before dismissing an obsolete request and acknowledging its
replacement.

Explicit rescheduling creates a new notification occurrence for the affected
milestone. Prediction revisions and small timing drift preserve acknowledgment.
A sustained material shift can replace an occurrence; a sustained higher
severity can notify once at that tier. Downgrading and returning to an already
acknowledged tier does not re-arm it. Acknowledgment never removes an event from
the timeline.

## Storage upgrade and backout

Operator remains disabled by default. Schema migration 002 adds notification
history/acknowledgment tables to its existing private SQLite store. It does not
change public contract version 1 or mission exports. Startup requires an
explicit upgrade for an existing schema-001 store; it does not silently migrate
it.

Stop the application before maintenance, then use the matching source/image:

```sh
python -m app.operator upgrade --root /your/operator/root --mode live
python -m app.operator check --root /your/operator/root --mode live
```

For simulation, use `--mode simulation --run YOUR_SYNTHETIC_RUN_ID`. Upgrade
takes exclusive maintenance admission, publishes a validated backup under
`pre-upgrade-backups`, then applies the migration transactionally. Preserve the
reported backup manifest. New initialized stores receive the current schema.

To back out, stop the upgraded application, preserve its current backup, and use
the previous application version's maintenance CLI to restore the pre-upgrade
manifest before running old code. Old code rejects schema 002. Restoring a prior
backup loses acknowledgments and other writes after that backup. The new code's
normal restore path expects its current schema; use the old version for this
schema downgrade. Disabling Operator requires no database downgrade and leaves
other application behavior intact.

Notification metadata stays within the store's existing retention/capacity and
backup boundaries. Cue caches keep bounded device-local identities for seven
days; clearing browser site data removes those local preferences/reservations,
not the backend's durable acknowledgments. Notification records are not added to
mission ZIPs, operations JSONL or existing CSV exports.

## Provisional model tuning

These software defaults are configurable and tested with synthetic rapid
crossings; they are not physically verified timing limits. They never change
issue #348's actual prediction or transition-window calculations.

| Environment setting                            | Default |
| ---------------------------------------------- | ------- |
| `OPERATOR_EVENT_MODEL_SHIFT_SECONDS`           | 300     |
| `OPERATOR_EVENT_MODEL_STABLE_CAPTURES`         | 2       |
| `OPERATOR_EVENT_MODEL_CAPTURE_SPACING_SECONDS` | 15      |
| `OPERATOR_EVENT_MODEL_ESCALATION_CAPTURES`     | 2       |

Capture counts must be at least two; seconds must be positive and finite. Keep
these deployment settings out of the customer-facing Overview.
