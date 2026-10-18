# Operator mission archive acceptance (#370)

The existing mission ZIP now retains the customer briefing, portable planning
files, existing CSVs, #349 telemetry archives and the complete Operator journal.
The same export/import controls are used. Ordinary plan import does not restore
historical Operator records or telemetry into active destination stores.

Production images were built from exact candidate
`462c62741b973922a6f1ed9395bd339d1a0ffa1b`. The final evidence commit only adds
this report and its artifacts.
[Production identity and complete results](production-summary.json) record both
image identities, source archive hash, browser checks and teardown.

## Verified production round trip

[Round-trip results](roundtrip.json) cover two synthetic mission legs, 22
current Operator records, 24 immutable revisions, one real #348-derived modeled
PoP advisory, conference reuse, participation, issues, transport decisions and
all preflight/between-leg/postflight scopes. The real #349 detector receives
synthetic takeoff, landing and on-blocks observations, seals both leg archives
and includes their existing manifests/observation/event CSVs in the same ZIP.
Sparse synthetic source metrics remain explicitly partial. Operator records use
the simulation namespace; #349 receives separately generated synthetic
operational-format inputs in its live namespace. Neither is aircraft evidence.

The downloaded customer PDF has two valid pages, its established filename and
can be independently extracted. Every journal member and both telemetry CSV sets
pass independent SHA-256 validation. The example ZIP contains 24 unique members
and preserves mission, leg, route and existing CSV files.

A clean second production backend, with separate private mission/route/Operator
storage, imports the enhanced ZIP successfully: two legs, one route and four
endpoint POIs. Destination Operator records and journal high-water remain empty
and unchanged. A legacy-format ZIP, with the new archival members and manifest
extension removed, also imports successfully. The browser additionally uploads
the enhanced ZIP through the existing import dialog after normal deactivation;
source Operator records and high-water remain unchanged.

Repeated exports return identical cached bytes. A retrospective change creates a
new snapshot while the original download remains immutable. A real historical
issue correction uses 15:55 UTC for chronology while preserving the issue's
16:00 UTC current-state timestamp; originals and correction lineage remain
available. Unknown correction times are covered by the backend regression.
[Restart evidence](restart.json) verifies that the ready download survives a
backend restart byte for byte. [Failure evidence](failure.json) makes the real
SQLite journal unreadable and verifies both export endpoints return 503 without
publishing an incomplete ZIP. Browser network failure shows the existing error
and allows a successful retry.

## Repository checks

- [Canonical backend suite](backend-tests.log): 4,179 passed, 20 skipped. The
  additional effective-time correction regression is included in the separate
  [30 focused journal/projection/preparation tests](focused-tests.log), all
  passed.
- [Frontend suite](frontend-tests.log): 1,844 tests passed on Node 22.22.2.
- [Production frontend build](frontend-build.log): passed.
- The real two-leg synthetic fixture validation passed independently before the
  final Docker run. Static formatting, lint and internal-link checks apply to
  the final evidence tree; required final-head CI remains visible on PR #381.
- Independent code review found draft-export compatibility and effective-time
  ordering gaps. Both have regression coverage and passed follow-up review.

## Browser evidence

[Browser results](browser.json) verify the production Nginx path at 1920×1080,
390×844 and 844×390, successful downloads, a real UI import, no horizontal page
overflow, fully visible settled export dialogs and no browser errors. These
captures are for review; the #376 interface redesign remains separate.

| Viewport         | Existing export control                   | Operator baseline                          |
| ---------------- | ----------------------------------------- | ------------------------------------------ |
| Desktop          | [1920×1080](archive-export-1920x1080.png) | [Operator](archive-operator-1920x1080.png) |
| Mobile portrait  | [390×844](archive-export-390x844.png)     | [Operator](archive-operator-390x844.png)   |
| Mobile landscape | [844×390](archive-export-844x390.png)     | [Operator](archive-operator-844x390.png)   |

[Existing import dialog after successful upload](archive-existing-import-controls.png)
shows the enhanced package using the original workflow.

## Sanitized example and operational contract

- [Complete synthetic mission ZIP](synthetic-complete-mission.zip)
- [Independently extracted customer briefing](synthetic-customer-brief.pdf)
- [Journal manifest](journal-manifest.json)
- [Compact handover example](handover-example.txt)
- [Archive contents, capture boundaries, migration and rollback](../../operations/mission-journal-archive.md)

All names, records, routes, positions and observations in the package are
synthetic. Text members contain no IP addresses. No aircraft, terminal,
Prometheus or optional external provider is used; the acceptance network is
internal. The unchanged Overview frontend and existing mission workflows remain
outside any UI redesign.

The owned runner removed all task containers, networks, private volumes, image
tags, browser/renderer children, byte-relay listener and temporary source
archives. Raw command logs and ownership evidence remain in
`/tmp/issue-370/acceptance-a8` without live resources. The feature worktree is
retained for the open PR. No merge was performed.

## Portability review follow-up

The [review follow-up evidence](review-followup/README.md) records the larger
spooled-import limit, independent planning bounds, snapshot capacities, actual
148 MiB and 2 GiB HTTP imports, memory measurements and recovery cleanup for
production candidate `5f3bc636`.
