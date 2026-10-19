# Operator transport decisions

The normal workflow is **select a service's transport → Apply**. Each enabled
service has a card showing its current reported transport. Changing the selector
does not save. Apply records an operator report in the journal; it never sends a
routing command to equipment. Wait for acceptance before treating a write as
saved. The active mission and leg are inherited automatically where available.

**Manage services** and **Manage transports** provide reusable installation-wide
catalogs: add, rename, enable/disable, archive and restore. Starshield, Ka-band
and X-band are initial choices, not a fixed list. Archived transports remain
visible as previous assignments. Journal rows retain stable catalog IDs and the
names used when recorded; renaming a catalog entry never rewrites history.

**History and advanced records** retains legacy intentions, requests, reported
applications, checks, corrections and links. A check is an operator report, not
independently verified routing telemetry. Old replay checks are not current
readiness. A later Apply creates another immutable journal record and carries no
previous check forward. Use History to inspect earlier assignments and
revisions.

Catalogs are stored atomically in `OPERATOR_ROOT/transport-catalog.json`, shared
across live/simulation mission namespaces. Include this file with your Operator
volume backups; mission ZIPs preserve journal references and name snapshots, not
installation catalog configuration. Catalog-linked new assignments reject stale,
disabled or archived selections. Exact retries of accepted commands remain safe.
Existing records without catalog IDs remain readable. This UI change requires no
SQLite migration beyond the existing schema 003.

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
