# Operator transport decisions

Transport decisions record service intentions and human reports. Requested,
Reported Applied and Operator Checked are independent: an operator may record
any one directly, including after the event. A check records someone's report of
checking the result; actual SDR/OSPF traffic routing remains unknown.

Use **Transport** in Operator. Enter a service such as secure voice, VTC or IPTV
and the report you want to log. Add service rows for one shared decision; use
**Record another move** for a later operational change. Reason, notes, planned
timing and call/conference links are optional. All operator-entered times use
UTC and can be corrected; historical revisions and server save times remain
immutable. Changing Reported Applied clears its previous check unless you
explicitly enter another check.

Communications and modeled restrictions show the existing event feed's current
snapshot. Airborne restrictions use its live route ETA; preflight can use
planned UTC. Unknown/stale context stays explicit. Warnings about active
customer communications are advisory and never require acknowledgment before
saving. Overview and mission planning behavior are unchanged.

A linked call/conference cannot be removed or moved to another mission while an
active decision references it. Correct the decision to unlink it, or remove the
decision first. Historical links remain in history. Restore revalidates targets;
restore/reconcile targets before restoring a dependent decision. The same rules
apply after restart and recovery.

## Deployment and backout

Keep the existing Operator feature gate disabled by default. Version 003 adds
transport decisions to its existing SQLite store. Normal startup never silently
upgrades an existing database. Stop the relevant Operator writer and use the
existing maintenance CLI's `upgrade` command, which obtains exclusive admission
and creates a validated backup before the transactional rebuild. Follow the
[Operator journal guide](operator-journal.md) for deployment paths and existing
backup/restore commands.

The migration preserves revision/receipt data, links, sequence state, indexes,
foreign keys and immutability triggers. A failed migration rolls back. Older
application versions reject the upgraded schema. Backout uses the previous
application with its pre-upgrade backup; preserve a separate current backup of
new decisions. Do not delete records or downgrade the database in place.

No hardware or external notification service is required. Synthetic acceptance
is software validation and does not establish aircraft readiness.
