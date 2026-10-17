# Operator conferences and customer participation

Operator remains disabled by default. When enabled, open Communications and
expand **Conferences and customers**. Create a conference, then use Establish,
Verify, Customer Joined, Interrupt, Restore connection and Close conference.
Notes, customer identity, coordinator, schedule and duration are optional.

A conference can serve sequential or overlapping calls. Completing, cancelling
or rescheduling a call never closes its conference. Conference verification is
an operator report about the conference; customer presence and call success are
separate. Closing or interrupting a conference while customers remain reported
connected shows **Discrepancy — continuity unknown**. Record customer departures
separately; the application never invents their leave times.

Customer Joined records an unknown customer immediately. Correct customer
interval can associate a call and optional identity afterward. Log customer
interval also supports joining before any conference is established: select a
call, a conference, or both. Leave unknown actual timing blank for retrospective
entries. Explicit UTC start/end and approximate precision follow the existing
journal validation.

**Restore connection** creates a new customer interval linked to the
interruption. It preserves the previous connection and gap. **Restore record**
undoes a removed record's tombstone; it does not record a new physical
connection. History and projections retain the different actions and immutable
corrections.

Intended transport is a plan. Operator-reported configuration records what the
operator reports, with optional report UTC. Neither identifies the transport
actually carrying a call. Changing configuration clears prior verification.
There is no independently measured customer connectivity or routing
verification.

## Protected-call source coverage

Connected customer reports remain protected even with unknown start or duration.
The panel compares that activity to supported saved mission-leg timelines. It
refreshes with existing read/save/reconnect behavior; it is not an automated
alert service. All times are UTC snapshots.

| Source                                       | Bounds                                | Meaning                                                       |
| -------------------------------------------- | ------------------------------------- | ------------------------------------------------------------- |
| Per-leg timeline `pop_forecast.transitions`  | `window_start_utc` / `window_end_utc` | Modeled #348 transition advisory                              |
| Per-leg timeline `call_continuity.intervals` | `start_utc` / `end_utc`               | Existing modeled call consequence and fallback classification |
| Per-leg timeline `segments`                  | `start_time` / `end_time`             | Modeled degraded/offline X, Ka or Starshield state            |

These come from `GET /api/v2/missions/{mission_id}/legs/{leg_id}/timeline`. The
global active-route `/api/status` is not attached to another selected mission.
Missing legs, incomplete records and saved timeline freshness/input alignment
produce partial or unknown coverage. A successful read does not prove that a
saved plan matches current inputs. No overlaps found is not an all-clear.

Modeled restrictions only: operator-planned transport changes are not included;
that correlation remains #369. Automatic alerts remain #368. No routing action
is blocked, approved or executed. PoP windows remain advisory; unknown location
is not an outage. Existing Ka/coordinated X fallback semantics remain unchanged.

## Saving, correction and recovery

Each tap captures the backend UTC clock and sends one idempotent command. Saved
appears only after acknowledgment. Retry same save retains the exact timestamp,
body and key. If another client edited the record, reread and reconcile instead
of overwriting it. Optional model/provider failures leave operational controls
available. Unsaved drafts remain bound to the store identity.

Use the existing journal backup/recovery and retention boundary described in
[Operator journal](operator-journal.md). Current/audit projections include these
records; operations-package integration remains #370. Existing mission and
telemetry package formats are unchanged.

Payload extensions preserve old raw revisions and receipts. Preserve a
pre-upgrade backup. Disable Operator to roll back feature use; older binaries
with closed payload models require the pre-upgrade backup before a binary
downgrade. Retain the newer store separately. No new database table or schema
migration is needed.

All acceptance uses synthetic data. Software simulation does not establish
in-flight operational readiness.
