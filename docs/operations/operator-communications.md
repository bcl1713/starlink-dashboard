# Operator communications (#365)

Operator is disabled by default. Enable and maintain its existing independent
store as described in [Operator journal maintenance](operator-journal.md).
Overview remains a passive display and Missions continues to own mission plans.

Open a mission in Operator and choose **Communications**. **Schedule call**
needs only a UTC planned start and party description for a short entry. Dates
use `YYYY-MM-DDTHH:MM:SSZ` explicitly; a call crossing midnight needs the
correct date. Optional details include voice/VTC/other type, duration,
preparation lead, coordinator, conference record reference, notes and
mission/leg scope. Blank optional values remain unknown. New planned
requirements default to a ten-minute preparation lead; zero means preparation at
the planned start. Clearing the lead means unknown. Later corrections never
silently replace unknown with ten.

Use the status selector for tentative, scheduled, delayed, canceled or
completed. New scheduled calls require a start; tentative/delayed timing may be
unknown. Edit a planned start directly or apply a signed shift in minutes/hours.
A known duration is retained and an unknown duration stays unknown. Canceled
calls remain in **Completed, canceled and removed calls**; edit the status
explicitly to reinstate. Completing a requirement preserves planned timing for
comparison with actuals.

**Log unscheduled/completed call** accepts actual start/end or unknown timing,
optional party, coordinator, conference reference and notes. It starts with no
planned times or preparation lead. Actual end requires an actual start and
cannot precede it. Future actual times beyond the acceptance clock tolerance are
input errors. These calls never generate retrospective preparation cues. Edit
mistakes through normal revisions; **Call history** retains accepted values,
corrections and associations. Remove/restore affects the call only and never
closes its conference session. Existing participation links can prevent removal;
resolve the reported relationship rather than expecting cascading deletion.

Preparation UTC and due/upcoming labels derive from the latest saved planned
start and lead against the backend snapshot clock. Completed, canceled, removed
and unknown-timing records have no cue. Overdue active requirements retain their
recorded status. Live ticking alerts and a unified event feed remain #368.

**Refresh calls**, focus/reconnect and successful local saves refresh server
state. Another client's edit never replaces an unsaved draft. A stale save needs
explicit reread/reconciliation. Offline or uncertain saves retain their request
and draft; **Retry same call save** reuses the original key. Saved appears only
after acknowledgment and a successful current-row reread. When a receipt is
acknowledged but current state cannot be read, reread before continuing: an old
receipt can predate another client's correction. Loading remaining pages is
required for a complete list/summary. Unknown/stale/unavailable data stays
visible.

The existing `/api/v2/operator/records` endpoints now accept typed call creates,
full replacements and remove/restore, using the existing epoch, idempotency and
expected-version rules. A call PUT must include nullable `prep_lead_minutes`;
missing legacy values read as null without rewriting history. Other new fields
are nullable. Party/coordinator are at most 200 characters, and lead is a strict
integer from 0 to 10080. Conference references use the existing same-mission
integrity checks; no conference lifecycle API is added. Raw journal projections
retain original revisions and old missing fields; mission-package wiring remains
[issue 370](https://github.com/bcl1713/starlink-dashboard/issues/370).

There is no SQLite schema migration. Back up the store before upgrade. Disable
Operator to hide these workflows while retaining data. Older binaries with
closed payload models cannot read extended call records: before a binary
downgrade, stop access and restore the explicitly selected pre-upgrade backup,
preserving the newer store separately. Restore rotates the epoch and may lose
later entries; reconcile clients as documented in journal maintenance. Do not
initialize a new store or delete the volume to silence a compatibility error.
Existing retention, soft-removal and export boundaries apply unchanged.

Reusable conference sessions and independent customer connection intervals are
covered in [Operator conferences](operator-conferences.md). Call completion and
schedule changes never automatically close a conference or customer interval.
