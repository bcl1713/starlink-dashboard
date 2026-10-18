# Operator issues #367 verification

This slice adds description-only issue entry, Open/Monitoring/Resolved/Reopened
states, independent workaround status, optional UTC follow-ups and manual
capability/redundancy assessments to the existing Operator journal. Overview,
mission readiness, transport allocation and live alert delivery are unchanged.
See the [operating guide](../../operations/operator-issues.md) for use,
retention and backup/backout instructions.

## Evidence provenance

The production qualification candidate is
`fe2f0399709074b8ef26c03d58a5b3e3c185b274`. Images are built from its Git
archive and served through production Nginx, using private synthetic SQLite
volumes and an unreachable optional feed. All times and records are synthetic.
These checks establish software behavior; they make no aircraft-readiness claim.

The additional card captures below came from the preceding candidate
`e257d75f326df3c31b033739ec41233ff71df208`, in isolated project
`starlink-operator-issue367-a11`. The subsequent product change only disables
the existing journal reconciliation button while its conflict recovery read
runs. These representative captures are separately seeded examples, not
screenshots of the automated workflow.

| Viewport    | Monitoring workaround with overdue follow-up | Independent capability and redundancy       |
| ----------- | -------------------------------------------- | ------------------------------------------- |
| 1920 × 1080 | [Issue](issue-card-1920x1080.png)            | [Capability](capability-card-1920x1080.png) |
| 390 × 844   | [Issue](issue-card-390x844.png)              | [Capability](capability-card-390x844.png)   |
| 844 × 390   | [Issue](issue-card-844x390.png)              | [Capability](capability-card-844x390.png)   |

## Production qualification results

[Production summary](production-summary.json) records image identities, source
archive checksum, browser proofs, failure controls, export hashes and cleanup.
All six browser suites passed. The issue journey covered description-only entry,
monitoring/workaround, independent manual capability, UTC boundary snapshots,
two-client conflicts, resolution/reopening, retrospective correction, lost
acknowledgment with reload/exact retry and changed-epoch quarantine after real
backup/restore and restart.

| Viewport    | Issue workflow                 | Capability workflow                               |
| ----------- | ------------------------------ | ------------------------------------------------- |
| 1920 × 1080 | [Issues](issues-1920x1080.png) | [Capabilities](issues-capabilities-1920x1080.png) |
| 390 × 844   | [Issues](issues-390x844.png)   | [Capabilities](issues-capabilities-390x844.png)   |
| 844 × 390   | [Issues](issues-844x390.png)   | [Capabilities](issues-capabilities-844x390.png)   |

The actual normal projection contained 30 immutable revision rows and three
selected corrections, one per logical message root; audit originals remained
available. A real synthetic two-leg lifecycle left issue/capability records and
planning/telemetry export hashes unchanged. Failure controls exercised crashes
before and after commit, read-only/full media, backup recovery, old-epoch
rejection and fail-closed recovery. All owned runtime resources were removed.

Local canonical frontend verification passed 1,807 tests and the production
build on Node 22.22.2. Canonical static checks passed formatting, lint, internal
documentation links and 12 policy/link tests. External link availability is
advisory under repository policy. The complete post-review Operator backend
suite passed 269 tests. The complete backend gate and final PR checks are
recorded on the PR; required CI must pass before merge.

## Correction example for retrospective analysis

[Normal activity JSONL](activity-example.jsonl),
[current state](current-example.json) and
[manifest with checksums](example-manifest.json) are actual projection bytes
from a temporary real SQLite journal using the shared deterministic test fixture
on candidate `e257d75f326df3c31b033739ec41233ff71df208`. This small example was
generated locally, separately from production-container qualification.

The four revisions preserve creation, the original message, resolution and a
later correction. The selected message is revision 4, rooted at revision 2, with
corrected occurrence at 10:04 UTC and recording at 10:30 UTC. The issue remains
resolved. A normal operational timeline selects `is_selected` and uses
`effective_at`; immutable revision activity retains the original message.
Neither revision ordering nor JSONL row identity changes. These files were
copied without reformatting so their manifest checksums remain verifiable.

## Scope and remaining review

No new database or SQL migration is introduced. Rollback requires the documented
pre-upgrade backup procedure because older strict readers may reject extended
payloads. Routine edits need no explanatory audit note. Pending requests retain
one frozen command, key and store epoch; conflicts preserve local drafts and
require explicit reconciliation.

Live notification delivery belongs to issue #368, allocation to #369, mission
ZIP integration to #370 and comprehensive UI consolidation to #376. PR #378
remains a draft for separate product review; this report does not authorize
merge.
